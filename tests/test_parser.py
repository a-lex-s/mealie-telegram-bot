import pytest

from mealie_bot.features.shopping.parser import (
    MAX_ENTRIES,
    MAX_ENTRY_LENGTH,
    MAX_QUANTITY,
    EntryTooLong,
    ParsedEntry,
    TooManyEntries,
    clean_text,
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


@pytest.mark.parametrize("text", ["0", "-1", "1e9", str(MAX_QUANTITY + 1), "0/5"])
def test_parse_quantity_rejects_nonsense(text):
    assert parse_quantity(text) is None


def test_absurd_number_stays_part_of_the_name():
    assert parse_entry("99999999 milk", UNITS) == ParsedEntry("99999999 milk")
    assert parse_entry("0 milk", UNITS) == ParsedEntry("0 milk")


def test_clean_text_strips_control_and_invisible_characters():
    assert clean_text("mi\x00lk\u200b\u202e, e\x07ggs\nbread\t1") == "milk, eggs\nbread\t1"
    assert parse_message("mi\u200blk\x00", UNITS) == [ParsedEntry("milk")]


def test_too_many_entries():
    with pytest.raises(TooManyEntries) as info:
        parse_message(", ".join(["milk"] * (MAX_ENTRIES + 1)), UNITS)
    assert info.value.limit == MAX_ENTRIES
    assert len(parse_message(", ".join(["milk"] * MAX_ENTRIES), UNITS)) == MAX_ENTRIES


def test_entry_too_long():
    with pytest.raises(EntryTooLong):
        parse_message("m" * (MAX_ENTRY_LENGTH + 1), UNITS)
    assert parse_message("m" * MAX_ENTRY_LENGTH, UNITS) == [ParsedEntry("m" * MAX_ENTRY_LENGTH)]


def test_numbered_lists_lose_their_numbering():
    assert split_entries("1. Milch\n2) Eier\n1,5 l Wasser\n1.5 l Saft") == [
        "Milch",
        "Eier",
        "1,5 l Wasser",
        "1.5 l Saft",
    ]
