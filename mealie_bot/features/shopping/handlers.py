"""Telegram handlers for the shopping list feature.

The chat is kept tidy around one *live* list message per chat:

* ``/list`` and every change show the list in that message. If something was
  posted below it since, the list is sent again at the bottom and the old
  message is rewritten into a short history entry (or deleted when nothing
  changed).
* Button taps edit the message in place and answer with a toast. Opening or
  closing a category re-renders from the items fetched last, without asking
  Mealie again.
* Bot commands are deleted before the list is shown (``DELETE_COMMANDS``); the
  live list is then still the last message and is edited in place. Messages
  that added items are deleted once Mealie has them (``DELETE_ITEM_MESSAGES``)
  and the list is sent again below, so the old message can become the history
  entry that records what was added. A message that failed stays, so the user
  can fix and resend it, and the error message is deleted the next time the
  list is shown.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from mealie_bot.features import FeatureContext
from mealie_bot.features.shopping.parser import (
    EntryTooLong,
    TooManyEntries,
    parse_message,
)
from mealie_bot.features.shopping.render import (
    VIEW_CLEAR,
    VIEW_DONE,
    VIEW_LISTS,
    VIEW_OPEN,
    ItemAction,
    ListAction,
    ListState,
    SelectList,
    UndoInfo,
    item_display,
    item_inline,
    label_key,
    render_list,
)
from mealie_bot.features.shopping.service import (
    AddResult,
    ListView,
    NoShoppingListError,
    ShoppingService,
)
from mealie_bot.features.shopping.state import ChatState, HistoryEvent, render_history
from mealie_bot.i18n import Translator, command_names
from mealie_bot.mealie import MealieError, MealieNotFound
from mealie_bot.mealie.client import JSON

log = logging.getLogger(__name__)

Clock = Callable[[], datetime]
_TELEGRAM_ERRORS = (TelegramBadRequest, TelegramForbiddenError)
# Mealie IDs are UUIDs. Button data can be forged by a client, so an ID is only
# put into a request path if it looks like one (no "/", "?", "." or "..").
_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def valid_id(value: str) -> bool:
    return bool(_SAFE_ID.match(value))


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
        label_emoji: Mapping[str, str] | None = None,
    ) -> None:
        self.service = service
        self.delete_commands = delete_commands
        self.delete_item_messages = delete_item_messages
        self.label_emoji = label_emoji
        self.clock = clock
        self.chats: dict[int, ChatState] = {}
        # Undo data by (chat id, message id); removed once used or superseded.
        self.undo: dict[tuple[int, int], AddResult] = {}
        # Last fetched list per chat with its fetch time, so toggles need no round trip.
        self.cache: dict[int, tuple[ListView, datetime]] = {}

    def chat(self, chat_id: int) -> ChatState:
        return self.chats.setdefault(chat_id, ChatState())

    # --- rendering ----------------------------------------------------------

    async def render(
        self, chat_id: int, user_id: int, state: ListState, tr: Translator, cached: bool = False
    ) -> tuple[str, InlineKeyboardMarkup, str]:
        lists: list[JSON] | None = None
        shopping_list = await self.service.active_list(user_id)
        if state.view == VIEW_LISTS:
            lists = await self.service.lists()
        if cached and chat_id in self.cache and self.cache[chat_id][0].id == shopping_list["id"]:
            data, now = self.cache[chat_id]
        else:
            data, now = await self.service.view(shopping_list["id"]), self.clock()
            self.cache[chat_id] = (data, now)
        text, markup = render_list(
            data.name,
            data.items,
            state,
            tr,
            now=now,
            emoji=self.label_emoji,
            lists=lists,
            active_id=shopping_list["id"],
        )
        return text, markup, data.name

    async def show(self, message: Message, user_id: int, tr: Translator, state: ListState) -> None:
        """Show the list as the live message: edit it if it is still last, else re-send."""
        chat = self.chat(message.chat.id)
        text, markup, list_name = await self.render(message.chat.id, user_id, state, tr)
        await self._drop_errors(message, chat)
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
        text, markup, list_name = await self.render(message.chat.id, user_id, state, tr)
        with suppress(*_TELEGRAM_ERRORS):
            await _edit(message.bot, message.chat.id, message.message_id, text, markup)
        if chat.live_message_id != message.message_id:
            await self._relocate(chat, message, message.message_id, list_name, tr)
        chat.states[message.message_id] = state

    async def refresh(
        self, message: Message, user_id: int, tr: Translator, cached: bool = False
    ) -> None:
        """Re-render a list message in place with its own display state."""
        chat = self.chat(message.chat.id)
        state = chat.state_for(message.message_id)
        text, markup, _ = await self.render(message.chat.id, user_id, state, tr, cached=cached)
        with suppress(*_TELEGRAM_ERRORS):
            await _edit(message.bot, message.chat.id, message.message_id, text, markup)

    async def _drop_errors(self, message: Message, chat: ChatState) -> None:
        """Delete the bot's own error messages once the list is shown again."""
        ids, chat.error_message_ids = chat.error_message_ids, []
        if message.bot is None:  # pragma: no cover - messages from the dispatcher carry a bot
            return
        for message_id in ids:
            with suppress(*_TELEGRAM_ERRORS):
                await message.bot.delete_message(message.chat.id, message_id)

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
                    render_history(list_name, events, tr, today=self.clock().date()),
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
        """Delete the user's message if configured, and note whether the list must move.

        A deleted command leaves the live list as the last message, so it is
        edited in place. A message that added items always makes the list move
        down (the old message turns into the history entry), whether or not it
        could be deleted. Deleting may fail (e.g. in a group where the bot cannot
        delete others' messages); the message then simply stays.
        """
        enabled = self.delete_item_messages if items else self.delete_commands
        deleted = False
        if enabled:
            with suppress(*_TELEGRAM_ERRORS):
                await message.delete()
                deleted = True
        if items or not deleted:
            self.note_message(message)


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
        label_emoji=context.settings.label_emoji,
    )
    router = Router(name="shopping")

    async def send_error(target: Message, tr: Translator, exc: Exception) -> None:
        ui.note_message(target)
        if isinstance(exc, NoShoppingListError):
            sent = await target.answer(tr("error.no_lists"))
        else:
            log.warning("Mealie request failed: %s", exc)
            sent = await target.answer(tr("error.mealie"))
        ui.chat(target.chat.id).error_message_ids.append(sent.message_id)

    async def toast_error(query: CallbackQuery, tr: Translator, exc: Exception) -> None:
        log.warning("Mealie request failed: %s", exc)
        with suppress(*_TELEGRAM_ERRORS):
            await query.answer(tr("error.mealie_toast"), show_alert=True)

    # --- commands -------------------------------------------------------

    async def show_command(message: Message, tr: Translator, state: ListState) -> None:
        """Handle a list command: drop the command first so the live list can stay in place."""
        await ui.tidy(message)
        try:
            await ui.show(message, _user_id(message), tr, state)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)

    @router.message(Command(*command_names("list")))
    async def cmd_list(message: Message, tr: Translator) -> None:
        await show_command(message, tr, ListState())

    @router.message(Command(*command_names("lists")))
    async def cmd_lists(message: Message, tr: Translator) -> None:
        try:
            lists = await service.lists()
        except MealieError as exc:
            ui.note_message(message)
            await send_error(message, tr, exc)
            return
        if len(lists) == 1:
            ui.note_message(message)
            await message.answer(tr("shopping.only_list", list=escape(lists[0].get("name") or "?")))
            return
        await show_command(message, tr, ListState(view=VIEW_LISTS))

    @router.message(Command(*command_names("clear")))
    async def cmd_clear(message: Message, tr: Translator) -> None:
        await show_command(message, tr, ListState(view=VIEW_CLEAR))

    @router.message(F.text & ~F.text.startswith("/"))
    async def add_items(message: Message, tr: Translator) -> None:
        try:
            units = await service.units()
            try:
                entries = parse_message(message.text or "", units.known_tokens)
            except TooManyEntries as exc:
                await message.answer(tr("error.too_many", max=exc.limit))
                return
            except EntryTooLong as exc:
                await message.answer(tr("error.too_long", max=exc.limit))
                return
            if not entries:
                ui.note_message(message)
                await message.answer(tr("error.not_understood"))
                return
            # "typing…" while Mealie is asked; the list follows within a few seconds.
            if message.bot is not None:
                with suppress(*_TELEGRAM_ERRORS):
                    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            shopping_list = await service.active_list(_user_id(message))
            result = await service.add_entries(shopping_list["id"], entries)
        except (MealieError, NoShoppingListError) as exc:
            ui.note_message(message)
            await send_error(message, tr, exc)
            return
        # The items are in Mealie: the message may go (it is kept whenever
        # something went wrong above, so it can be resent).
        await ui.tidy(message, items=True)
        names = [item_inline(item, tr.language) for item in result.items]
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

    # --- buttons --------------------------------------------------------

    @router.callback_query(ItemAction.filter())
    async def on_item(query: CallbackQuery, callback_data: ItemAction, tr: Translator) -> None:
        message = query.message
        if not isinstance(message, Message) or not valid_id(callback_data.item_id):
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
                message.chat.id,
                "checked" if checked else "unchecked",
                _user_name(query),
                [item_inline(item, tr.language)],
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
        cached = False
        try:
            if action == "toggle":
                state.toggle(callback_data.arg)
                cached = True
                await query.answer()
            elif action == "refresh":
                await query.answer(tr("shopping.toast_refreshed"))
                state.view = VIEW_OPEN
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
            await ui.refresh(message, query.from_user.id, tr, cached=cached)
        except (MealieError, NoShoppingListError) as exc:
            await toast_error(query, tr, exc)

    @router.callback_query(SelectList.filter())
    async def on_select(query: CallbackQuery, callback_data: SelectList, tr: Translator) -> None:
        message = query.message
        if not isinstance(message, Message) or not valid_id(callback_data.list_id):
            await query.answer()
            return
        service.select_list(query.from_user.id, callback_data.list_id)
        try:
            await query.answer()
            await ui.show_in(message, query.from_user.id, tr, ListState())
        except (MealieError, NoShoppingListError) as exc:
            await toast_error(query, tr, exc)

    return router
