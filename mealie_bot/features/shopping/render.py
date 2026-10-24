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

from mealie_bot.features.shopping.service import AddResult, AssignResult
from mealie_bot.i18n import Translator
from mealie_bot.i18n.labels import (
    FALLBACK_EMOJI,
    LabelIcons,
    color_circle,
    find_label_emoji,
    split_label_name,
)
from mealie_bot.mealie.client import JSON

# Either the full display settings or just the LABEL_EMOJI overrides.
Icons = LabelIcons | Mapping[str, str] | None

# Telegram allows 100 buttons per keyboard; item buttons and category headers share
# this budget, the rest is room for the control row.
MAX_ITEM_BUTTONS = 80
# The sort picker shows this many category buttons besides New, Skip and Back.
MAX_SORT_LABELS = MAX_ITEM_BUTTONS - 3
# Telegram ellipsises long button texts itself; cut earlier so our "…" lands after the name.
MAX_BUTTON_TEXT = 40
# Telegram messages hold 4096 characters; quotes list at most this many items.
MAX_QUOTE_ITEMS = 20
# answerCallbackQuery accepts at most 200 characters.
MAX_TOAST_TEXT = 200
PROGRESS_CELLS = 10
# Buttons in one row share its width equally, so short names are packed together.
_ROW_SIZES = ((10, 3), (18, 2))

VIEW_OPEN = "open"
VIEW_DONE = "done"
VIEW_CLEAR = "clear"  # confirmation before deleting ticked-off items
VIEW_LISTS = "lists"  # choose the active list
VIEW_SORT = "sort"  # sort the items under "Other" into categories, one at a time

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


class SortAction(CallbackData, prefix="so"):
    """A tap in the sort picker (or on the button that opens it)."""

    # "start" | "pick" | "new" | "skip" | "back" | "food_use" | "food_new" | "food_back"
    action: str
    arg: str = ""  # label id for "pick", food id for "food_use"


class AssignAnswer(CallbackData, prefix="as"):
    """Answer to a question asked while sorting products into a category."""

    # "label_new" | "label_use" | "food_new" | "food_use" | "cancel"
    action: str
    arg: str = ""  # label id or food id for "*_use"


@dataclass
class SortQuestion:
    """The sort picker asks whether a note item means a similar existing product."""

    item_id: str
    label_id: str  # the category that was tapped
    food_id: str
    food_name: str


@dataclass
class ListState:
    """Per-message display state of a list message."""

    view: str = VIEW_OPEN
    # The list this message shows; None until first rendered (then the user's active list).
    list_id: str | None = None
    expanded: set[str] = field(default_factory=set)
    added: list[JSON] = field(default_factory=list)
    # Products just sorted into a category: (name, label) pairs, shown like ``added``.
    sorted_into: list[tuple[str, JSON]] = field(default_factory=list)
    # One extra HTML line above the list, e.g. "category created".
    notice: str = ""
    # What the last change on this message did, as long as it can be undone.
    undo: AddResult | AssignResult | None = None
    # The sort picker (VIEW_SORT): item ids still to sort, how many there were,
    # and what was sorted so far (it becomes ``undo`` when the picker closes).
    sort_queue: list[str] = field(default_factory=list)
    sort_total: int = 0
    sort_result: AssignResult | None = None
    # Open "did you mean" question for the current item, if any.
    sort_question: SortQuestion | None = None

    def toggle(self, label_key: str) -> None:
        if label_key in self.expanded:
            self.expanded.discard(label_key)
        else:
            self.expanded.add(label_key)

    def start_sort(self, items: list[JSON]) -> None:
        self.view = VIEW_SORT
        self.sort_queue = [str(item["id"]) for item in uncategorised(items)]
        self.sort_total = len(self.sort_queue)
        self.sort_result = AssignResult()
        self.sort_question = None

    def sort_current(self, items: list[JSON]) -> JSON | None:
        """The item the picker asks about. Items that were ticked off, deleted or
        sorted elsewhere in the meantime are dropped from the queue."""
        waiting = {str(item["id"]): item for item in uncategorised(items)}
        while self.sort_queue and self.sort_queue[0] not in waiting:
            self.sort_queue.pop(0)
        return waiting[self.sort_queue[0]] if self.sort_queue else None

    @property
    def sort_index(self) -> int:
        """1-based position of the current item among all items the picker started with."""
        return self.sort_total - len(self.sort_queue) + 1

    def finish_sort(self) -> None:
        """Close the picker; what was sorted is shown like an arrow sorting, with Undo."""
        result = self.sort_result
        self.view = VIEW_OPEN
        self.sort_queue, self.sort_total, self.sort_result = [], 0, None
        self.sort_question = None
        if result is not None and result.assigned:
            self.added = []
            self.sorted_into = list(result.assigned)
            self.undo = result if result.undoable else None
            self.expanded |= {str(label["id"]) for _, label in result.assigned}


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


def uncategorised(items: list[JSON]) -> list[JSON]:
    """Open items under "Other", in list order: what the sort picker goes through."""
    waiting = [i for i in items if not i.get("checked") and label_key(i) == NO_LABEL]
    return sorted(waiting, key=lambda i: i.get("position") or 0)


