from datetime import datetime, timedelta

from mealie_bot.features.shopping.render import VIEW_DONE, VIEW_OPEN
from mealie_bot.features.shopping.state import (
    MAX_FOLD_TEXT,
    MAX_HISTORY_EVENTS,
    MAX_HISTORY_ITEMS,
    ChatState,
    HistoryEvent,
    render_history,
)
from mealie_bot.i18n import Translator

T0 = datetime(2026, 1, 1, 21, 0)


def event(kind, user="Alice", minutes=0, items=(), count=0, user_id=None):
    return HistoryEvent(
        kind, user, T0 + timedelta(minutes=minutes), list(items), count, user_id=user_id
    )


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


def test_pending_events_are_capped():
    chat = ChatState()
    for i in range(MAX_HISTORY_EVENTS + 3):
        chat.record(event("added" if i % 2 else "checked", items=[f"item {i}"], minutes=i))
    assert len(chat.pending) == MAX_HISTORY_EVENTS
    assert chat.pending[-1].items == [f"item {MAX_HISTORY_EVENTS + 2}"]


def test_state_for_takes_the_view_from_the_callback_only_once():
    chat = ChatState()
    assert chat.state_for(1, VIEW_DONE).view == VIEW_DONE
    assert chat.state_for(1, VIEW_OPEN).view == VIEW_DONE  # existing state wins
    assert chat.state_for(2, "clear").view == VIEW_OPEN  # only the two list views count


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


def test_window_counts_from_the_latest_change_of_the_entry():
    chat = ChatState()
    chat.record(event("checked", items=["Milk"]))
    chat.record(event("checked", items=["Eggs"], minutes=20))  # merged into one line
    chat.take_pending()
    chat.history_message_id = 42
    chat.record(event("added", items=["Bread"], minutes=30))
    extend, _ = chat.take_pending()
    assert extend  # 10 minutes after the last change, although 30 after the first


def test_render_history_hides_the_chat_owners_own_name():
    events = [
        event("added", items=["Milk"], user_id=1001),
        event("checked", user="Bob", minutes=5, items=["Milk"], user_id=1002),
    ]
    lines = render_history("G", events, Translator("en"), owner_id=1001).split("\n")
    assert lines[1] == "<i>21:00</i> ➕ Milk"
    assert lines[2] == "<i>21:05 · Bob</i> ✅ Milk"
    # In a group (no owner) every line carries the name.
    assert (
        render_history("G", events, Translator("en")).split("\n")[1]
        == "<i>21:00 · Alice</i> ➕ Milk"
    )


def test_entries_are_due_after_the_setting_or_before_telegrams_limit():
    chat = ChatState()
    chat.sent_at[1] = T0 - timedelta(hours=40)
    chat.note_entry(1, "Groceries", [event("added", items=["Milk"])], T0)
    chat.note_entry(2, "Groceries", [event("added", items=["Eggs"])], T0)
    chat.history_message_id = 2
    assert chat.take_due(T0 + timedelta(hours=6), timedelta(hours=24)) == []
    # Entry 1 was a list message for 40 hours already: it goes at 47 hours.
    due = chat.take_due(T0 + timedelta(hours=7), timedelta(hours=24))
    assert [entry.message_id for entry in due] == [1]
    assert [e.message_id for e in chat.take_due(T0 + timedelta(hours=24), timedelta(hours=24))] == [
        2
    ]
    # The entry new changes would have extended is gone.
    assert chat.history_message_id is None and chat.history_entries == []


def test_rewriting_an_entry_updates_it():
    chat = ChatState()
    chat.note_entry(1, "Groceries", [event("added", items=["Milk"])], T0)
    chat.note_entry(
        1, "Groceries", [event("added", items=["Milk", "Eggs"])], T0 + timedelta(hours=1)
    )
    assert len(chat.history_entries) == 1
    assert chat.history_entries[0].written_at == T0 + timedelta(hours=1)


def test_fold_lines_keep_the_newest_that_fit():
    chat = ChatState()
    chat.add_fold_lines([f"line {i:04} " + "x" * 90 for i in range(100)])
    assert len("\n".join(chat.fold_lines)) <= MAX_FOLD_TEXT
    assert chat.fold_lines[-1].startswith("line 0099") and len(chat.fold_lines) < 100
