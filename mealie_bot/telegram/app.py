"""Wire settings, Mealie client, middlewares and feature routers together."""

from __future__ import annotations

import logging
from collections.abc import Callable

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, BotCommandScopeDefault, Message

from mealie_bot.config import Settings
from mealie_bot.features import Feature, FeatureContext, available_features
from mealie_bot.i18n import CATALOGS, DEFAULT_LANGUAGE, Translator, command_names
from mealie_bot.mealie import MealieClient
from mealie_bot.telegram.middleware import AccessMiddleware, I18nMiddleware

log = logging.getLogger(__name__)


def enabled_features(settings: Settings) -> list[Feature]:
    features = available_features()
    return [features[name] for name in sorted(settings.features) if name in features]


def _command_args(tr: Translator) -> dict[str, str]:
    return {key: tr.command(key) for key in CATALOGS[tr.language].COMMANDS}


def build_core_router(features: list[Feature]) -> Router:
    router = Router(name="core")

    def sections(tr: Translator, intro_key: str, key: Callable[[Feature], str]) -> str:
        """The intro followed by one section per enabled feature."""
        if not features:
            return tr("help.no_features")
        args = _command_args(tr)
        return "\n\n".join([tr(intro_key, **args), *(tr(key(f), **args) for f in features)])

    @router.message(CommandStart())
    async def cmd_start(message: Message, tr: Translator) -> None:
        await message.answer(sections(tr, "start", lambda f: f.start_key))

    @router.message(Command(*command_names("help")))
    async def cmd_help(message: Message, tr: Translator) -> None:
        await message.answer(sections(tr, "help", lambda f: f.help_key))

    return router


def build_fallback_router() -> Router:
    """Answers whatever no feature handled: unknown commands and non-text messages."""
    router = Router(name="fallback")

    @router.message(F.text)
    async def unknown_command(message: Message, tr: Translator) -> None:
        await message.answer(tr("error.unknown_command"))

    @router.message()
    async def not_text(message: Message, tr: Translator) -> None:
        # Photos, voice messages, stickers: say what the bot can work with.
        await message.answer(tr("error.only_text"))

    return router


def build_dispatcher(settings: Settings, mealie: MealieClient) -> Dispatcher:
    dispatcher = Dispatcher()
    # Access control on the update observer covers every update type, not only the
    # ones that currently have handlers.
    dispatcher.update.outer_middleware(AccessMiddleware(settings.allowed_user_ids))
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.middleware(I18nMiddleware(settings.bot_language))

    features = enabled_features(settings)
    dispatcher.include_router(build_core_router(features))
    context = FeatureContext(settings=settings, mealie=mealie)
    for feature in features:
        dispatcher.include_router(feature.build_router(context))
        log.info("Feature enabled: %s", feature.name)
    dispatcher.include_router(build_fallback_router())
    return dispatcher


def menu_commands(features: list[Feature], language: str) -> list[BotCommand]:
    # Most used first: the features' own commands, then help.
    keys = [*(key for feature in features for key in feature.commands), "help"]
    catalog = CATALOGS[language].COMMANDS
    return [BotCommand(command=catalog[key][0], description=catalog[key][1]) for key in keys]


async def _publish(bot: Bot, features: list[Feature], language: str, code: str | None) -> None:
    tr = Translator(language)
    await bot.set_my_commands(
        menu_commands(features, language), scope=BotCommandScopeDefault(), language_code=code
    )
    await bot.set_my_description(tr("bot.description"), language_code=code)
    await bot.set_my_short_description(tr("bot.short_description"), language_code=code)


async def register_commands(bot: Bot, settings: Settings) -> None:
    """Publish menu commands and bot description per catalog language (or the forced one)."""
    features = enabled_features(settings)
    if settings.bot_language:
        await _publish(bot, features, settings.bot_language, None)
        return
    await _publish(bot, features, DEFAULT_LANGUAGE, None)
    for language in CATALOGS:
        if language != DEFAULT_LANGUAGE:
            await _publish(bot, features, language, language)
