"""German catalog."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Bot starten"),
    "list": ("liste", "Liste anzeigen"),
    "clear": ("aufraeumen", "Erledigtes entfernen"),
    "lists": ("listen", "Andere Liste wählen"),
    "help": ("hilfe", "Hilfe"),
}

MESSAGES: dict[str, str] = {
    "bot.description": (
        "Deine Mealie-Einkaufsliste in Telegram: schick, was du brauchst, "
        "tippe zum Abhaken, alle sehen dieselbe Liste."
    ),
    "bot.short_description": "Einkaufsliste für deine Mealie-Instanz",
    "start": (
        "👋 <b>Hallo! Ich bin deine Einkaufsliste.</b>\n\n"
        "Schick mir einfach, was du brauchst:\n"
        "<code>2 l Milch, 500 g Mehl, Eier</code>\n\n"
        "<blockquote expandable>💡 <b>Tipps und Befehle</b>\n"
        "Mengen vorn oder hinten: <code>Milch 2l</code>, "
        "<code>3x Zitronen</code>, <code>½ Brot</code>\n"
        "Ein Eintrag pro Zeile oder mit Komma getrennt\n"
        "/{list} zeigt die Liste, ein Tipp auf einen Eintrag hakt ihn ab\n"
        "/{lists} wechselt die Liste · /{clear} entfernt Erledigtes · "
        "/{help} zeigt alles noch einmal</blockquote>"
    ),
    "help": (
        "<b>🛒 Einkaufsliste</b>\n"
        "Schick Einträge als Text, einen pro Zeile oder mit Komma getrennt. "
        "Menge und Einheit sind optional:\n"
        "<code>2 l Milch</code> · <code>Milch 2l</code> · <code>3x Zitronen</code> · "
        "<code>500g Mehl</code>\n\n"
        "/{list} zeigt die Liste. Tipp auf eine Kategorie öffnet sie, Tipp auf einen "
        "Eintrag hakt ihn ab.\n"
        "/{lists} wechselt zu einer anderen Einkaufsliste.\n"
        "/{clear} entfernt alle erledigten Einträge, nach Bestätigung.\n\n"
        "<blockquote expandable>💡 <b>So verhält sich die Liste</b>\n"
        "Es gibt immer eine Listen-Nachricht, ganz unten im Chat. "
        "Wenn du etwas hinzufügst, rückt sie nach unten, und die alte Nachricht wird zu "
        "einem kurzen Historien-Eintrag.\n"
        "<b>Rückgängig</b> entfernt, was du gerade hinzugefügt hast.\n"
        "Ein Wort zählt nur als Einheit, wenn Mealie es kennt: <code>7up</code> bleibt "
        "ein Name.</blockquote>"
    ),
    "help.no_features": "Es sind keine Funktionen aktiviert.",
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
    "shopping.list_header": "🛒 <b>{list}</b>",
    "shopping.count_open": "{count} offen",
    "shopping.count_done": "{count} erledigt",
    "shopping.list_empty": "Die Liste ist leer.",
    "shopping.list_all_done": "🎉 Alles gekauft.",
    "shopping.added_header": "➕ <b>Hinzugefügt</b> ({count})",
    "shopping.added_one": "➕ <b>Hinzugefügt:</b> {item}",
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
    "history.header": "📜 <b>{list}</b>",
    "history.line": "<i>{time} · {user}</i> {what}",
    # Day shown before the time for entries from another day (strftime format).
    "history.date_format": "%d.%m.",
    "history.added": "➕ {items}",
    "history.checked": "✅ {items}",
    "history.unchecked": "🔁 {items}",
    "history.cleared": "🧹 {count} Einträge entfernt",
    "history.cleared.one": "🧹 1 Eintrag entfernt",
    "history.undone": "↩️ {count} Einträge rückgängig",
    "history.undone.one": "↩️ 1 Eintrag rückgängig",
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
