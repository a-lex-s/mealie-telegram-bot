"""Turn free text into shopping list entries.

The parser is purely lexical: it splits a message into entries and pulls out an
optional quantity and unit. Matching units and foods against Mealie happens in
the service layer.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Container
from dataclasses import dataclass

# Limits on what one message may contain. They protect Mealie (one food search
# per entry) and Telegram (message and button sizes), not the user's patience.
MAX_ENTRIES = 50
MAX_ENTRY_LENGTH = 200
MAX_QUANTITY = 10_000

# Invisible characters that must not end up in Mealie or in rendered messages:
# zero-width spaces/joiners, bidi controls, byte order mark.
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")


class InputError(ValueError):
    """The message cannot be turned into shopping list entries."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"limit {limit} exceeded")
        self.limit = limit


class TooManyEntries(InputError):
    pass


class EntryTooLong(InputError):
    pass


def clean_text(text: str) -> str:
    """Drop control and invisible characters; keep line breaks and tabs for splitting."""
    text = _INVISIBLE.sub("", text)
    return "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cs"}
    )


_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}
_NUMBER = r"(?:\d+(?:[.,]\d+)?|\d+/\d+|[½¼¾⅓⅔])"
# A quantity token, optionally glued to a unit or an "x" multiplier: "2", "1,5", "500g", "3x".
_QTY_TOKEN = re.compile(rf"^(?P<qty>{_NUMBER})(?P<unit>[^\W\d_][\w.]*)?$", re.UNICODE)
# Commas separate entries unless they sit between two digits ("1,5 l").
_SPLIT = re.compile(r"\n|(?<!\d),|,(?!\d)|;")
_MULTIPLIER = {"x", "×"}  # noqa: RUF001
# Numbering of a pasted list ("1. milk", "2) eggs"); "1.5 l" has no space after the dot.
_NUMBERING = re.compile(r"^\d+[.)]\s+")


@dataclass(frozen=True)
class ParsedEntry:
    name: str
    quantity: float | None = None
    unit: str | None = None


def parse_quantity(text: str) -> float | None:
    """Parse a quantity token; ``None`` if it is not a sensible quantity (0 < q <= MAX_QUANTITY)."""
    if text in _FRACTIONS:
        return _FRACTIONS[text]
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            value = int(numerator) / int(denominator)
        except (ValueError, ZeroDivisionError):
            return None
    else:
        try:
            value = float(text.replace(",", "."))
        except ValueError:
            return None
    return value if 0 < value <= MAX_QUANTITY else None


def split_entries(text: str) -> list[str]:
    parts = (_NUMBERING.sub("", part.strip(" \t-•*")) for part in _SPLIT.split(text))
    return [part for part in parts if part.strip(" \t-•*")]


def _match_qty(token: str, known_units: Container[str]) -> tuple[float, str | None] | None:
    match = _QTY_TOKEN.match(token)
    if not match:
        return None
    quantity = parse_quantity(match.group("qty"))
    if quantity is None:
        return None
    unit = match.group("unit")
    if unit is not None:
        if unit.casefold() in _MULTIPLIER:
            unit = None
        elif unit.casefold() not in known_units:
            # "7up" is a name, not seven of unit "up".
            return None
    return quantity, unit


def parse_entry(text: str, known_units: Container[str]) -> ParsedEntry:
    """Parse one entry such as "2 l milk", "500g flour", "milk 2l" or "3x lemons".

    ``known_units`` holds case-folded unit spellings; a separate word after (or
    before) a quantity is only treated as a unit if it is in this set.
    """
    tokens = text.split()
    if not tokens:
        return ParsedEntry(name="")

    def is_unit(token: str) -> bool:
        return token.casefold() in known_units

    # Leading quantity: "2 l milk", "500g flour", "3x lemons", "3 x lemons".
    leading = _match_qty(tokens[0], known_units)
    if leading is not None and len(tokens) > 1:
        quantity, unit = leading
        rest = tokens[1:]
        if unit is None and len(rest) > 1 and rest[0].casefold() in _MULTIPLIER:
            rest = rest[1:]
        elif unit is None and len(rest) > 1 and is_unit(rest[0]):
            unit, rest = rest[0], rest[1:]
        return ParsedEntry(name=" ".join(rest), quantity=quantity, unit=unit)

    # Trailing quantity: "milk 2l", "milk 2 l", "lemons x3", "lemons 3".
    if len(tokens) > 1:
        trailing = _match_qty(tokens[-1], known_units)
        if trailing is not None:
            quantity, unit = trailing
            return ParsedEntry(name=" ".join(tokens[:-1]), quantity=quantity, unit=unit)
        if len(tokens) > 2 and is_unit(tokens[-1]):
            trailing = _match_qty(tokens[-2], known_units)
            if trailing is not None and trailing[1] is None:
                return ParsedEntry(
                    name=" ".join(tokens[:-2]), quantity=trailing[0], unit=tokens[-1]
                )
        multiplier = tokens[-1].casefold()
        if multiplier[:1] in _MULTIPLIER and len(multiplier) > 1:
            quantity_only = parse_quantity(multiplier[1:])
            if quantity_only is not None:
                return ParsedEntry(name=" ".join(tokens[:-1]), quantity=quantity_only)

    return ParsedEntry(name=" ".join(tokens))


def parse_message(text: str, known_units: Container[str]) -> list[ParsedEntry]:
    """Parse a whole message; raises ``InputError`` when it exceeds the limits."""
    parts = split_entries(clean_text(text))
    if len(parts) > MAX_ENTRIES:
        raise TooManyEntries(MAX_ENTRIES)
    if any(len(part) > MAX_ENTRY_LENGTH for part in parts):
        raise EntryTooLong(MAX_ENTRY_LENGTH)
    entries = (parse_entry(part, known_units) for part in parts)
    return [entry for entry in entries if entry.name]
