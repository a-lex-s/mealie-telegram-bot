"""End-to-end handler tests: Telegram updates in, Mealie requests and bot replies out."""

import json
from datetime import UTC, datetime

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from mealie_bot.config import Settings
from mealie_bot.features.shopping.render import VIEW_OPEN, ItemAction
from mealie_bot.mealie import MealieClient
from mealie_bot.telegram.app import build_dispatcher
from tests.conftest import BASE_URL, LIST_ID, TOKEN, make_item

ALICE = 1001
BOB = 1002
STRANGER = 9999


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage | EditMessageText):
            return Message(
                message_id=len(self.calls),
                date=datetime.now(UTC),
                chat=Chat(id=1, type="private"),
                text=method.text,
            )
        return True

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    def sent(self, kind):
        return [c for c in self.calls if isinstance(c, kind)]


@pytest.fixture
async def harness(mealie_mock):
    settings = Settings(
        telegram_token="123456:placeholder",
        mealie_url=BASE_URL,
        mealie_token=TOKEN,
        allowed_user_ids=frozenset({ALICE, BOB}),
    )
    client = MealieClient(BASE_URL, TOKEN)
    session = RecordingSession()
    bot = Bot("123456:placeholder", session=session)
    dispatcher = build_dispatcher(settings, client)
    mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    mealie_mock.get("/api/units").respond(json={"items": []})
    mealie_mock.get("/api/foods").respond(json={"items": []})

    async def feed(update):
        await dispatcher.feed_update(bot, update)

    yield feed, session
    await client.aclose()


def message(text, user_id=ALICE, language="en"):
    return Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Alice", language_code=language),
            text=text,
        ),
    )


def callback(data, user_id=ALICE):
    user = User(id=user_id, is_bot=False, first_name="Bob", language_code="de")
    return Update(
        update_id=2,
        callback_query=CallbackQuery(
            id="cb",
            from_user=user,
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=5,
                date=datetime.now(UTC),
                chat=Chat(id=user_id, type="private"),
                from_user=user,
                text="old",
            ),
        ),
    )


async def test_text_adds_items(harness, mealie_mock):
    feed, session = harness
    route = mealie_mock.post("/api/households/shopping/items/create-bulk").respond(201, json={})
    await feed(message("2 l milk, eggs"))
    body = json.loads(route.calls.last.request.content)
    assert [(i["quantity"], i["note"]) for i in body] == [(2, "l milk"), (1, "eggs")]
    reply = session.sent(SendMessage)[-1]
    assert "Groceries" in reply.text and "eggs" in reply.text


async def test_stranger_is_ignored(harness, mealie_mock):
    feed, session = harness
    route = mealie_mock.post("/api/households/shopping/items/create-bulk")
    await feed(message("milk", user_id=STRANGER))
    assert not route.called
    assert session.calls == []


async def test_list_command_in_german(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": [make_item("i-1", "Milch")]}
    )
    await feed(message("/liste", user_id=BOB, language="de"))
    reply = session.sent(SendMessage)[-1]
    assert "1 offen" in reply.text
    assert reply.reply_markup.inline_keyboard[0][0].text == "⬜ Milch"


async def test_tap_checks_item_and_refreshes(harness, mealie_mock):
    feed, session = harness
    item = make_item("i-1", "Milch")
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=item)
    put = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": [{**item, "checked": True}]}
    )
    await feed(callback(ItemAction(action="check", item_id="i-1", view=VIEW_OPEN).pack()))
    assert json.loads(put.calls.last.request.content)["checked"] is True
    assert session.sent(AnswerCallbackQuery)
    assert "Nichts zu kaufen" in session.sent(EditMessageText)[-1].text


async def test_mealie_down_reports_error(harness, mealie_mock):
    feed, session = harness
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(502)
    await feed(message("/list"))
    assert "not reachable" in session.sent(SendMessage)[-1].text
