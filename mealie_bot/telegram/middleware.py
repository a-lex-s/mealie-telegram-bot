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


# Unknown user IDs are logged once per process; the set is capped so that a flood
# of strangers cannot grow memory without bound.
MAX_REPORTED_STRANGERS = 1000


class AccessMiddleware(BaseMiddleware):
    """Drops every update that does not come from an allowed Telegram user.

    Registered on the dispatcher's ``update`` observer, so it covers every
    update type, including ones no feature handles yet.
    """

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self._allowed = allowed_user_ids
        self._reported: set[int | None] = set()

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.id not in self._allowed:
            self._report(user.id if user else None)
            return None
        return await handler(event, data)

    def _report(self, user_id: int | None) -> None:
        """Log an unknown user once, so strangers cannot flood the log."""
        if user_id in self._reported:
            return
        if len(self._reported) >= MAX_REPORTED_STRANGERS:
            self._reported.clear()
        self._reported.add(user_id)
        log.warning("Ignoring updates from unauthorized user id %s", user_id)


class I18nMiddleware(BaseMiddleware):
    """Provides a ``tr`` translator matching the user's Telegram language."""

    def __init__(self, override: str | None) -> None:
        self._override = override

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        language = resolve_language(user.language_code if user else None, self._override)
        data["tr"] = Translator(language)
        return await handler(event, data)
