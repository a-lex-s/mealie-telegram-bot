"""Entry point: configuration errors exit with 2, crashes never leak secrets,
start-up survives a Mealie outage."""

import logging
import os

import httpx
import pytest
from aiogram import Dispatcher

from mealie_bot import __main__ as entry
from mealie_bot.config import Settings
from tests.conftest import BASE_URL, TOKEN

ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:s3cr3t-telegram",
    "MEALIE_API_TOKEN": "s3cr3t-mealie",
    "ALLOWED_USER_IDS": "1",
}


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    logging.getLogger().handlers[:] = []


def test_config_error_exits_with_2(monkeypatch, capsys):
    monkeypatch.setattr(os, "environ", {"ALLOWED_USER_IDS": "1"})
    assert entry.main() == 2
    assert "Configuration error" in capsys.readouterr().err


def test_missing_configuration_exits_with_2(monkeypatch, capsys):
    monkeypatch.setattr("os.environ", {})
    assert entry.main() == 2
    err = capsys.readouterr().err
    assert "TELEGRAM_BOT_TOKEN" in err and "placeholder" not in err


def test_crash_is_logged_through_redacting_filter(monkeypatch, capsys):
    monkeypatch.setattr(os, "environ", dict(ENV))

    async def crash(settings):
        raise RuntimeError("connect failed for 123456:s3cr3t-telegram with s3cr3t-mealie")

    monkeypatch.setattr(entry, "run", crash)
    assert entry.main() == 1
    captured = capsys.readouterr()
    assert "s3cr3t" not in captured.out + captured.err
    assert "Bot stopped with an error" in captured.out
    assert "RuntimeError: connect failed for *** with ***" in captured.out


async def test_run_starts_polling_even_when_mealie_is_down(monkeypatch, mealie_mock, caplog):
    mealie_mock.get("/api/app/about").mock(side_effect=httpx.ConnectError("down"))
    started = []

    async def fake_polling(self, bot, **kwargs):
        started.append(kwargs.get("allowed_updates"))

    async def fake_register(bot, settings):
        started.append("commands")

    monkeypatch.setattr(Dispatcher, "start_polling", fake_polling)
    monkeypatch.setattr(entry, "register_commands", fake_register)
    settings = Settings(
        telegram_token="123456:placeholder",
        mealie_url=BASE_URL,
        mealie_token=TOKEN,
        allowed_user_ids=frozenset({1}),
    )
    with caplog.at_level(logging.WARNING, logger="mealie_bot"):
        await entry.run(settings)
    assert started[0] == "commands" and set(started[1]) == {"message", "callback_query"}
    assert "Mealie check failed" in caplog.text and TOKEN not in caplog.text


@pytest.mark.parametrize("version", ["3.29.0"])
async def test_run_logs_the_mealie_version(monkeypatch, mealie_mock, caplog, version):
    mealie_mock.get("/api/app/about").respond(json={"version": version})
    mealie_mock.get("/api/users/self").respond(json={"id": "bot"})

    async def fake_polling(self, bot, **kwargs):
        pass

    async def fake_register(bot, settings):
        pass

    monkeypatch.setattr(Dispatcher, "start_polling", fake_polling)
    monkeypatch.setattr(entry, "register_commands", fake_register)
    settings = Settings(
        telegram_token="123456:placeholder",
        mealie_url=BASE_URL,
        mealie_token=TOKEN,
        allowed_user_ids=frozenset({1}),
    )
    with caplog.at_level(logging.INFO, logger="mealie_bot"):
        await entry.run(settings)
    assert f"Connected to Mealie {version}" in caplog.text
