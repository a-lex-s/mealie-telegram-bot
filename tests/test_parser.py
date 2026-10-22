import pytest

from mealie_bot.features.shopping.parser import (
    ParsedEntry,
    parse_entry,
    parse_message,
    parse_quantity,
    split_entries,
)
from mealie_bot.i18n import unit_synonyms

UNITS = frozenset().union(*unit_synonyms().values())


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("milk", ParsedEntry("milk")),
        ("2 l milk", ParsedEntry("milk", 2, "l")),
        ("2 L Milch", ParsedEntry("Milch", 2, "L")),
        ("500g flour", ParsedEntry("flour", 500, "g")),
        ("1,5 l Milch", ParsedEntry("Milch", 1.5, "l")),
        ("1.5 kg potatoes", ParsedEntry("potatoes", 1.5, "kg")),
        ("½ Bund Petersilie", ParsedEntry("Petersilie", 0.5, "Bund")),
        ("1/2 Packung Butter", ParsedEntry("Butter", 0.5, "Packung")),
        ("3 eggs", ParsedEntry("eggs", 3)),
        ("3x Zitronen", ParsedEntry("Zitronen", 3)),
        ("3 x Zitronen", ParsedEntry("Zitronen", 3)),
        ("Milch 2l", ParsedEntry("Milch", 2, "l")),
        ("Milch 2 l", ParsedEntry("Milch", 2, "l")),
        ("Zitronen x3", ParsedEntry("Zitronen", 3)),
        ("Eier 6", ParsedEntry("Eier", 6)),
        ("2 Stück Kuchen", ParsedEntry("Kuchen", 2, "Stück")),
        ("2 large onions", ParsedEntry("large onions", 2)),
        ("7up", ParsedEntry("7up")),
        ("7up Zero", ParsedEntry("7up Zero")),
        ("Cola 7up", ParsedEntry("Cola 7up")),
        ("Vitamin B12", ParsedEntry("Vitamin B12")),
        ("Tomaten aus der Dose", ParsedEntry("Tomaten aus der Dose")),
    ],
)
def test_parse_entry(text, expected):
    assert parse_entry(text, UNITS) == expected


def test_unknown_glued_unit_is_name():
    assert parse_entry("2 l milk", frozenset()) == ParsedEntry("l milk", 2)


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("milk, eggs", ["milk", "eggs"]),
        ("1,5 l Milch, Eier", ["1,5 l Milch", "Eier"]),
        ("Milch\nEier\n\n- Brot", ["Milch", "Eier", "Brot"]),
        ("Milch; Eier", ["Milch", "Eier"]),
        (" , ,", []),
    ],
)
def test_split_entries(text, parts):
    assert split_entries(text) == parts


def test_parse_message_multiple():
    assert parse_message("2 l Milch, Eier\n500g Mehl", UNITS) == [
        ParsedEntry("Milch", 2, "l"),
        ParsedEntry("Eier"),
        ParsedEntry("Mehl", 500, "g"),
    ]


@pytest.mark.parametrize(
    ("text", "value"), [("2", 2), ("1,5", 1.5), ("1/4", 0.25), ("¾", 0.75), ("1/0", None)]
)
def test_parse_quantity(text, value):
    assert parse_quantity(text) == value
