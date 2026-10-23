"""Entry point: configuration errors and crashes never leak secrets."""

import logging
import os

import pytest

from mealie_bot import __main__ as entry

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
