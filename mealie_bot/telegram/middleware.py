"""Access control and per-user language for every incoming update."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from mealie_bot.i18n import Translator, resolve_language

log = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class AccessMiddleware(BaseMiddleware):
    """Drops every update that does not come from an allowed Telegram user."""

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self._allowed = allowed_user_ids

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.id not in self._allowed:
            log.warning("Ignoring update from unauthorized user id %s", user.id if user else None)
            return None
        return await handler(event, data)


class I18nMiddleware(BaseMiddleware):
    """Provides a ``tr`` translator matching the user's Telegram language."""

    def __init__(self, override: str | None) -> None:
        self._override = override

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        language = resolve_language(user.language_code if user else None, self._override)
        data["tr"] = Translator(language)
        return await handler(event, data)
