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

from mealie_bot import __version__
from mealie_bot.config import Settings
from mealie_bot.features.shopping.render import (
    NO_LABEL,
    VIEW_DONE,
    VIEW_OPEN,
    AssignAnswer,
    ItemAction,
    ListAction,
    SelectList,
    SortAction,
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
async def harness(mealie_mock, request):
    """Dispatcher with recording Telegram session; parametrize with Settings overrides."""
    overrides = getattr(request, "param", {})
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings(**overrides), client)
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


def message(text, user_id=ALICE, language="en", message_id=1, chat_id=None, reply_to=None):
    chat = Chat(id=user_id, type="private") if chat_id is None else Chat(id=chat_id, type="group")
    return Update(
        update_id=1,
        message=Message(
            message_id=message_id,
            date=datetime.now(UTC),
            chat=chat,
            from_user=User(id=user_id, is_bot=False, first_name="Alice", language_code=language),
            text=text,
            reply_to_message=reply_to,
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
                chat=Chat(id=chat_id, type="group" if chat_id < 0 else "private"),
                from_user=user,
                text="old",
            ),
        ),
    )


# --- start and help ---------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "language", "expected"),
    [
        ("/start", "en", "👋 <b>Hi!</b>\n\n<b>I am your shopping list.</b>"),
        ("/start", "en", "/list shows the list"),
        ("/start", "de", "/liste zeigt die Liste"),
        ("/help", "en", "/help shows this again.\n\n<b>🛒 Shopping list</b>"),
        ("/help", "de", "/listen wechselt"),
        ("/hilfe", "de", "/aufraeumen entfernt"),
    ],
)
async def test_start_and_help_render_with_localized_commands(harness, command, language, expected):
    feed, session = harness
    await feed(message(command, language=language))
    assert expected in session.last(SendMessage).text


# --- version ----------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "de"])
async def test_version_without_commit_shows_only_the_version(harness, monkeypatch, language):
    feed, session = harness
    monkeypatch.delenv("VCS_REF", raising=False)
    await feed(message("/version", language=language))
    assert session.last(SendMessage).text == f"🔖 <b>mealie-telegram-bot</b> {__version__}"
    # Like other commands, the user's message is deleted.
    assert session.sent(DeleteMessage)


@pytest.mark.parametrize("vcs_ref", ["0123456789abcdef0123456789abcdef01234567", "0123456"])
async def test_version_with_commit_shows_the_short_commit(harness, monkeypatch, vcs_ref):
    feed, session = harness
    monkeypatch.setenv("VCS_REF", vcs_ref)
    await feed(message("/version"))
    assert (
        session.last(SendMessage).text
        == f"🔖 <b>mealie-telegram-bot</b> {__version__} · <code>0123456</code>"
    )


async def test_version_ignores_a_value_that_is_no_commit(harness, monkeypatch):
    feed, session = harness
    monkeypatch.setenv("VCS_REF", "<b>main")
    await feed(message("/version"))
    assert session.last(SendMessage).text == f"🔖 <b>mealie-telegram-bot</b> {__version__}"


async def test_version_answer_goes_when_the_list_is_shown(harness, mealie_mock, monkeypatch):
    feed, session = harness
    monkeypatch.delenv("VCS_REF", raising=False)
    mock_list(mealie_mock)
    await feed(message("/version", message_id=7))
    answer_id = session.next_id
    assert [(d.chat_id, d.message_id) for d in session.sent(DeleteMessage)] == [(ALICE, 7)]
    await feed(message("/list", message_id=8))
    assert answer_id in [d.message_id for d in session.sent(DeleteMessage)]


@pytest.mark.parametrize("harness", [{"delete_commands": False}], indirect=True)
async def test_version_is_kept_when_commands_are_kept(harness, monkeypatch):
    feed, session = harness
    monkeypatch.delenv("VCS_REF", raising=False)
    await feed(message("/version"))
    assert session.sent(SendMessage) and not session.sent(DeleteMessage)


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


@pytest.mark.parametrize("harness", [{"delete_item_messages": False}], indirect=True)
async def test_item_messages_are_kept_when_configured(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await feed(message("eggs"))
    assert session.sent(SendMessage) and not session.sent(DeleteMessage)


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
    list_message_id = session.next_id

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


@pytest.mark.parametrize("harness", [{"shopping_create_foods": True}], indirect=True)
async def test_created_foods_land_in_other_and_undo_deletes_them(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    foods = mealie_mock.post("/api/foods").respond(201, json={"id": "f-new", "name": "Ketchup"})
    created = make_item("n-1", "Ketchup", foodId="f-new", food={"id": "f-new", "name": "Ketchup"})
    bulk = mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [created]}
    )
    await feed(message("Ketchup"))
    assert json.loads(foods.calls.last.request.content) == {"name": "Ketchup"}
    assert json.loads(bulk.calls.last.request.content)[0]["foodId"] == "f-new"
    assert "<b>Ketchup</b> · <i>📦 Other</i>" in session.last(SendMessage).text

    mealie_mock.delete("/api/households/shopping/items").respond(json={})
    delete_food = mealie_mock.delete("/api/foods/f-new").respond(json={})
    await feed(callback(ListAction(action="undo").pack(), message_id=session.next_id))
    assert delete_food.called


@pytest.mark.parametrize("harness", [{"shopping_create_foods": True}], indirect=True)
async def test_unparseable_text_creates_no_food(harness, mealie_mock):
    feed, _ = harness
    foods = mealie_mock.post("/api/foods").respond(201, json={"id": "f"})
    await feed(message(" , ; "))
    assert not foods.called


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


