import logging
from types import SimpleNamespace

from aiogram.types import BotCommand

from mealie_bot.config import Settings
from mealie_bot.mealie import MealieClient
from mealie_bot.telegram.app import build_dispatcher, enabled_features, menu_commands
from mealie_bot.telegram.middleware import (
    MAX_REPORTED_STRANGERS,
    AccessMiddleware,
    I18nMiddleware,
)
from tests.conftest import BASE_URL


async def _call(middleware, user):
    seen = {}

    async def handler(event, data):
        seen.update(data)
        return "handled"

    result = await middleware(handler, object(), {"event_from_user": user})
    return result, seen


async def test_access_allows_listed_user():
    result, _ = await _call(AccessMiddleware(frozenset({1})), SimpleNamespace(id=1))
    assert result == "handled"


async def test_access_drops_others():
    assert (await _call(AccessMiddleware(frozenset({1})), SimpleNamespace(id=2)))[0] is None
    assert (await _call(AccessMiddleware(frozenset({1})), None))[0] is None


async def test_access_logs_each_stranger_once(caplog):
    middleware = AccessMiddleware(frozenset({1}))
    with caplog.at_level(logging.WARNING, logger="mealie_bot.telegram.middleware"):
        for user_id in (2, 2, 2, 3, 2):
            await _call(middleware, SimpleNamespace(id=user_id))
    reported = [r.getMessage() for r in caplog.records]
    assert reported == [
        "Ignoring updates from unauthorized user id 2",
        "Ignoring updates from unauthorized user id 3",
    ]


async def test_access_reported_set_is_bounded():
    middleware = AccessMiddleware(frozenset({1}))
    for user_id in range(2, MAX_REPORTED_STRANGERS + 10):
        await _call(middleware, SimpleNamespace(id=user_id))
    assert len(middleware._reported) <= MAX_REPORTED_STRANGERS


async def test_i18n_uses_language_code_and_override():
    _, data = await _call(I18nMiddleware(None), SimpleNamespace(language_code="de"))
    assert data["tr"].language == "de"
    _, data = await _call(I18nMiddleware("en"), SimpleNamespace(language_code="de"))
    assert data["tr"].language == "en"


def _settings(**overrides):
    values = dict(
        telegram_token="t",
        mealie_url=BASE_URL,
        mealie_token="m",
        allowed_user_ids=frozenset({1}),
    )
    values.update(overrides)
    return Settings(**values)


def test_feature_toggle():
    assert [f.name for f in enabled_features(_settings())] == ["shopping"]
    assert enabled_features(_settings(features=frozenset())) == []


async def test_dispatcher_builds_with_and_without_features():
    client = MealieClient(BASE_URL, "m")
    try:
        routers = [r.name for r in build_dispatcher(_settings(), client).sub_routers]
        assert routers == ["core", "shopping", "fallback"]
        without = build_dispatcher(_settings(features=frozenset()), client).sub_routers
        assert [r.name for r in without] == ["core", "fallback"]
    finally:
        await client.aclose()


def test_menu_commands_localized():
    features = enabled_features(_settings())
    assert BotCommand(command="liste", description="Liste anzeigen") in menu_commands(
        features, "de"
    )
    assert [c.command for c in menu_commands(features, "en")] == [
        "list",
        "clear",
        "lists",
        "help",
    ]
