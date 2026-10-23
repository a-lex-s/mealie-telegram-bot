"""End-to-end handler tests: Telegram updates in, Mealie requests and bot replies out."""

import json
from datetime import UTC, datetime

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

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
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


def callback(data, user_id=ALICE, message_id=5, language="de"):
    user = User(id=user_id, is_bot=False, first_name="Bob", language_code=language)
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
                chat=Chat(id=user_id, type="private"),
                from_user=user,
                text="old",
            ),
        ),
    )


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
    assert "➕ <b>Added</b> (1)" in reply.text
    assert "<b>l milk</b> <i>2</i> <i>· 🥛 Dairy</i>" in reply.text
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
    original = session.make_request

    async def make_request(bot, method, timeout=None):
        if isinstance(method, DeleteMessage):
            session.calls.append(method)
            raise TelegramBadRequest(method, "Bad Request: message can't be deleted")
        return await original(bot, method, timeout)

    session.make_request = make_request
    await feed(message("eggs"))
    assert session.sent(DeleteMessage)  # tried, failed quietly
    assert "➕ <b>Added</b> (1)" in session.last(SendMessage).text


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
    assert "nichts mehr" in session.last(AnswerCallbackQuery).text


async def test_unparseable_text(harness, mealie_mock):
    feed, session = harness
    await feed(message("   "))
    assert "could not find" in session.last(SendMessage).text
    assert not session.sent(DeleteMessage)  # kept so the user can fix and resend it


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
    assert "2 offen · 0 erledigt" in reply.text
    assert buttons(reply) == [
        "🍞 Backwaren · 1 ▸",
        "🥛 Milchprodukte · 1 ▸",
        "🔄 Aktualisieren",
        "✅ Erledigt (0)",
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
    assert texts[:3] == ["🥛 Dairy · 1 ▸", "📦 Sonstiges · 1 ▾", "Soap"]
    await feed(callback(ListAction(action="toggle", arg=NO_LABEL).pack()))
    texts = buttons(session.last(EditMessageText))
    assert texts[:2] == ["🥛 Dairy · 1 ▸", "📦 Sonstiges · 1 ▸"]


async def test_second_list_command_replaces_the_old_message(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    await feed(message("/list", message_id=2))
    assert len(session.sent(SendMessage)) == 2
    # The old list message is deleted (nothing changed, so no history entry).
    assert first in [d.message_id for d in session.sent(DeleteMessage)]


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
    assert history and history[-1].text.startswith("<i>📜 Groceries</i>\n")
    assert "· Alice</i> ➕ eggs · 6" in history[-1].text
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
    assert session.last(AnswerCallbackQuery).text == "✓ Milch"
    edited = session.last(EditMessageText)
    assert "Alles gekauft" in edited.text and "<s>Milch</s>" in edited.text


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
    assert "1 erledigt" in edited.text
    assert edited.reply_markup.inline_keyboard[-1][1].text == "🧹 Entfernen (1)"

    await feed(callback(ListAction(action="clear_ask", view=VIEW_DONE).pack()))
    edited = session.last(EditMessageText)
    assert "entfernen?" in edited.text
    assert buttons(edited) == ["🧹 Ja, entfernen", "Abbrechen"]

    delete = mealie_mock.delete("/api/households/shopping/items").respond(json={})
    await feed(callback(ListAction(action="clear", view=VIEW_OPEN).pack()))
    assert delete.calls.last.request.url.params.get_list("ids") == ["i-1"]
    assert "1 erledigte" in session.last(AnswerCallbackQuery).text


async def test_clear_command_asks_first(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk", checked=True), make_item("i-2", "Eggs"))
    await feed(message("/clear"))
    reply = session.last(SendMessage)
    assert "Remove 1 ticked-off items from Groceries?" in reply.text
    assert reply.reply_markup.inline_keyboard[0][1].text == "Cancel"


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
    await feed(message("/lists"))
    reply = session.last(SendMessage)
    assert "Which shopping list?" in reply.text
    assert buttons(reply) == ["● Groceries", "Hardware"]
    chooser_id = session.next_id

    mealie_mock.get(f"/api/households/shopping/lists/{OTHER_LIST_ID}").respond(
        json={"id": OTHER_LIST_ID, "name": "Hardware", "listItems": [make_item("h-1", "Nails")]}
    )
    await feed(callback(SelectList(list_id=OTHER_LIST_ID).pack(), message_id=chooser_id))
    edited = session.last(EditMessageText)
    assert edited.message_id == chooser_id and "<b>Hardware</b>" in edited.text
    assert edited.reply_markup.inline_keyboard[0][0].text == "Nails"


# --- errors -----------------------------------------------------------------


async def test_mealie_down_reports_error(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get(LIST_URL).respond(502)
    await feed(message("/list"))
    assert "not reachable" in session.last(SendMessage).text


async def test_mealie_down_on_tap_shows_alert(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/items/i-1").respond(502)
    await feed(callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack()))
    toast = session.last(AnswerCallbackQuery)
    assert toast.show_alert and "nicht erreichbar" in toast.text


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
    assert session.sent(SetMyCommands)[0].commands[1].command == "liste"
