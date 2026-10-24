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
* Every handler holds the chat's lock, so two taps or two texts at the same
  time are handled one after another.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from mealie_bot.features import FeatureContext, TransientMessages
from mealie_bot.features.shopping.parser import (
    MAX_LABEL_LENGTH,
    EntryTooLong,
    InvalidAssignment,
    LabelTooLong,
    TooManyEntries,
    clean_text,
    has_arrow,
    parse_assignments,
    parse_message,
)
from mealie_bot.features.shopping.render import (
    STYLE_DONE,
    VIEW_CLEAR,
    VIEW_DONE,
    VIEW_LISTS,
    VIEW_OPEN,
    AssignAnswer,
    ItemAction,
    ListAction,
    ListState,
    SelectList,
    item_display,
    item_inline,
    label_dict_text,
    label_key,
    label_text,
    render_list,
    toast_text,
)
from mealie_bot.features.shopping.service import (
    AddResult,
    AssignResult,
    ListView,
    NoShoppingListError,
    ShoppingService,
)
from mealie_bot.features.shopping.state import (
    ChatState,
    HistoryEvent,
    PendingAssignment,
    render_history,
)
from mealie_bot.i18n import Translator, command_names
from mealie_bot.i18n.labels import LabelIcons
from mealie_bot.mealie import MealieError, MealieNotFound

log = logging.getLogger(__name__)

Clock = Callable[[], datetime]
_TELEGRAM_ERRORS = (TelegramBadRequest, TelegramForbiddenError)
# Mealie IDs are UUIDs. Button data can be forged by a client, so an ID is only
# put into a request path if it looks like one (no "/", "?", "." or "..").
_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def valid_id(value: str) -> bool:
    return bool(_SAFE_ID.match(value))


