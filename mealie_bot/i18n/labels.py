"""Emoji for Mealie labels (shopping list categories).

A label gets its emoji from the first keyword that occurs in its name
(case-insensitive, substring), so "Obst & Gemüse", "Fruit" and "Frozen fruit"
all resolve without configuration. ``LABEL_EMOJI`` adds or overrides exact
label names, e.g. ``Würzmittel=🌶️;Tiere=🐾``.
"""

from __future__ import annotations

from collections.abc import Mapping

FALLBACK_EMOJI = "📦"

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


def label_emoji(label_name: str | None, overrides: Mapping[str, str] | None = None) -> str:
    """Emoji for a label name: exact override first, then keyword match, then the fallback."""
    folded = (label_name or "").strip().casefold()
    if overrides and folded in overrides:
        return overrides[folded]
    for emoji, keywords in DEFAULT_LABEL_EMOJI:
        if any(keyword in folded for keyword in keywords):
            return emoji
    return FALLBACK_EMOJI
