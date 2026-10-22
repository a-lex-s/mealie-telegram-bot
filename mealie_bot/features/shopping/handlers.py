"""Telegram handlers for the shopping list feature."""

from __future__ import annotations

import logging
from contextlib import suppress
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from mealie_bot.features import FeatureContext
from mealie_bot.features.shopping.parser import parse_message
from mealie_bot.features.shopping.render import (
    VIEW_OPEN,
    ItemAction,
    ListAction,
    SelectList,
    entry_display,
    render_list,
)
from mealie_bot.features.shopping.service import NoShoppingListError, ShoppingService
from mealie_bot.i18n import Translator, command_names
from mealie_bot.mealie import MealieError, MealieNotFound

log = logging.getLogger(__name__)


def build_router(context: FeatureContext) -> Router:
    service = ShoppingService(context.mealie, default_list=context.settings.shopping_list)
    router = Router(name="shopping")

    async def send_error(target: Message, tr: Translator, exc: Exception) -> None:
        if isinstance(exc, NoShoppingListError):
            await target.answer(tr("error.no_lists"))
        else:
            log.warning("Mealie request failed: %s", exc)
            await target.answer(tr("error.mealie"))

    async def show_list(message: Message, user_id: int, tr: Translator, view: str) -> None:
        shopping_list = await service.active_list(user_id)
        data = await service.view(shopping_list["id"])
        text, markup = render_list(data.name, data.items, view, tr)
        await message.answer(text, reply_markup=markup)

    async def refresh(query: CallbackQuery, tr: Translator, view: str) -> None:
        shopping_list = await service.active_list(query.from_user.id)
        data = await service.view(shopping_list["id"])
        text, markup = render_list(data.name, data.items, view, tr)
        if isinstance(query.message, Message):
            try:
                await query.message.edit_text(text, reply_markup=markup)
            except TelegramBadRequest as exc:
                if "message is not modified" not in str(exc):
                    raise

    @router.message(Command(*command_names("list")))
    async def cmd_list(message: Message, tr: Translator) -> None:
        try:
            await show_list(message, message.from_user.id, tr, VIEW_OPEN)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)

    @router.message(Command(*command_names("lists")))
    async def cmd_lists(message: Message, tr: Translator) -> None:
        try:
            lists = await service.lists()
            if not lists:
                raise NoShoppingListError
            active = await service.active_list(message.from_user.id)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        rows = [
            [
                InlineKeyboardButton(
                    text=("● " if item["id"] == active["id"] else "") + (item.get("name") or "?"),
                    callback_data=SelectList(list_id=item["id"]).pack(),
                )
            ]
            for item in lists
        ]
        await message.answer(
            tr("shopping.choose_list"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )

    @router.message(Command(*command_names("clear")))
    async def cmd_clear(message: Message, tr: Translator) -> None:
        try:
            shopping_list = await service.active_list(message.from_user.id)
            count = await service.clear_checked(shopping_list["id"])
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        await message.answer(tr("shopping.cleared", count=count))

    @router.message(F.text & ~F.text.startswith("/"))
    async def add_items(message: Message, tr: Translator) -> None:
        try:
            units = await service.units()
            entries = parse_message(message.text or "", units.known_tokens)
            if not entries:
                await message.answer(tr("error.not_understood"))
                return
            shopping_list = await service.active_list(message.from_user.id)
            await service.add_entries(shopping_list["id"], entries)
        except (MealieError, NoShoppingListError) as exc:
            await send_error(message, tr, exc)
            return
        lines = "\n".join(f"• {escape(entry_display(e, tr.language))}" for e in entries)
        show = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=tr("shopping.btn_show"),
                        callback_data=ListAction(action="new", view=VIEW_OPEN).pack(),
                    )
                ]
            ]
        )
        await message.answer(
            tr("shopping.added", list=escape(shopping_list.get("name") or ""), items=lines),
            reply_markup=show,
        )

    @router.callback_query(ItemAction.filter())
    async def on_item(query: CallbackQuery, callback_data: ItemAction, tr: Translator) -> None:
        try:
            await service.set_checked(callback_data.item_id, callback_data.action == "check")
        except MealieNotFound:
            await query.answer(tr("shopping.item_gone"))
        except MealieError as exc:
            log.warning("Mealie request failed: %s", exc)
            await query.answer(tr("error.mealie"), show_alert=True)
            return
        else:
            await query.answer()
        try:
            await refresh(query, tr, callback_data.view)
        except (MealieError, NoShoppingListError) as exc:
            log.warning("Refreshing list failed: %s", exc)

    @router.callback_query(ListAction.filter())
    async def on_list(query: CallbackQuery, callback_data: ListAction, tr: Translator) -> None:
        if callback_data.action == "noop":
            await query.answer()
            return
        try:
            if callback_data.action == "new" and isinstance(query.message, Message):
                await query.answer()
                await show_list(query.message, query.from_user.id, tr, VIEW_OPEN)
                return
            if callback_data.action == "clear":
                shopping_list = await service.active_list(query.from_user.id)
                count = await service.clear_checked(shopping_list["id"])
                await query.answer(tr("shopping.cleared", count=count))
                await refresh(query, tr, VIEW_OPEN)
                return
            await query.answer()
            await refresh(query, tr, callback_data.view)
        except (MealieError, NoShoppingListError) as exc:
            log.warning("Mealie request failed: %s", exc)
            with suppress(TelegramBadRequest):
                await query.answer(tr("error.mealie"), show_alert=True)

    @router.callback_query(SelectList.filter())
    async def on_select(query: CallbackQuery, callback_data: SelectList, tr: Translator) -> None:
        service.select_list(query.from_user.id, callback_data.list_id)
        try:
            shopping_list = await service.active_list(query.from_user.id)
        except (MealieError, NoShoppingListError) as exc:
            log.warning("Mealie request failed: %s", exc)
            await query.answer(tr("error.mealie"), show_alert=True)
            return
        await query.answer()
        if isinstance(query.message, Message):
            await query.message.edit_text(
                tr("shopping.list_selected", list=escape(shopping_list.get("name") or ""))
            )

    return router
