"""English catalog (reference)."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Start the bot"),
    "help": ("help", "How to use the bot"),
    "list": ("list", "Show the shopping list"),
    "lists": ("lists", "Choose a shopping list"),
    "clear": ("clear", "Remove ticked-off items"),
}

MESSAGES: dict[str, str] = {
    # Shown in the bot's profile ("What can this bot do?") and in chat lists.
    "bot.description": (
        "Your Mealie shopping list in Telegram: send what you need, "
        "tap to tick items off, everyone sees the same list."
    ),
    "bot.short_description": "Shopping list for your Mealie instance.",
    "start": (
        "👋 <b>Hi! I am your shopping list.</b>\n\n"
        "Just send me what you need:\n"
        "<code>2 l milk, 500 g flour, eggs</code>\n\n"
        "<blockquote expandable>💡 <b>Tips and commands</b>\n"
        "Quantities go in front or at the end: <code>milk 2l</code>, "
        "<code>3x lemons</code>, <code>½ bread</code>\n"
        "One item per line, or separated by commas\n"
        "/{list} shows the list, tap an item to tick it off\n"
        "/{lists} switches lists · /{clear} removes ticked-off items · /{help}</blockquote>"
    ),
    "help": (
        "<b>🛒 Shopping list</b>\n"
        "Send items as text, one per line or separated by commas. "
        "Quantities and units are optional:\n"
        "<code>2 l milk</code> · <code>milk 2l</code> · <code>3x lemons</code> · "
        "<code>500g flour</code>\n\n"
        "/{list} shows the list. Tap a category to open it, tap an item to tick it off.\n"
        "/{lists} switches to another shopping list.\n"
        "/{clear} removes all ticked-off items after asking.\n\n"
        "<blockquote expandable>💡 <b>How the list behaves</b>\n"
        "There is always one list message, at the bottom of the chat. "
        "When you add items it moves down, and the old message turns into a short "
        "history entry.\n"
        "<b>Undo</b> removes what you just added.\n"
        "A word counts as a unit only if Mealie knows it, so <code>7up</code> stays a name."
        "</blockquote>"
    ),
    "help.no_features": "No features are enabled.",
    "error.mealie": "Mealie is not reachable right now. Please try again later.",
    "error.no_lists": "There is no shopping list in Mealie yet. Create one in Mealie first.",
    "error.not_understood": "I could not find any items in that message.",
    "error.too_many": "That is more than {max} items in one message. Please split it up.",
    "error.too_long": "One item is longer than {max} characters. Please shorten it.",
    # List message
    "shopping.list_header": "🛒 <b>{list}</b>",
    "shopping.list_counts": "{open} open · {done} done",
    "shopping.list_empty": "Nothing to buy. 🎉",
    "shopping.list_all_done": "Everything bought. 🎉",
    "shopping.added_header": "➕ <b>Added</b> ({count})",
    "shopping.done_quote": "✅ <b>Done</b> ({count})",
    "shopping.updated_at": "<i>As of {time}</i>",
    "shopping.more": "… and {count} more (open Mealie to see all)",
    "shopping.label_none": "Other",
    "shopping.done_header": "✅ <b>{list}</b> · {count} done\n<i>Tap an item to put it back.</i>",
    "shopping.done_empty": "✅ <b>{list}</b>\nNo ticked-off items.",
    "shopping.clear_question": "🧹 <b>Remove {count} ticked-off items from {list}?</b>",
    "shopping.clear_hint": "<i>This deletes them from Mealie for good.</i>",
    # Buttons
    "shopping.btn_refresh": "🔄 Refresh",
    "shopping.btn_undo": "↩️ Undo",
    "shopping.btn_done": "✅ Done ({count})",
    "shopping.btn_open": "⬅️ Open ({count})",
    "shopping.btn_clear": "🧹 Remove ({count})",
    "shopping.btn_clear_yes": "🧹 Yes, remove",
    "shopping.btn_cancel": "Cancel",
    # Toasts (answerCallbackQuery)
    "shopping.toast_checked": "✓ {item}",
    "shopping.toast_unchecked": "↩️ {item} is back on the list",
    "shopping.toast_undone": "↩️ Undone: {count} entries",
    "shopping.toast_nothing_to_undo": "Nothing to undo any more.",
    "shopping.cleared": "🧹 Removed {count} ticked-off items.",
    "shopping.item_gone": "That item no longer exists.",
    # Lists
    "shopping.choose_list": "📋 <b>Which shopping list?</b>",
    # History entries (old list messages are rewritten into these)
    "history.header": "<i>📜 {list}</i>",
    "history.line": "<i>{time} · {user}</i> {what}",
    "history.added": "➕ {items}",
    "history.checked": "✅ {items}",
    "history.unchecked": "↩️ {items}",
    "history.cleared": "🧹 {count} removed",
    "history.undone": "↩️ {count} undone",
}

UNITS: dict[str, list[str]] = {
    "g": ["g", "gram", "grams", "gramme", "grammes"],
    "kg": ["kg", "kilo", "kilos", "kilogram", "kilograms"],
    "ml": ["ml", "milliliter", "milliliters", "millilitre", "millilitres"],
    "l": ["l", "liter", "liters", "litre", "litres"],
    "piece": ["pc", "pcs", "piece", "pieces"],
    "pack": ["pack", "packs", "pkg", "package", "packages"],
    "can": ["can", "cans", "tin", "tins"],
    "bottle": ["bottle", "bottles"],
    "bunch": ["bunch", "bunches"],
    "tbsp": ["tbsp", "tablespoon", "tablespoons"],
    "tsp": ["tsp", "teaspoon", "teaspoons"],
    "cup": ["cup", "cups"],
}
