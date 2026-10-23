import re

import pytest

from mealie_bot.i18n import (
    CATALOGS,
    DEFAULT_LANGUAGE,
    Translator,
    command_names,
    resolve_language,
    unit_synonyms,
)

REFERENCE = CATALOGS[DEFAULT_LANGUAGE]
OTHERS = [lang for lang in CATALOGS if lang != DEFAULT_LANGUAGE]
PLACEHOLDER = re.compile(r"{(\w+)}")


@pytest.mark.parametrize("language", OTHERS)
def test_catalog_is_complete(language):
    catalog = CATALOGS[language]
    assert set(catalog.MESSAGES) == set(REFERENCE.MESSAGES)
    assert set(catalog.COMMANDS) == set(REFERENCE.COMMANDS)
    assert set(catalog.UNITS) == set(REFERENCE.UNITS)


@pytest.mark.parametrize("language", OTHERS)
def test_placeholders_match(language):
    for key, text in REFERENCE.MESSAGES.items():
        expected = set(PLACEHOLDER.findall(text))
        assert set(PLACEHOLDER.findall(CATALOGS[language].MESSAGES[key])) == expected, key


@pytest.mark.parametrize("language", list(CATALOGS))
def test_command_names_are_valid_for_telegram(language):
    for name, description in CATALOGS[language].COMMANDS.values():
        assert re.fullmatch(r"[a-z0-9_]{1,32}", name)
        assert 1 <= len(description) <= 256


@pytest.mark.parametrize(
    ("code", "override", "expected"),
    [
        ("de", None, "de"),
        ("de-AT", None, "de"),
        ("en-US", None, "en"),
        ("fr", None, "en"),
        (None, None, "en"),
        ("en", "de", "de"),
        ("de", "en", "en"),
    ],
)
def test_resolve_language(code, override, expected):
    assert resolve_language(code, override) == expected


def test_translator_formats():
    assert "Alice" in Translator("de")("shopping.toast_checked", item="Alice")
    assert Translator("de")("shopping.cleared", count=1) == "🧹 1 Eintrag entfernt"
    assert Translator("de")("shopping.cleared", count=2) == "🧹 2 Einträge entfernt"
    assert Translator("en")("shopping.more", count=1) == "… and 1 more (open Mealie to see all)"
    # A ".one" variant must exist in every language that has the base key.
    for language in ("de", "en"):
        catalog = Translator(language)
        assert all(
            key[: -len(".one")] in catalog._messages
            for key in catalog._messages
            if key.endswith(".one")
        )


def test_command_names_cover_all_languages():
    assert set(command_names("list")) == {"list", "liste"}


def test_unit_synonyms_merge_languages():
    synonyms = unit_synonyms()
    assert {"l", "liter", "litre"} <= synonyms["l"]
    assert "stück" in synonyms["piece"]
