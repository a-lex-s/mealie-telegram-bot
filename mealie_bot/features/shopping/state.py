"""In-memory chat state: the live list message and the change history.

Everything here is per chat and lives only as long as the process; after a
restart the next ``/list`` simply starts a fresh live message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import escape

from mealie_bot.features.shopping.render import ListState
from mealie_bot.i18n import Translator

# Changes closer together than this share one history message.
HISTORY_WINDOW = timedelta(minutes=15)
# Keep history entries short; more events are summarised by count.
MAX_HISTORY_EVENTS = 12
MAX_HISTORY_ITEMS = 8


@dataclass
class HistoryEvent:
    kind: str  # "added" | "checked" | "unchecked" | "cleared" | "undone"
    user: str
    at: datetime
    items: list[str] = field(default_factory=list)
    count: int = 0

    def merge(self, other: HistoryEvent) -> bool:
        """Fold ``other`` into this event if it is the same kind by the same person."""
        if (self.kind, self.user) != (other.kind, other.user):
            return False
        self.items.extend(other.items)
        self.count += other.count
        return True


@dataclass
class ChatState:
    live_message_id: int | None = None
    # False as soon as anything (a user message, an error) was posted below the live list.
    live_is_last: bool = False
    states: dict[int, ListState] = field(default_factory=dict)
    # Changes since the last history entry was written.
    pending: list[HistoryEvent] = field(default_factory=list)
    history_message_id: int | None = None
    history_events: list[HistoryEvent] = field(default_factory=list)

    def state_for(self, message_id: int) -> ListState:
        return self.states.setdefault(message_id, ListState())

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
        extend = bool(
            self.history_message_id is not None
            and self.history_events
            and events[0].at - self.history_events[-1].at <= HISTORY_WINDOW
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


def render_history(
    list_name: str, events: list[HistoryEvent], tr: Translator, today: date | None = None
) -> str:
    """History entry text; events from a day other than ``today`` carry their date."""
    lines = [tr("history.header", list=escape(list_name))]
    for event in events:
        time = event.at.strftime("%H:%M")
        if today is not None and event.at.date() != today:
            time = f"{event.at.strftime(tr('history.date_format'))} {time}"
        if event.kind in {"cleared", "undone"}:
            what = tr(f"history.{event.kind}", count=event.count or len(event.items))
        else:
            shown = [escape(name) for name in event.items[:MAX_HISTORY_ITEMS]]
            if len(event.items) > MAX_HISTORY_ITEMS:
                shown.append(f"+{len(event.items) - MAX_HISTORY_ITEMS}")
            what = tr(f"history.{event.kind}", items=", ".join(shown))
        lines.append(tr("history.line", time=time, user=escape(event.user), what=what))
    return "\n".join(lines)