@pytest.mark.parametrize("harness", [{"delete_commands": False}], indirect=True)
async def test_commands_are_kept_when_configured(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    await feed(message("/list"))
    assert session.sent(SendMessage) and not session.sent(DeleteMessage)


async def test_toggle_expands_category(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milch", label="Dairy"), make_item("i-2", "Soap"))
    await feed(callback(ListAction(action="toggle", arg=NO_LABEL).pack()))
    texts = buttons(session.last(EditMessageText))
    assert texts[:3] == ["🥛 Dairy (1) ▸", "📦 Sonstiges (1) ▾", "Soap"]
    await feed(callback(ListAction(action="toggle", arg=NO_LABEL).pack()))
    texts = buttons(session.last(EditMessageText))
    assert texts[:2] == ["🥛 Dairy (1) ▸", "📦 Sonstiges (1) ▸"]


async def test_second_list_command_resends_the_list_and_drops_the_old_one(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    await feed(message("/list", message_id=2))
    # The command is deleted and the list is sent again; the old list message
    # goes (nothing changed, so there is no history entry). It is never edited
    # in place: a message the user has cleared from their side would take the
    # edit without anyone seeing it.
    assert len(session.sent(SendMessage)) == 2
    assert [d.message_id for d in session.sent(DeleteMessage)] == [1, 2, first]
    assert not session.sent(EditMessageText)
    await feed(message("/clear", message_id=3))
    sent = session.last(SendMessage)
    assert "Nothing ticked off yet" in sent.text
    assert len(session.sent(SendMessage)) == 3


class ClearedChatSession(RecordingSession):
    """Telegram after the user cleared the chat history: ``gone`` holds the IDs of
    messages that no longer exist for the bot either (cleared for both sides);
    ``hidden`` the IDs cleared on the user's side only, which the bot can still
    edit without the user seeing anything."""

    def __init__(self) -> None:
        super().__init__()
        self.gone: set[int] = set()
        self.hidden: set[int] = set()

    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, (EditMessageText, DeleteMessage)) and method.message_id in self.gone:
            self.calls.append(method)
            what = "edit" if isinstance(method, EditMessageText) else "delete"
            raise TelegramBadRequest(method, f"Bad Request: message to {what} not found")
        return await super().make_request(bot, method, timeout)


@pytest.fixture
async def cleared_harness(mealie_mock):
    client = MealieClient(BASE_URL, TOKEN)
    session = ClearedChatSession()
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


@pytest.mark.parametrize("both_sides", [True, False], ids=["cleared_for_both", "cleared_for_user"])
async def test_list_command_after_the_user_cleared_the_chat(
    cleared_harness, mealie_mock, both_sides
):
    feed, session = cleared_harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    (session.gone if both_sides else session.hidden).add(first)
    await feed(message("/list", message_id=2))
    # A new list is sent in either case, without a restart and without an error reply.
    sent = session.sent(SendMessage)
    assert len(sent) == 2 and "<b>Groceries</b>" in sent[-1].text
    assert first in [d.message_id for d in session.sent(DeleteMessage)]
    assert not [e for e in session.sent(EditMessageText) if e.message_id == first]
    # The new message is the live one: a tap on it refreshes it.
    live = session.next_id
    await feed(callback(ListAction(action="refresh").pack(), message_id=live))
    assert session.last(EditMessageText).message_id == live


async def test_sync_forgets_a_live_message_deleted_on_both_sides(cleared_harness, mealie_mock):
    feed, session = cleared_harness
    route = mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list", user_id=ALICE))
    await feed(message("/list", user_id=BOB, language="de"))
    bob_list = session.next_id
    session.gone.add(bob_list)
    route.respond(
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": [make_item("i-1", "Milk"), make_item("n-1", "Eggs")],
        }
    )
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await feed(message("eggs", user_id=ALICE, message_id=2))
    # One failed edit, then Bob's chat is no longer synced until he asks for the list again.
    assert len([e for e in session.sent(EditMessageText) if e.message_id == bob_list]) == 1
    await feed(message("bread", user_id=ALICE, message_id=3))
    assert len([e for e in session.sent(EditMessageText) if e.message_id == bob_list]) == 1
    await feed(message("/list", user_id=BOB, language="de", message_id=4))
    assert "2 offen" in session.last(SendMessage).text
    assert bob_list not in [d.message_id for d in session.sent(DeleteMessage)]


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


@pytest.mark.parametrize("harness", [{"delete_commands": False}], indirect=True)
async def test_list_command_that_stays_in_the_chat_resends_the_list(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    await feed(message("/list", message_id=2))
    assert len(session.sent(SendMessage)) == 2
    # The old list message is deleted (nothing changed, so no history entry).
    assert first in [d.message_id for d in session.sent(DeleteMessage)]


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
    # In a private chat the owner's own name is left out.
    assert "</i> ➕ 6 eggs" in history[-1].text and "Alice" not in history[-1].text
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
    # The chooser is the new live list message; the old one is deleted.
    reply = session.last(SendMessage)
    assert live_id in [d.message_id for d in session.sent(DeleteMessage)]
    assert "Which shopping list?" in reply.text
    assert buttons(reply) == ["Groceries", "Hardware", "✕ Cancel"]
    styles = [b.style for row in reply.reply_markup.inline_keyboard for b in row]
    assert styles == ["primary", None, None]
    chooser_id = session.next_id

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


# --- robustness (review findings) -------------------------------------------


async def test_undo_survives_a_mealie_outage(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock)
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")], "updatedItems": []}
    )
    await feed(message("eggs"))
    list_message_id = session.next_id
    delete = mealie_mock.delete("/api/households/shopping/items").respond(503)
    await feed(callback(ListAction(action="undo").pack(), message_id=list_message_id))
    assert "Mealie antwortet nicht" in session.last(AnswerCallbackQuery).text

    delete.respond(json={})
    await feed(callback(ListAction(action="undo").pack(), message_id=list_message_id))
    assert delete.calls.last.request.url.params.get_list("ids") == ["n-1"]
    assert session.last(AnswerCallbackQuery).text == "↩️ 1 Eintrag rückgängig"


async def test_old_list_message_is_rewritten_when_it_cannot_be_deleted(harness, mealie_mock):
    feed, session = harness
    mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list"))
    first = session.next_id
    # Telegram refuses every deletion: the command stays, so the list is sent
    # again, and the old list message cannot go either.
    session.fail_deletes = True
    await feed(message("/list", message_id=2))
    stub = [e for e in session.sent(EditMessageText) if e.message_id == first][-1]
    assert stub.text == "📜 <b>Groceries</b>\n<i>↓ The current list is further down.</i>"
    assert stub.reply_markup is None


async def test_long_toast_is_cut_to_telegram_limit(harness, mealie_mock):
    feed, session = harness
    item = make_item("l-1", "", note="very long note " * 20)
    mock_list(mealie_mock, item)
    mealie_mock.get("/api/households/shopping/items/l-1").respond(json=item)
    mealie_mock.put("/api/households/shopping/items/l-1").respond(json=item)
    await feed(callback(ItemAction(action="check", item_id="l-1", view=VIEW_OPEN).pack()))
    toast = session.last(AnswerCallbackQuery).text
    assert len(toast) == 200 and toast.endswith("…")


async def test_unknown_command_and_photo_get_a_hint(harness, mealie_mock):
    feed, session = harness
    await feed(message("/foo"))
    assert "/help" in session.last(SendMessage).text
    photo = Update(
        update_id=3,
        message=Message(
            message_id=4,
            date=datetime.now(UTC),
            chat=Chat(id=ALICE, type="private"),
            from_user=User(id=ALICE, is_bot=False, first_name="Alice", language_code="de"),
            caption="Einkauf",
        ),
    )
    await feed(photo)
    assert session.last(SendMessage).text.startswith("Ich verstehe nur Text")


# --- two people, two chats ---------------------------------------------------


async def test_change_in_one_chat_updates_the_other_chats_live_message(harness, mealie_mock):
    feed, session = harness
    route = mock_list(mealie_mock, make_item("i-1", "Milk"))
    await feed(message("/list", user_id=ALICE))
    await feed(message("/list", user_id=BOB, language="de"))
    bob_list = session.next_id
    route.respond(
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": [make_item("i-1", "Milk"), make_item("n-1", "Eggs")],
        }
    )
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await feed(message("eggs", user_id=ALICE, message_id=2))
    bob = [e for e in session.sent(EditMessageText) if e.message_id == bob_list]
    assert bob and "2 offen" in bob[-1].text  # Bob's message, in Bob's language
    assert "Eggs" in buttons(bob[-1])

    # Bob's history later names Alice, since the change was not his own; his
    # own addition carries no name in his private chat.
    await feed(message("bread", user_id=BOB, language="de", message_id=3))
    history = [e for e in session.sent(EditMessageText) if e.message_id == bob_list]
    assert "· Alice</i> ➕ Eggs" in history[-1].text
    own = history[-1].text.split("\n")[-1]
    assert own.endswith("</i> ➕ Eggs") and "·" not in own


