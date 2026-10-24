"""Entry point: ``python -m mealie_bot``."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from mealie_bot import __version__, revision
from mealie_bot.config import ConfigError, Settings
from mealie_bot.logging_setup import setup_logging
from mealie_bot.mealie import MealieClient, MealieError
from mealie_bot.telegram.app import build_dispatcher, register_commands

log = logging.getLogger("mealie_bot")


async def run(settings: Settings) -> None:
    mealie = MealieClient(settings.mealie_url, settings.mealie_token, settings.http_timeout)
    bot = Bot(settings.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        try:
            info = await mealie.get_app_info()
            await mealie.get_self()
            log.info("Connected to Mealie %s", info.get("version", "?"))
        except MealieError as exc:
            # Keep running: Mealie may still be starting. Requests are retried per message.
            log.warning("Mealie check failed: %s", exc)
        dispatcher = build_dispatcher(settings, mealie)
        await register_commands(bot, settings)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await mealie.aclose()
        await bot.session.close()


def main() -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    setup_logging(settings.log_level, settings.secrets)
    commit = revision()
    log.info("Starting mealie-telegram-bot %s%s", __version__, f" ({commit})" if commit else "")
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Through the logger, so the redacting filter sees the traceback; an
        # uncaught exception would be printed to stderr unfiltered.
        log.exception("Bot stopped with an error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
