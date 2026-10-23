"""End-to-end handler tests: Telegram updates in, Mealie requests and bot replies out."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageText,
    SendChatAction,
    SendMessage,
)
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from mealie_bot.config import Settings
from mealie_bot.features.shopping.render import (
    NO_LABEL,
    VIEW_DONE,
    VIEW_OPEN,
    ItemAction,
    ListAction,
    SelectList,
)
from mealie_bot.mealie import MealieClient
from mealie_bot.telegram.app import build_dispatcher, register_commands
from tests.conftest import BASE_URL, LIST_ID, OTHER_LIST_ID, TOKEN, make_item

ALICE = 1001
BOB = 1002
STRANGER = 9999
LIST_URL = f"/api/households/shopping/lists/{LIST_ID}"


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []
        self.next_id = 100
        self.fail_deletes = False  # e.g. a group where the bot may not delete messages

    async def make_request(self, bot, method, timeout=None):
        # Yield to the event loop like a real request would, so that concurrent
        # updates really interleave.
        await asyncio.sleep(0)
        self.calls.append(method)
        if isinstance(method, DeleteMessage) and self.fail_deletes:
            raise TelegramBadRequest(method, "Bad Request: message can't be deleted")
        if isinstance(method, SendMessage):
            self.next_id += 1
            return Message(
                message_id=self.next_id,
                date=datetime.now(UTC),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, EditMessageText):
            return Message(
                message_id=method.message_id,
                date=datetime.now(UTC),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        return True

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    def sent(self, kind):
        return [c for c in self.calls if isinstance(c, kind)]

    def last(self, kind):
        return self.sent(kind)[-1]


def settings(**overrides):
    values = dict(
        telegram_token="123456:placeholder",
        mealie_url=BASE_URL,
        mealie_token=TOKEN,
        allowed_user_ids=frozenset({ALICE, BOB}),
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
async def harness(mealie_mock):
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings(), client)
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    mealie_mock.get("/api/units").respond(json={"items": []})
    mealie_mock.get("/api/foods").respond(json={"items": []})

    async def feed(update):
        await dispatcher.feed_update(bot, update)

    yield feed, session
    await client.aclose()


def buttons(sent):
    return [b.text for row in sent.reply_markup.inline_keyboard for b in row]


def mock_list(mealie_mock, *items):
    return mealie_mock.get(LIST_URL).respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": list(items)}
    )


def message(text, user_id=ALICE, language="en", message_id=1):
    return Update(
        update_id=1,
        message=Message(
            message_id=message_id,
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Alice", language_code=language),
            text=text,
        ),
    )


def callback(data, user_id=ALICE, message_id=5, language="de", chat_id=None):
    user = User(id=user_id, is_bot=False, first_name="Bob", language_code=language)
    chat_id = user_id if chat_id is None else chat_id
    return Update(
        update_id=2,
        callback_query=CallbackQuery(
            id="cb",
            from_user=user,
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=message_id,
                date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private"),
                from_user=user,
                text="old",
            ),
        ),
    )


# --- start and help ---------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "language", "expected"),
    [
        ("/start", "en", "/list shows the list"),
        ("/start", "de", "/liste zeigt die Liste"),
        ("/help", "en", "/lists switches"),
        ("/help", "de", "/listen wechselt"),
        ("/hilfe", "de", "/aufraeumen entfernt"),
    ],
)
async def test_start_and_help_render_with_localized_commands(harness, command, language, expected):
    feed, session = harness
    await feed(message(command, language=language))
    assert expected in session.last(SendMessage).text


# --- adding items -----------------------------------------------------------


async def test_text_adds_items_and_shows_list_with_undo(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    created = make_item("n-1", "", quantity=2, note="l milk", label="Dairy")
    route = mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [created], "updatedItems": []}
    )
    await feed(message("2 l milk, eggs"))
    body = json.loads(route.calls.last.request.content)
    assert [(i["quantity"], i["note"]) for i in body] == [(2, "l milk"), (1, "eggs")]
    assert session.sent(SendChatAction)
    reply = session.last(SendMessage)
    assert "Groceries" in reply.text
    assert "➕ <b>Added:</b> <b>l milk</b> · <i>2 · 🥛 Dairy</i>" in reply.text
    assert reply.reply_markup.inline_keyboard[-1][0].text == "↩️ Undo"
    # The user's text is deleted once the items are on the list.
    deleted = session.last(DeleteMessage)
    assert (deleted.chat_id, deleted.message_id) == (ALICE, 1)


async def test_item_messages_are_kept_when_configured(mealie_mock):
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings(delete_item_messages=False), client)
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    mealie_mock.get("/api/units").respond(json={"items": []})
    mealie_mock.get("/api/foods").respond(json={"items": []})
    mock_list(mealie_mock)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await dispatcher.feed_update(bot, message("eggs"))
    assert session.sent(SendMessage) and not session.sent(DeleteMessage)
    await client.aclose()


async def test_item_message_stays_when_mealie_fails(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(500)
    await feed(message("eggs"))
    assert "Mealie" in session.last(SendMessage).text
    assert not session.sent(DeleteMessage)


async def test_item_message_stays_when_delete_is_not_allowed(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    session.fail_deletes = True
    await feed(message("eggs"))
    assert session.sent(DeleteMessage)  # tried, failed quietly
    assert "➕ <b>Added:</b>" in session.last(SendMessage).text


async def test_undo_deletes_created_and_restores_merged_items(harness, mealie_mock):
    feed, session = harness
    old = make_item("m-1", "Milk", quantity=1, recipeReferences=[])
    mock_list(mealie_mock, old)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201,
        json={
            "createdItems": [make_item("n-1", "Eggs")],
            "updatedItems": [{**old, "quantity": 2}],
        },
    )
    await feed(message("milk, eggs"))
    list_message_id = session.last(SendMessage).chat_id and session.next_id

    delete = mealie_mock.delete("/api/households/shopping/items").respond(json={})
    put = mealie_mock.put("/api/households/shopping/items/m-1").respond(json={})
    await feed(callback(ListAction(action="undo").pack(), message_id=list_message_id))
    assert delete.calls.last.request.url.params.get_list("ids") == ["n-1"]
    assert json.loads(put.calls.last.request.content)["quantity"] == 1
    assert "2 Einträge" in session.last(AnswerCallbackQuery).text
    edited = session.last(EditMessageText)
    assert edited.reply_markup.inline_keyboard[-1][0].text == "🔄 Aktualisieren"

    await feed(callback(ListAction(action="undo").pack(), message_id=list_message_id))
    assert "Nichts mehr" in session.last(AnswerCallbackQuery).text


async def test_unparseable_text(harness, mealie_mock):
    feed, session = harness
    await feed(message("   "))
    assert "could not find" in session.last(SendMessage).text
    assert not session.sent(DeleteMessage)  # kept so the user can fix and resend it


async def test_too_many_entries_are_rejected_before_mealie(harness, mealie_mock):
    feed, session = harness
    route = mealie_mock.post("/api/households/shopping/items/create-bulk")
    await feed(message(", ".join(["milk"] * 51)))
    assert not route.called
    assert "more than 50" in session.last(SendMessage).text
    assert not session.sent(DeleteMessage)  # kept so the user can split it


async def test_too_long_entry_is_rejected(harness, mealie_mock):
    feed, session = harness
    await feed(message("x" * 201, language="de"))
    assert "länger als 200" in session.last(SendMessage).text


async def test_forged_callback_ids_never_reach_mealie(harness, mealie_mock):
    feed, session = harness
    get = mealie_mock.get(url__regex=r".*")
    await feed(callback(ItemAction(action="check", item_id="../users/self", view=VIEW_OPEN).pack()))
    await feed(callback(SelectList(list_id="x/../../api/users").pack()))
    assert [type(c).__name__ for c in session.calls] == ["AnswerCallbackQuery"] * 2
    assert not get.called


async def test_stranger_is_ignored(harness, mealie_mock):
    feed, session = harness
    route = mealie_mock.post("/api/households/shopping/items/create-bulk")
    await feed(message("milk", user_id=STRANGER))
    assert not route.called
    assert session.calls == []


async def test_stranger_is_ignored_on_every_update_type(harness, mealie_mock):
    """Access control sits on the update observer, so unhandled update types are covered too."""
    feed, session = harness
    edited = Update(
        update_id=3,
        edited_message=Message(
            message_id=7,
            date=datetime.now(UTC),
            chat=Chat(id=STRANGER, type="private"),
            from_user=User(id=STRANGER, is_bot=False, first_name="Mallory"),
            text="milk",
        ),
    )
    await feed(edited)
    await feed(callback(ListAction(action="show").pack(), user_id=STRANGER))
    assert session.calls == []


# --- showing the list -------------------------------------------------------


async def test_list_command_in_german_collapsed_and_tidy(harness, mealie_mock):
    feed, session = harness
    mock_list(
        mealie_mock,
        make_item("i-1", "Milch", label="Milchprodukte"),
        make_item("i-2", "Brot", label="Backwaren"),
    )
    await feed(message("/liste", user_id=BOB, language="de", message_id=7))
    reply = session.last(SendMessage)
    assert "\n2 offen · <i>" in reply.text  # no bar and no "0 erledigt" before the first tick
    assert buttons(reply) == [
        "🍞 Backwaren (1) ▸",
        "🥛 Milchprodukte (1) ▸",
        "🔄 Aktualisieren",
        "✅ Erledigt",
    ]
    deleted = session.last(DeleteMessage)
    assert (deleted.chat_id, deleted.message_id) == (BOB, 7)


async def test_commands_are_kept_when_configured(mealie_mock):
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings(delete_commands=False), client)
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    mock_list(mealie_mock)
    await dispatcher.feed_update(bot, message("/list"))
    assert session.sent(SendMessage) and not session.sent(DeleteMessage)
    await client.aclose()


async def test_toggle_expands_category(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milch", label="Dairy"), make_item("i-2", "Soap"))
    await feed(callback(ListAction(action="toggle", arg=NO_LABEL).pack()))
    texts = buttons(session.last(EditMessageText))
    assert texts[:3] == ["🥛 Dairy (1) ▸", "📦 Sonstiges (1) ▾", "Soap"]
    await feed(callback(ListAction(action="toggle", arg=NO_LABEL).pack()))
    texts = buttons(session.last(EditMessageText))
    assert texts[:2] == ["🥛 Dairy (1) ▸", "📦 Sonstiges (1) ▸"]


async def test_second_list_command_edits_the_live_message_in_place(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    await feed(message("/list", message_id=2))
    # The command was deleted, so the live list is still last and is edited in place.
    assert len(session.sent(SendMessage)) == 1
    assert session.last(EditMessageText).message_id == first
    assert first not in [d.message_id for d in session.sent(DeleteMessage)]
    assert [d.message_id for d in session.sent(DeleteMessage)] == [1, 2]
    await feed(message("/clear", message_id=3))
    edited = session.last(EditMessageText)
    assert edited.message_id == first and "Nothing ticked off yet" in edited.text
    assert len(session.sent(SendMessage)) == 1


async def test_list_command_resends_when_the_command_could_not_be_deleted(harness, mealie_mock):
    feed, session = harness
    session.fail_deletes = True
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    await feed(message("/list", message_id=2))
    assert len(session.sent(SendMessage)) == 2
    # The old list message is deleted (nothing changed, so no history entry).
    assert first in [d.message_id for d in session.sent(DeleteMessage)]


async def test_list_command_that_stays_in_the_chat_resends_the_list(mealie_mock):
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings(delete_commands=False), client)
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await dispatcher.feed_update(bot, message("/list"))
    first = session.next_id
    await dispatcher.feed_update(bot, message("/list", message_id=2))
    assert len(session.sent(SendMessage)) == 2
    # The old list message is deleted (nothing changed, so no history entry).
    assert first in [d.message_id for d in session.sent(DeleteMessage)]
    await client.aclose()


async def test_concurrent_texts_are_handled_one_after_another(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))

    async def slow_create(request):
        await asyncio.sleep(0.01)  # Mealie takes a moment, the other text arrives meanwhile
        return httpx.Response(201, json={"createdItems": [make_item("n-1", "Eggs")]})

    mealie_mock.post("/api/households/shopping/items/create-bulk").mock(side_effect=slow_create)
    await asyncio.gather(feed(message("eggs", message_id=2)), feed(message("eggs", message_id=3)))
    # The per-chat lock keeps the Telegram calls of the first text (typing, delete,
    # list) together instead of interleaving them with the second text's.
    kinds = [type(call).__name__ for call in session.calls]
    assert kinds[:4] == ["SendChatAction", "DeleteMessage", "SendMessage", "SendChatAction"]
    first_id = session.next_id - 1
    history = [e for e in session.sent(EditMessageText) if e.message_id == first_id]
    assert history and history[-1].text.startswith("📜 <b>Groceries</b>")


async def test_old_list_message_becomes_history_when_items_were_added(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "", note="eggs", quantity=6)]}
    )
    await feed(message("6 eggs", message_id=2))
    history = [e for e in session.sent(EditMessageText) if e.message_id == first]
    assert history and history[-1].text.startswith("📜 <b>Groceries</b>\n")
    assert "· Alice</i> ➕ 6 eggs" in history[-1].text
    assert first not in [d.message_id for d in session.sent(DeleteMessage)]


async def test_changes_within_the_window_extend_the_history_entry(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await feed(message("/list"))
    history_id = session.next_id
    await feed(message("eggs", message_id=2))
    second_list = session.next_id
    await feed(message("eggs", message_id=3))
    edits = [e for e in session.sent(EditMessageText) if e.message_id == history_id]
    assert "➕ Eggs, Eggs" in edits[-1].text
    assert second_list in [d.message_id for d in session.sent(DeleteMessage)]


# --- ticking off ------------------------------------------------------------


async def test_tap_checks_item_toasts_and_refreshes(harness, mealie_mock):
    feed, session = harness
    item = make_item("i-1", "Milch")
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=item)
    put = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    mock_list(mealie_mock, {**item, "checked": True})
    await feed(callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack()))
    assert json.loads(put.calls.last.request.content)["checked"] is True
    assert session.last(AnswerCallbackQuery).text == "✅ Milch"
    edited = session.last(EditMessageText)
    assert "Alles gekauft" in edited.text and "<s>Milch</s>" in edited.text


async def test_tap_after_restart_keeps_the_done_view(harness, mealie_mock):
    feed, session = harness
    item = make_item("i-1", "Milch", checked=True)
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=item)
    mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    mock_list(mealie_mock, {**item, "checked": False}, make_item("i-2", "Brot", checked=True))
    # No state exists for message 5: the view in the callback data decides.
    await feed(callback(ItemAction(action="uncheck", item_id="i-1", view=VIEW_DONE).pack()))
    assert "<b>Erledigt</b> · 1" in session.last(EditMessageText).text


async def test_tap_on_missing_item(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/items/gone").respond(404)
    mock_list(mealie_mock)
    await feed(callback(ItemAction(action="check", item_id="gone", view=VIEW_OPEN).pack()))
    assert "nicht mehr" in session.last(AnswerCallbackQuery).text
    assert session.sent(EditMessageText)


async def test_done_view_uncheck_and_clear_with_confirmation(harness, mealie_mock):
    feed, session = harness
    item = make_item("i-1", "Milch", checked=True)
    mock_list(mealie_mock, item)
    await feed(callback(ListAction(action="show", view=VIEW_DONE).pack()))
    edited = session.last(EditMessageText)
    assert "✅ <b>Erledigt</b> · 1" in edited.text
    assert edited.reply_markup.inline_keyboard[-1][1].text == "🧹 Entfernen (1)"

    await feed(callback(ListAction(action="clear_ask", view=VIEW_DONE).pack()))
    edited = session.last(EditMessageText)
    assert "entfernen?" in edited.text
    assert buttons(edited) == ["✕ Abbrechen", "🧹 Ja, entfernen"]

    delete = mealie_mock.delete("/api/households/shopping/items").respond(json={})
    await feed(callback(ListAction(action="clear", view=VIEW_OPEN).pack()))
    assert delete.calls.last.request.url.params.get_list("ids") == ["i-1"]
    assert session.last(AnswerCallbackQuery).text == "🧹 1 Eintrag entfernt"


async def test_clear_command_asks_first(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk", checked=True), make_item("i-2", "Eggs"))
    await feed(message("/clear"))
    reply = session.last(SendMessage)
    assert "Remove <b>1</b> ticked-off item for good?" in reply.text
    assert reply.reply_markup.inline_keyboard[0][0].text == "✕ Cancel"


# --- choosing a list --------------------------------------------------------


async def test_lists_command_and_selection_turns_into_the_list(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={
            "items": [
                {"id": LIST_ID, "name": "Groceries"},
                {"id": OTHER_LIST_ID, "name": "Hardware"},
            ]
        }
    )
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    live_id = session.next_id
    await feed(message("/lists", message_id=2))
    # The chooser is rendered into the live list message.
    reply = session.last(EditMessageText)
    assert reply.message_id == live_id
    assert "Which shopping list?" in reply.text
    assert buttons(reply) == ["Groceries", "Hardware", "✕ Cancel"]
    styles = [b.style for row in reply.reply_markup.inline_keyboard for b in row]
    assert styles == ["primary", None, None]
    chooser_id = live_id

    mealie_mock.get(f"/api/households/shopping/lists/{OTHER_LIST_ID}").respond(
        json={"id": OTHER_LIST_ID, "name": "Hardware", "listItems": [make_item("h-1", "Nails")]}
    )
    await feed(callback(SelectList(list_id=OTHER_LIST_ID).pack(), message_id=chooser_id))
    edited = session.last(EditMessageText)
    assert edited.message_id == chooser_id and "<b>Hardware</b>" in edited.text
    assert edited.reply_markup.inline_keyboard[0][0].text == "Nails"


async def test_list_message_keeps_its_list_after_switching(harness, mealie_mock):
    feed, session = harness
    lists = mealie_mock.get("/api/households/shopping/lists").respond(
        json={
            "items": [
                {"id": LIST_ID, "name": "Groceries"},
                {"id": OTHER_LIST_ID, "name": "Hardware"},
            ]
        }
    )
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    mealie_mock.get(f"/api/households/shopping/lists/{OTHER_LIST_ID}").respond(
        json={"id": OTHER_LIST_ID, "name": "Hardware", "listItems": []}
    )
    # Bob, in the same chat, switches the live message to Hardware.
    await feed(message("/lists", user_id=BOB))
    assert lists.called
    chooser_id = session.next_id
    select = SelectList(list_id=OTHER_LIST_ID).pack()
    await feed(callback(select, user_id=BOB, message_id=chooser_id))
    assert "<b>Hardware</b>" in session.last(EditMessageText).text
    # Alice's active list is still Groceries, but her tap refreshes the message's own list.
    show = ListAction(action="show", view=VIEW_OPEN).pack()
    await feed(callback(show, chat_id=BOB, message_id=chooser_id))
    edited = session.last(EditMessageText)
    assert edited.message_id == chooser_id and "<b>Hardware</b>" in edited.text


# --- errors -----------------------------------------------------------------


async def test_mealie_down_reports_error_and_the_error_goes_once_the_list_is_back(
    harness, mealie_mock
):
    feed, session = harness
    route = mealie_mock.get(LIST_URL).respond(502)
    await feed(message("/list"))
    assert (
        "⚠️" in session.last(SendMessage).text and "not reachable" in session.last(SendMessage).text
    )
    error_id = session.next_id
    route.respond(json={"id": LIST_ID, "name": "Groceries", "listItems": []})
    await feed(message("/list", message_id=2))
    assert "🛒" in session.last(SendMessage).text
    assert error_id in [d.message_id for d in session.sent(DeleteMessage)]


async def test_toggle_renders_from_cache_without_asking_mealie(harness, mealie_mock):
    feed, session = harness
    route = mock_list(
        mealie_mock, make_item("i-1", "Milch", label="Dairy"), make_item("i-2", "Soap")
    )
    await feed(message("/list"))
    assert route.call_count == 1
    await feed(
        callback(ListAction(action="toggle", arg=NO_LABEL).pack(), message_id=session.next_id)
    )
    assert route.call_count == 1  # no new fetch for opening a category
    assert buttons(session.last(EditMessageText))[2] == "Soap"
    await feed(callback(ListAction(action="refresh").pack(), message_id=session.next_id))
    assert route.call_count == 2
    assert session.last(AnswerCallbackQuery).text == "🔄 Aktualisiert"


async def test_lists_command_with_a_single_list_just_says_so(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    await feed(message("/lists"))
    assert session.last(SendMessage).text == "📋 There is only the list <b>Groceries</b>."


async def test_item_message_is_deleted_before_the_list_is_sent(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await feed(message("eggs"))
    kinds = [type(c) for c in session.calls if isinstance(c, (DeleteMessage, SendMessage))]
    assert kinds == [DeleteMessage, SendMessage]


async def test_mealie_answering_html_reports_error(harness, mealie_mock):
    mealie_mock.get(LIST_URL).respond(200, text="<html>maintenance</html>")
    feed, session = harness
    await feed(message("/list"))
    assert "not reachable" in session.last(SendMessage).text


async def test_telegram_rejecting_the_list_reports_error(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    original = session.make_request

    async def make_request(bot, method, timeout=None):
        if isinstance(method, SendMessage) and method.text.startswith("🛒"):
            raise TelegramBadRequest(method, "Bad Request: message is too long")
        return await original(bot, method, timeout)

    session.make_request = make_request
    await feed(message("/list"))
    assert "did not accept" in session.last(SendMessage).text


async def test_mealie_down_on_tap_shows_alert(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/items/i-1").respond(502)
    await feed(callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack()))
    toast = session.last(AnswerCallbackQuery)
    assert toast.show_alert and "Mealie antwortet nicht" in toast.text


async def test_no_lists(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/lists").respond(json={"items": []})
    await feed(message("/lists"))
    assert "no shopping list" in session.last(SendMessage).text


# --- start-up ---------------------------------------------------------------


async def test_register_commands_publishes_menu_and_description():
    from aiogram.methods import SetMyCommands, SetMyDescription, SetMyShortDescription

    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    await register_commands(bot, settings())
    assert [c.language_code for c in session.sent(SetMyCommands)] == [None, "de"]
    assert "Mealie" in session.sent(SetMyDescription)[0].description
    assert session.sent(SetMyShortDescription)[1].language_code == "de"

    session = RecordingSession()
    await register_commands(Bot("123456:placeholder", session=session), settings(bot_language="de"))
    assert [c.language_code for c in session.sent(SetMyCommands)] == [None]
    assert session.sent(SetMyCommands)[0].commands[0].command == "liste"