async def test_list_choice_is_per_chat(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}, {"id": OTHER_LIST_ID, "name": "Z"}]}
    )
    mock_list(mealie_mock)
    mealie_mock.get(f"/api/households/shopping/lists/{OTHER_LIST_ID}").respond(
        json={"id": OTHER_LIST_ID, "name": "Z", "listItems": []}
    )
    await feed(callback(SelectList(list_id=OTHER_LIST_ID).pack(), user_id=ALICE))
    assert "<b>Z</b>" in session.last(EditMessageText).text
    await feed(message("/list", user_id=BOB))
    assert "<b>Groceries</b>" in session.last(SendMessage).text


GROUP = -5001


async def test_sync_reuses_the_loaded_list_for_every_other_chat(harness, mealie_mock):
    feed, session = harness
    item = make_item("i-1", "Milk")
    route = mock_list(mealie_mock, item, make_item("i-2", "Eggs"))
    await feed(message("/list", user_id=ALICE))
    await feed(message("/list", user_id=BOB, language="de"))
    bob_list = session.next_id
    await feed(message("/list", user_id=BOB, chat_id=GROUP))
    group_list = session.next_id
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=item)
    mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    route.respond(
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": [{**item, "checked": True}, make_item("i-2", "Eggs")],
        }
    )
    before = route.call_count
    await feed(
        callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack(), user_id=ALICE)
    )
    # One list request for Alice's refresh; Bob's chat and the group reuse it.
    assert route.call_count - before == 1
    edits = {e.message_id: e for e in session.sent(EditMessageText)}
    assert "1 erledigt" in edits[bob_list].text  # Bob's chat, in Bob's language
    assert "1 done" in edits[group_list].text


async def test_sync_leaves_chats_on_another_list_alone(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}, {"id": OTHER_LIST_ID, "name": "Z"}]}
    )
    item = make_item("i-1", "Milk")
    route = mock_list(mealie_mock, item)
    other = mealie_mock.get(f"/api/households/shopping/lists/{OTHER_LIST_ID}").respond(
        json={"id": OTHER_LIST_ID, "name": "Z", "listItems": []}
    )
    await feed(message("/list", user_id=ALICE))
    await feed(callback(SelectList(list_id=OTHER_LIST_ID).pack(), user_id=BOB, message_id=50))
    other_calls = other.call_count
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=item)
    mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    before = route.call_count
    edits = len(session.sent(EditMessageText))
    await feed(
        callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack(), user_id=ALICE)
    )
    assert route.call_count - before == 1 and other.call_count == other_calls
    assert [e.message_id for e in session.sent(EditMessageText)[edits:]] == [5]


async def test_sync_after_a_failed_refresh_asks_mealie_again(harness, mealie_mock):
    feed, session = harness
    item = make_item("i-1", "Milk")
    route = mock_list(mealie_mock, item)
    await feed(message("/list", user_id=ALICE))
    await feed(message("/list", user_id=BOB, language="de"))
    bob_list = session.next_id
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=item)
    mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(
            200,
            json={"id": LIST_ID, "name": "Groceries", "listItems": [{**item, "checked": True}]},
        ),
    ]
    await feed(
        callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack(), user_id=ALICE)
    )
    # Alice's refresh failed; Bob's chat is not rendered from the copy from
    # before the change but fetched anew.
    bob = [e for e in session.sent(EditMessageText) if e.message_id == bob_list]
    assert bob and "1 erledigt" in bob[-1].text


