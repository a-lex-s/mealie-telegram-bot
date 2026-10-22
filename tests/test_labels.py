import pytest

from mealie_bot.i18n.labels import (
    DEFAULT_LABEL_EMOJI,
    FALLBACK_EMOJI,
    label_emoji,
    parse_label_emoji,
)


@pytest.mark.parametrize(
    ("name", "emoji"),
    [
        ("Obst & Gemüse", "🍎"),
        ("Fruit & vegetables", "🍎"),
        ("Milchprodukte", "🥛"),
        ("Dairy", "🥛"),
        ("Würzmittel", "🧂"),
        ("Spices", "🧂"),
        ("Tiefkühl", "🧊"),
        ("Drogerie", "🧴"),
        ("Personal Care", "🧴"),
        ("Haushalt", "🧻"),
        ("Getränke", "🥤"),
        ("Bier & Wein", "🍷"),
        ("Sonstiges", FALLBACK_EMOJI),
        ("Other", FALLBACK_EMOJI),
        ("", FALLBACK_EMOJI),
        (None, FALLBACK_EMOJI),
    ],
)
def test_keyword_matching(name, emoji):
    assert label_emoji(name) == emoji


def test_override_beats_keywords():
    assert label_emoji("Würzmittel", {"würzmittel": "🌶️"}) == "🌶️"
    assert label_emoji("Tiere", {"tiere": "🐾"}) == "🐾"
    assert label_emoji("Spices", {"würzmittel": "🌶️"}) == "🧂"


def test_parse_overrides():
    assert parse_label_emoji("A=🍎;  B = 🐾 ;broken;=🙂;C=") == {"a": "🍎", "b": "🐾"}
    assert parse_label_emoji("A=🍎\nB=🐾") == {"a": "🍎", "b": "🐾"}
    assert parse_label_emoji(None) == {}


def test_table_has_unique_lowercase_keywords():
    seen: set[str] = set()
    for _, keywords in DEFAULT_LABEL_EMOJI:
        for keyword in keywords:
            assert keyword == keyword.casefold()
            assert keyword not in seen, keyword
            seen.add(keyword)
