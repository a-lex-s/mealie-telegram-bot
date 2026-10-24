"""Feature modules. Each one contributes a router and its menu commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from aiogram import Router

from mealie_bot.config import Settings
from mealie_bot.mealie import MealieClient


class TransientMessages:
    """Short bot replies per chat that are deleted once the chat's main message
    (the shopping list) is shown again. Shared by the core commands and the
    features, so a ``/version`` answer goes like a feature's own info replies."""

    def __init__(self) -> None:
        self._ids: dict[int, list[int]] = {}

    def add(self, chat_id: int, message_id: int) -> None:
        self._ids.setdefault(chat_id, []).append(message_id)

    def take(self, chat_id: int) -> list[int]:
        return self._ids.pop(chat_id, [])


@dataclass(frozen=True)
class FeatureContext:
    settings: Settings
    mealie: MealieClient
    transient: TransientMessages = field(default_factory=TransientMessages)


@dataclass(frozen=True)
class Feature:
    name: str
    # Command keys from the i18n catalog shown in the Telegram menu.
    commands: tuple[str, ...]
    # Catalog keys of this feature's sections in /start and /help.
    start_key: str
    help_key: str
    build_router: Callable[[FeatureContext], Router]


def available_features() -> dict[str, Feature]:
    from mealie_bot.features import shopping

    return {feature.name: feature for feature in (shopping.FEATURE,)}