# Everything that can go wrong while showing the list and deserves a reply.
_SHOW_ERRORS = (MealieError, NoShoppingListError, *_TELEGRAM_ERRORS)


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
        label_icons: str = "both",
        transient: TransientMessages | None = None,
    ) -> None:
        self.service = service
        # Replies of the core commands (``/version``) that go with the shopping ones.
        self.transient = transient or TransientMessages()
        self.delete_commands = delete_commands
        self.delete_item_messages = delete_item_messages
        self.label_emoji = label_emoji
        # Display settings for categories (LABEL_ICONS plus LABEL_EMOJI overrides).
        self.label_icons = LabelIcons.from_mode(label_icons, label_emoji)
        self.clock = clock
        self.chats: dict[int, ChatState] = {}
        # Last fetched list per chat with its fetch time, so toggles need no round trip.
        self.cache: dict[int, tuple[ListView, datetime]] = {}

    def chat(self, chat_id: int) -> ChatState:
        return self.chats.setdefault(chat_id, ChatState())

    @asynccontextmanager
    async def locked(self, chat_id: int) -> AsyncIterator[ChatState]:
        chat = self.chat(chat_id)
        async with chat.lock:
            yield chat

    # --- rendering ----------------------------------------------------------

    async def list_id(self, chat_id: int, state: ListState) -> str:
        """The list a message shows: fixed on first render, else the chat's active list."""
        if state.list_id is None:
            state.list_id = str((await self.service.active_list(chat_id))["id"])
        return state.list_id

    async def render(
        self,
        chat_id: int,
        state: ListState,
        tr: Translator,
        cached: bool = False,
        loaded: tuple[ListView, datetime] | None = None,
    ) -> tuple[str, InlineKeyboardMarkup, str]:
        """Render a list message. ``cached`` reuses this chat's last fetch;
        ``loaded`` is a fetch another chat just made, used if it is the same list."""
        try:
            list_id = await self.list_id(chat_id, state)
            data, now = await self._view(chat_id, list_id, cached, loaded)
        except MealieNotFound:
            # The list was deleted in Mealie: fall back to whatever is active now.
            state.list_id = None
            list_id = await self.list_id(chat_id, state)
            data, now = await self._view(chat_id, list_id, cached, loaded)
        lists = await self.service.lists() if state.view == VIEW_LISTS else None
        text, markup = render_list(
            data.name,
            data.items,
            state,
            tr,
            now=now,
            emoji=self.label_icons,
            lists=lists,
            active_id=list_id,
            label_order=data.label_order,
        )
        # Remembered so that a change in another chat can re-render this one.
        self.chat(chat_id).language = tr.language
        return text, markup, data.name

    async def _view(
        self,
        chat_id: int,
        list_id: str,
        cached: bool,
        loaded: tuple[ListView, datetime] | None = None,
    ) -> tuple[ListView, datetime]:
        """The list's items: from ``loaded`` or, when ``cached``, from the chat's
        cache if that is the same list; otherwise fetched from Mealie."""
        if loaded is not None and loaded[0].id == list_id:
            self.cache[chat_id] = loaded
            return loaded
        if cached and chat_id in self.cache and self.cache[chat_id][0].id == list_id:
            return self.cache[chat_id]
        # Dropped first, so a failed fetch leaves no outdated copy to sync from.
        self.cache.pop(chat_id, None)
        data, now = await self.service.view(list_id), self.clock()
        self.cache[chat_id] = (data, now)
        return data, now

    async def show(self, message: Message, tr: Translator, state: ListState) -> None:
        """Show the list as a new live message at the bottom of the chat.

        The list is always sent again, never edited in place: when the user has
        cleared the chat history on their side, the old message still exists for
        the bot and an edit would succeed without anyone seeing it. The old
        message becomes a history entry or is deleted (see ``_relocate``).
        """
        chat = self.chat(message.chat.id)
        text, markup, list_name = await self.render(message.chat.id, state, tr)
        await self._drop_errors(message, chat)
        sent = await message.answer(text, reply_markup=markup)
        await self._relocate(chat, message, sent.message_id, list_name, tr)
        chat.states[sent.message_id] = state

    async def show_in(self, message: Message, tr: Translator, state: ListState) -> None:
        """Turn ``message`` (a bot message) into the live list message."""
        chat = self.chat(message.chat.id)
        text, markup, list_name = await self.render(message.chat.id, state, tr)
        with suppress(*_TELEGRAM_ERRORS):
            await _edit(message.bot, message.chat.id, message.message_id, text, markup)
        if chat.live_message_id != message.message_id:
            await self._relocate(chat, message, message.message_id, list_name, tr)
        chat.states[message.message_id] = state

    async def refresh(self, message: Message, tr: Translator, cached: bool = False) -> None:
        """Re-render a list message in place with its own display state."""
        chat = self.chat(message.chat.id)
        state = chat.state_for(message.message_id)
        text, markup, _ = await self.render(message.chat.id, state, tr, cached=cached)
        with suppress(*_TELEGRAM_ERRORS):
            await _edit(message.bot, message.chat.id, message.message_id, text, markup)

    async def sync_others(self, bot: Bot | None, origin_chat_id: int) -> None:
        """After a change in one chat, re-render the live messages of the other chats
        that show the same list, quietly and in their own language. There is no
        notification; the other person sees the change when they look.

        The list the origin chat fetched right after the change is reused, so a
        change costs one Mealie request however many chats show the list.
        """
        origin = self.chat(origin_chat_id)
        if bot is None or origin.live_list_id is None:
            return
        loaded = self.cache.get(origin_chat_id)
        for chat_id, chat in list(self.chats.items()):
            if chat_id == origin_chat_id or chat.live_message_id is None:
                continue
            if chat.live_list_id != origin.live_list_id or chat.language is None:
                continue
            try:
                tr = Translator(chat.language)
                state = chat.state_for(chat.live_message_id)
                text, markup, _ = await self.render(chat_id, state, tr, loaded=loaded)
                with suppress(*_TELEGRAM_ERRORS):
                    if not await _edit(bot, chat_id, chat.live_message_id, text, markup):
                        # Deleted on both sides: the chat has no live message any more.
                        chat.drop_live_message()
            except (MealieError, NoShoppingListError) as exc:
                log.warning("Syncing list for another chat failed: %s", exc)

    async def _drop_errors(self, message: Message, chat: ChatState) -> None:
        """Delete the bot's own error and info messages, and questions nobody
        answered, once the list is shown again."""
        ids = [
            *chat.transient_message_ids,
            *chat.questions,
            *self.transient.take(message.chat.id),
        ]
        chat.transient_message_ids, chat.questions = [], {}
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
        if old_id is None or old_id == new_id or message.bot is None:
            return
        chat.forget_message(old_id)
        extend, events = chat.take_pending()
        if events and not (extend and chat.history_message_id is not None):
            # Nothing recent to extend: the old list message itself becomes the entry.
            chat.history_message_id = old_id
        else:
            await self._remove(message.bot, message.chat.id, old_id, list_name, tr)
        if events and chat.history_message_id is not None:
            with suppress(*_TELEGRAM_ERRORS):
                await message.bot.edit_message_text(
                    render_history(
                        list_name,
                        events,
                        tr,
                        today=self.clock().date(),
                        owner_id=_owner_id(message),
                    ),
                    chat_id=message.chat.id,
                    message_id=chat.history_message_id,
                )

    async def _remove(
        self, bot: Bot, chat_id: int, message_id: int, list_name: str, tr: Translator
    ) -> None:
        """Delete an old list message. Telegram allows that for 48 hours only; after
        that the message is rewritten into a stub without buttons instead."""
        try:
            await bot.delete_message(chat_id, message_id)
        except _TELEGRAM_ERRORS as exc:
            if "message to delete not found" in str(exc):
                return  # already gone (e.g. the user cleared the chat for both sides)
            log.info("Could not delete message %s, rewriting it: %s", message_id, exc)
            with suppress(*_TELEGRAM_ERRORS):
                await bot.edit_message_text(
                    tr("history.superseded", list=escape(list_name)),
                    chat_id=chat_id,
                    message_id=message_id,
                )

    # --- bookkeeping --------------------------------------------------------

    def record(
        self,
        chat_id: int,
        kind: str,
        actor: Message | CallbackQuery,
        items: list[str],
        count: int = 0,
    ) -> None:
        """Note a change for the history of this chat and of every other chat
        that shows the same list, so both people's histories are complete."""
        user = actor.from_user
        event = HistoryEvent(
            kind,
            (user.first_name if user else None) or "?",
            self.clock(),
            items,
            count,
            user_id=user.id if user else None,
        )
        origin = self.chat(chat_id)
        origin.record(event)
        list_id = origin.live_list_id
        for other_id, other in self.chats.items():
            if other_id != chat_id and list_id is not None and other.live_list_id == list_id:
                other.record(HistoryEvent(**vars(event)))

    async def tidy(self, message: Message, *, items: bool = False) -> None:
        """Delete the user's command or item message if configured.

        Deleting may fail (e.g. in a group where the bot cannot delete others'
        messages); the message then simply stays.
        """
        enabled = self.delete_item_messages if items else self.delete_commands
        if enabled:
            with suppress(*_TELEGRAM_ERRORS):
                await message.delete()


