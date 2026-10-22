"""German catalog."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Bot starten"),
    "help": ("hilfe", "So funktioniert der Bot"),
    "list": ("liste", "Einkaufsliste anzeigen"),
    "lists": ("listen", "Einkaufsliste wählen"),
    "clear": ("aufraeumen", "Erledigte Einträge entfernen"),
}

MESSAGES: dict[str, str] = {
    "bot.description": (
        "Eure Mealie-Einkaufsliste in Telegram: schick, was ihr braucht, "
        "tippe zum Abhaken, alle sehen dieselbe Liste."
    ),
    "bot.short_description": "Einkaufsliste für eure Mealie-Instanz.",
    "start": (
        "👋 <b>Hallo! Ich bin eure Einkaufsliste.</b>\n\n"
        "Schick mir einfach, was ihr braucht:\n"
        "<code>2 l Milch, 500 g Mehl, Eier</code>\n\n"
        "<blockquote expandable>💡 <b>Tipps und Befehle</b>\n"
        "Mengen vorn oder hinten: <code>Milch 2l</code>, "
        "<code>3x Zitronen</code>, <code>½ Brot</code>\n"
        "Ein Eintrag pro Zeile oder mit Komma getrennt\n"
        "/{list} zeigt die Liste, ein Tipp auf einen Eintrag hakt ihn ab\n"
        "/{lists} wechselt die Liste · /{clear} entfernt Erledigtes · /{help}</blockquote>"
    ),
    "help": (
        "<b>🛒 Einkaufsliste</b>\n"
        "Einträge als Text schicken, einer pro Zeile oder mit Komma getrennt. "
        "Menge und Einheit sind optional:\n"
        "<code>2 l Milch</code> · <code>Milch 2l</code> · <code>3x Zitronen</code> · "
        "<code>500g Mehl</code>\n\n"
        "/{list} zeigt die Liste. Tipp auf eine Kategorie öffnet sie, Tipp auf einen "
        "Eintrag hakt ihn ab.\n"
        "/{lists} wechselt zu einer anderen Einkaufsliste.\n"
        "/{clear} entfernt alle erledigten Einträge, nach Rückfrage.\n\n"
        "<blockquote expandable>💡 <b>So verhält sich die Liste</b>\n"
        "Es gibt immer eine Listen-Nachricht, ganz unten im Chat. "
        "Wenn ihr etwas hinzufügt, rückt sie nach unten, und die alte Nachricht wird zu "
        "einem kurzen Historien-Eintrag.\n"
        "<b>Rückgängig</b> entfernt, was ihr gerade hinzugefügt habt.\n"
        "Ein Wort gilt nur als Einheit, wenn Mealie sie kennt, <code>7up</code> bleibt "
        "also ein Name.</blockquote>"
    ),
    "help.no_features": "Es sind keine Funktionen aktiviert.",
    "error.mealie": "Mealie ist gerade nicht erreichbar. Bitte später noch einmal versuchen.",
    "error.no_lists": "In Mealie gibt es noch keine Einkaufsliste. Bitte zuerst dort eine anlegen.",
    "error.not_understood": "Ich habe in der Nachricht keine Einträge gefunden.",
    "shopping.list_header": "🛒 <b>{list}</b>",
    "shopping.list_counts": "{open} offen · {done} erledigt",
    "shopping.list_empty": "Nichts zu kaufen. 🎉",
    "shopping.list_all_done": "Alles gekauft. 🎉",
    "shopping.added_header": "➕ <b>Hinzugefügt</b> ({count})",
    "shopping.done_quote": "✅ <b>Erledigt</b> ({count})",
    "shopping.updated_at": "<i>Stand {time}</i>",
    "shopping.more": "… und {count} weitere (alle in Mealie sichtbar)",
    "shopping.label_none": "Sonstiges",
    "shopping.done_header": (
        "✅ <b>{list}</b> · {count} erledigt\n<i>Antippen holt einen Eintrag zurück.</i>"
    ),
    "shopping.done_empty": "✅ <b>{list}</b>\nKeine erledigten Einträge.",
    "shopping.clear_question": "🧹 <b>{count} erledigte Einträge aus {list} entfernen?</b>",
    "shopping.clear_hint": "<i>Das löscht sie endgültig aus Mealie.</i>",
    "shopping.btn_refresh": "🔄 Aktualisieren",
    "shopping.btn_undo": "↩️ Rückgängig",
    "shopping.btn_done": "✅ Erledigt ({count})",
    "shopping.btn_open": "⬅️ Offen ({count})",
    "shopping.btn_clear": "🧹 Entfernen ({count})",
    "shopping.btn_clear_yes": "🧹 Ja, entfernen",
    "shopping.btn_cancel": "Abbrechen",
    "shopping.toast_checked": "✓ {item}",
    "shopping.toast_unchecked": "↩️ {item} ist wieder auf der Liste",
    "shopping.toast_undone": "↩️ Rückgängig gemacht: {count} Einträge",
    "shopping.toast_nothing_to_undo": "Da gibt es nichts mehr rückgängig zu machen.",
    "shopping.cleared": "🧹 {count} erledigte Einträge entfernt.",
    "shopping.item_gone": "Diesen Eintrag gibt es nicht mehr.",
    "shopping.choose_list": "📋 <b>Welche Einkaufsliste?</b>",
    "history.header": "<i>📜 {list}</i>",
    "history.line": "<i>{time} · {user}</i> {what}",
    "history.added": "➕ {items}",
    "history.checked": "✅ {items}",
    "history.unchecked": "↩️ {items}",
    "history.cleared": "🧹 {count} entfernt",
    "history.undone": "↩️ {count} rückgängig",
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
