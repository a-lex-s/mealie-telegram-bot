from datetime import datetime, timedelta

from mealie_bot.features.shopping.state import (
    MAX_HISTORY_ITEMS,
    ChatState,
    HistoryEvent,
    render_history,
)
from mealie_bot.i18n import Translator

T0 = datetime(2026, 1, 1, 21, 0)


def event(kind, user="Alice", minutes=0, items=(), count=0):
    return HistoryEvent(kind, user, T0 + timedelta(minutes=minutes), list(items), count)


def test_consecutive_same_kind_events_merge():
    chat = ChatState()
    chat.record(event("added", items=["Milk"]))
    chat.record(event("added", items=["Eggs"], minutes=1))
    chat.record(event("added", user="Bob", items=["Bread"], minutes=2))
    chat.record(event("checked", user="Bob", items=["Milk"], minutes=3))
    assert [(e.kind, e.user, e.items) for e in chat.pending] == [
        ("added", "Alice", ["Milk", "Eggs"]),
        ("added", "Bob", ["Bread"]),
        ("checked", "Bob", ["Milk"]),
    ]


def test_take_pending_starts_or_extends_an_entry():
    chat = ChatState()
    assert chat.take_pending() == (False, [])
    chat.record(event("added", items=["Milk"]))
    extend, events = chat.take_pending()
    assert (extend, [e.items for e in events]) == (False, [["Milk"]])
    chat.history_message_id = 42

    chat.record(event("checked", items=["Milk"], minutes=10))
    extend, events = chat.take_pending()
    assert extend and [e.kind for e in events] == ["added", "checked"]

    chat.record(event("added", items=["Eggs"], minutes=40))
    extend, events = chat.take_pending()
    assert not extend and [e.items for e in events] == [["Eggs"]]


def test_render_history_lines_and_truncation():
    events = [
        event("added", items=[f"item {i}" for i in range(MAX_HISTORY_ITEMS + 2)]),
        event("checked", user="Bob", minutes=5, items=["Milk <b>"]),
        event("cleared", minutes=9, count=3),
    ]
    text = render_history("Groceries & more", events, Translator("de"))
    lines = text.split("\n")
    assert lines[0] == "📜 <b>Groceries &amp; more</b>"
    assert lines[1].startswith("<i>21:00 · Alice</i> ➕ item 0, ")
    assert lines[1].endswith(f", item {MAX_HISTORY_ITEMS - 1}, +2")
    assert lines[2] == "<i>21:05 · Bob</i> ✅ Milk &lt;b&gt;"
    assert lines[3] == "<i>21:09 · Alice</i> 🧹 3 Einträge entfernt"


def test_render_history_dates_entries_from_other_days():
    events = [event("added", items=["milk"]), event("checked", minutes=60 * 24 * 2, items=["milk"])]
    today = (T0 + timedelta(days=2)).date()
    lines = render_history("G", events, Translator("de"), today=today).split("\n")
    assert lines[1] == "<i>01.01. 21:00 · Alice</i> ➕ milk"
    assert lines[2] == "<i>21:00 · Alice</i> ✅ milk"
    lines = render_history("G", events, Translator("en"), today=today).split("\n")
    assert lines[1] == "<i>Jan 01 21:00 · Alice</i> ➕ milk"
