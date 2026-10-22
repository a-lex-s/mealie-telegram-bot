"""Configuration from environment variables.

Every variable can alternatively be provided as a file by setting
``<NAME>_FILE`` to its path (Docker/Compose secrets). Setting both is an error.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from mealie_bot.i18n import SUPPORTED_LANGUAGES
from mealie_bot.i18n.labels import parse_label_emoji

# Feature modules that exist in this build, with their default state.
KNOWN_FEATURES: dict[str, bool] = {"shopping": True}

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """Raised for missing or invalid configuration. Never contains secret values."""


def _read(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    file_path = env.get(f"{name}_FILE")
    if value and file_path:
        raise ConfigError(f"Set either {name} or {name}_FILE, not both")
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip() or None
        except OSError as exc:
            raise ConfigError(f"Cannot read {name}_FILE: {exc.strerror}") from None
    if value is None:
        return None
    return value.strip() or None


def _required(env: Mapping[str, str], name: str) -> str:
    value = _read(env, name)
    if value is None:
        raise ConfigError(f"{name} (or {name}_FILE) is required")
    return value


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = _read(env, name)
    if value is None:
        return default
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false)")


def _user_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise ConfigError(
                "ALLOWED_USER_IDS must be a comma-separated list of integers"
            ) from None
    if not ids:
        raise ConfigError("ALLOWED_USER_IDS must contain at least one Telegram user ID")
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    telegram_token: str = field(repr=False)
    mealie_url: str
    mealie_token: str = field(repr=False)
    allowed_user_ids: frozenset[int]
    bot_language: str | None = None
    shopping_list: str | None = None
    features: frozenset[str] = frozenset({"shopping"})
    delete_commands: bool = True
    delete_item_messages: bool = True
    # Exact label name (case-folded) -> emoji, from LABEL_EMOJI; keywords cover the rest.
    label_emoji: Mapping[str, str] = field(default_factory=dict)
    log_level: str = "INFO"
    http_timeout: float = 10.0

    @property
    def secrets(self) -> tuple[str, ...]:
        return (self.telegram_token, self.mealie_token)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        mealie_url = (_read(env, "MEALIE_URL") or "http://mealie:9000").rstrip("/")
        parsed = urlparse(mealie_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("MEALIE_URL must be an http(s) URL")

        language = _read(env, "BOT_LANGUAGE")
        if language is not None:
            language = language.lower()
            if language not in SUPPORTED_LANGUAGES:
                supported = ", ".join(SUPPORTED_LANGUAGES)
                raise ConfigError(f"BOT_LANGUAGE must be one of: {supported}")

        features = frozenset(
            name
            for name, default in KNOWN_FEATURES.items()
            if _bool(env, f"FEATURE_{name.upper()}", default)
        )

        log_level = (_read(env, "LOG_LEVEL") or "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigError("LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")

        timeout_raw = _read(env, "MEALIE_TIMEOUT") or "10"
        try:
            timeout = float(timeout_raw)
        except ValueError:
            raise ConfigError("MEALIE_TIMEOUT must be a number of seconds") from None
        if timeout <= 0:
            raise ConfigError("MEALIE_TIMEOUT must be positive")

        return cls(
            telegram_token=_required(env, "TELEGRAM_BOT_TOKEN"),
            mealie_url=mealie_url,
            mealie_token=_required(env, "MEALIE_API_TOKEN"),
            allowed_user_ids=_user_ids(_required(env, "ALLOWED_USER_IDS")),
            bot_language=language,
            shopping_list=_read(env, "SHOPPING_LIST"),
            features=features,
            delete_commands=_bool(env, "DELETE_COMMANDS", True),
            delete_item_messages=_bool(env, "DELETE_ITEM_MESSAGES", True),
            label_emoji=parse_label_emoji(_read(env, "LABEL_EMOJI")),
            log_level=log_level,
            http_timeout=timeout,
        )