# --- categories -------------------------------------------------------------

LABEL = {"id": "lab-1", "name": "Würzmittel", "color": "#9b7bb8", "groupId": "g"}


def mock_categories(mealie_mock, labels=(LABEL,), foods=()):
    mealie_mock.get("/api/groups/labels").respond(json={"items": list(labels)})
    mealie_mock.get("/api/foods").respond(json={"items": list(foods)})


async def test_arrow_sorts_a_known_product_without_questions(harness, mealie_mock):
    feed, session = harness
    ketchup = {"id": "f-k", "name": "Ketchup", "labelId": None, "aliases": []}
    mock_categories(mealie_mock, foods=[ketchup])
    item = make_item("i-1", "Ketchup", foodId="f-k", food=ketchup)
    mock_list(mealie_mock, item)
    put_food = mealie_mock.put("/api/foods/f-k").respond(json={**ketchup, "labelId": "lab-1"})
    put_item = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    await feed(message("Ketchup → Würzmittel", language="de"))
    assert json.loads(put_food.calls.last.request.content)["labelId"] == "lab-1"
    assert json.loads(put_item.calls.last.request.content)["labelId"] == "lab-1"
    reply = session.last(SendMessage)
    assert "🏷️ <b>Einsortiert:</b> <b>Ketchup</b> · <i>🟣 🧂 Würzmittel</i>" in reply.text
    assert reply.reply_markup.inline_keyboard[-1][0].text == "↩️ Rückgängig"
    deleted = session.last(DeleteMessage)
    assert (deleted.chat_id, deleted.message_id) == (ALICE, 1)
    assert not session.sent(AnswerCallbackQuery)


async def test_arrow_asks_before_creating_a_category_and_a_food(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock, foods=[{"id": "f-k", "name": "Ketchup", "aliases": []}])
    mock_list(mealie_mock, make_item("i-1", "Ketchap", note="Ketchap"))
    create_label = mealie_mock.post("/api/groups/labels").respond(
        201, json={"id": "lab-2", "name": "Haushalt", "color": "#5d8aa8", "groupId": "g"}
    )
    create_food = mealie_mock.post("/api/foods")
    put_item = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    put_food = mealie_mock.put("/api/foods/f-k").respond(json={})

    await feed(message("Ketchap -> Haushalt", language="de"))
    question = session.last(SendMessage)
    assert question.text == "❓ Die Kategorie <b>🧻 Haushalt</b> gibt es noch nicht."
    assert buttons(question) == ["➕ 🧻 Haushalt anlegen", "✕ Abbrechen"]
    question_id = session.next_id
    assert not create_label.called

    await feed(callback(AssignAnswer(action="label_new").pack(), message_id=question_id))
    assert json.loads(create_label.calls.last.request.content) == {
        "name": "Haushalt",
        "color": "#5d8aa8",
    }
    edited = session.last(EditMessageText)
    assert edited.message_id == question_id
    assert edited.text == "❓ <b>Ketchap</b> kenne ich nicht. Meinst du <b>Ketchup</b>?"
    assert buttons(edited) == ["Ja, Ketchup", "➕ Nein, Ketchap anlegen", "✕ Abbrechen"]

    await feed(callback(AssignAnswer(action="food_use", arg="f-k").pack(), message_id=question_id))
    assert not create_food.called
    assert json.loads(put_food.calls.last.request.content)["labelId"] == "lab-2"
    assert put_item.calls.last.request.url.path.endswith("i-1")
    # The question and the user's line are gone, the list shows the result.
    deleted = [(d.chat_id, d.message_id) for d in session.sent(DeleteMessage)]
    assert (ALICE, question_id) in deleted and (ALICE, 1) in deleted
    assert (
        "<b>Einsortiert:</b> <b>Ketchup</b> · <i>🔵 🧻 Haushalt</i>"
        in session.last(SendMessage).text
    )


