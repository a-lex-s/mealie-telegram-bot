"""Render a shopping list as Telegram HTML text plus an inline keyboard.

The list message is built from a ``ListView`` (what Mealie has) and a
``ListState`` (what this particular message shows: which view, which label
groups are expanded, what was just added). Rendering is pure; the handlers
decide when to send, edit or delete messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.i18n import Translator
from mealie_bot.mealie.client import JSON

# Telegram allows 100 buttons per keyboard; keep room for headers and controls.
MAX_ITEM_BUTTONS = 80
MAX_BUTTON_TEXT = 60
PROGRESS_CELLS = 10
# Buttons in one row share its width equally, so short names are packed together.
_ROW_SIZES = ((10, 3), (18, 2))

VIEW_OPEN = "open"
VIEW_DONE = "done"
VIEW_CLEAR = "clear"  # confirmation before deleting ticked-off items

# Key used for items without a label, both in ``ListState.expanded`` and callback data.
NO_LABEL = "-"


class ItemAction(CallbackData, prefix="it"):
    action: str  # "check" | "uncheck"
    item_id: str
    view: str


class ListAction(CallbackData, prefix="ls"):
    # "show" | "new" | "toggle" | "undo" | "clear_ask" | "clear" | "noop"
    action: str
    view: str = VIEW_OPEN
    arg: str = ""  # label id for "toggle"


class SelectList(CallbackData, prefix="sel"):
    list_id: str


@dataclass
class UndoInfo:
    """What it takes to revert one "add items" request."""

    created_ids: list[str] = field(default_factory=list)
    # Previous versions of items Mealie merged the new entries into.
    previous: list[JSON] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.created_ids or self.previous)


@dataclass
class ListState:
    """Per-message display state of a list message."""

    view: str = VIEW_OPEN
    expanded: set[str] = field(default_factory=set)
    added: list[JSON] = field(default_factory=list)
    undo: UndoInfo | None = None

    def toggle(self, label_key: str) -> None:
        if label_key in self.expanded:
            self.expanded.discard(label_key)
        else:
            self.expanded.add(label_key)


# --- item texts -----------------------------------------------------------


def format_quantity(quantity: float, language: str) -> str:
    text = f"{quantity:g}" if quantity != int(quantity) else str(int(quantity))
    return text.replace(".", ",") if language == "de" else text


def entry_display(entry: ParsedEntry, language: str) -> str:
    parts = []
    if entry.quantity is not None:
        parts.append(format_quantity(entry.quantity, language))
    if entry.unit:
        parts.append(entry.unit)
    parts.append(entry.name)
    return " ".join(parts)


def item_parts(item: JSON, language: str) -> tuple[str, str]:
    """Split an item into (name, quantity text), e.g. ("Mehl", "500 g").

    The quantity text is empty for "1" without a unit, which is Mealie's default.
    """
    food = item.get("food") or {}
    note = (item.get("note") or "").strip()
    name = (food.get("name") or "").strip()
    if name and note:
        name = f"{name}, {note}"
    elif not name:
        name = note or (item.get("display") or "").strip() or "?"

    quantity = item.get("quantity") or 0
    unit = item.get("unit") or {}
    unit_text = (
        (
            unit.get("abbreviation")
            if unit.get("useAbbreviation") and unit.get("abbreviation")
            else ""
        )
        or unit.get("name")
        or ""
    )
    qty_parts: list[str] = []
    if quantity and (quantity != 1 or unit_text):
        qty_parts.append(format_quantity(quantity, language))
    if unit_text:
        qty_parts.append(unit_text)
    return name, " ".join(qty_parts)


def item_display(item: JSON, language: str) -> str:
    """Plain text for buttons: "Mehl · 500 g"."""
    name, quantity = item_parts(item, language)
    return f"{name} · {quantity}" if quantity else name


def item_html(item: JSON, language: str) -> str:
    """HTML for message texts: name bold, quantity muted."""
    name, quantity = item_parts(item, language)
    text = f"<b>{escape(name)}</b>"
    return f"{text} <i>{escape(quantity)}</i>" if quantity else text


def label_key(item: JSON) -> str:
    label = item.get("label") or {}
    return str(label.get("id") or item.get("labelId") or NO_LABEL)


def label_name(item: JSON, tr: Translator) -> str:
    return str((item.get("label") or {}).get("name") or tr("shopping.label_none"))


def _truncate(text: str) -> str:
    return text if len(text) <= MAX_BUTTON_TEXT else text[: MAX_BUTTON_TEXT - 1] + "…"


# --- text -----------------------------------------------------------------


def progress_bar(done: int, total: int) -> str:
    filled = round(done / total * PROGRESS_CELLS) if total else 0
    return "▰" * filled + "▱" * (PROGRESS_CELLS - filled)


def _group(items: list[JSON], tr: Translator) -> list[tuple[str, str, list[JSON]]]:
    """Group open items by label: (label key, label name, items), labels sorted, "Other" last."""
    groups: dict[str, tuple[str, list[JSON]]] = {}
    for item in items:
        key = label_key(item)
        groups.setdefault(key, (label_name(item, tr), []))[1].append(item)
    ordered = sorted(groups.items(), key=lambda kv: (kv[0] == NO_LABEL, kv[1][0].casefold()))
    return [
        (key, name, sorted(group, key=lambda i: i.get("position") or 0))
        for key, (name, group) in ordered
    ]


def render_list(
    list_name: str,
    items: list[JSON],
    state: ListState,
    tr: Translator,
    now: datetime | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    language = tr.language
    checked = [i for i in items if i.get("checked")]
    unchecked = [i for i in items if not i.get("checked")]
    name = escape(list_name)

    if state.view == VIEW_CLEAR:
        return _render_clear_question(name, checked, tr)
    if state.view == VIEW_DONE:
        return _render_done(name, checked, unchecked, tr)

    lines = [tr("shopping.list_header", list=name)]
    if items:
        lines.append(
            f"<code>{progress_bar(len(checked), len(items))}</code> "
            + tr("shopping.list_counts", open=len(unchecked), done=len(checked))
        )
    if not unchecked:
        lines.append(tr("shopping.list_all_done" if checked else "shopping.list_empty"))
    if state.added:
        added_lines = [
            f"{item_html(item, language)} <i>· {escape(label_name(item, tr))}</i>"
            for item in state.added
        ]
        lines.append(
            "<blockquote expandable>"
            + tr("shopping.added_header", count=len(state.added))
            + "\n"
            + "\n".join(added_lines)
            + "</blockquote>"
        )
    if checked:
        done_lines = [f"<s>{escape(item_display(i, language))}</s>" for i in checked]
        lines.append(
            "<blockquote expandable>"
            + tr("shopping.done_quote", count=len(checked))
            + "\n"
            + "\n".join(done_lines)
            + "</blockquote>"
        )

    rows: list[list[InlineKeyboardButton]] = []
    groups = _group(unchecked, tr)
    shown = 0
    hidden = 0
    for key, group_name, group in groups:
        expanded = len(groups) == 1 or key in state.expanded
        if len(groups) > 1:
            arrow = "▾" if expanded else "▸"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=_truncate(f"{arrow} {group_name} · {len(group)}"),
                        callback_data=ListAction(action="toggle", view=VIEW_OPEN, arg=key).pack(),
                    )
                ]
            )
        if not expanded:
            continue
        room = MAX_ITEM_BUTTONS - shown
        visible, rest = group[:room], group[room:]
        hidden += len(rest)
        shown += len(visible)
        rows.extend(_pack_rows(visible, "check", VIEW_OPEN, language))
    if hidden:
        lines.append(tr("shopping.more", count=hidden))

    if now is not None:
        lines.append(tr("shopping.updated_at", time=now.strftime("%H:%M")))

    controls = [
        InlineKeyboardButton(
            text=tr("shopping.btn_undo"), callback_data=ListAction(action="undo").pack()
        )
        if state.undo
        else InlineKeyboardButton(
            text=tr("shopping.btn_refresh"),
            callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
        ),
        InlineKeyboardButton(
            text=tr("shopping.btn_done", count=len(checked)),
            callback_data=ListAction(action="show", view=VIEW_DONE).pack(),
        ),
    ]
    rows.append(controls)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _render_done(
    name: str, checked: list[JSON], unchecked: list[JSON], tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    shown = sorted(checked, key=lambda i: i.get("updatedAt") or "", reverse=True)
    text = (
        tr("shopping.done_header", list=name, count=len(checked))
        if checked
        else tr("shopping.done_empty", list=name)
    )
    rows = _pack_rows(shown[:MAX_ITEM_BUTTONS], "uncheck", VIEW_DONE, tr.language)
    if len(shown) > MAX_ITEM_BUTTONS:
        text += "\n" + tr("shopping.more", count=len(shown) - MAX_ITEM_BUTTONS)
    controls = [
        InlineKeyboardButton(
            text=tr("shopping.btn_open", count=len(unchecked)),
            callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
        )
    ]
    if checked:
        controls.append(
            InlineKeyboardButton(
                text=tr("shopping.btn_clear", count=len(checked)),
                callback_data=ListAction(action="clear_ask", view=VIEW_DONE).pack(),
            )
        )
    rows.append(controls)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _render_clear_question(
    name: str, checked: list[JSON], tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    if not checked:
        return _render_done(name, [], [], tr)
    quote = " · ".join(f"<s>{escape(item_display(i, tr.language))}</s>" for i in checked)
    text = (
        tr("shopping.clear_question", list=name, count=len(checked))
        + f"\n<blockquote expandable>{quote}</blockquote>\n"
        + tr("shopping.clear_hint")
    )
    rows = [
        [
            InlineKeyboardButton(
                text=tr("shopping.btn_clear_yes"),
                callback_data=ListAction(action="clear", view=VIEW_OPEN).pack(),
            ),
            InlineKeyboardButton(
                text=tr("shopping.btn_cancel"),
                callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
            ),
        ]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


# --- keyboard -------------------------------------------------------------


def _row_size(text: str) -> int:
    for max_length, per_row in _ROW_SIZES:
        if len(text) <= max_length:
            return per_row
    return 1


def _pack_rows(
    items: list[JSON], action: str, view: str, language: str
) -> list[list[InlineKeyboardButton]]:
    """Put short names three to a row, medium ones two, long ones alone."""
    buckets: dict[int, list[InlineKeyboardButton]] = {3: [], 2: [], 1: []}
    for item in items:
        text = _truncate(item_display(item, language))
        buckets[_row_size(text)].append(
            InlineKeyboardButton(
                text=text,
                callback_data=ItemAction(action=action, item_id=item["id"], view=view).pack(),
            )
        )
    rows: list[list[InlineKeyboardButton]] = []
    for per_row, buttons in buckets.items():
        rows.extend(buttons[i : i + per_row] for i in range(0, len(buttons), per_row))
    return rows


def list_chooser(
    lists: list[JSON], active_id: str, tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        [
            InlineKeyboardButton(
                text=_truncate(
                    ("● " if item["id"] == active_id else "") + (item.get("name") or "?")
                ),
                callback_data=SelectList(list_id=item["id"]).pack(),
            )
        ]
        for item in lists
    ]
    return tr("shopping.choose_list"), InlineKeyboardMarkup(inline_keyboard=rows)
