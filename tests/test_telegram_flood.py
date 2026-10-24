"""Telegram flood control and unreachable chats (issue #84)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from mealie_bot.features.shopping.handlers import ShoppingUI, _flood_safe
from mealie_bot.features.shopping.state import ListState


def _ui() -> ShoppingUI:
    return ShoppingUI(MagicMock(), delete_commands=False, delete_item_messages=False)


def _retry_after(seconds: int) -> TelegramRetryAfter:
    return TelegramRetryAfter(MagicMock(), "Too Many Requests", seconds)


@pytest.mark.asyncio
async def test_flood_safe_waits_once_and_returns_the_result(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("mealie_bot.features.shopping.handlers.asyncio.sleep", fake_sleep)
    calls = 0

    async def call():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _retry_after(3)
        return "sent"

    assert await _flood_safe(call) == "sent"
    assert calls == 2
    assert slept == [3]


@pytest.mark.asyncio
async def test_flood_safe_gives_up_after_the_second_refusal(monkeypatch, caplog):
    monkeypatch.setattr(
        "mealie_bot.features.shopping.handlers.asyncio.sleep", AsyncMock(return_value=None)
    )

    async def call():
        raise _retry_after(1)

    with caplog.at_level("WARNING"):
        assert await _flood_safe(call) is None
    assert any("rate limits" in record.message for record in caplog.records)
    assert not any(record.levelname == "ERROR" for record in caplog.records)


@pytest.mark.asyncio
async def test_unreachable_chat_is_forgotten_and_never_retried(monkeypatch):
    ui = _ui()
    ui.render = AsyncMock(return_value=("list text", None, "list"))
    origin = ui.chat(1)
    origin.states[10] = ListState(list_id="list-1")
    origin.live_message_id = 10
    other = ui.chat(2)
    other.states[20] = ListState(list_id="list-1")
    other.language = "en"
    other.live_message_id = 20

    calls: list[int] = []

    async def forbidden(bot, chat_id, message_id, text, markup):
        calls.append(chat_id)
        raise TelegramForbiddenError(MagicMock(), "Forbidden: bot was blocked by the user")

    monkeypatch.setattr("mealie_bot.features.shopping.handlers._edit", forbidden)
    monkeypatch.setattr(
        "mealie_bot.features.shopping.handlers.asyncio.sleep", AsyncMock(return_value=None)
    )

    await ui.sync_others(MagicMock(), 1)

    assert calls == [2]
    assert other.live_message_id is None, "a blocked chat must not be tried again"
    assert origin.live_message_id == 10, "the origin chat keeps its message"


@pytest.mark.asyncio
async def test_sync_pauses_between_chats(monkeypatch):
    ui = _ui()
    ui.render = AsyncMock(return_value=("list text", None, "list"))
    origin = ui.chat(1)
    origin.states[10] = ListState(list_id="list-1")
    origin.live_message_id = 10
    for chat_id in (2, 3):
        chat = ui.chat(chat_id)
        chat.states[chat_id * 10] = ListState(list_id="list-1")
        chat.language = "en"
        chat.live_message_id = chat_id * 10

    monkeypatch.setattr("mealie_bot.features.shopping.handlers._edit", AsyncMock(return_value=True))
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("mealie_bot.features.shopping.handlers.asyncio.sleep", fake_sleep)

    await ui.sync_others(MagicMock(), 1)

    assert slept == [0.2, 0.2], "one pause per synced chat"
