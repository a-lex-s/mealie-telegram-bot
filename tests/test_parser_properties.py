"""Property-based tests for the shopping list parser.

These complement the example-based tests in test_parser.py. They use
hypothesis to explore a wide range of inputs, including Unicode edge cases.
"""

from __future__ import annotations

import unicodedata

import hypothesis.strategies as st
from hypothesis import given, settings

from mealie_bot.features.shopping.parser import (
    MAX_ENTRIES,
    MAX_ENTRY_LENGTH,
    MAX_QUANTITY,
    InputError,
    clean_text,
    parse_message,
)

# A small, realistic set of known units for the parser.
UNITS = frozenset({"l", "ml", "g", "kg", "Stück", "x"})


@settings(max_examples=200, deadline=None)
@given(text=st.text(max_size=2000))
def test_parse_message_only_raises_input_error(text: str) -> None:
    """Parsing never raises anything except InputError (or subclasses)."""
    try:
        entries = parse_message(text, UNITS)
    except InputError:
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"unexpected exception: {type(exc).__name__}: {exc}") from exc

    # When it succeeds, the limits are respected.
    assert len(entries) <= MAX_ENTRIES
    for entry in entries:
        assert len(entry.name) <= MAX_ENTRY_LENGTH
        if entry.quantity is not None:
            assert 0 < entry.quantity <= MAX_QUANTITY


@settings(max_examples=100, deadline=None)
@given(text=st.text(max_size=500))
def test_clean_text_removes_control_and_invisible(text: str) -> None:
    """cleaned text contains no control or invisible characters."""
    cleaned = clean_text(text)
    for ch in cleaned:
        if ch in "\n\t":
            continue
        category = unicodedata.category(ch)
        assert category not in {"Cc", "Cs"}, f"control/surrogate left: {ch!r} ({category})"
        # Invisible characters that the regex targets.
        assert not (0x200B <= ord(ch) <= 0x200F)
        assert not (0x202A <= ord(ch) <= 0x202E)
        assert not (0x2060 <= ord(ch) <= 0x2069)
        assert ord(ch) != 0xFEFF
