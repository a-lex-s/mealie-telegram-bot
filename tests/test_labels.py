import pytest

from mealie_bot.i18n.labels import (
    DEFAULT_LABEL_COLOR,
    DEFAULT_LABEL_EMOJI,
    FALLBACK_EMOJI,
    color_circle,
    find_label_emoji,
    label_color,
    label_emoji,
    parse_label_emoji,
    split_label_name,
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


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("🧴 Drogerie", ("🧴", "Drogerie")),
        ("🌶️Scharf", ("🌶️", "Scharf")),
        ("👩‍🍳 Kochen", ("👩‍🍳", "Kochen")),
        ("Drogerie", (None, "Drogerie")),
        ("🧴", (None, "🧴")),
        ("", (None, "")),
    ],
)
def test_split_label_name(name, expected):
    assert split_label_name(name) == expected


def test_own_emoji_beats_the_keyword_table_but_not_an_override():
    assert label_emoji("🌶️ Würzmittel") == "🌶️"
    assert label_emoji("🌶️ Würzmittel", {"würzmittel": "🥫"}) == "🥫"
    assert find_label_emoji("Eigenes") is None
    assert label_emoji("Eigenes") == FALLBACK_EMOJI


@pytest.mark.parametrize(
    ("color", "circle"),
    [
        ("#959595", ""),  # Mealie's default: no circle
        ("#808080", ""),  # a grey without hue
        ("#d9534f", "🔴"),
        ("ff8800", "🟠"),
        ("#ffd700", "🟡"),
        ("#5cb85c", "🟢"),
        ("#5bc0de", "🔵"),
        ("#800080", "🟣"),
        ("#8b4513", "🟤"),
        ("#000000", "⚫"),
        ("#ffffff", "⚪"),
        ("not a colour", ""),
        (None, ""),
    ],
)
def test_color_circle(color, circle):
    assert color_circle(color) == circle


def test_new_labels_get_a_colour_from_their_emoji():
    assert label_color("🍎") == "#d9534f"
    assert label_color("📦") == DEFAULT_LABEL_COLOR
