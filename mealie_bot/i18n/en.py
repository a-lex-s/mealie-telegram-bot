"""English catalog (reference)."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Start the bot"),
    "list": ("list", "Show the list"),
    "clear": ("clear", "Remove ticked-off items"),
    "lists": ("lists", "Switch list"),
    "category": ("category", "Create a category"),
    "categories": ("categories", "Show categories"),
    "help": ("help", "Help"),
    # Answered, but not published in the command menu.
    "version": ("version", "Show the version"),
}

MESSAGES: dict[str, str] = {
    # Shown in the bot's profile ("What can this bot do?") and in chat lists.
    "bot.description": (
        "Your Mealie shopping list in Telegram: send what you need, "
        "tap to tick items off, everyone sees the same list."
    ),
    "bot.short_description": "Shopping list for your Mealie instance",
    # /start and /help: a short intro, then one section per enabled feature.
    "start": "👋 <b>Hi!</b>",
    "help": "<b>Help</b> · /{help} shows this again.",
    "start.shopping": (
        "<b>I am your shopping list.</b> "
        "Just send me what you need:\n"
        "<code>2 l milk, 500 g flour, eggs</code>\n\n"
        "<blockquote expandable>💡 <b>Tips and commands</b>\n"
        "Quantities go in front or at the end: <code>milk 2l</code>, "
        "<code>3x lemons</code>, <code>½ bread</code>\n"
        "One item per line, or separated by commas\n"
        "/{list} shows the list, tap an item to tick it off\n"
        "<code>Ketchup → Condiments</code> puts a product into a category\n"
        "/{lists} switches lists · /{clear} removes ticked-off items · "
        "/{help} shows this again</blockquote>"
    ),
    "help.shopping": (
        "<b>🛒 Shopping list</b>\n"
        "Send items as text, one per line or separated by commas. "
        "Quantities and units are optional:\n"
        "<code>2 l milk</code> · <code>milk 2l</code> · <code>3x lemons</code> · "
        "<code>500g flour</code>\n\n"
        "/{list} shows the list. Tap a category to open it, tap an item to tick it off.\n"
        "/{lists} switches to another shopping list.\n"
        "/{clear} removes all ticked-off items after a confirmation.\n\n"
        "<b>🏷️ Categories</b>\n"
        "<code>Ketchup → Condiments</code> puts a product into a category, for good "
        "(also <code>-></code>, <code>=></code> or <code>></code>; several products: "
        "<code>Mustard, Mayo → Condiments</code>). "
        "A new category is created after you confirm; a product Mealie does not know yet "
        "is created too.\n"
        "Under <i>Other</i>, <b>🏷️ Sort</b> goes through the items one by one, "
        "one tap per product.\n"
        "/{category} creates a category, /{categories} shows them all.\n\n"
        "<blockquote expandable>💡 <b>How the list behaves</b>\n"
        "There is always one list message, at the bottom of the chat. "
        "When you add items it moves down, and the old message turns into a short "
        "history entry.\n"
        "<b>Undo</b> removes what you just added.\n"
        "A word counts as a unit only if Mealie knows it, so <code>7up</code> stays a name."
        "</blockquote>"
    ),
    "help.no_features": "No features are enabled.",
    "version": "🔖 <b>mealie-telegram-bot</b> {version}",
    "version.commit": "🔖 <b>mealie-telegram-bot</b> {version} · <code>{commit}</code>",
    "error.mealie": "⚠️ Mealie is not reachable right now. Please try again later.",
    "error.mealie_toast": "⚠️ Mealie is not answering. Please try again in a moment.",
    "error.no_lists": "📋 There is no shopping list in Mealie yet. Create one in Mealie first.",
    "error.not_understood": (
        "I could not find any items in that message. Example: <code>2 l milk, eggs</code>"
    ),
    "error.too_many": "⚠️ That is more than {max} items in one message. Please split it up.",
    "error.too_long": "⚠️ One item is longer than {max} characters. Please shorten it.",
    "error.telegram": (
        "⚠️ Telegram did not accept the list message. Please try again or open Mealie."
    ),
    "error.only_text": "I only understand text. Send the items as a message, or /help.",
    # Categories
    "category.usage": (
        "🏷️ Name the category: <code>/{category} Household</code>. "
        "Or sort a product directly: <code>Sponges → Household</code>"
    ),
    "category.too_long": "⚠️ A category name may have at most {max} characters.",
    "category.exists": "🏷️ The category <b>{label}</b> already exists.",
    "category.created": "🏷️ <b>New category:</b> {label}",
    "category.list_header": "🏷️ <b>Categories</b> ({count})",
    "category.list_line": "{label} · {count}",
    "category.list_none": (
        "🏷️ There are no categories yet. "
        "Create one with /{category} or with <code>Ketchup → Condiments</code>."
    ),
    "category.list_uncategorized": (
        "📦 Without category: {foods} products, {items} open on this list"
    ),
    "assign.not_understood": (
        "I could not read that. Example: <code>Ketchup → Condiments</code> "
        "or <code>Mustard, Mayo -> Condiments</code>, one category per line."
    ),
    "assign.ask_label": "❓ The category <b>{label}</b> does not exist yet.",
    "assign.btn_label_new": "➕ Create {label}",
    "assign.btn_label_use": "Use {label}",
    "assign.ask_food": "❓ I do not know <b>{name}</b>. Did you mean <b>{food}</b>?",
    "assign.btn_food_use": "Yes, {food}",
    "assign.btn_food_new": "➕ No, create {name}",
    "assign.stale": "⚠️ That question is no longer open. Please send the line again.",
    # Sort picker (button under "Other")
    "sort.btn_start": "🏷️ Sort ({count})",
    "sort.header": "🏷️ <b>Sort</b> · {index} of {total}",
    "sort.question": "<b>{item}</b> · <i>Which category?</i>",
    "sort.no_labels": "<i>There are no categories yet. Create the first one.</i>",
    "sort.more_labels": (
        "<i>… and {count} more categories: send <code>product → category</code> for those.</i>"
    ),
    "sort.more_labels.one": (
        "<i>… and 1 more category: send <code>product → category</code> for it.</i>"
    ),
    "sort.btn_food_back": "↩️ Other category",
    "sort.food_gone": "⚠️ That product no longer exists",
    "sort.btn_new": "➕ New category…",
    "sort.btn_skip": "⏭ Skip",
    "sort.btn_back": "✕ Back to the list",
    "sort.toast_sorted": "✅ {item} → {label}",
    "sort.nothing": "Nothing left to sort",
    "sort.stale": "⚠️ Sorting is no longer open",
    "sort.label_gone": "⚠️ That category no longer exists",
    "sort.ask_name": "✏️ What should the new category be called? Reply with its name.",
    "sort.ask_name_user": (
        "✏️ {user}, what should the new category be called? Reply with its name."
    ),
    "sort.name_placeholder": "Category name",
    "error.unknown_command": "I do not know that command. /help lists what I can do.",
    # List message
    "shopping.list_header": "🛒 <b>{list}</b>",
    "shopping.count_open": "{count} open",
    "shopping.count_done": "{count} done",
    "shopping.list_empty": "The list is empty.",
    "shopping.list_all_done": "🎉 All bought.",
    "shopping.added_header": "➕ <b>Added</b> ({count})",
    "shopping.added_one": "➕ <b>Added:</b> {item}",
    "shopping.sorted_header": "🏷️ <b>Sorted</b> ({count})",
    "shopping.sorted_one": "🏷️ <b>Sorted:</b> {item}",
    "shopping.done_quote": "✅ <b>Done</b>",
    "shopping.updated_at": "<i>As of {time}</i>",
    "shopping.more": "… and {count} more (open Mealie to see all)",
    "shopping.more.one": "… and 1 more (open Mealie to see all)",
    "shopping.label_none": "Other",
    "shopping.done_header": (
        "✅ <b>Done</b> · {count}\n<i>Tap an item to put it back on the list.</i>"
    ),
    "shopping.done_empty": "✅ <b>Done</b>\nNothing ticked off yet.",
    "shopping.clear_question": "🧹 Remove <b>{count}</b> ticked-off items for good?",
    "shopping.clear_question.one": "🧹 Remove <b>1</b> ticked-off item for good?",
    "shopping.clear_hint": "<i>This also deletes them in Mealie.</i>",
    # Buttons
    "shopping.btn_refresh": "🔄 Refresh",
    "shopping.btn_undo": "↩️ Undo",
    "shopping.btn_done": "✅ Done ({count})",
    "shopping.btn_done_none": "✅ Done",
    "shopping.btn_open": "🛒 Open ({count})",
    "shopping.btn_clear": "🧹 Remove ({count})",
    "shopping.btn_clear_yes": "🧹 Yes, remove",
    "shopping.btn_cancel": "✕ Cancel",
    # Toasts (answerCallbackQuery)
    "shopping.toast_checked": "✅ {item}",
    "shopping.toast_unchecked": "🔁 {item} is open again",
    "shopping.toast_undone": "↩️ Undid {count} items",
    "shopping.toast_undone.one": "↩️ Undid 1 item",
    "shopping.toast_nothing_to_undo": "Nothing left to undo",
    "shopping.cleared": "🧹 Removed {count} items",
    "shopping.cleared.one": "🧹 Removed 1 item",
    "shopping.item_gone": "⚠️ That item no longer exists, list refreshed",
    # Lists
    "shopping.choose_list": "📋 <b>Which shopping list?</b>",
    "shopping.only_list": "📋 There is only the list <b>{list}</b>.",
    "shopping.toast_refreshed": "🔄 Refreshed",
    # History entries (old list messages are rewritten into these)
    "history.header": "📜 <b>{list}</b>",
    # The one message that collects old history entries (HISTORY_FOLD_HOURS).
    "history.fold_header": "📜 <b>Earlier changes</b>",
    "history.fold_list": "<b>{list}</b>",
    # An old list message that could not be deleted (Telegram allows that for 48 hours only).
    "history.superseded": "📜 <b>{list}</b>\n<i>↓ The current list is further down.</i>",
    "history.line": "<i>{time} · {user}</i> {what}",
    # Day shown before the time for entries from another day (strftime format).
    "history.date_format": "%b %d",
    "history.line_own": "<i>{time}</i> {what}",
    "history.added": "➕ {items}",
    "history.checked": "✅ {items}",
    "history.unchecked": "🔁 {items}",
    "history.cleared": "🧹 {count} items removed",
    "history.cleared.one": "🧹 1 item removed",
    "history.undone": "↩️ {count} items undone",
    "history.undone.one": "↩️ 1 item undone",
    "history.sorted": "🏷️ {items}",
    "history.label": "🏷️ new category {items}",
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