async def test_arrow_offers_the_similar_category_and_creates_an_unknown_food(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    create_food = mealie_mock.post("/api/foods").respond(
        201, json={"id": "f-new", "name": "Sojasoße", "labelId": "lab-1"}
    )
    await feed(message("Sojasoße → Würzmitel"))
    question = session.last(SendMessage)
    assert buttons(question) == ["➕ Create 🧂 Würzmitel", "Use 🟣 🧂 Würzmittel", "✕ Cancel"]
    await feed(
        callback(AssignAnswer(action="label_use", arg="lab-1").pack(), message_id=session.next_id)
    )
    assert json.loads(create_food.calls.last.request.content) == {
        "name": "Sojasoße",
        "labelId": "lab-1",
    }
    assert "<b>Sojasoße</b> · <i>🟣 🧂 Würzmittel</i>" in session.last(SendMessage).text


async def test_arrow_question_can_be_cancelled_and_is_stale_afterwards(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    create = mealie_mock.post("/api/groups/labels")
    await feed(message("Seife → Drogerie"))
    question_id = session.next_id
    await feed(callback(AssignAnswer(action="cancel").pack(), message_id=question_id))
    deleted = session.last(DeleteMessage)
    assert deleted.message_id == question_id
    assert not create.called
    await feed(callback(AssignAnswer(action="label_new").pack(), message_id=question_id))
    assert "nicht mehr offen" in session.last(AnswerCallbackQuery).text


async def test_unanswered_question_is_dropped_when_the_list_is_shown(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    await feed(message("Seife → Drogerie"))
    question_id = session.next_id
    await feed(message("/list"))
    assert question_id in [d.message_id for d in session.sent(DeleteMessage)]
    await feed(callback(AssignAnswer(action="label_new").pack(), message_id=question_id))
    assert "nicht mehr offen" in session.last(AnswerCallbackQuery).text


async def test_answer_survives_a_mealie_outage_during_the_next_lookup(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    create_label = mealie_mock.post("/api/groups/labels").respond(
        201, json={"id": "lab-2", "name": "Drogerie", "color": "#d58cc0", "groupId": "g"}
    )
    await feed(message("Seife → Drogerie"))
    question_id = session.next_id
    # The label is created, then the food lookup fails: the question stays answerable.
    foods = mealie_mock.get("/api/foods").mock(side_effect=httpx.ConnectError("down"))
    await feed(callback(AssignAnswer(action="label_new").pack(), message_id=question_id))
    assert create_label.call_count == 1
    assert "Mealie" in session.last(SendMessage).text
    foods.respond(json={"items": []})
    mealie_mock.post("/api/foods").respond(201, json={"id": "f-s", "name": "Seife"})
    await feed(callback(AssignAnswer(action="label_new").pack(), message_id=question_id))
    assert create_label.call_count == 1  # the label is not created twice
    assert "<b>Seife</b>" in session.last(SendMessage).text


async def test_undo_reverts_a_sorting(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    mealie_mock.post("/api/foods").respond(201, json={"id": "f-new", "name": "Senf"})
    await feed(message("Senf → Würzmittel", language="de"))
    list_message_id = session.next_id
    delete = mealie_mock.delete("/api/foods/f-new").respond(204)
    await feed(callback(ListAction(action="undo").pack(), message_id=list_message_id))
    assert delete.called
    assert "1 Eintrag rückgängig" in session.last(AnswerCallbackQuery).text
    edited = session.last(EditMessageText)
    assert "Einsortiert" not in edited.text
    assert edited.reply_markup.inline_keyboard[-1][0].text == "🔄 Aktualisieren"


async def test_unreadable_arrow_line_is_explained_and_kept(harness, mealie_mock):
    feed, session = harness
    await feed(message("Ketchup →"))
    assert "could not read" in session.last(SendMessage).text
    assert not session.sent(DeleteMessage)


async def test_category_command_creates_and_reports_existing(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    create = mealie_mock.post("/api/groups/labels").respond(
        201, json={"id": "lab-3", "name": "🧴 Drogerie", "color": "#d58cc0", "groupId": "g"}
    )
    await feed(message("/kategorie 🧴 Dro\u200bgerie", language="de"))  # invisible char dropped
    assert json.loads(create.calls.last.request.content) == {
        "name": "🧴 Drogerie",
        "color": "#d58cc0",
    }
    reply = session.last(SendMessage)
    assert "🏷️ <b>Neue Kategorie:</b> 🟣 🧴 Drogerie" in reply.text
    assert session.last(DeleteMessage).message_id == 1  # the command is tidied away

    await feed(message("/category würzmittel"))
    assert session.last(SendMessage).text == (
        "🏷️ The category <b>🟣 🧂 Würzmittel</b> already exists."
    )
    await feed(message("/category"))
    assert "/category Household" in session.last(SendMessage).text
    usage_id = session.next_id
    await feed(message("/category " + "x" * 41))
    assert "at most 40" in session.last(SendMessage).text
    # Those replies are tidied away the next time the list is shown.
    await feed(message("/list"))
    assert usage_id in [d.message_id for d in session.sent(DeleteMessage)]


async def test_categories_command_lists_counts_and_is_tidied_later(harness, mealie_mock):
    feed, session = harness
    mock_categories(
        mealie_mock,
        labels=[LABEL, {"id": "lab-2", "name": "Eigenes", "color": "#5cb85c", "groupId": "g"}],
        foods=[{"id": "f-1", "name": "Senf", "labelId": "lab-1"}, {"id": "f-2", "name": "Milch"}],
    )
    mock_list(mealie_mock, make_item("i-1", "Milch", note="Milch"))
    await feed(message("/kategorien", language="de"))
    info = session.last(SendMessage)
    assert info.text == (
        "🏷️ <b>Kategorien</b> (2)\n"
        "🟢 Eigenes · 0\n"
        "🟣 🧂 Würzmittel · 1\n"
        "📦 Ohne Kategorie: 1 Produkte, 1 offen auf dieser Liste"
    )
    info_id = session.next_id
    await feed(message("/liste", language="de"))
    assert info_id in [d.message_id for d in session.sent(DeleteMessage)]


async def test_sorting_is_recorded_in_the_history(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock)
    mealie_mock.post("/api/foods").respond(201, json={"id": "f-new", "name": "Senf"})
    await feed(message("/list"))
    await feed(message("Senf → Würzmittel"))
    history = [e for e in session.sent(EditMessageText) if "📜" in (e.text or "")]
    assert history and "🏷️ Senf → 🟣 🧂 Würzmittel" in history[-1].text


@pytest.mark.parametrize("harness", [{"label_icons": "none"}], indirect=True)
async def test_label_icons_none_shows_plain_category_names(harness, mealie_mock):
    feed, session = harness
    soap = make_item("i-1", "Soap", label="Eigenes")
    soap["label"]["color"] = "#5cb85c"
    mock_list(mealie_mock, soap, make_item("i-2", "Milk"))
    await feed(message("/list"))
    assert buttons(session.last(SendMessage))[:2] == ["Eigenes (1) ▸", "Other (1) ▸"]


# --- sort picker ------------------------------------------------------------

DAIRY = {"id": "lab-2", "name": "Milchprodukte", "color": "#5bc0de", "groupId": "g"}
MILK_FOOD = {"id": "f-milk", "name": "Milch", "labelId": None, "aliases": [], "substitutions": []}


def other_items():
    return [
        make_item("i-1", "Ketchup", note="Ketchup", position=1),
        make_item(
            "i-2", "Milch", foodId="f-milk", food={"id": "f-milk", "name": "Milch"}, position=2
        ),
    ]


def sort_tap(action, message_id, arg="", language="de", user_id=ALICE):
    return callback(
        SortAction(action=action, arg=arg).pack(),
        message_id=message_id,
        language=language,
        user_id=user_id,
    )


async def open_picker(feed, session, mealie_mock):
    mock_categories(mealie_mock, labels=(LABEL, DAIRY), foods=[MILK_FOOD])
    route = mock_list(mealie_mock, *other_items())
    await feed(message("/liste", language="de"))
    list_id = session.next_id
    start = session.last(SendMessage).reply_markup.inline_keyboard[-2][0]
    assert start.text == "🏷️ Einsortieren (2)"
    await feed(callback(start.callback_data, message_id=list_id))
    return list_id, route


async def test_sort_button_opens_the_picker_in_the_list_message(harness, mealie_mock):
    feed, session = harness
    list_id, _ = await open_picker(feed, session, mealie_mock)
    picker = session.last(EditMessageText)
    assert picker.message_id == list_id
    assert "🏷️ <b>Einsortieren</b> · 1 von 2\n<b>Ketchup</b> · <i>Welche Kategorie?</i>" in (
        picker.text
    )
    assert buttons(picker) == [
        "🔵 🥛 Milchprodukte",
        "🟣 🧂 Würzmittel",
        "➕ Neue Kategorie…",
        "⏭ Überspringen",
        "✕ Zurück zur Liste",
    ]
    # No new message in the chat: only the list itself was sent.
    assert len(session.sent(SendMessage)) == 1


async def test_picking_sorts_one_item_after_the_other_and_ends_with_undo(harness, mealie_mock):
    feed, session = harness
    list_id, route = await open_picker(feed, session, mealie_mock)
    create_food = mealie_mock.post("/api/foods").respond(
        201, json={"id": "f-k", "name": "Ketchup", "labelId": "lab-1"}
    )
    put_ketchup = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    await feed(sort_tap("pick", list_id, "lab-1"))
    assert json.loads(create_food.calls.last.request.content) == {
        "name": "Ketchup",
        "labelId": "lab-1",
    }
    assert json.loads(put_ketchup.calls.last.request.content)["foodId"] == "f-k"
    assert session.last(AnswerCallbackQuery).text == "✅ Ketchup → 🟣 🧂 Würzmittel"
    picker = session.last(EditMessageText)
    assert "2 von 2" in picker.text and "<b>Milch</b>" in picker.text
    # The keyword table suggests the dairy category for milk.
    assert buttons(picker)[0] == "🔵 🥛 Milchprodukte"

    put_food = mealie_mock.put("/api/foods/f-milk").respond(json={})
    put_milk = mealie_mock.put("/api/households/shopping/items/i-2").respond(json={})
    sorted_items = [
        make_item("i-1", "Ketchup", label="Würzmittel"),
        make_item("i-2", "Milch", label="Milchprodukte"),
    ]
    route.side_effect = lambda request: httpx.Response(
        200,
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": sorted_items if put_milk.called else other_items(),
        },
    )
    await feed(sort_tap("pick", list_id, "lab-2"))
    # The whole food goes back, only the label changes.
    assert json.loads(put_food.calls.last.request.content) == {**MILK_FOOD, "labelId": "lab-2"}
    done = session.last(EditMessageText)
    assert "🏷️ <b>Einsortiert</b> (2)" in done.text
    assert done.reply_markup.inline_keyboard[-1][0].text == "↩️ Rückgängig"

    delete_food = mealie_mock.delete("/api/foods/f-k").respond(204)
    await feed(callback(ListAction(action="undo").pack(), message_id=list_id))
    assert delete_food.called
    assert json.loads(put_food.calls.last.request.content)["labelId"] is None
    assert "2 Einträge rückgängig" in session.last(AnswerCallbackQuery).text


async def test_skip_and_back_return_to_the_list(harness, mealie_mock):
    feed, session = harness
    list_id, _ = await open_picker(feed, session, mealie_mock)
    await feed(sort_tap("skip", list_id))
    assert "2 von 2" in session.last(EditMessageText).text
    await feed(sort_tap("back", list_id))
    back = session.last(EditMessageText)
    assert "Einsortieren</b> ·" not in back.text and "Einsortiert" not in back.text
    assert back.reply_markup.inline_keyboard[-1][0].text == "🔄 Aktualisieren"
    # A tap on the closed picker is answered and changes nothing in Mealie.
    await feed(sort_tap("pick", list_id, "lab-1"))
    assert "nicht mehr offen" in session.last(AnswerCallbackQuery).text


KETCHUP_FOOD = {"id": "f-k", "name": "Ketchup", "labelId": None, "aliases": []}


async def open_picker_with_typo(feed, session, mealie_mock):
    """Picker on a note item "Ketschup" while the product "Ketchup" exists."""
    mock_categories(mealie_mock, labels=(LABEL, DAIRY), foods=[MILK_FOOD, KETCHUP_FOOD])
    mock_list(mealie_mock, make_item("i-1", "Ketschup", note="Ketschup", position=1))
    await feed(message("/liste", language="de"))
    list_id = session.next_id
    await feed(sort_tap("start", list_id))
    await feed(sort_tap("pick", list_id, "lab-1"))
    return list_id


async def test_picker_asks_before_creating_a_product_like_an_existing_one(harness, mealie_mock):
    feed, session = harness
    create_food = mealie_mock.post("/api/foods").respond(201, json={})
    list_id = await open_picker_with_typo(feed, session, mealie_mock)
    question = session.last(EditMessageText)
    assert question.message_id == list_id
    assert "❓ <b>Ketschup</b> kenne ich nicht. Meinst du <b>Ketchup</b>?" in question.text
    assert buttons(question) == ["Ja, Ketchup", "➕ Nein, Ketschup anlegen", "↩️ Andere Kategorie"]
    assert not create_food.called
    assert not session.last(AnswerCallbackQuery).text

    put_food = mealie_mock.put("/api/foods/f-k").respond(json={**KETCHUP_FOOD, "labelId": "lab-1"})
    put_item = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    await feed(sort_tap("food_use", list_id, "f-k"))
    assert json.loads(put_food.calls.last.request.content)["labelId"] == "lab-1"
    assert json.loads(put_item.calls.last.request.content)["foodId"] == "f-k"
    assert not create_food.called
    assert session.last(AnswerCallbackQuery).text == "✅ Ketchup → 🟣 🧂 Würzmittel"


async def test_picker_creates_the_typed_product_when_asked_to(harness, mealie_mock):
    feed, session = harness
    list_id = await open_picker_with_typo(feed, session, mealie_mock)
    await feed(sort_tap("food_back", list_id))
    assert "<i>Welche Kategorie?</i>" in session.last(EditMessageText).text
    await feed(sort_tap("pick", list_id, "lab-1"))
    create_food = mealie_mock.post("/api/foods").respond(
        201, json={"id": "f-new", "name": "Ketschup", "labelId": "lab-1"}
    )
    put_item = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    await feed(sort_tap("food_new", list_id))
    assert json.loads(create_food.calls.last.request.content)["name"] == "Ketschup"
    assert json.loads(put_item.calls.last.request.content)["foodId"] == "f-new"
    assert session.last(AnswerCallbackQuery).text == "✅ Ketschup → 🟣 🧂 Würzmittel"


async def test_picker_food_answer_that_no_longer_fits(harness, mealie_mock):
    feed, session = harness
    list_id = await open_picker_with_typo(feed, session, mealie_mock)
    # A product Mealie no longer knows (deleted in the meantime).
    await feed(sort_tap("food_use", list_id, "f-gone"))
    assert session.last(AnswerCallbackQuery).text == "⚠️ Dieses Produkt gibt es nicht mehr"
    assert "<i>Welche Kategorie?</i>" in session.last(EditMessageText).text
    # Without an open question the answer is stale.
    await feed(sort_tap("food_new", list_id))
    assert "nicht mehr offen" in session.last(AnswerCallbackQuery).text


async def test_new_category_is_asked_with_a_reply_prompt(harness, mealie_mock):
    feed, session = harness
    list_id, _ = await open_picker(feed, session, mealie_mock)
    await feed(sort_tap("new", list_id))
    prompt = session.last(SendMessage)
    assert prompt.text.startswith("✏️ Wie soll die neue Kategorie heißen?")
    assert prompt.reply_markup.force_reply and prompt.reply_markup.selective
    prompt_id = session.next_id

    create_label = mealie_mock.post("/api/groups/labels").respond(
        201, json={"id": "lab-3", "name": "Saucen", "color": "#9b7bb8", "groupId": "g"}
    )
    mealie_mock.post("/api/foods").respond(201, json={"id": "f-k", "name": "Ketchup"})
    mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    bulk = mealie_mock.post("/api/households/shopping/items/create-bulk")
    prompt_message = Message(
        message_id=prompt_id,
        date=datetime.now(UTC),
        chat=Chat(id=ALICE, type="private"),
        text=prompt.text,
    )
    await feed(message("Saucen", language="de", message_id=30, reply_to=prompt_message))
    assert json.loads(create_label.calls.last.request.content)["name"] == "Saucen"
    deleted = [d.message_id for d in session.sent(DeleteMessage)]
    assert prompt_id in deleted and 30 in deleted
    picker = session.last(EditMessageText)
    assert picker.message_id == list_id and "2 von 2" in picker.text
    # The reply names the category; it adds no item.
    assert not bulk.called


async def test_new_category_prompt_mentions_the_user_in_a_group(harness, mealie_mock):
    feed, session = harness
    mock_categories(mealie_mock)
    mock_list(mealie_mock, *other_items())
    await feed(message("/list", chat_id=GROUP))
    list_id = session.next_id
    await feed(
        callback(
            SortAction(action="start").pack(), message_id=list_id, chat_id=GROUP, language="en"
        )
    )
    await feed(
        callback(SortAction(action="new").pack(), message_id=list_id, chat_id=GROUP, language="en")
    )
    prompt = session.last(SendMessage)
    assert prompt.text.startswith(f'✏️ <a href="tg://user?id={ALICE}">Bob</a>, what should')


async def test_picker_taps_on_a_changed_list(harness, mealie_mock):
    feed, session = harness
    list_id, route = await open_picker(feed, session, mealie_mock)
    await feed(sort_tap("pick", list_id, "lab-gone"))
    assert session.last(AnswerCallbackQuery).text == "⚠️ Diese Kategorie gibt es nicht mehr"
    # Both items were sorted elsewhere meanwhile: the picker closes.
    route.respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": [make_item("i-1", "K", label="X")]}
    )
    await feed(sort_tap("pick", list_id, "lab-1"))
    assert session.last(AnswerCallbackQuery).text == "Nichts mehr einzusortieren"
    assert "Einsortieren</b> ·" not in session.last(EditMessageText).text
    await feed(sort_tap("start", list_id))
    assert session.last(AnswerCallbackQuery).text == "Nichts mehr einzusortieren"


async def test_picker_tap_while_mealie_is_down(harness, mealie_mock):
    feed, session = harness
    list_id, route = await open_picker(feed, session, mealie_mock)
    route.respond(500)
    await feed(sort_tap("pick", list_id, "lab-1"))
    assert session.last(AnswerCallbackQuery).show_alert


def _reply_to(prompt_id):
    return Message(
        message_id=prompt_id, date=datetime.now(UTC), chat=Chat(id=ALICE, type="private"), text="?"
    )


async def test_category_name_reply_edge_cases(harness, mealie_mock):
    feed, session = harness
    list_id, _ = await open_picker(feed, session, mealie_mock)
    await feed(sort_tap("new", list_id))
    prompt_id = session.next_id
    await feed(message("x" * 41, language="de", message_id=31, reply_to=_reply_to(prompt_id)))
    assert "höchstens 40 Zeichen" in session.last(SendMessage).text
    # Mealie down: the user gets the error, the prompt stays open.
    create = mealie_mock.post("/api/groups/labels").respond(500)
    await feed(message("Saucen", language="de", message_id=32, reply_to=_reply_to(prompt_id)))
    assert "Mealie" in session.last(SendMessage).text and create.call_count == 1
    # Closing the picker deletes the prompt; a late reply is just ignored as a
    # reply and treated as items, so nothing is created as a category.
    await feed(sort_tap("back", list_id))
    assert prompt_id in [d.message_id for d in session.sent(DeleteMessage)]
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": []}
    )
    await feed(message("Saucen", language="de", message_id=33, reply_to=_reply_to(prompt_id)))
    assert create.call_count == 1


# --- folding old history entries ----------------------------------------------


class Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, **delta):
        from datetime import timedelta

        self.now += timedelta(**delta)


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr("mealie_bot.features.shopping.handlers._local_now", clock)
    return clock


async def add_and_show(feed, mealie_mock, text, message_id):
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item(f"n-{message_id}", text)]}
    )
    await feed(message(text, message_id=message_id))


