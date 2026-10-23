from datetime import datetime

from mealie_bot.features.shopping.render import (
    MAX_ITEM_BUTTONS,
    MAX_QUOTE_ITEMS,
    NO_LABEL,
    VIEW_CLEAR,
    VIEW_DONE,
    ItemAction,
    ListAction,
    ListState,
    format_quantity,
    item_display,
    item_html,
    item_inline,
    progress_bar,
    render_list,
)
from mealie_bot.features.shopping.service import AddResult
from mealie_bot.i18n import Translator
from tests.conftest import make_item

EN = Translator("en")
DE = Translator("de")
NOW = datetime(2026, 1, 1, 21, 4)


def button_texts(markup):
    return [b.text for row in markup.inline_keyboard for b in row]


def rows(markup):
    return [[b.text for b in row] for row in markup.inline_keyboard]


def test_collapsed_by_default_with_category_headers():
    items = [
        make_item("1", "Apples", label="Fruit", position=2),
        make_item("2", "Soap"),
        make_item("3", "Bananas", label="Fruit", position=1),
        make_item("4", "Milk", checked=True),
    ]
    text, markup = render_list("Groceries", items, ListState(), EN, now=NOW)
    assert "🛒 <b>Groceries</b>" in text
    assert "<code>▰▰▱▱▱▱▱▱▱▱</code> 3 open · 1 done · <i>21:04</i>" in text  # 1 of 4 done
    assert "<blockquote expandable>✅ <b>Done</b>\n<s>Milk</s></blockquote>" in text
    assert button_texts(markup) == ["🍎 Fruit (2) ▸", "📦 Other (1) ▸", "🔄 Refresh", "✅ Done (1)"]
    toggle = ListAction.unpack(markup.inline_keyboard[0][0].callback_data)
    assert (toggle.action, toggle.arg) == ("toggle", "l-Fruit")
    assert ListAction.unpack(markup.inline_keyboard[1][0].callback_data).arg == NO_LABEL


def test_expanded_category_lists_items_in_position_order():
    items = [
        make_item("1", "Apples", label="Fruit", position=2),
        make_item("2", "Soap"),
        make_item("3", "Bananas", label="Fruit", position=1),
    ]
    _, markup = render_list("G", items, ListState(expanded={"l-Fruit"}), EN)
    assert rows(markup)[:3] == [["🍎 Fruit (2) ▾"], ["Bananas", "Apples"], ["📦 Other (1) ▸"]]
    data = ItemAction.unpack(markup.inline_keyboard[1][0].callback_data)
    assert (data.action, data.item_id) == ("check", "3")


def test_single_group_needs_no_header_and_is_open():
    _, markup = render_list("L", [make_item("1", "Soap")], ListState(), EN)
    assert rows(markup)[0] == ["Soap"]


def test_short_names_share_a_row_in_list_order():
    names = ["Eggs", "Butter", "Quark", "Milk", "Something rather long", "Medium length", "Tea"]
    items = [make_item(str(i), name) for i, name in enumerate(names)]
    _, markup = render_list("L", items, ListState(), EN)
    assert rows(markup)[:-1] == [
        ["Eggs", "Butter", "Quark"],
        ["Milk"],
        ["Something rather long"],
        ["Medium length", "Tea"],
    ]


def test_added_quote_and_undo_button():
    added = [make_item("9", "", note="Flour", quantity=500, unit={"name": "g"}, label="Baking")]
    state = ListState(expanded={"l-Baking"}, added=added, undo=AddResult(created=added))
    text, markup = render_list("G", [*added, make_item("1", "Soap")], state, EN)
    assert "➕ <b>Added:</b> <b>Flour</b> · <i>500 g · 🧁 Baking</i>" in text
    assert button_texts(markup)[-2:] == ["↩️ Undo", "✅ Done"]
    assert markup.inline_keyboard[-1][1].style is None  # nothing done yet: no green, no count
    state.added.append(make_item("1", "Soap"))
    text, _ = render_list("G", [*added, make_item("1", "Soap")], state, EN)
    assert "<blockquote expandable>➕ <b>Added</b> (2)\n<b>Flour</b>" in text
    assert ListAction.unpack(markup.inline_keyboard[-1][0].callback_data).action == "undo"