async def _edit(
    bot: Bot | None, chat_id: int, message_id: int, text: str, markup: InlineKeyboardMarkup
) -> bool:
    """Edit a list message. Returns False if Telegram no longer knows the message
    (deleted on both sides); an unchanged message counts as edited."""
    if bot is None:  # pragma: no cover - messages from the dispatcher always carry a bot
        return True
    try:
        await bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id, reply_markup=markup
        )
    except TelegramBadRequest as exc:
        if "message to edit not found" in str(exc):
            return False
        if "message is not modified" not in str(exc):
            raise
    return True


def _owner_id(message: Message) -> int | None:
    """The user a private chat belongs to; their own name is left out of the history."""
    return message.chat.id if message.chat.type == "private" else None


def build_router(context: FeatureContext) -> Router:
    service = ShoppingService(context.mealie, default_list=context.settings.shopping_list)
    ui = ShoppingUI(
        service,
        delete_commands=context.settings.delete_commands,
        delete_item_messages=context.settings.delete_item_messages,
        label_emoji=context.settings.label_emoji,
        label_icons=context.settings.label_icons,
        transient=context.transient,
    )
    router = Router(name="shopping")

    async def send_error(target: Message, tr: Translator, exc: Exception) -> None:
        if isinstance(exc, NoShoppingListError):
            sent = await target.answer(tr("error.no_lists"))
        elif isinstance(exc, _TELEGRAM_ERRORS):
            # The list message itself was rejected (too long, too many buttons, ...).
            log.warning("Telegram rejected the list message: %s", exc)
            sent = await target.answer(tr("error.telegram"))
        else:
            log.warning("Mealie request failed: %s", exc)
            sent = await target.answer(tr("error.mealie"))
        ui.chat(target.chat.id).transient_message_ids.append(sent.message_id)

    async def toast_error(query: CallbackQuery, tr: Translator, exc: Exception) -> None:
        log.warning("Mealie request failed: %s", exc)
        with suppress(*_TELEGRAM_ERRORS):
            await query.answer(tr("error.mealie_toast"), show_alert=True)

    # --- commands -------------------------------------------------------

    async def show_command(message: Message, tr: Translator, state: ListState) -> None:
        """Handle a list command: drop the command, then send the list anew."""
        async with ui.locked(message.chat.id):
            await ui.tidy(message)
            try:
                await ui.show(message, tr, state)
            except _SHOW_ERRORS as exc:
                await send_error(message, tr, exc)

    @router.message(Command(*command_names("list")))
    async def cmd_list(message: Message, tr: Translator) -> None:
        await show_command(message, tr, ListState())

    @router.message(Command(*command_names("lists")))
    async def cmd_lists(message: Message, tr: Translator) -> None:
        try:
            lists = await service.lists()
        except MealieError as exc:
            await send_error(message, tr, exc)
            return
        if len(lists) == 1:
            await message.answer(tr("shopping.only_list", list=escape(lists[0].get("name") or "?")))
            return
        await show_command(message, tr, ListState(view=VIEW_LISTS))

    @router.message(Command(*command_names("clear")))
    async def cmd_clear(message: Message, tr: Translator) -> None:
        await show_command(message, tr, ListState(view=VIEW_CLEAR))

    async def send_transient(target: Message, text: str) -> None:
        """An info message that goes when the list is next shown, like an error."""
        sent = await target.answer(text)
        ui.chat(target.chat.id).transient_message_ids.append(sent.message_id)

    @router.message(Command(*command_names("category")))
    async def cmd_category(message: Message, command: CommandObject, tr: Translator) -> None:
        name = " ".join(clean_text(command.args or "").split())
        if not name:
            await send_transient(message, tr("category.usage", category=tr.command("category")))
            return
        if len(name) > MAX_LABEL_LENGTH:
            await send_transient(message, tr("category.too_long", max=MAX_LABEL_LENGTH))
            return
        async with ui.locked(message.chat.id):
            try:
                existing = await service.find_label(name)
                if existing is not None:
                    shown = escape(label_dict_text(existing, tr, ui.label_icons))
                    await send_transient(message, tr("category.exists", label=shown))
                    return
                label = await service.create_label(name, ui.label_emoji)
            except MealieError as exc:
                await send_error(message, tr, exc)
                return
            shown = label_dict_text(label, tr, ui.label_icons)
            ui.record(message.chat.id, "label", message, [shown])
            await ui.tidy(message)
            try:
                await ui.show(
                    message, tr, ListState(notice=tr("category.created", label=escape(shown)))
                )
            except _SHOW_ERRORS as exc:
                await send_error(message, tr, exc)

    @router.message(Command(*command_names("categories")))
    async def cmd_categories(message: Message, tr: Translator) -> None:
        async with ui.locked(message.chat.id):
            try:
                shopping_list = await service.active_list(message.chat.id)
                counts = await service.label_counts(str(shopping_list["id"]))
            except (MealieError, NoShoppingListError) as exc:
                await send_error(message, tr, exc)
                return
            await ui.tidy(message)
            if counts.labels:
                lines = [tr("category.list_header", count=len(counts.labels))]
                lines.extend(
                    tr(
                        "category.list_line",
                        label=escape(label_dict_text(label, tr, ui.label_icons)),
                        count=counts.foods_per_label.get(str(label["id"]), 0),
                    )
                    for label in counts.labels
                )
            else:
                lines = [tr("category.list_none", category=tr.command("category"))]
            lines.append(
                tr(
                    "category.list_uncategorized",
                    foods=counts.foods_without_label,
                    items=counts.items_without_label,
                )
            )
            await send_transient(message, "\n".join(lines))

    @router.message(F.text & ~F.text.startswith("/"))
    async def add_items(message: Message, tr: Translator) -> None:
        async with ui.locked(message.chat.id):
            if has_arrow(message.text or ""):
                await assign_locked(message, tr)
            else:
                await add_items_locked(message, tr)

    # --- "items → category" -----------------------------------------------

    async def assign_locked(message: Message, tr: Translator) -> None:
        try:
            units = await service.units()
            try:
                assignments = parse_assignments(message.text or "", units.known_tokens)
            except LabelTooLong as exc:
                await message.answer(tr("category.too_long", max=exc.limit))
                return
            except TooManyEntries as exc:
                await message.answer(tr("error.too_many", max=exc.limit))
                return
            except InvalidAssignment:
                await message.answer(tr("assign.not_understood"))
                return
            shopping_list = await service.active_list(message.chat.id)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        pending = PendingAssignment(
            list_id=str(shopping_list["id"]),
            user_message_id=message.message_id,
            assignments=assignments,
        )
        await advance_assignment(message, None, pending, tr, message)

    async def advance_assignment(
        message: Message,
        question: Message | None,
        pending: PendingAssignment,
        tr: Translator,
        actor: Message | CallbackQuery,
    ) -> None:
        """Resolve the next unknown name, asking when needed, and finally assign.

        ``message`` is any message in the chat to answer to; ``question`` is the
        bot's open question message, edited for the next question and deleted
        at the end; ``actor`` is the user's message or tap, for the history.
        """
        chat = ui.chat(message.chat.id)
        try:
            text, markup = await next_question(pending, tr)
        except MealieError as exc:
            if question is not None:
                # The answer counts; the open question can be answered again later.
                chat.questions[question.message_id] = pending
            await send_error(message, tr, exc)
            return
        if text is not None:
            if question is not None:
                with suppress(*_TELEGRAM_ERRORS):
                    await _edit(message.bot, message.chat.id, question.message_id, text, markup)
                chat.questions[question.message_id] = pending
            else:
                sent = await message.answer(text, reply_markup=markup)
                chat.questions[sent.message_id] = pending
            return
        if question is not None and message.bot is not None:
            with suppress(*_TELEGRAM_ERRORS):
                await message.bot.delete_message(message.chat.id, question.message_id)
        await run_assignment(message, pending, tr, actor)

    async def next_question(
        pending: PendingAssignment, tr: Translator
    ) -> tuple[str | None, InlineKeyboardMarkup]:
        """Resolve labels and foods that are known; return the question for the first
        one that is not, or ``(None, …)`` when everything is resolved."""
        empty = InlineKeyboardMarkup(inline_keyboard=[])
        cancel = InlineKeyboardButton(
            text=tr("shopping.btn_cancel"), callback_data=AssignAnswer(action="cancel").pack()
        )
        for assignment in pending.assignments:
            if assignment.label in pending.labels:
                continue
            label = await service.find_label(assignment.label)
            if label is not None:
                pending.labels[assignment.label] = label
                continue
            pending.asking = ("label", assignment.label)
            shown = label_text(assignment.label, None, ui.label_icons)
            rows = [
                [
                    InlineKeyboardButton(
                        text=tr("assign.btn_label_new", label=shown),
                        callback_data=AssignAnswer(action="label_new").pack(),
                        style=STYLE_DONE,
                    )
                ]
            ]
            similar = (await service.labels()).similar(assignment.label)
            if similar is not None:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=tr(
                                "assign.btn_label_use",
                                label=label_dict_text(similar, tr, ui.label_icons),
                            ),
                            callback_data=AssignAnswer(
                                action="label_use", arg=str(similar["id"])
                            ).pack(),
                        )
                    ]
                )
            rows.append([cancel])
            return tr("assign.ask_label", label=escape(shown)), InlineKeyboardMarkup(
                inline_keyboard=rows
            )
        for assignment in pending.assignments:
            for name in assignment.names:
                if name in pending.foods:
                    continue
                food = await service.find_food(name)
                if food is not None:
                    pending.foods[name] = food
                    continue
                similar = (await service.foods()).similar(name)
                if similar is None:
                    pending.foods[name] = None
                    continue
                pending.asking = ("food", name)
                similar_name = str(similar.get("name") or "?")
                rows = [
                    [
                        InlineKeyboardButton(
                            text=tr("assign.btn_food_use", food=similar_name),
                            callback_data=AssignAnswer(
                                action="food_use", arg=str(similar["id"])
                            ).pack(),
                            style=STYLE_DONE,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=tr("assign.btn_food_new", name=name),
                            callback_data=AssignAnswer(action="food_new").pack(),
                        )
                    ],
                    [cancel],
                ]
                return tr(
                    "assign.ask_food", name=escape(name), food=escape(similar_name)
                ), InlineKeyboardMarkup(inline_keyboard=rows)
        pending.asking = None
        return None, empty

    async def run_assignment(
        message: Message, pending: PendingAssignment, tr: Translator, actor: Message | CallbackQuery
    ) -> None:
        """Everything is resolved: write it to Mealie and show the list."""
        result = AssignResult()
        try:
            for assignment in pending.assignments:
                label = pending.labels[assignment.label]
                result.extend(
                    await service.assign(pending.list_id, assignment.names, label, pending.foods)
                )
        except MealieError as exc:
            await send_error(message, tr, exc)
            return
        if message.bot is not None and ui.delete_item_messages:
            with suppress(*_TELEGRAM_ERRORS):
                await message.bot.delete_message(message.chat.id, pending.user_message_id)
        ui.record(
            message.chat.id,
            "sorted",
            actor,
            [
                f"{name} → {label_dict_text(label, tr, ui.label_icons)}"
                for name, label in result.assigned
            ],
        )
        state = ListState(
            list_id=pending.list_id,
            expanded={str(label["id"]) for _, label in result.assigned},
            sorted_into=result.assigned,
            undo=result if result.undoable else None,
        )
        try:
            await ui.show(message, tr, state)
        except _SHOW_ERRORS as exc:
            await send_error(message, tr, exc)
            return
        await ui.sync_others(message.bot, message.chat.id)

    @router.callback_query(AssignAnswer.filter())
    async def on_assign_answer(
        query: CallbackQuery, callback_data: AssignAnswer, tr: Translator
    ) -> None:
        message = query.message
        if not isinstance(message, Message) or (
            callback_data.arg and not valid_id(callback_data.arg)
        ):
            await query.answer()
            return
        async with ui.locked(message.chat.id) as chat:
            pending = chat.questions.pop(message.message_id, None)
            if pending is None or pending.asking is None:
                # Answered already, or asked before a restart.
                await query.answer(tr("assign.stale"))
                with suppress(*_TELEGRAM_ERRORS):
                    await message.delete()
                return
            await query.answer()
            kind, name = pending.asking
            answered = name in (pending.labels if kind == "label" else pending.foods)
            try:
                if callback_data.action == "cancel":
                    with suppress(*_TELEGRAM_ERRORS):
                        await message.delete()
                    return
                if answered:
                    # Decided already; the next lookup failed last time (Mealie down).
                    pass
                elif kind == "label" and callback_data.action == "label_new":
                    pending.labels[name] = await service.create_label(name, ui.label_emoji)
                    ui.record(
                        message.chat.id,
                        "label",
                        query,
                        [label_dict_text(pending.labels[name], tr, ui.label_icons)],
                    )
                elif kind == "label" and callback_data.action == "label_use":
                    label = next(
                        (
                            candidate
                            for candidate in (await service.labels()).labels
                            if str(candidate["id"]) == callback_data.arg
                        ),
                        None,
                    )
                    if label is None:
                        await message.answer(tr("assign.stale"))
                        return
                    pending.labels[name] = label
                elif kind == "food" and callback_data.action == "food_new":
                    pending.foods[name] = None
                elif kind == "food" and callback_data.action == "food_use":
                    food = next(
                        (
                            candidate
                            for candidate in (await service.foods()).foods
                            if str(candidate["id"]) == callback_data.arg
                        ),
                        None,
                    )
                    if food is None:
                        await message.answer(tr("assign.stale"))
                        return
                    pending.foods[name] = food
                else:
                    chat.questions[message.message_id] = pending
                    return
            except MealieError as exc:
                chat.questions[message.message_id] = pending
                await toast_error(query, tr, exc)
                return
            await advance_assignment(message, message, pending, tr, query)

    async def add_items_locked(message: Message, tr: Translator) -> None:
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
                await message.answer(tr("error.not_understood"))
                return
            # "typing…" while Mealie is asked; the list follows within a few seconds.
            if message.bot is not None:
                with suppress(*_TELEGRAM_ERRORS):
                    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            shopping_list = await service.active_list(message.chat.id)
            result = await service.add_entries(shopping_list["id"], entries)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        # The items are in Mealie: the message may go (it is kept whenever
        # something went wrong above, so it can be resent).
        await ui.tidy(message, items=True)
        names = [item_inline(item, tr.language) for item in result.items]
        ui.record(message.chat.id, "added", message, names)
        state = ListState(
            list_id=str(shopping_list["id"]),
            expanded={label_key(item) for item in result.items},
            added=result.items,
            undo=result if result.undoable else None,
        )
        try:
            await ui.show(message, tr, state)
        except _SHOW_ERRORS as exc:
            await send_error(message, tr, exc)
            return
        await ui.sync_others(message.bot, message.chat.id)

    # --- buttons --------------------------------------------------------

    @router.callback_query(ItemAction.filter())
    async def on_item(query: CallbackQuery, callback_data: ItemAction, tr: Translator) -> None:
        message = query.message
        if not isinstance(message, Message) or not valid_id(callback_data.item_id):
            await query.answer()
            return
        async with ui.locked(message.chat.id) as chat:
            chat.state_for(message.message_id, callback_data.view)
            await on_item_locked(query, message, callback_data, tr)

    async def on_item_locked(
        query: CallbackQuery, message: Message, callback_data: ItemAction, tr: Translator
    ) -> None:
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
                query,
                [item_inline(item, tr.language)],
            )
            key = "shopping.toast_checked" if checked else "shopping.toast_unchecked"
            await query.answer(toast_text(tr(key, item=name)))
        try:
            await ui.refresh(message, tr)
        except (MealieError, NoShoppingListError) as exc:
            log.warning("Refreshing list failed: %s", exc)
        await ui.sync_others(message.bot, message.chat.id)

    @router.callback_query(ListAction.filter())
    async def on_list(query: CallbackQuery, callback_data: ListAction, tr: Translator) -> None:
        message = query.message
        action = callback_data.action
        if action == "noop" or not isinstance(message, Message):
            await query.answer()
            return
        async with ui.locked(message.chat.id) as chat:
            state = chat.state_for(message.message_id, callback_data.view)
            await on_list_locked(query, message, state, callback_data, tr)

    async def on_list_locked(
        query: CallbackQuery,
        message: Message,
        state: ListState,
        callback_data: ListAction,
        tr: Translator,
    ) -> None:
        action = callback_data.action
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
                if state.undo is None:
                    await query.answer(tr("shopping.toast_nothing_to_undo"))
                else:
                    # Keep the undo data until Mealie confirmed, so a failed
                    # attempt (Mealie down) can be repeated.
                    if isinstance(state.undo, AddResult):
                        created_ids = [item["id"] for item in state.undo.created]
                        count = await service.undo_add(created_ids, state.undo.previous)
                    else:
                        count = await service.undo_assign(state.undo)
                    ui.record(message.chat.id, "undone", query, [], count)
                    await query.answer(tr("shopping.toast_undone", count=count))
                state.undo = None
                state.added = []
                state.sorted_into = []
            elif action == "clear":
                list_id = await ui.list_id(message.chat.id, state)
                removed = await service.clear_checked(list_id)
                ui.record(message.chat.id, "cleared", query, [], len(removed))
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
            await ui.refresh(message, tr, cached=cached)
            if action in {"undo", "clear"}:
                await ui.sync_others(message.bot, message.chat.id)
        except (MealieError, NoShoppingListError) as exc:
            await toast_error(query, tr, exc)

    @router.callback_query(SelectList.filter())
    async def on_select(query: CallbackQuery, callback_data: SelectList, tr: Translator) -> None:
        message = query.message
        if not isinstance(message, Message) or not valid_id(callback_data.list_id):
            await query.answer()
            return
        service.select_list(message.chat.id, callback_data.list_id)
        async with ui.locked(message.chat.id):
            try:
                await query.answer()
                state = ListState(list_id=callback_data.list_id)
                await ui.show_in(message, tr, state)
            except (MealieError, NoShoppingListError) as exc:
                await toast_error(query, tr, exc)

    return router
