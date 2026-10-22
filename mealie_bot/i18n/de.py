"""German catalog."""

COMMANDS: dict[str, tuple[str, str]] = {
    "start": ("start", "Bot starten"),
    "help": ("hilfe", "So funktioniert der Bot"),
    "list": ("liste", "Einkaufsliste anzeigen"),
    "lists": ("listen", "Einkaufsliste wählen"),
    "clear": ("aufraeumen", "Abgehakte Einträge entfernen"),
}

MESSAGES: dict[str, str] = {
    "start": (
        "Hallo! Ich verwalte eure Mealie-Einkaufsliste.\n\n"
        "Schick mir, was ihr braucht, ein Eintrag pro Zeile oder mit Kommas getrennt, "
        "zum Beispiel <code>2 l Milch, 500 g Mehl, Eier</code>.\n"
        "Mit /{list} siehst du die Liste; tippe auf einen Eintrag, um ihn abzuhaken."
    ),
    "help": (
        "<b>Einkaufsliste</b>\n"
        "• Einträge als Text schicken: einer pro Zeile oder mit Kommas getrennt.\n"
        "  Menge und Einheit sind optional: <code>2 l Milch</code>, <code>Milch 2l</code>, "
        "<code>3x Zitronen</code>.\n"
        "• /{list} zeigt die offenen Einträge. Antippen hakt ab.\n"
        "• /{lists} wechselt zu einer anderen Einkaufsliste.\n"
        "• /{clear} entfernt alle abgehakten Einträge."
    ),
    "help.no_features": "Es sind keine Funktionen aktiviert.",
    "error.mealie": "Mealie ist gerade nicht erreichbar. Bitte später noch einmal versuchen.",
    "error.no_lists": "In Mealie gibt es noch keine Einkaufsliste. Bitte zuerst dort eine anlegen.",
    "error.not_understood": "Ich habe in der Nachricht keine Einträge gefunden.",
    "shopping.added": "Zu <b>{list}</b> hinzugefügt:\n{items}",
    "shopping.list_header": "🛒 <b>{list}</b> · {count} offen",
    "shopping.list_empty": "🛒 <b>{list}</b>\nNichts zu kaufen. 🎉",
    "shopping.done_header": (
        "✅ <b>{list}</b> · {count} abgehakt\nAntippen holt einen Eintrag zurück."
    ),
    "shopping.done_empty": "✅ <b>{list}</b>\nKeine abgehakten Einträge.",
    "shopping.more": "… und {count} weitere (alle in Mealie sichtbar)",
    "shopping.label_none": "Sonstiges",
    "shopping.btn_refresh": "🔄 Aktualisieren",
    "shopping.btn_done": "✅ Abgehakt ({count})",
    "shopping.btn_open": "⬅️ Offene Einträge",
    "shopping.btn_clear": "🧹 Abgehakte entfernen ({count})",
    "shopping.btn_show": "📋 Liste zeigen",
    "shopping.cleared": "{count} abgehakte Einträge entfernt.",
    "shopping.choose_list": "Welche Einkaufsliste möchtest du verwenden?",
    "shopping.list_selected": "Aktive Liste: <b>{list}</b>.",
    "shopping.item_gone": "Diesen Eintrag gibt es nicht mehr.",
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
