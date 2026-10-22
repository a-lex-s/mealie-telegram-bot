"""Wire settings, Mealie client, middlewares and feature routers together."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
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

    def help_text(tr: Translator) -> str:
        if not features:
            return tr("help.no_features")
        return "\n\n".join(tr(feature.help_key, **_command_args(tr)) for feature in features)

    @router.message(CommandStart())
    async def cmd_start(message: Message, tr: Translator) -> None:
        if features:
            await message.answer(tr("start", **_command_args(tr)))
        else:
            await message.answer(tr("help.no_features"))

    @router.message(Command(*command_names("help")))
    async def cmd_help(message: Message, tr: Translator) -> None:
        await message.answer(help_text(tr))

    return router


def build_dispatcher(settings: Settings, mealie: MealieClient) -> Dispatcher:
    dispatcher = Dispatcher()
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(AccessMiddleware(settings.allowed_user_ids))
        observer.middleware(I18nMiddleware(settings.bot_language))

    features = enabled_features(settings)
    dispatcher.include_router(build_core_router(features))
    context = FeatureContext(settings=settings, mealie=mealie)
    for feature in features:
        dispatcher.include_router(feature.build_router(context))
        log.info("Feature enabled: %s", feature.name)
    return dispatcher


def menu_commands(features: list[Feature], language: str) -> list[BotCommand]:
    keys = ["help", *(key for feature in features for key in feature.commands)]
    catalog = CATALOGS[language].COMMANDS
    return [BotCommand(command=catalog[key][0], description=catalog[key][1]) for key in keys]


async def register_commands(bot: Bot, settings: Settings) -> None:
    """Publish the command menu: one per catalog language, or only the forced one."""
    features = enabled_features(settings)
    if settings.bot_language:
        await bot.set_my_commands(
            menu_commands(features, settings.bot_language), scope=BotCommandScopeDefault()
        )
        return
    await bot.set_my_commands(
        menu_commands(features, DEFAULT_LANGUAGE), scope=BotCommandScopeDefault()
    )
    for language in CATALOGS:
        if language != DEFAULT_LANGUAGE:
            await bot.set_my_commands(
                menu_commands(features, language),
                scope=BotCommandScopeDefault(),
                language_code=language,
            )