def test_done_view_offers_uncheck_and_clear():
    items = [make_item("1", "Milk", checked=True), make_item("2", "Eggs")]
    text, markup = render_list("Groceries", items, ListState(view=VIEW_DONE), EN)
    assert "✅ <b>Done</b> · 1" in text
    assert rows(markup) == [["Milk"], ["🛒 Open (1)", "🧹 Remove (1)"]]
    assert ItemAction.unpack(markup.inline_keyboard[0][0].callback_data).action == "uncheck"
    assert ListAction.unpack(markup.inline_keyboard[1][1].callback_data).action == "clear_ask"


def test_clear_question_lists_items_and_asks():
    items = [make_item("1", "Milk", checked=True), make_item("2", "Eggs", checked=True)]
    text, markup = render_list("G", items, ListState(view=VIEW_CLEAR), DE)
    assert "🧹 <b>2</b> erledigte Einträge endgültig entfernen?" in text
    assert "<s>Milk</s>\n<s>Eggs</s>" in text
    assert rows(markup) == [["✕ Abbrechen", "🧹 Ja, entfernen"]]
    assert ListAction.unpack(markup.inline_keyboard[0][1].callback_data).action == "clear"


def test_clear_question_without_checked_items_falls_back_to_done_view():
    text, _ = render_list("G", [make_item("1", "Eggs")], ListState(view=VIEW_CLEAR), EN)
    assert "Nothing ticked off yet" in text


def test_empty_list_and_escaping():
    text, _ = render_list("<b>&", [], ListState(), DE)
    assert "&lt;b&gt;&amp;" in text
    assert "Die Liste ist leer" in text
    text, _ = render_list("G", [make_item("1", "x", checked=True)], ListState(), DE)
    assert "Alles gekauft" in text and "▰▰▰▰▰▰▰▰▰▰" in text


def test_long_lists_are_capped():
    items = [make_item(str(i), f"item number {i}") for i in range(MAX_ITEM_BUTTONS + 5)]
    text, markup = render_list("L", items, ListState(), EN)
    assert "5 more" in text
    assert sum(len(row) for row in markup.inline_keyboard) <= 100


def test_category_headers_count_against_the_button_limit():
    items = [make_item(str(i), f"item {i}", label=f"Label {i % 30}") for i in range(90)]
    state = ListState(expanded={f"l-Label {i}" for i in range(30)})
    text, markup = render_list("L", items, state, EN)
    assert sum(len(row) for row in markup.inline_keyboard) <= 100
    assert "40 more" in text  # 80 - 30 headers = 50 items shown


def test_long_quotes_are_capped_to_fit_a_message():
    items = [make_item(str(i), f"Some item number {i}", checked=True) for i in range(300)]
    added = [make_item(f"a{i}", f"Added item number {i}") for i in range(100)]
    text, _ = render_list("L", [*items, *added], ListState(added=added), EN)
    assert len(text) < 4096
    assert text.count("<s>") == MAX_QUOTE_ITEMS
    assert f"{300 - MAX_QUOTE_ITEMS} more" in text and f"{100 - MAX_QUOTE_ITEMS} more" in text
    text, _ = render_list("L", items, ListState(view=VIEW_CLEAR), DE)
    assert len(text) < 4096 and f"{300 - MAX_QUOTE_ITEMS} weitere" in text


def test_callback_data_fits_telegram_limit():
    uuid = "12345678-1234-4234-8234-123456789012"
    assert len(ItemAction(action="uncheck", item_id=uuid, view=VIEW_DONE).pack().encode()) <= 64
    assert len(ListAction(action="toggle", arg=uuid).pack().encode()) <= 64


def test_item_display_puts_name_first():
    item = make_item("1", "", quantity=2, unit={"name": "Liter"}, food={"name": "Milch"})
    assert item_display(item, "de") == "Milch · 2 Liter"
    assert item_html(item, "de") == "<b>Milch</b> · <i>2 Liter</i>"
    assert item_html(item, "de", "🥛 Milch") == "<b>Milch</b> · <i>2 Liter · 🥛 Milch</i>"
    assert item_inline(item, "de") == "2 Liter Milch"
    assert item_inline(make_item("2", "", note="Soap"), "en") == "Soap"
    assert item_display(make_item("2", "", note="Soap"), "en") == "Soap"
    assert item_display(make_item("3", "", quantity=3, note="Lemons"), "en") == "Lemons · 3"
    assert item_display(make_item("4", "legacy display"), "en") == "legacy display"
    with_note = make_item("5", "", food={"name": "Flour"}, note="type 405")
    assert item_display(with_note, "en") == "Flour, type 405"
    abbreviated = make_item(
        "6", "", quantity=500, unit={"name": "Gramm", "abbreviation": "g", "useAbbreviation": True}
    )
    assert item_display(abbreviated, "de") == "? · 500 g"