async def test_old_history_entries_fold_into_one_message(harness, mealie_mock, clock):
    feed, session = harness
    mock_list(mealie_mock)
    await feed(message("/list"))
    first_list = session.next_id
    await add_and_show(feed, mealie_mock, "Eggs", 2)  # first list -> entry 1
    clock.advance(hours=1)
    second_list = session.next_id
    await add_and_show(feed, mealie_mock, "Milk", 3)  # second list -> entry 2
    clock.advance(hours=2)
    await add_and_show(feed, mealie_mock, "Bread", 4)
    deleted_before = [d.message_id for d in session.sent(DeleteMessage)]

    clock.advance(hours=24)
    await feed(message("/list", message_id=5))
    # The oldest entry became the fold message, the next one was deleted.
    fold = [e for e in session.sent(EditMessageText) if e.message_id == first_list][-1]
    assert fold.text.startswith("📜 <b>Earlier changes</b>\n<b>Groceries</b>\n")
    assert "Jan 01 10:00</i> ➕ Eggs" in fold.text and "Jan 01 11:00</i> ➕ Milk" in fold.text
    assert fold.reply_markup is None
    deleted = [d.message_id for d in session.sent(DeleteMessage)][len(deleted_before) :]
    assert second_list in deleted and first_list not in deleted

    # Later entries are appended to the same message.
    clock.advance(hours=25)
    await feed(message("/list", message_id=6))
    fold = [e for e in session.sent(EditMessageText) if e.message_id == first_list][-1]
    assert fold.text.count("<b>Groceries</b>") == 1 and "➕ Bread" in fold.text