def label_name(item: JSON, tr: Translator) -> str:
    return str((item.get("label") or {}).get("name") or tr("shopping.label_none"))


def label_text(name: str, color: str | None = None, emoji: Icons = None) -> str:
    """Plain text for a label: colour circle, emoji, name (``🟢 🧂 Würzmittel``).

    A label without an emoji match shows just its colour circle (``🟢 Drogerie``);
    the fallback 📦 appears only when there is neither. An emoji that is part of
    the Mealie name is shown once, in front of the rest. ``LABEL_ICONS`` can
    switch circles, emojis or both off (``LabelIcons``).
    """
    icons = emoji if isinstance(emoji, LabelIcons) else LabelIcons(overrides=emoji or {})
    circle = color_circle(color) if icons.circles else ""
    _, plain = split_label_name(name)
    found = ""
    if icons.emojis:
        found = find_label_emoji(name, icons.overrides) or ("" if circle else FALLBACK_EMOJI)
    return " ".join(part for part in (circle, found, plain or name) if part)


def label_dict_text(label: JSON | None, tr: Translator, emoji: Icons) -> str:
    """``label_text`` for a Mealie label dict; ``None`` is "Other"."""
    if not label:
        return label_text(tr("shopping.label_none"), None, emoji)
    return label_text(str(label.get("name") or "?"), label.get("color"), emoji)


