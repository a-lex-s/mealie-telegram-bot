"""Feature modules. Each one contributes a router and its menu commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiogram import Router

from mealie_bot.config import Settings
from mealie_bot.mealie import MealieClient


@dataclass(frozen=True)
class FeatureContext:
    settings: Settings
    mealie: MealieClient


@dataclass(frozen=True)
class Feature:
    name: str
    # Command keys from the i18n catalog shown in the Telegram menu.
    commands: tuple[str, ...]
    # Catalog key of this feature's section in /help.
    help_key: str
    build_router: Callable[[FeatureContext], Router]


def available_features() -> dict[str, Feature]:
    from mealie_bot.features import shopping

    return {feature.name: feature for feature in (shopping.FEATURE,)}
