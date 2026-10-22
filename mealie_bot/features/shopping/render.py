"""Render a shopping list as Telegram text plus inline keyboard."""

from __future__ import annotations

from html import escape

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.i18n import Translator
from mealie_bot.mealie.client import JSON

# Telegram allows 100 buttons per keyboard; keep room for headers and controls.
MAX_ITEM_BUTTONS = 80
MAX_BUTTON_TEXT = 60

VIEW_OPEN = "open"
VIEW_DONE = "done"


class ItemAction(CallbackData, prefix="it"):
    action: str  # "check" | "uncheck"
    item_id: str
    view: str


class ListAction(CallbackData, prefix="ls"):
    action: str  # "show" | "clear" | "noop"
    view: str = VIEW_OPEN


class SelectList(CallbackData, prefix="sel"):
    list_id: str


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


def item_display(item: JSON, language: str) -> str:
    display = (item.get("display") or "").strip()
    if display:
        return display
    parts: list[str] = []
    quantity = item.get("quantity") or 0
    unit = item.get("unit") or {}
    food = item.get("food") or {}
    if quantity and (quantity != 1 or unit):
        parts.append(format_quantity(quantity, language))
    if unit:
        unit_name = unit.get("abbreviation") if unit.get("useAbbreviation") else unit.get("name")
        parts.append(str(unit_name or ""))
    if food:
        parts.append(str(food.get("name") or ""))
    if item.get("note"):
        parts.append(item["note"])
    return " ".join(p for p in parts if p) or "?"


def _truncate(text: str) -> str:
    return text if len(text) <= MAX_BUTTON_TEXT else text[: MAX_BUTTON_TEXT - 1] + "…"


def _sort_key(item: JSON) -> tuple[int, str, int]:
    label = (item.get("label") or {}).get("name")
    return (label is None, (label or "").casefold(), item.get("position") or 0)


def render_list(
    list_name: str, items: list[JSON], view: str, tr: Translator
) -> tuple[str, InlineKeyboardMarkup]:
    language = tr.language
    checked = [i for i in items if i.get("checked")]
    unchecked = [i for i in items if not i.get("checked")]
    name = escape(list_name)
    rows: list[list[InlineKeyboardButton]] = []

    if view == VIEW_DONE:
        shown = sorted(checked, key=lambda i: i.get("updatedAt") or "", reverse=True)
        text = (
            tr("shopping.done_header", list=name, count=len(checked))
            if checked
            else tr("shopping.done_empty", list=name)
        )
        for item in shown[:MAX_ITEM_BUTTONS]:
            rows.append([_item_button("↩️ ", item, "uncheck", view, language)])
    else:
        shown = sorted(unchecked, key=_sort_key)
        text = (
            tr("shopping.list_header", list=name, count=len(unchecked))
            if unchecked
            else tr("shopping.list_empty", list=name)
        )
        current_label: object = object()
        for item in shown[:MAX_ITEM_BUTTONS]:
            label = (item.get("label") or {}).get("name")
            if label != current_label and len({_sort_key(i)[:2] for i in shown}) > 1:
                current_label = label
                header = f"— {label or tr('shopping.label_none')} —"
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=_truncate(header),
                            callback_data=ListAction(action="noop", view=view).pack(),
                        )
                    ]
                )
            rows.append([_item_button("⬜ ", item, "check", view, language)])

    hidden = len(shown) - MAX_ITEM_BUTTONS
    if hidden > 0:
        text += "\n" + tr("shopping.more", count=hidden)

    if view == VIEW_DONE:
        controls = [
            InlineKeyboardButton(
                text=tr("shopping.btn_open"),
                callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
            )
        ]
        if checked:
            controls.append(
                InlineKeyboardButton(
                    text=tr("shopping.btn_clear", count=len(checked)),
                    callback_data=ListAction(action="clear", view=VIEW_DONE).pack(),
                )
            )
    else:
        controls = [
            InlineKeyboardButton(
                text=tr("shopping.btn_refresh"),
                callback_data=ListAction(action="show", view=VIEW_OPEN).pack(),
            ),
            InlineKeyboardButton(
                text=tr("shopping.btn_done", count=len(checked)),
                callback_data=ListAction(action="show", view=VIEW_DONE).pack(),
            ),
        ]
    rows.append(controls)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _item_button(
    prefix: str, item: JSON, action: str, view: str, language: str
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=_truncate(prefix + item_display(item, language)),
        callback_data=ItemAction(action=action, item_id=item["id"], view=view).pack(),
    )
