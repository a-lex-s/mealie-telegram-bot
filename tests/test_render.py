from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.features.shopping.render import (
    MAX_ITEM_BUTTONS,
    VIEW_DONE,
    VIEW_OPEN,
    ItemAction,
    entry_display,
    format_quantity,
    item_display,
    render_list,
)
from mealie_bot.i18n import Translator
from tests.conftest import make_item

EN = Translator("en")


def button_texts(markup):
    return [b.text for row in markup.inline_keyboard for b in row]


def test_open_view_groups_by_label():
    items = [
        make_item("1", "Apples", label="Fruit", position=2),
        make_item("2", "Soap"),
        make_item("3", "Bananas", label="Fruit", position=1),
        make_item("4", "Milk", checked=True),
    ]
    text, markup = render_list("Groceries", items, VIEW_OPEN, EN)
    assert "3 open" in text
    assert button_texts(markup) == [
        "— Fruit —",
        "⬜ Bananas",
        "⬜ Apples",
        "— Other —",
        "⬜ Soap",
        "🔄 Refresh",
        "✅ Ticked off (1)",
    ]
    data = ItemAction.unpack(markup.inline_keyboard[1][0].callback_data)
    assert (data.action, data.item_id, data.view) == ("check", "3", VIEW_OPEN)


def test_no_label_headers_for_single_group():
    _, markup = render_list("L", [make_item("1", "Soap")], VIEW_OPEN, EN)
    assert button_texts(markup)[0] == "⬜ Soap"


def test_done_view_offers_uncheck_and_clear():
    items = [make_item("1", "Milk", checked=True), make_item("2", "Eggs")]
    text, markup = render_list("Groceries", items, VIEW_DONE, EN)
    assert "1 ticked off" in text
    texts = button_texts(markup)
    assert texts[0] == "↩️ Milk"
    assert "🧹 Remove ticked off (1)" in texts
    assert ItemAction.unpack(markup.inline_keyboard[0][0].callback_data).action == "uncheck"


def test_empty_list_and_escaping():
    text, _ = render_list("<b>&", [], VIEW_OPEN, Translator("de"))
    assert "&lt;b&gt;&amp;" in text
    assert "Nichts zu kaufen" in text


def test_long_lists_are_capped():
    items = [make_item(str(i), f"item {i}") for i in range(MAX_ITEM_BUTTONS + 5)]
    text, markup = render_list("L", items, VIEW_OPEN, EN)
    assert "5 more" in text
    assert sum(len(row) for row in markup.inline_keyboard) <= 100


def test_callback_data_fits_telegram_limit():
    uuid = "12345678-1234-4234-8234-123456789012"
    assert len(ItemAction(action="uncheck", item_id=uuid, view=VIEW_DONE).pack().encode()) <= 64


def test_item_display_fallback():
    item = make_item("1", "", quantity=2, unit={"name": "Liter"}, food={"name": "Milch"})
    assert item_display(item, "de") == "2 Liter Milch"
    assert item_display(make_item("2", "", note="Soap"), "en") == "Soap"


def test_quantity_format():
    assert format_quantity(1.5, "de") == "1,5"
    assert format_quantity(1.5, "en") == "1.5"
    assert format_quantity(2.0, "de") == "2"
    assert entry_display(ParsedEntry("Milch", 1.5, "l"), "de") == "1,5 l Milch"