async def test_a_deleted_fold_message_is_replaced(harness, mealie_mock, clock):
    feed, session = harness
    mock_list(mealie_mock)
    await feed(message("/list"))
    fold_id = session.next_id
    await add_and_show(feed, mealie_mock, "Eggs", 2)
    clock.advance(hours=25)
    await feed(message("/list", message_id=3))
    assert "Earlier changes" in session.last(EditMessageText).text
    entry_id = session.next_id
    await add_and_show(feed, mealie_mock, "Milk", 4)

    # The user deleted the fold message in the meantime.
    original = session.make_request

    async def make_request(bot, method, timeout=None):
        if isinstance(method, EditMessageText) and method.message_id == fold_id:
            raise TelegramBadRequest(method, "Bad Request: message to edit not found")
        return await original(bot, method, timeout)

    session.make_request = make_request
    clock.advance(hours=25)
    await feed(message("/list", message_id=5))
    fold = session.last(EditMessageText)
    while "Earlier changes" not in fold.text:
        fold = session.sent(EditMessageText)[session.sent(EditMessageText).index(fold) - 1]
    # The next entry took its place and keeps the earlier lines.
    assert fold.message_id == entry_id
    assert "➕ Eggs" in fold.text and "➕ Milk" in fold.text


@pytest.mark.parametrize("harness", [{"history_fold_hours": 0}], indirect=True)
async def test_folding_can_be_switched_off(harness, mealie_mock, clock):
    feed, session = harness
    mock_list(mealie_mock)
    await feed(message("/list"))
    await add_and_show(feed, mealie_mock, "Eggs", 2)
    clock.advance(hours=30)
    await feed(message("/list", message_id=3))
    assert not [e for e in session.sent(EditMessageText) if "Earlier changes" in e.text]