def _truncate(text: str, limit: int = MAX_BUTTON_TEXT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def toast_text(text: str) -> str:
    """Cut a toast to what Telegram accepts."""
    return _truncate(text, MAX_TOAST_TEXT)


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


def _group(
    items: list[JSON], tr: Translator, label_order: Mapping[str, int] | None = None
) -> list[tuple[str, JSON | None, list[JSON]]]:
    """Group open items by label: (label key, label dict or None, items).

    Labels follow the order set in Mealie for the list (``label_order``), labels
    without a position come after them alphabetically, "Other" is last.
    """
    groups: dict[str, tuple[JSON | None, list[JSON]]] = {}
    for item in items:
        key = label_key(item)
        groups.setdefault(key, (item.get("label") or None, []))[1].append(item)
    order = label_order or {}
    ordered = sorted(
        groups.items(),
        key=lambda kv: (
            kv[0] == NO_LABEL,
            kv[0] not in order,
            order.get(kv[0], 0),
            str((kv[1][0] or {}).get("name") or "").casefold(),
        ),
    )
    return [
        (key, label, sorted(group, key=lambda i: i.get("position") or 0))
        for key, (label, group) in ordered
    ]


def category_title(
    name: str,
    count: int,
    expanded: bool,
    emoji: Icons,
    color: str | None = None,
) -> str:
    """Text of a category header button: ``🟢 🧂 Würzmittel (2) ▾``."""
    arrow = "▾" if expanded else "▸"
    return f"{label_text(name, color, emoji)} ({count}) {arrow}"


def render_list(
    list_name: str,
    items: list[JSON],
    state: ListState,
    tr: Translator,
    now: datetime | None = None,
    emoji: Icons = None,
    lists: list[JSON] | None = None,
    active_id: str = "",
    label_order: Mapping[str, int] | None = None,
    labels: list[JSON] | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Render the list message; ``emoji`` says how categories are shown (``LabelIcons``,
    or just the ``LABEL_EMOJI`` overrides),
    ``label_order`` the category positions from Mealie's list settings.

    ``lists`` and ``active_id`` are only needed for the list chooser view,
    ``labels`` (all Mealie labels) only for the sort picker.
    """
    language = tr.language
    checked = [i for i in items if i.get("checked")]
    unchecked = [i for i in items if not i.get("checked")]
    name = escape(list_name)

    if state.view == VIEW_LISTS:
        return list_chooser(lists or [], active_id, tr)
    if state.view == VIEW_SORT:
        current = state.sort_current(items)
        if current is not None:
            return render_sort(name, current, state, tr, labels or [], emoji, label_order)
    if state.view == VIEW_CLEAR:
        return _render_clear_question(name, checked, tr)
    if state.view == VIEW_DONE:
        return _render_done(name, checked, unchecked, tr)

    time_text = now.strftime("%H:%M") if now is not None else ""
    lines = [tr("shopping.list_header", list=name)]
    if items:
        # A bar line, then "3 open · 1 done · 21:12"; the bar and the done count
        # appear once something is done.
        if checked:
            lines.append(f"<code>{progress_bar(len(checked), len(items))}</code>")
        status = tr("shopping.count_open", count=len(unchecked))
        if checked:
            status += " · " + tr("shopping.count_done", count=len(checked))
        if time_text:
            status += f" · <i>{time_text}</i>"
        lines.append(status)
    if not unchecked:
        lines.append(tr("shopping.list_all_done" if checked else "shopping.list_empty"))
        if not items and time_text:
            lines.append(tr("shopping.updated_at", time=time_text))
    if state.notice:
        lines.append(state.notice)
    if state.added:
        added_lines = [
            item_html(item, language, escape(label_dict_text(item.get("label"), tr, emoji)))
            for item in state.added
        ]
        if len(added_lines) == 1:
            lines.append(tr("shopping.added_one", item=added_lines[0]))
        else:
            lines.append(
                _quote(tr("shopping.added_header", count=len(added_lines)), added_lines, tr)
            )
    if state.sorted_into:
        sorted_lines = [
            f"<b>{escape(name)}</b> · <i>{escape(label_dict_text(label, tr, emoji))}</i>"
            for name, label in state.sorted_into
        ]
        if len(sorted_lines) == 1:
            lines.append(tr("shopping.sorted_one", item=sorted_lines[0]))
        else:
            lines.append(
                _quote(tr("shopping.sorted_header", count=len(sorted_lines)), sorted_lines, tr)
            )
    if checked:
        done_lines = [f"<s>{escape(item_display(i, language))}</s>" for i in checked]
        lines.append(_quote(tr("shopping.done_quote"), done_lines, tr))

    rows: list[list[InlineKeyboardButton]] = []
    groups = _group(unchecked, tr, label_order)
    # Category headers and the Sort button come out of the same budget as the items.
    has_other = any(key == NO_LABEL for key, _, _ in groups)
    budget = MAX_ITEM_BUTTONS - (len(groups) if len(groups) > 1 else 0) - has_other
    shown = 0
    hidden = 0
    for key, label, group in groups:
        expanded = len(groups) == 1 or key in state.expanded
        if len(groups) > 1:
            group_name = str((label or {}).get("name") or tr("shopping.label_none"))
            color = (label or {}).get("color")
            rows.append(
                [
                    InlineKeyboardButton(
                        text=_truncate(
                            category_title(group_name, len(group), expanded, emoji, color)
                        ),
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
        if key == NO_LABEL:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=tr("sort.btn_start", count=len(group)),
                        callback_data=SortAction(action="start").pack(),
                        style=STYLE_DONE,
                    )
                ]
            )
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


def suggest_labels(
    item_name: str,
    labels: list[JSON],
    emoji: Icons = None,
    label_order: Mapping[str, int] | None = None,
) -> list[JSON]:
    """Labels in the order the sort picker offers them for ``item_name``.

    A label whose emoji the keyword table also finds in the product name comes
    first ("Milch" → 🥛 → "Milchprodukte"), then the list's own category order,
    then the rest by name. A suggestion only; the user always picks.
    """
    overrides = emoji.overrides if isinstance(emoji, LabelIcons) else (emoji or {})
    hint = find_label_emoji(item_name)
    order = label_order or {}

    def key(label: JSON) -> tuple[bool, bool, int, str]:
        name = str(label.get("name") or "")
        matches = hint is not None and find_label_emoji(name, overrides) == hint
        label_id = str(label.get("id"))
        return (
            not matches,
            label_id not in order,
            order.get(label_id, 0),
            split_label_name(name)[1].casefold(),
        )

    return sorted(labels, key=key)


def render_sort(
    name: str,
    item: JSON,
    state: ListState,
    tr: Translator,
    labels: list[JSON],
    emoji: Icons = None,
    label_order: Mapping[str, int] | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """The sort picker inside the list message: one item, one button per category."""
    item_name = item_parts(item, tr.language)[0]
    lines = [
        tr("shopping.list_header", list=name),
        tr("sort.header", index=state.sort_index, total=state.sort_total),
        tr("sort.question", item=escape(item_display(item, tr.language))),
    ]
    question = state.sort_question
    if question is not None and question.item_id == str(item.get("id")):
        lines[-1] = tr("assign.ask_food", name=escape(item_name), food=escape(question.food_name))
        return "\n".join(lines), InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_truncate(tr("assign.btn_food_use", food=question.food_name)),
                        callback_data=SortAction(action="food_use", arg=question.food_id).pack(),
                        style=STYLE_DONE,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_truncate(tr("assign.btn_food_new", name=item_name)),
                        callback_data=SortAction(action="food_new").pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=tr("sort.btn_food_back"),
                        callback_data=SortAction(action="food_back").pack(),
                    )
                ],
            ]
        )
    ordered = suggest_labels(item_name, labels, emoji, label_order)
    shown = ordered[:MAX_SORT_LABELS]
    if not labels:
        lines.append(tr("sort.no_labels"))
    elif len(ordered) > len(shown):
        lines.append(tr("sort.more_labels", count=len(ordered) - len(shown)))
    buttons = [
        InlineKeyboardButton(
            text=_truncate(label_dict_text(label, tr, emoji)),
            callback_data=SortAction(action="pick", arg=str(label["id"])).pack(),
            style=STYLE_CATEGORY,
        )
        for label in shown
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("sort.btn_new"),
                callback_data=SortAction(action="new").pack(),
                style=STYLE_DONE,
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("sort.btn_skip"), callback_data=SortAction(action="skip").pack()
            ),
            InlineKeyboardButton(
                text=tr("sort.btn_back"), callback_data=SortAction(action="back").pack()
            ),
        ]
    )
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
