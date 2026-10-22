"""String catalog and language selection.

Each language module (``en``, ``de``, ...) defines three dicts:

* ``MESSAGES``: user-facing texts, formatted with ``str.format``.
* ``COMMANDS``: command key -> (command name, menu description).
* ``UNITS``: canonical unit key -> spellings users may type.

English is the reference catalog; every other language must define the same keys.
"""

from __future__ import annotations

from types import ModuleType

from mealie_bot.i18n import de, en

DEFAULT_LANGUAGE = "en"
CATALOGS: dict[str, ModuleType] = {"en": en, "de": de}
SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(CATALOGS)


def resolve_language(language_code: str | None, override: str | None = None) -> str:
    """Pick the catalog for a user: explicit override, then Telegram's language_code."""
    if override in CATALOGS:
        return override
    if language_code:
        base = language_code.split("-")[0].lower()
        if base in CATALOGS:
            return base
    return DEFAULT_LANGUAGE


class Translator:
    def __init__(self, language: str) -> None:
        self.language = language if language in CATALOGS else DEFAULT_LANGUAGE
        self._messages: dict[str, str] = CATALOGS[self.language].MESSAGES

    def __call__(self, key: str, **kwargs: object) -> str:
        template = self._messages.get(key) or en.MESSAGES[key]
        return template.format(**kwargs) if kwargs else template

    def command(self, key: str) -> str:
        return CATALOGS[self.language].COMMANDS[key][0]


def command_names(key: str) -> tuple[str, ...]:
    """All spellings of a command across languages, so /list works for everyone."""
    names = {catalog.COMMANDS[key][0] for catalog in CATALOGS.values()}
    return tuple(sorted(names))


def unit_synonyms() -> dict[str, frozenset[str]]:
    """Canonical unit key -> every spelling from every catalog, case-folded."""
    merged: dict[str, set[str]] = {}
    for catalog in CATALOGS.values():
        for key, spellings in catalog.UNITS.items():
            merged.setdefault(key, set()).update(s.casefold() for s in spellings)
    return {key: frozenset(values) for key, values in merged.items()}