async def test_entries_fold_before_telegram_stops_deleting(harness, mealie_mock, clock):
    feed, session = harness
    mock_list(mealie_mock)
    await feed(message("/list"))
    first_list = session.next_id
    # The list message lives for 46 hours before it becomes a history entry.
    clock.advance(hours=46)
    await add_and_show(feed, mealie_mock, "Eggs", 2)
    clock.advance(hours=1)
    await feed(message("/list", message_id=3))
    fold = [e for e in session.sent(EditMessageText) if e.message_id == first_list][-1]
    assert "Earlier changes" in fold.text


async def test_fold_loop_runs_without_activity(harness, mealie_mock, clock, monkeypatch):
    import mealie_bot.features.shopping.handlers as handlers

    monkeypatch.setattr(handlers, "FOLD_INTERVAL_SECONDS", 0.01)
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings(), client)
    mock_list(mealie_mock)
    await dispatcher.feed_update(bot, message("/list"))
    first_list = session.next_id
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "Eggs")]}
    )
    await dispatcher.feed_update(bot, message("Eggs", message_id=2))
    clock.advance(hours=25)
    await dispatcher.emit_startup(bot=bot)
    try:
        for _ in range(100):
            if any(
                isinstance(c, EditMessageText)
                and "Earlier" in c.text
                and c.message_id == first_list
                for c in session.calls
            ):
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("the fold loop did not run")
    finally:
        await dispatcher.emit_shutdown(bot=bot)
        await client.aclose()
