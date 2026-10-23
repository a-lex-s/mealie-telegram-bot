"""Render a shopping list as Telegram HTML text plus an inline keyboard.

The list message is built from a ``ListView`` (what Mealie has) and a
``ListState`` (what this particular message shows: which view, which label
groups are expanded, what was just added). Rendering is pure; the handlers
decide when to send, edit or delete messages.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from html import escape

from aiogram.enums import ButtonStyle
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.i18n import Translator
from mealie_bot.i18n.labels import label_emoji
from mealie_bot.mealie.client import JSON

# Telegram allows 100 buttons per keyboard; item buttons and category headers share
# this budget, the rest is room for the control row.
MAX_ITEM_BUTTONS = 80
# Telegram ellipsises long button texts itself; cut earlier so our "…" lands after the name.
MAX_BUTTON_TEXT = 40
# Telegram messages hold 4096 characters; quotes list at most this many items.
MAX_QUOTE_ITEMS = 20
PROGRESS_CELLS = 10
# Buttons in one row share its width equally, so short names are packed together.
_ROW_SIZES = ((10, 3), (18, 2))

VIEW_OPEN = "open"
VIEW_DONE = "done"
VIEW_CLEAR = "clear"  # confirmation before deleting ticked-off items
VIEW_LISTS = "lists"  # choose the active list

# Key used for items without a label, both in ``ListState.expanded`` and callback data.
NO_LABEL = "-"

# Button colours (Bot API ``style``): category headers stand out from plain item buttons,
# the safe control is green and the destructive ones are red. Older clients ignore them.
STYLE_CATEGORY = ButtonStyle.PRIMARY
STYLE_DONE = ButtonStyle.SUCCESS
STYLE_DESTRUCTIVE = ButtonStyle.DANGER


class ItemAction(CallbackData, prefix="it"):
    action: str  # "check" | "uncheck"
    item_id: str
    view: str


class ListAction(CallbackData, prefix="ls"):
    # "show" | "refresh" | "toggle" | "undo" | "clear_ask" | "clear" | "noop"
    # ("new" may still arrive from messages rendered by older versions)
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


# Pure fractions are shown as typed (``½``); everything else gets at most two decimals.
_FRACTION_GLYPHS = {0.5: "½", 0.25: "¼", 0.75: "¾", 1 / 3: "⅓", 2 / 3: "⅔"}


def format_quantity(quantity: float, language: str) -> str:
    if 0 < quantity < 1:
        for value, glyph in _FRACTION_GLYPHS.items():
            if abs(quantity - value) < 0.001:
                return glyph
    rounded = round(quantity, 2)
    text = f"{rounded:g}" if rounded != int(rounded) else str(int(rounded))
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
    """Plain text for buttons and toasts: "Mehl · 500 g"."""
    name, quantity = item_parts(item, language)
    return f"{name} · {quantity}" if quantity else name


def item_inline(item: JSON, language: str) -> str:
    """Plain text for running text such as history lines: "500 g Mehl", as one would type it."""
    name, quantity = item_parts(item, language)
    return f"{quantity} {name}" if quantity else name


def item_html(item: JSON, language: str, suffix: str = "") -> str:
    """HTML for message texts: ``<b>Mehl</b> · <i>500 g · suffix</i>``."""
    name, quantity = item_parts(item, language)
    details = " · ".join(part for part in (escape(quantity), suffix) if part)
    return f"<b>{escape(name)}</b> · <i>{details}</i>" if details else f"<b>{escape(name)}</b>"


def label_key(item: JSON) -> str:
    label = item.get("label") or {}
    return str(label.get("id") or item.get("labelId") or NO_LABEL)


def label_name(item: JSON, tr: Translator) -> str:
    return str((item.get("label") or {}).get("name") or tr("shopping.label_none"))


def _truncate(text: str) -> str:
    return text if len(text) <= MAX_BUTTON_TEXT else text[: MAX_BUTTON_TEXT - 1] + "…"


def _quote(header: str, lines: list[str], tr: Translator) -> str:
    """An expandable quote with at most MAX_QUOTE_ITEMS lines; the rest is counted."""
    shown = lines[:MAX_QUOTE_ITEMS]
    if len(lines) > MAX_QUOTE_ITEMS:
        shown.append(tr("shopping.more", count=len(lines) - MAX_QUOTE_ITEMS))
    return "<blockquote expandable>" + header + "\n" + "\n".join(shown) + "</blockquote>"


# --- text -----------------------------------------------------------------


def progress_bar(done: int, total: int) -> str:
    """Ten cells; anything done fills at least one, anything open leaves at least one empty."""
    filled = round(done / total * PROGRESS_CELLS) if total else 0
    if done:
        filled = max(filled, 1)
    if done < total:
        filled = min(filled, PROGRESS_CELLS - 1)
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


def category_title(name: str, count: int, expanded: bool, emoji: Mapping[str, str] | None) -> str:
    """Text of a category header button: ``🧂 Würzmittel (2) ▾``."""
    arrow = "▾" if expanded else "▸"
    return f"{label_emoji(name, emoji)} {name} ({count}) {arrow}"


def render_list(
    list_name: str,
    items: list[JSON],
    state: ListState,
    tr: Translator,
    now: datetime | None = None,
    emoji: Mapping[str, str] | None = None,
    lists: list[JSON] | None = None,
    active_id: str = "",
) -> tuple[str, InlineKeyboardMarkup]:
    """Render the list message; ``emoji`` holds ``LABEL_EMOJI`` overrides for categories.

    ``lists`` and ``active_id`` are only needed for the list chooser view.
    """
    language = tr.language
    checked = [i for i in items if i.get("checked")]
    unchecked = [i for i in items if not i.get("checked")]
    name = escape(list_name)

    if state.view == VIEW_LISTS:
        return list_chooser(lists or [], active_id, tr)
    if state.view == VIEW_CLEAR:
        return _render_clear_question(name, checked, tr)
    if state.view == VIEW_DONE:
        return _render_done(name, checked, unchecked, tr)

    time_text = now.strftime("%H:%M") if now is not None else ""
    lines = [tr("shopping.list_header", list=name)]
    if items:
        # "3 open · 1 done · 21:12"; the bar and the done count appear once something is done.
        status = tr("shopping.count_open", count=len(unchecked))
        if checked:
            status = f"<code>{progress_bar(len(checked), len(items))}</code> {status} · " + tr(
                "shopping.count_done", count=len(checked)
            )
        if time_text:
            status += f" · <i>{time_text}</i>"
        lines.append(status)
    if not unchecked:
        lines.append(tr("shopping.list_all_done" if checked else "shopping.list_empty"))
        if not items and time_text:
            lines.append(tr("shopping.updated_at", time=time_text))
    if state.added:
        added_lines = [
            item_html(
                item,
                language,
                f"{label_emoji(label_name(item, tr), emoji)} {escape(label_name(item, tr))}",
            )
            for item in state.added
        ]
        if len(added_lines) == 1:
            lines.append(tr("shopping.added_one", item=added_lines[0]))
        else:
            lines.append(
                _quote(tr("shopping.added_header", count=len(added_lines)), added_lines, tr)
            )
    if checked:
        done_lines = [f"<s>{escape(item_display(i, language))}</s>" for i in checked]
        lines.append(_quote(tr("shopping.done_quote"), done_lines, tr))

    rows: list[list[InlineKeyboardButton]] = []
    groups = _group(unchecked, tr)
    # Category headers come out of the same budget as the item buttons.
    budget = MAX_ITEM_BUTTONS - (len(groups) if len(groups) > 1 else 0)
    shown = 0
    hidden = 0
    for key, group_name, group in groups:
        expanded = len(groups) == 1 or key in state.expanded
        if len(groups) > 1:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=_truncate(category_title(group_name, len(group), expanded, emoji)),
                        callback_data=ListAction(action="toggle", view=VIEW_OPEN, arg=key).pack(),
                        style=STYLE_CATEGORY,
                    )
                ]
            )
        if not expanded:
            continue
        room = max(budget - shown, 0)
        visible, rest = group[:room], group[room:]
        hidden += len(rest)
        shown += len(visible)
        rows.extend(_pack_rows(visible, "check", VIEW_OPEN, language))
    if hidden:
        lines.append(tr("shopping.more", count=hidden))

    # Undo is the safe button, so it keeps the default colour; red is for deleting.
    controls = [
        InlineKeyboardButton(
            text=tr("shopping.btn_undo"), callback_data=ListAction(action="undo").pack()
        )
        if state.undo
        else InlineKeyboardButton(
            text=tr("shopping.btn_refresh"), callback_data=ListAction(action="refresh").pack()
        ),
        InlineKeyboardButton(
            text=tr("shopping.btn_done", count=len(checked))
            if checked
            else tr("shopping.btn_done_none"),
            callback_data=ListAction(action="show", view=VIEW_DONE).pack(),
            style=STYLE_DONE if checked else None,
        ),
    ]
    if checked and not unchecked:
        # Everything is bought: offer the clean-up right here.
        controls.append(
            InlineKeyboardButton(
                text=tr("shopping.btn_clear", count=len(checked)),
                callback_data=ListAction(action="clear_ask", view=VIEW_OPEN).pack(),
                style=STYLE_DESTRUCTIVE,
            )
        )
    rows.append(controls)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _render_done(
    name: str, checked: list[JSON], unchecked: list[JSON], tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    shown = sorted(checked, key=lambda i: i.get("updatedAt") or "", reverse=True)
    text = tr("shopping.done_header", count=len(checked)) if checked else tr("shopping.done_empty")
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
                style=STYLE_DESTRUCTIVE,
            )
        )
    rows.append(controls)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _render_clear_question(
    name: str, checked: list[JSON], tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    if not checked:
        return _render_done(name, [], [], tr)
    struck = [f"<s>{escape(item_display(i, tr.language))}</s>" for i in checked[:MAX_QUOTE_ITEMS]]
    if len(checked) > MAX_QUOTE_ITEMS:
        struck.append(tr("shopping.more", count=len(checked) - MAX_QUOTE_ITEMS))
    text = (
        tr("shopping.clear_question", count=len(checked))
        + "\n<blockquote expandable>"
        + "\n".join(struck)
        + "</blockquote>\n"
        + tr("shopping.clear_hint")
    )
    # Cancel left, the destructive confirmation right, as in Telegram's own dialogs.
    rows = [
        [
            InlineKeyboardButton(
                text=tr("shopping.btn_cancel"),
                callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
            ),
            InlineKeyboardButton(
                text=tr("shopping.btn_clear_yes"),
                callback_data=ListAction(action="clear", view=VIEW_OPEN).pack(),
                style=STYLE_DESTRUCTIVE,
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
    """Fill rows in list order: short names three to a row, medium ones two, long ones alone.

    A row takes the next item as long as every item in it (the new one included)
    allows that many per row, so the order of the list is kept.
    """
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    capacity = 0
    for item in items:
        text = _truncate(item_display(item, language))
        button = InlineKeyboardButton(
            text=text, callback_data=ItemAction(action=action, item_id=item["id"], view=view).pack()
        )
        size = _row_size(text)
        if row and len(row) < min(capacity, size):
            row.append(button)
            capacity = min(capacity, size)
        else:
            if row:
                rows.append(row)
            row, capacity = [button], size
    if row:
        rows.append(row)
    return rows


def list_chooser(
    lists: list[JSON], active_id: str, tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    """The list chooser, shown inside the live message; Cancel returns to the list."""
    rows = [
        [
            InlineKeyboardButton(
                text=_truncate(item.get("name") or "?"),
                callback_data=SelectList(list_id=item["id"]).pack(),
                style=STYLE_CATEGORY if item["id"] == active_id else None,
            )
        ]
        for item in lists
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("shopping.btn_cancel"),
                callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
            )
        ]
    )
    return tr("shopping.choose_list"), InlineKeyboardMarkup(inline_keyboard=rows)
