"""Emoji and colours for Mealie labels (shopping list categories).

A label gets its emoji, in this order, from ``LABEL_EMOJI`` (exact name), from
an emoji at the start of its own name ("🧴 Drugstore"), or from the first
keyword that occurs in its name (case-insensitive, substring), so "Obst &
Gemüse", "Fruit" and "Frozen fruit" all resolve without configuration.
``LABEL_EMOJI`` is ``Würzmittel=🌶️;Tiere=🐾``.

A label's colour in Mealie is shown as a coloured circle (🔴🟠🟡🟢🔵🟣🟤⚫⚪)
before the emoji. A label without an emoji match shows just its circle, so own
categories need no configuration; only a label with neither colour nor match
gets the fallback 📦. Mealie's default grey counts as no colour.
"""

from __future__ import annotations

import colorsys
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

FALLBACK_EMOJI = "📦"
# LABEL_ICONS values: what is shown in front of a category name.
LABEL_ICON_MODES = ("both", "color", "emoji", "none")


@dataclass(frozen=True)
class LabelIcons:
    """How categories are shown: ``LABEL_EMOJI`` overrides plus the ``LABEL_ICONS`` switches."""

    overrides: Mapping[str, str] = field(default_factory=dict)
    circles: bool = True
    emojis: bool = True

    @classmethod
    def from_mode(cls, mode: str, overrides: Mapping[str, str] | None = None) -> LabelIcons:
        return cls(
            overrides=overrides or {},
            circles=mode in {"both", "color"},
            emojis=mode in {"both", "emoji"},
        )


# Mealie's default label colour; labels with it are shown without a circle.
DEFAULT_LABEL_COLOR = "#959595"

# An emoji (with optional variation selector, skin tone and ZWJ sequence) at the
# start of a label name, followed by optional whitespace.
_EMOJI = r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF][\uFE0F\U0001F3FB-\U0001F3FF]*"
_LEADING_EMOJI = re.compile(rf"^(?P<emoji>{_EMOJI}(?:\u200D{_EMOJI})*)\s*")

# (emoji, keywords in any catalog language); order matters, first match wins.
DEFAULT_LABEL_EMOJI: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("🍎", ("obst", "frucht", "früchte", "fruit")),
    ("🥕", ("gemüse", "vegetable", "produce", "salat", "salad")),
    ("🥛", ("milch", "molkerei", "dairy", "käse", "cheese", "joghurt", "yoghurt", "yogurt")),
    ("🥩", ("fleisch", "wurst", "meat", "geflügel", "poultry", "sausage")),
    ("🐟", ("fisch", "fish", "seafood", "meeresfrüchte")),
    ("🍞", ("brot", "backwaren", "bakery", "bread", "baked goods")),
    ("🧁", ("backen", "backzutat", "baking", "mehl", "flour")),
    ("🍝", ("nudeln", "pasta", "reis", "rice", "getreide", "grain", "cereal", "müsli")),
    ("🥫", ("konserve", "canned", "dose", "dosen", "tins")),
    ("🧊", ("tiefkühl", "frozen", "gefroren", "tk")),
    (
        "🧂",
        ("gewürz", "würz", "spice", "condiment", "sauce", "sosse", "sossen", "öl", "oil", "essig"),
    ),
    (
        "🍫",
        ("süss", "suess", "snack", "sweet", "candy", "schoko", "chocolate", "confect", "knabber"),
    ),
    ("☕", ("kaffee", "tee", "coffee", "tea")),
    ("🍷", ("alkohol", "wein", "bier", "alcohol", "wine", "beer", "spirit")),
    ("🥤", ("getränk", "drink", "beverage", "wasser", "water", "saft", "juice")),
    (
        "🧴",
        (
            "drogerie",
            "hygiene",
            "körperpflege",
            "personal care",
            "pflege",
            "toilet",
            "kosmetik",
            "cosmetic",
        ),
    ),
    ("🧻", ("haushalt", "household", "putz", "cleaning", "reinig", "waschmittel", "laundry")),
    ("💊", ("gesundheit", "health", "apotheke", "pharmacy", "medizin", "medicine")),
    ("🐾", ("tier", "pet", "hund", "katze", "dog", "cat")),
    ("🍼", ("baby", "kind", "kids", "children")),
    ("❄️", ("kühl", "chilled", "refrigerat")),
    ("🥚", ("eier", "egg")),
)


