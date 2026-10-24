"""In-memory chat state: the live list message and the change history.

Everything here is per chat and lives only as long as the process; after a
restart the next ``/list`` simply starts a fresh live message.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import escape

from mealie_bot.features.shopping.parser import Assignment
from mealie_bot.features.shopping.render import VIEW_DONE, VIEW_OPEN, ListState
from mealie_bot.i18n import Translator
from mealie_bot.mealie.client import JSON

# Changes closer together than this share one history message.
HISTORY_WINDOW = timedelta(minutes=15)
# Telegram lets bots delete messages for 48 hours; entries are folded before that.
FOLD_DEADLINE = timedelta(hours=47)
# Room for the folded lines in one Telegram message (4096 characters).
MAX_FOLD_TEXT = 4000
# Keep history entries short; more events are summarised by count.
MAX_HISTORY_EVENTS = 12
MAX_HISTORY_ITEMS = 8


@dataclass
class PendingAssignment:
    """An "items → category" message waiting for an answer to a question.

    Labels and foods are resolved one after the other; each unknown name is
    asked about once (create it, or take the similar one), then the
    assignment runs.
    """

    list_id: str
    user_message_id: int
    assignments: list[Assignment]
    # Resolved so far: typed label name -> label, typed product name -> food (None = create).
    labels: dict[str, JSON] = field(default_factory=dict)
    foods: dict[str, JSON | None] = field(default_factory=dict)
    # What a pending question is about: ("label", name) or ("food", name).
    asking: tuple[str, str] | None = None


@dataclass
class HistoryEvent:
    kind: str  # "added" | "checked" | "unchecked" | "cleared" | "undone" | "sorted" | "label"
    user: str
    at: datetime
    items: list[str] = field(default_factory=list)
    count: int = 0
    # Telegram id of the person; a private chat hides its owner's own name.
    user_id: int | None = None
    # Time of the latest change folded into this event (``at`` is the first).
    last_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.last_at is None:
            self.last_at = self.at

    def merge(self, other: HistoryEvent) -> bool:
        """Fold ``other`` into this event if it is the same kind by the same person."""
        if (self.kind, self.user, self.user_id) != (other.kind, other.user, other.user_id):
            return False
        self.items.extend(other.items)
        self.count += other.count
        self.last_at = other.last_at or other.at
        return True


@dataclass
class HistoryEntry:
    """A history message in the chat, as long as it can still be folded."""

    message_id: int
    list_name: str
    events: list[HistoryEvent]
    # When the entry was last written, and when Telegram created the message
    # (it was a list message before; the 48-hour delete limit counts from then).
    written_at: datetime
    sent_at: datetime
    # Private chat owner, whose own name the lines leave out (see render_history).
    owner_id: int | None = None

    def due(self, now: datetime, fold_after: timedelta) -> bool:
        return now - self.written_at >= fold_after or now - self.sent_at >= FOLD_DEADLINE


@dataclass
class ChatState:
    live_message_id: int | None = None
    # Language of the live message; lets another chat's change re-render this
    # message (see ShoppingUI.sync_others).
    language: str | None = None
    states: dict[int, ListState] = field(default_factory=dict)
    # Changes since the last history entry was written.
    pending: list[HistoryEvent] = field(default_factory=list)
    history_message_id: int | None = None
    history_events: list[HistoryEvent] = field(default_factory=list)
    # Error and info messages the bot posted; deleted once the list is shown again.
    transient_message_ids: list[int] = field(default_factory=list)
    # Questions asked for "items → category" messages, by the question's message id.
    # Deleted together with the transient messages when the list is shown again.
    questions: dict[int, PendingAssignment] = field(default_factory=dict)
    # When each list message was sent, for the 48-hour limit of history entries.
    sent_at: dict[int, datetime] = field(default_factory=dict)
    # History messages since the start of the bot, oldest first (HISTORY_FOLD_HOURS).
    history_entries: list[HistoryEntry] = field(default_factory=list)
    # The one message that collects the lines of folded entries, and those lines.
    fold_message_id: int | None = None
    fold_lines: list[str] = field(default_factory=list)
    # List name of the last folded lines; a new name gets its own heading line.
    fold_list: str | None = None
    # "New category" prompts of the sort picker: prompt message id -> list message id.
    # The prompts are transient messages too and go with them.
    name_prompts: dict[int, int] = field(default_factory=dict)
    # Handlers for one chat run one after another (two taps, two texts at once).
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def live_list_id(self) -> str | None:
        """The list the live message shows, if there is one and it was rendered."""
        if self.live_message_id is None:
            return None
        state = self.states.get(self.live_message_id)
        return state.list_id if state is not None else None

    def state_for(self, message_id: int, view: str = VIEW_OPEN) -> ListState:
        """The display state of a list message.

        After a restart no state exists; ``view`` (from the callback data) then
        keeps a tap in the done view from jumping back to the open list.
        """
        if message_id not in self.states:
            self.states[message_id] = ListState(view=view if view == VIEW_DONE else VIEW_OPEN)
        return self.states[message_id]

    def record(self, event: HistoryEvent) -> None:
        if not (self.pending and self.pending[-1].merge(event)):
            self.pending.append(event)
        del self.pending[:-MAX_HISTORY_EVENTS]

    def take_pending(self) -> tuple[bool, list[HistoryEvent]]:
        """Return (extend existing history message?, events to show) and reset pending.

        The caller edits the existing history message when the new changes are
        close in time to the ones already shown; otherwise it starts a new one.
        """
        events = self.pending
        self.pending = []
        if not events:
            return False, []
        last = self.history_events[-1] if self.history_events else None
        extend = bool(
            self.history_message_id is not None
            and last is not None
            and events[0].at - (last.last_at or last.at) <= HISTORY_WINDOW
        )
        if extend:
            for event in events:
                if not (self.history_events and self.history_events[-1].merge(event)):
                    self.history_events.append(event)
            del self.history_events[:-MAX_HISTORY_EVENTS]
        else:
            self.history_events = events
        return extend, list(self.history_events)

    def forget_message(self, message_id: int) -> None:
        self.states.pop(message_id, None)

    def note_entry(
        self,
        message_id: int,
        list_name: str,
        events: list[HistoryEvent],
        now: datetime,
        owner_id: int | None = None,
    ) -> None:
        """Remember that ``message_id`` now holds these history events."""
        for entry in self.history_entries:
            if entry.message_id == message_id:
                entry.events, entry.list_name, entry.written_at = list(events), list_name, now
                return
        sent_at = self.sent_at.pop(message_id, now)
        self.history_entries.append(
            HistoryEntry(message_id, list_name, list(events), now, sent_at, owner_id)
        )

    def take_due(self, now: datetime, fold_after: timedelta) -> list[HistoryEntry]:
        """Remove and return the entries to fold, oldest first."""
        due = [entry for entry in self.history_entries if entry.due(now, fold_after)]
        self.history_entries = [e for e in self.history_entries if e not in due]
        if any(entry.message_id == self.history_message_id for entry in due):
            # The entry that new changes would extend is going: the next starts afresh.
            self.history_message_id = None
            self.history_events = []
        return due

    def add_fold_lines(self, lines: list[str]) -> None:
        """Append lines to the fold message; the oldest go once it would get too long."""
        self.fold_lines.extend(lines)
        while self.fold_lines and len("\n".join(self.fold_lines)) > MAX_FOLD_TEXT:
            self.fold_lines.pop(0)

    def drop_live_message(self) -> None:
        """The live message is gone (deleted on both sides): the next command sends a new one."""
        if self.live_message_id is not None:
            self.forget_message(self.live_message_id)
        self.live_message_id = None


def render_history(
    list_name: str,
    events: list[HistoryEvent],
    tr: Translator,
    today: date | None = None,
    owner_id: int | None = None,
) -> str:
    """History entry text.

    Events from a day other than ``today`` carry their date. ``owner_id`` is the
    user whose private chat this is; their own name is left out (other people's
    names stay, so in a group or for the partner's changes it is clear who did
    what).
    """
    lines = [tr("history.header", list=escape(list_name))]
    lines.extend(history_lines(events, tr, today, owner_id))
    return "\n".join(lines)


def history_lines(
    events: list[HistoryEvent],
    tr: Translator,
    today: date | None = None,
    owner_id: int | None = None,
    always_date: bool = False,
) -> list[str]:
    """One line per event; ``always_date`` puts the date before every time (folded lines)."""
    lines = []
    for event in events:
        time = event.at.strftime("%H:%M")
        if always_date or (today is not None and event.at.date() != today):
            time = f"{event.at.strftime(tr('history.date_format'))} {time}"
        if event.kind in {"cleared", "undone"}:
            what = tr(f"history.{event.kind}", count=event.count or len(event.items))
        else:
            shown = [escape(name) for name in event.items[:MAX_HISTORY_ITEMS]]
            if len(event.items) > MAX_HISTORY_ITEMS:
                shown.append(f"+{len(event.items) - MAX_HISTORY_ITEMS}")
            what = tr(f"history.{event.kind}", items=", ".join(shown))
        if owner_id is not None and event.user_id == owner_id:
            lines.append(tr("history.line_own", time=time, what=what))
        else:
            lines.append(tr("history.line", time=time, user=escape(event.user), what=what))
    return lines
