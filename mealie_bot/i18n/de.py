"""German catalog."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Bot starten"),
    "list": ("liste", "Liste anzeigen"),
    "clear": ("aufraeumen", "Erledigtes entfernen"),
    "lists": ("listen", "Andere Liste wählen"),
    "category": ("kategorie", "Kategorie anlegen"),
    "categories": ("kategorien", "Kategorien anzeigen"),
    "help": ("hilfe", "Hilfe"),
    "version": ("version", "Version anzeigen"),
}

MESSAGES: dict[str, str] = {
    "bot.description": (
        "Deine Mealie-Einkaufsliste in Telegram: schick, was du brauchst, "
        "tippe zum Abhaken, alle sehen dieselbe Liste."
    ),
    "bot.short_description": "Einkaufsliste für deine Mealie-Instanz",
    # /start and /help: a short intro, then one section per enabled feature.
    "start": "👋 <b>Hallo!</b>",
    "help": "<b>Hilfe</b> · /{help} zeigt das hier noch einmal.",
    "start.shopping": (
        "<b>Ich bin deine Einkaufsliste.</b> "
        "Schick mir einfach, was du brauchst:\n"
        "<code>2 l Milch, 500 g Mehl, Eier</code>\n\n"
        "<blockquote expandable>💡 <b>Tipps und Befehle</b>\n"
        "Mengen vorn oder hinten: <code>Milch 2l</code>, "
        "<code>3x Zitronen</code>, <code>½ Brot</code>\n"
        "Ein Eintrag pro Zeile oder mit Komma getrennt\n"
        "/{list} zeigt die Liste, ein Tipp auf einen Eintrag hakt ihn ab\n"
        "<code>Ketchup → Würzmittel</code> sortiert ein Produkt in eine Kategorie\n"
        "/{lists} wechselt die Liste · /{clear} entfernt Erledigtes · "
        "/{help} zeigt alles noch einmal</blockquote>"
    ),
    "help.shopping": (
        "<b>🛒 Einkaufsliste</b>\n"
        "Schick Einträge als Text, einen pro Zeile oder mit Komma getrennt. "
        "Menge und Einheit sind optional:\n"
        "<code>2 l Milch</code> · <code>Milch 2l</code> · <code>3x Zitronen</code> · "
        "<code>500g Mehl</code>\n\n"
        "/{list} zeigt die Liste. Tipp auf eine Kategorie öffnet sie, Tipp auf einen "
        "Eintrag hakt ihn ab.\n"
        "/{lists} wechselt zu einer anderen Einkaufsliste.\n"
        "/{clear} entfernt alle erledigten Einträge, nach Bestätigung.\n\n"
        "<b>🏷️ Kategorien</b>\n"
        "<code>Ketchup → Würzmittel</code> sortiert ein Produkt dauerhaft in eine Kategorie "
        "(auch <code>-></code>, <code>=></code> oder <code>></code>; mehrere Produkte: "
        "<code>Senf, Mayo → Würzmittel</code>). "
        "Eine neue Kategorie wird nach Rückfrage angelegt; ein Produkt, das Mealie noch "
        "nicht kennt, ebenfalls.\n"
        "Unter <i>Sonstiges</i> geht <b>🏷️ Einsortieren</b> die Einträge einzeln durch, "
        "ein Tipp pro Produkt.\n"
        "/{category} legt eine Kategorie an, /{categories} zeigt alle.\n\n"
        "<blockquote expandable>💡 <b>So verhält sich die Liste</b>\n"
        "Es gibt immer eine Listen-Nachricht, ganz unten im Chat. "
        "Wenn du etwas hinzufügst, rückt sie nach unten, und die alte Nachricht wird zu "
        "einem kurzen Historien-Eintrag.\n"
        "<b>Rückgängig</b> entfernt, was du gerade hinzugefügt hast.\n"
        "Ein Wort zählt nur als Einheit, wenn Mealie es kennt: <code>7up</code> bleibt "
        "ein Name.</blockquote>"
    ),
    "help.no_features": "Es sind keine Funktionen aktiviert.",
    "version": "🔖 <b>mealie-telegram-bot</b> {version}",
    "version.commit": "🔖 <b>mealie-telegram-bot</b> {version} · <code>{commit}</code>",
    "error.mealie": "⚠️ Mealie ist gerade nicht erreichbar. Bitte später noch einmal versuchen.",
    "error.mealie_toast": "⚠️ Mealie antwortet nicht. Bitte gleich noch einmal.",
    "error.no_lists": (
        "📋 In Mealie gibt es noch keine Einkaufsliste. Bitte zuerst dort eine anlegen."
    ),
    "error.not_understood": (
        "Ich habe in der Nachricht keine Einträge gefunden. Beispiel: <code>2 l Milch, Eier</code>"
    ),
    "error.too_many": "⚠️ Das sind mehr als {max} Einträge in einer Nachricht. Bitte aufteilen.",
    "error.too_long": "⚠️ Ein Eintrag ist länger als {max} Zeichen. Bitte kürzen.",
    "error.telegram": (
        "⚠️ Telegram hat die Listennachricht nicht angenommen. "
        "Bitte noch einmal versuchen oder in Mealie nachsehen."
    ),
    "error.only_text": "Ich verstehe nur Text. Schick die Einträge als Nachricht, oder /hilfe.",
    # Kategorien
    "category.usage": (
        "🏷️ Gib der Kategorie einen Namen: <code>/{category} Haushalt</code>. "
        "Oder sortiere direkt ein Produkt ein: <code>Schwämme → Haushalt</code>"
    ),
    "category.too_long": "⚠️ Ein Kategoriename darf höchstens {max} Zeichen lang sein.",
    "category.exists": "🏷️ Die Kategorie <b>{label}</b> gibt es schon.",
    "category.created": "🏷️ <b>Neue Kategorie:</b> {label}",
    "category.list_header": "🏷️ <b>Kategorien</b> ({count})",
    "category.list_line": "{label} · {count}",
    "category.list_none": (
        "🏷️ Es gibt noch keine Kategorien. "
        "Leg eine an mit /{category} oder mit <code>Ketchup → Würzmittel</code>."
    ),
    "category.list_uncategorized": (
        "📦 Ohne Kategorie: {foods} Produkte, {items} offen auf dieser Liste"
    ),
    "assign.not_understood": (
        "Das konnte ich nicht lesen. Beispiel: <code>Ketchup → Würzmittel</code> "
        "oder <code>Senf, Mayo -> Würzmittel</code>, eine Kategorie pro Zeile."
    ),
    "assign.ask_label": "❓ Die Kategorie <b>{label}</b> gibt es noch nicht.",
    "assign.btn_label_new": "➕ {label} anlegen",
    "assign.btn_label_use": "{label} nehmen",
    "assign.ask_food": "❓ <b>{name}</b> kenne ich nicht. Meinst du <b>{food}</b>?",
    "assign.btn_food_use": "Ja, {food}",
    "assign.btn_food_new": "➕ Nein, {name} anlegen",
    "assign.stale": "⚠️ Die Frage ist nicht mehr offen. Bitte schick die Zeile noch einmal.",
    # Sort picker (button under "Other")
    "sort.btn_start": "🏷️ Einsortieren ({count})",
    "sort.header": "🏷️ <b>Einsortieren</b> · {index} von {total}",
    "sort.question": "<b>{item}</b> · <i>Welche Kategorie?</i>",
    "sort.no_labels": "<i>Es gibt noch keine Kategorien. Leg die erste an.</i>",
    "sort.more_labels": (
        "<i>… und {count} weitere Kategorien: dafür <code>Produkt → Kategorie</code> schicken.</i>"
    ),
    "sort.more_labels.one": (
        "<i>… und 1 weitere Kategorie: dafür <code>Produkt → Kategorie</code> schicken.</i>"
    ),
    "sort.btn_food_back": "↩️ Andere Kategorie",
    "sort.food_gone": "⚠️ Dieses Produkt gibt es nicht mehr",
    "sort.btn_new": "➕ Neue Kategorie…",
    "sort.btn_skip": "⏭ Überspringen",
    "sort.btn_back": "✕ Zurück zur Liste",
    "sort.toast_sorted": "✅ {item} → {label}",
    "sort.nothing": "Nichts mehr einzusortieren",
    "sort.stale": "⚠️ Das Einsortieren ist nicht mehr offen",
    "sort.label_gone": "⚠️ Diese Kategorie gibt es nicht mehr",
    "sort.ask_name": "✏️ Wie soll die neue Kategorie heißen? Antworte mit dem Namen.",
    "sort.ask_name_user": ("✏️ {user}, wie soll die neue Kategorie heißen? Antworte mit dem Namen."),
    "sort.name_placeholder": "Name der Kategorie",
    "error.unknown_command": "Den Befehl kenne ich nicht. /hilfe zeigt, was ich kann.",
    "shopping.list_header": "🛒 <b>{list}</b>",
    "shopping.count_open": "{count} offen",
    "shopping.count_done": "{count} erledigt",
    "shopping.list_empty": "Die Liste ist leer.",
    "shopping.list_all_done": "🎉 Alles gekauft.",
    "shopping.added_header": "➕ <b>Hinzugefügt</b> ({count})",
    "shopping.added_one": "➕ <b>Hinzugefügt:</b> {item}",
    "shopping.sorted_header": "🏷️ <b>Einsortiert</b> ({count})",
    "shopping.sorted_one": "🏷️ <b>Einsortiert:</b> {item}",
    "shopping.done_quote": "✅ <b>Erledigt</b>",
    "shopping.updated_at": "<i>Stand {time}</i>",
    "shopping.more": "… und {count} weitere (alle in Mealie sichtbar)",
    "shopping.more.one": "… und 1 weiterer (alle in Mealie sichtbar)",
    "shopping.label_none": "Sonstiges",
    "shopping.done_header": (
        "✅ <b>Erledigt</b> · {count}\n<i>Antippen holt einen Eintrag zurück auf die Liste.</i>"
    ),
    "shopping.done_empty": "✅ <b>Erledigt</b>\nNoch nichts abgehakt.",
    "shopping.clear_question": "🧹 <b>{count}</b> erledigte Einträge endgültig entfernen?",
    "shopping.clear_question.one": "🧹 <b>1</b> erledigten Eintrag endgültig entfernen?",
    "shopping.clear_hint": "<i>Das löscht sie auch in Mealie.</i>",
    "shopping.btn_refresh": "🔄 Aktualisieren",
    "shopping.btn_undo": "↩️ Rückgängig",
    "shopping.btn_done": "✅ Erledigt ({count})",
    "shopping.btn_done_none": "✅ Erledigt",
    "shopping.btn_open": "🛒 Offen ({count})",
    "shopping.btn_clear": "🧹 Entfernen ({count})",
    "shopping.btn_clear_yes": "🧹 Ja, entfernen",
    "shopping.btn_cancel": "✕ Abbrechen",
    "shopping.toast_checked": "✅ {item}",
    "shopping.toast_unchecked": "🔁 {item} ist wieder offen",
    "shopping.toast_undone": "↩️ {count} Einträge rückgängig",
    "shopping.toast_undone.one": "↩️ 1 Eintrag rückgängig",
    "shopping.toast_nothing_to_undo": "Nichts mehr rückgängig zu machen",
    "shopping.cleared": "🧹 {count} Einträge entfernt",
    "shopping.cleared.one": "🧹 1 Eintrag entfernt",
    "shopping.item_gone": "⚠️ Den Eintrag gibt es nicht mehr, Liste aktualisiert",
    "shopping.choose_list": "📋 <b>Welche Einkaufsliste?</b>",
    "shopping.only_list": "📋 Es gibt nur die Liste <b>{list}</b>.",
    "shopping.toast_refreshed": "🔄 Aktualisiert",
    "history.header": "📜 <b>{list}</b>",
    # The one message that collects old history entries (HISTORY_FOLD_HOURS).
    "history.fold_header": "📜 <b>Frühere Änderungen</b>",
    "history.fold_list": "<b>{list}</b>",
    "history.superseded": "📜 <b>{list}</b>\n<i>↓ Die aktuelle Liste steht weiter unten.</i>",
    "history.line": "<i>{time} · {user}</i> {what}",
    # Day shown before the time for entries from another day (strftime format).
    "history.date_format": "%d.%m.",
    "history.line_own": "<i>{time}</i> {what}",
    "history.added": "➕ {items}",
    "history.checked": "✅ {items}",
    "history.unchecked": "🔁 {items}",
    "history.cleared": "🧹 {count} Einträge entfernt",
    "history.cleared.one": "🧹 1 Eintrag entfernt",
    "history.undone": "↩️ {count} Einträge rückgängig",
    "history.undone.one": "↩️ 1 Eintrag rückgängig",
    "history.sorted": "🏷️ {items}",
    "history.label": "🏷️ neue Kategorie {items}",
}

UNITS: dict[str, list[str]] = {
    "g": ["g", "gr", "gramm"],
    "kg": ["kg", "kilo", "kilogramm"],
    "ml": ["ml", "milliliter"],
    "l": ["l", "liter"],
    "piece": ["stk", "stk.", "st", "st.", "stück"],
    "pack": ["pck", "pck.", "pkg", "packung", "packungen", "päckchen", "pack"],
    "can": ["dose", "dosen"],
    "bottle": ["fl", "fl.", "flasche", "flaschen"],
    "bunch": ["bund"],
    "tbsp": ["el", "essl", "esslöffel"],
    "tsp": ["tl", "teel", "teelöffel"],
    "cup": ["tasse", "tassen"],
}