def parse_label_emoji(raw: str | None) -> dict[str, str]:
    """Parse ``LABEL_EMOJI``: ``Name=🌶️;Other name=🐾`` into {casefolded name: emoji}."""
    overrides: dict[str, str] = {}
    for part in (raw or "").replace("\n", ";").split(";"):
        name, sep, emoji = part.partition("=")
        if sep and name.strip() and emoji.strip():
            overrides[name.strip().casefold()] = emoji.strip()
    return overrides


def split_label_name(label_name: str | None) -> tuple[str | None, str]:
    """Split "🧴 Drugstore" into ("🧴", "Drugstore"); a name without emoji gives (None, name)."""
    name = (label_name or "").strip()
    match = _LEADING_EMOJI.match(name)
    if match and match.end() < len(name):
        return match.group("emoji"), name[match.end() :]
    return None, name


def find_label_emoji(
    label_name: str | None, overrides: Mapping[str, str] | None = None
) -> str | None:
    """Emoji for a label name: exact override, the name's own emoji, keyword match; else None."""
    own, plain = split_label_name(label_name)
    folded = (label_name or "").strip().casefold()
    if overrides and (folded in overrides or plain.casefold() in overrides):
        return overrides.get(folded) or overrides[plain.casefold()]
    if own:
        return own
    for emoji, keywords in DEFAULT_LABEL_EMOJI:
        if any(keyword in folded for keyword in keywords):
            return emoji
    return None


def label_emoji(label_name: str | None, overrides: Mapping[str, str] | None = None) -> str:
    """``find_label_emoji`` with the fallback for labels nothing matches."""
    return find_label_emoji(label_name, overrides) or FALLBACK_EMOJI


# Colour given to labels the bot creates, by their emoji; anything else keeps Mealie's grey.
LABEL_COLORS: dict[str, str] = {
    "🍎": "#d9534f",
    "🥕": "#5cb85c",
    "🥛": "#5bc0de",
    "🥩": "#b5473c",
    "🐟": "#3f7fbf",
    "🍞": "#c69c6d",
    "🧁": "#e8b84a",
    "🍝": "#e0a040",
    "🥫": "#8d6e63",
    "🧊": "#6fb7e0",
    "🧂": "#9b7bb8",
    "🍫": "#7b4f3a",
    "☕": "#6d4c41",
    "🍷": "#8e3b5c",
    "🥤": "#3b8ec2",
    "🧴": "#d58cc0",
    "🧻": "#5d8aa8",
    "💊": "#e06c6c",
    "🐾": "#a0785a",
    "🍼": "#f0a0b8",
    "❄️": "#8fcde8",
    "🥚": "#e8d58a",
}


def label_color(emoji: str) -> str:
    return LABEL_COLORS.get(emoji, DEFAULT_LABEL_COLOR)


_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def color_circle(color: str | None) -> str:
    """The circle emoji closest to a hex colour; "" for Mealie's default grey,
    an unreadable value or a grey without a hue."""
    match = _HEX.match((color or "").strip())
    if not match or f"#{match.group(1).lower()}" == DEFAULT_LABEL_COLOR:
        return ""
    value = int(match.group(1), 16)
    red, green, blue = (value >> 16) / 255, (value >> 8 & 0xFF) / 255, (value & 0xFF) / 255
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if lightness < 0.12:
        return "⚫"
    if lightness > 0.92:
        return "⚪"
    if saturation < 0.15:
        return ""
    degrees = hue * 360
    if degrees < 15 or degrees >= 340:
        return "🔴"
    if degrees < 45:
        return "🟤" if lightness < 0.4 else "🟠"
    if degrees < 68:
        return "🟤" if lightness < 0.3 else "🟡"
    if degrees < 170:
        return "🟢"
    if degrees < 260:
        return "🔵"
    return "🟣"
