"""English catalog (reference)."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Start the bot"),
    "help": ("help", "How to use the bot"),
    "list": ("list", "Show the shopping list"),
    "lists": ("lists", "Choose a shopping list"),
    "clear": ("clear", "Remove ticked-off items"),
}

MESSAGES: dict[str, str] = {
    "start": (
        "Hi! I manage your Mealie shopping list.\n\n"
        "Send me what you need, one item per line or separated by commas, "
        "for example <code>2 l milk, 500 g flour, eggs</code>.\n"
        "Use /{list} to see the list and tap an item to tick it off."
    ),
    "help": (
        "<b>Shopping list</b>\n"
        "• Send items as text: one per line or separated by commas.\n"
        "  Quantities and units are optional: <code>2 l milk</code>, <code>milk 2l</code>, "
        "<code>3x lemons</code>.\n"
        "• /{list} shows open items. Tap an item to tick it off.\n"
        "• /{lists} switches to another shopping list.\n"
        "• /{clear} removes all ticked-off items."
    ),
    "help.no_features": "No features are enabled.",
    "error.mealie": "Mealie is not reachable right now. Please try again later.",
    "error.no_lists": "There is no shopping list in Mealie yet. Create one in Mealie first.",
    "error.not_understood": "I could not find any items in that message.",
    "shopping.added": "Added to <b>{list}</b>:\n{items}",
    "shopping.list_header": "🛒 <b>{list}</b> · {count} open",
    "shopping.list_empty": "🛒 <b>{list}</b>\nNothing to buy. 🎉",
    "shopping.done_header": "✅ <b>{list}</b> · {count} ticked off\nTap an item to put it back.",
    "shopping.done_empty": "✅ <b>{list}</b>\nNo ticked-off items.",
    "shopping.more": "… and {count} more (open Mealie to see all)",
    "shopping.label_none": "Other",
    "shopping.btn_refresh": "🔄 Refresh",
    "shopping.btn_done": "✅ Ticked off ({count})",
    "shopping.btn_open": "⬅️ Open items",
    "shopping.btn_clear": "🧹 Remove ticked off ({count})",
    "shopping.btn_show": "📋 Show list",
    "shopping.cleared": "Removed {count} ticked-off items.",
    "shopping.choose_list": "Which shopping list do you want to use?",
    "shopping.list_selected": "Now using <b>{list}</b>.",
    "shopping.item_gone": "That item no longer exists.",
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
