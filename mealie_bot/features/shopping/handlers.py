"""Telegram handlers for the shopping list feature.

The chat is kept tidy around one *live* list message per chat:

* ``/list`` and every change show the list in that message. If something was
  posted below it since, the list is sent again at the bottom and the old
  message is rewritten into a short history entry (or deleted when nothing
  changed).
* Button taps edit the message in place and answer with a toast.
* Bot commands are deleted after they were handled (``DELETE_COMMANDS``), and
  so are messages that added items (``DELETE_ITEM_MESSAGES``): the history
  entry already records what was added. A message that failed stays, so the
  user can fix and resend it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from mealie_bot.features import FeatureContext
from mealie_bot.features.shopping.parser import parse_message
from mealie_bot.features.shopping.render import (
    VIEW_CLEAR,
    VIEW_DONE,
    VIEW_OPEN,
    ItemAction,
    ListAction,
    ListState,
    SelectList,
    UndoInfo,
    item_display,
    label_key,
    list_chooser,
    render_list,
)
from mealie_bot.features.shopping.service import (
    AddResult,
    NoShoppingListError,
    ShoppingService,
)
from mealie_bot.features.shopping.state import ChatState, HistoryEvent, render_history
from mealie_bot.i18n import Translator, command_names
from mealie_bot.mealie import MealieError, MealieNotFound

log = logging.getLogger(__name__)

Clock = Callable[[], datetime]
_TELEGRAM_ERRORS = (TelegramBadRequest, TelegramForbiddenError)


def _local_now() -> datetime:
    return datetime.now().astimezone()


class ShoppingUI:
    """Keeps the live list message and history per chat and renders into Telegram."""

    def __init__(
        self,
        service: ShoppingService,
        delete_commands: bool,
        delete_item_messages: bool,
        clock: Clock = _local_now,
    ) -> None:
        self.service = service
        self.delete_commands = delete_commands
        self.delete_item_messages = delete_item_messages
        self.clock = clock
        self.chats: dict[int, ChatState] = {}
        # Undo data by (chat id, message id); removed once used or superseded.
        self.undo: dict[tuple[int, int], AddResult] = {}

    def chat(self, chat_id: int) -> ChatState:
        return self.chats.setdefault(chat_id, ChatState())

    # --- rendering ----------------------------------------------------------

    async def render(
        self, user_id: int, state: ListState, tr: Translator
    ) -> tuple[str, InlineKeyboardMarkup, str]:
        shopping_list = await self.service.active_list(user_id)
        data = await self.service.view(shopping_list["id"])
        text, markup = render_list(data.name, data.items, state, tr, now=self.clock())
        return text, markup, data.name

    async def show(self, message: Message, user_id: int, tr: Translator, state: ListState) -> None:
        """Show the list as the live message: edit it if it is still last, else re-send."""
        chat = self.chat(message.chat.id)
        text, markup, list_name = await self.render(user_id, state, tr)
        if chat.live_message_id is not None and chat.live_is_last:
            with suppress(*_TELEGRAM_ERRORS):
                await _edit(message.bot, message.chat.id, chat.live_message_id, text, markup)
                chat.states[chat.live_message_id] = state
                return
        sent = await message.answer(text, reply_markup=markup)
        await self._relocate(chat, message, sent.message_id, list_name, tr)
        chat.states[sent.message_id] = state

    async def show_in(
        self, message: Message, user_id: int, tr: Translator, state: ListState
    ) -> None:
        """Turn ``message`` (a bot message) into the live list message."""
        chat = self.chat(message.chat.id)
        text, markup, list_name = await self.render(user_id, state, tr)
        with suppress(*_TELEGRAM_ERRORS):
            await _edit(message.bot, message.chat.id, message.message_id, text, markup)
        if chat.live_message_id != message.message_id:
            await self._relocate(chat, message, message.message_id, list_name, tr)
        chat.states[message.message_id] = state

    async def refresh(self, message: Message, user_id: int, tr: Translator) -> None:
        """Re-render a list message in place with its own display state."""
        chat = self.chat(message.chat.id)
        state = chat.state_for(message.message_id)
        text, markup, _ = await self.render(user_id, state, tr)
        with suppress(*_TELEGRAM_ERRORS):
            await _edit(message.bot, message.chat.id, message.message_id, text, markup)

    async def _relocate(
        self, chat: ChatState, message: Message, new_id: int, list_name: str, tr: Translator
    ) -> None:
        """Make ``new_id`` the live message; the old one becomes history or disappears."""
        old_id = chat.live_message_id
        chat.live_message_id = new_id
        chat.live_is_last = True
        if old_id is None or old_id == new_id or message.bot is None:
            return
        chat.forget_message(old_id)
        self.undo.pop((message.chat.id, old_id), None)
        extend, events = chat.take_pending()
        if events and not (extend and chat.history_message_id is not None):
            # Nothing recent to extend: the old list message itself becomes the entry.
            chat.history_message_id = old_id
        else:
            with suppress(*_TELEGRAM_ERRORS):
                await message.bot.delete_message(message.chat.id, old_id)
        if events and chat.history_message_id is not None:
            with suppress(*_TELEGRAM_ERRORS):
                await message.bot.edit_message_text(
                    render_history(list_name, events, tr),
                    chat_id=message.chat.id,
                    message_id=chat.history_message_id,
                )

    # --- bookkeeping --------------------------------------------------------

    def note_message(self, message: Message) -> None:
        """A message arrived or was sent below the live list."""
        self.chat(message.chat.id).live_is_last = False

    def record(self, chat_id: int, kind: str, user: str, items: list[str], count: int = 0) -> None:
        self.chat(chat_id).record(HistoryEvent(kind, user, self.clock(), items, count))

    async def tidy(self, message: Message, *, items: bool = False) -> None:
        """Delete the user's message once it has been handled, if configured.

        Deleting may fail (e.g. in a group where the bot cannot delete others'
        messages); the message then simply stays.
        """
        enabled = self.delete_item_messages if items else self.delete_commands
        if enabled:
            with suppress(*_TELEGRAM_ERRORS):
                await message.delete()


async def _edit(
    bot: Bot | None, chat_id: int, message_id: int, text: str, markup: InlineKeyboardMarkup
) -> None:
    if bot is None:  # pragma: no cover - messages from the dispatcher always carry a bot
        return
    try:
        await bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id, reply_markup=markup
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


def _user_id(message: Message) -> int:
    assert message.from_user is not None  # guaranteed by AccessMiddleware
    return message.from_user.id


def _user_name(message_or_query: Message | CallbackQuery) -> str:
    user = message_or_query.from_user
    return (user.first_name if user else None) or "?"


def build_router(context: FeatureContext) -> Router:
    service = ShoppingService(context.mealie, default_list=context.settings.shopping_list)
    ui = ShoppingUI(
        service,
        delete_commands=context.settings.delete_commands,
        delete_item_messages=context.settings.delete_item_messages,
    )
    router = Router(name="shopping")

    async def send_error(target: Message, tr: Translator, exc: Exception) -> None:
        ui.note_message(target)
        if isinstance(exc, NoShoppingListError):
            await target.answer(tr("error.no_lists"))
        else:
            log.warning("Mealie request failed: %s", exc)
            await target.answer(tr("error.mealie"))

    async def toast_error(query: CallbackQuery, tr: Translator, exc: Exception) -> None:
        log.warning("Mealie request failed: %s", exc)
        with suppress(*_TELEGRAM_ERRORS):
            await query.answer(tr("error.mealie"), show_alert=True)

    # --- commands -------------------------------------------------------

    @router.message(Command(*command_names("list")))
    async def cmd_list(message: Message, tr: Translator) -> None:
        ui.note_message(message)
        try:
            await ui.show(message, _user_id(message), tr, ListState())
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
        await ui.tidy(message)

    @router.message(Command(*command_names("lists")))
    async def cmd_lists(message: Message, tr: Translator) -> None:
        ui.note_message(message)
        try:
            lists = await service.lists()
            if not lists:
                raise NoShoppingListError
            active = await service.active_list(_user_id(message))
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
        else:
            text, markup = list_chooser(lists, active["id"], tr)
            await message.answer(text, reply_markup=markup)
        await ui.tidy(message)

    @router.message(Command(*command_names("clear")))
    async def cmd_clear(message: Message, tr: Translator) -> None:
        ui.note_message(message)
        try:
            await ui.show(message, _user_id(message), tr, ListState(view=VIEW_CLEAR))
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
        await ui.tidy(message)

    @router.message(F.text & ~F.text.startswith("/"))
    async def add_items(message: Message, tr: Translator) -> None:
        ui.note_message(message)
        try:
            units = await service.units()
            entries = parse_message(message.text or "", units.known_tokens)
            if not entries:
                await message.answer(tr("error.not_understood"))
                return
            # "typing…" while Mealie is asked; the list follows within a few seconds.
            if message.bot is not None:
                with suppress(*_TELEGRAM_ERRORS):
                    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            shopping_list = await service.active_list(_user_id(message))
            result = await service.add_entries(shopping_list["id"], entries)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        names = [item_display(item, tr.language) for item in result.items]
        ui.record(message.chat.id, "added", _user_name(message), names)
        state = ListState(
            expanded={label_key(item) for item in result.items},
            added=result.items,
            undo=UndoInfo(created_ids=[i["id"] for i in result.created], previous=result.previous),
        )
        try:
            await ui.show(message, _user_id(message), tr, state)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        chat = ui.chat(message.chat.id)
        if chat.live_message_id is not None and result:
            ui.undo[(message.chat.id, chat.live_message_id)] = result
        # Only now, after the items were added and the list shows them: the
        # message is kept whenever something went wrong so it can be resent.
        await ui.tidy(message, items=True)

    # --- buttons --------------------------------------------------------

    @router.callback_query(ItemAction.filter())
    async def on_item(query: CallbackQuery, callback_data: ItemAction, tr: Translator) -> None:
        message = query.message
        if not isinstance(message, Message):
            await query.answer()
            return
        checked = callback_data.action == "check"
        try:
            item = await service.set_checked(callback_data.item_id, checked)
        except MealieNotFound:
            await query.answer(tr("shopping.item_gone"))
        except MealieError as exc:
            await toast_error(query, tr, exc)
            return
        else:
            name = item_display(item, tr.language)
            ui.record(
                message.chat.id, "checked" if checked else "unchecked", _user_name(query), [name]
            )
            await query.answer(
                tr("shopping.toast_checked" if checked else "shopping.toast_unchecked", item=name)
            )
        try:
            await ui.refresh(message, query.from_user.id, tr)
        except (MealieError, NoShoppingListError) as exc:
            log.warning("Refreshing list failed: %s", exc)

    @router.callback_query(ListAction.filter())
    async def on_list(query: CallbackQuery, callback_data: ListAction, tr: Translator) -> None:
        message = query.message
        action = callback_data.action
        if action == "noop" or not isinstance(message, Message):
            await query.answer()
            return
        chat = ui.chat(message.chat.id)
        state = chat.state_for(message.message_id)
        try:
            if action == "toggle":
                state.toggle(callback_data.arg)
                await query.answer()
            elif action == "undo":
                result = ui.undo.pop((message.chat.id, message.message_id), None)
                if result is None:
                    await query.answer(tr("shopping.toast_nothing_to_undo"))
                else:
                    count = await service.undo_add(result)
                    ui.record(message.chat.id, "undone", _user_name(query), [], count)
                    await query.answer(tr("shopping.toast_undone", count=count))
                state.undo = None
                state.added = []
            elif action == "clear":
                shopping_list = await service.active_list(query.from_user.id)
                removed = await service.clear_checked(shopping_list["id"])
                ui.record(message.chat.id, "cleared", _user_name(query), [], len(removed))
                await query.answer(tr("shopping.cleared", count=len(removed)))
                state.view = VIEW_OPEN
            elif action == "clear_ask":
                await query.answer()
                state.view = VIEW_CLEAR
            else:  # "show" (and "new" from older messages)
                await query.answer()
                state.view = (
                    callback_data.view
                    if callback_data.view in {VIEW_OPEN, VIEW_DONE}
                    else VIEW_OPEN
                )
            await ui.refresh(message, query.from_user.id, tr)
        except (MealieError, NoShoppingListError) as exc:
            await toast_error(query, tr, exc)

    @router.callback_query(SelectList.filter())
    async def on_select(query: CallbackQuery, callback_data: SelectList, tr: Translator) -> None:
        message = query.message
        service.select_list(query.from_user.id, callback_data.list_id)
        if not isinstance(message, Message):
            await query.answer()
            return
        try:
            await query.answer()
            await ui.show_in(message, query.from_user.id, tr, ListState())
        except (MealieError, NoShoppingListError) as exc:
            await toast_error(query, tr, exc)

    return router
