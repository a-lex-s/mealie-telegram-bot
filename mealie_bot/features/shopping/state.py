"""In-memory chat state: the live list message and the change history.

Everything here is per chat and lives only as long as the process; after a
restart the next ``/list`` simply starts a fresh live message.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import escape

from mealie_bot.features.shopping.render import VIEW_DONE, VIEW_OPEN, ListState
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
class ChatState:
    live_message_id: int | None = None
    # Language of the live message; lets another chat's change re-render this
    # message (see ShoppingUI.sync_others).
    language: str | None = None
    # False as soon as anything (a user message, an error) was posted below the live list.
    live_is_last: bool = False
    states: dict[int, ListState] = field(default_factory=dict)
    # Changes since the last history entry was written.
    pending: list[HistoryEvent] = field(default_factory=list)
    history_message_id: int | None = None
    history_events: list[HistoryEvent] = field(default_factory=list)
    # Error messages the bot posted; deleted once the list is shown again.
    error_message_ids: list[int] = field(default_factory=list)
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
        if owner_id is not None and event.user_id == owner_id:
            lines.append(tr("history.line_own", time=time, what=what))
        else:
            lines.append(tr("history.line", time=time, user=escape(event.user), what=what))
    return "\n".join(lines)