def test_category_buttons_are_coloured_and_items_are_not():
    items = [
        make_item("1", "Apples", label="Fruit"),
        make_item("2", "Soap"),
        make_item("3", "Milk", checked=True),
    ]
    _, markup = render_list("G", items, ListState(expanded={"l-Fruit"}), EN)
    header, apple, other, controls = markup.inline_keyboard
    assert header[0].style == other[0].style == "primary" and apple[0].style is None
    assert [b.style for b in controls] == [None, "success"]
    _, markup = render_list("G", items, ListState(undo=AddResult(created=items[:1])), EN)
    assert markup.inline_keyboard[-1][0].style is None  # undo is safe, so not red
    _, markup = render_list("G", items, ListState(view=VIEW_DONE), EN)
    assert [b.style for b in markup.inline_keyboard[-1]] == [None, "danger"]
    _, markup = render_list("G", items, ListState(view=VIEW_CLEAR), EN)
    assert [b.style for b in markup.inline_keyboard[0]] == [None, "danger"]


def test_all_bought_offers_remove_in_the_control_row():
    items = [make_item("1", "Milk", checked=True), make_item("2", "Eggs", checked=True)]
    text, markup = render_list("G", items, ListState(), EN)
    assert "🎉 All bought." in text
    assert "<code>▰▰▰▰▰▰▰▰▰▰</code> 0 open · 2 done" in text
    assert rows(markup) == [["🔄 Refresh", "✅ Done (2)", "🧹 Remove (2)"]]
    assert ListAction.unpack(markup.inline_keyboard[0][2].callback_data).action == "clear_ask"


def test_label_emoji_overrides_reach_headers_and_added_quote():
    items = [make_item("1", "Pepper", label="Würzmittel"), make_item("2", "Soap")]
    state = ListState(added=[items[0]])
    text, markup = render_list("G", items, state, DE, emoji={"würzmittel": "🌶️"})
    assert button_texts(markup)[0] == "🌶️ Würzmittel (1) ▸"
    assert "<b>Pepper</b> · <i>🌶️ Würzmittel</i>" in text


def test_quantities_and_progress():
    assert format_quantity(1.5, "de") == "1,5"
    assert format_quantity(2.0, "en") == "2"
    assert format_quantity(0.5, "en") == "½"
    assert format_quantity(1 / 3, "de") == "⅓"
    assert format_quantity(1.25, "en") == "1.25"
    assert format_quantity(0.333, "de") == "⅓"
    assert format_quantity(0.123456, "de") == "0,12"
    assert progress_bar(0, 0) == "▱" * 10
    # A started list never looks empty, an unfinished one never full.
    assert progress_bar(1, 20) == "▰" + "▱" * 9
    assert progress_bar(19, 20) == "▰" * 9 + "▱"
    assert progress_bar(1, 3) == "▰▰▰▱▱▱▱▱▱▱"
    assert progress_bar(1, 40) == "▰" + "▱" * 9  # something done shows
    assert progress_bar(39, 40) == "▰" * 9 + "▱"  # something open shows


def test_categories_follow_the_order_set_in_mealie():
    items = [
        make_item("1", "Milk", label="Dairy"),
        make_item("2", "Apple", label="Fruit"),
        make_item("3", "Soap"),
        make_item("4", "Bread", label="Bakery"),
    ]
    order = {"l-Fruit": 0, "l-Dairy": 1}  # Bakery has no position: alphabetical after them
    _, markup = render_list("G", items, ListState(), EN, label_order=order)
    headers = [text.split(" (")[0] for text in button_texts(markup)[:4]]
    assert headers == ["🍎 Fruit", "🥛 Dairy", "🍞 Bakery", "📦 Other"]
