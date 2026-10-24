# Configuration

All configuration comes from environment variables. Every variable can instead
be read from a file by setting `<NAME>_FILE` (Docker or Compose secrets).
The process in the container runs as UID 10001, so a secret file must be
readable by that user (Compose bind-mounts it with its host permissions).

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | | Telegram bot token |
| `MEALIE_API_TOKEN` | yes | | Mealie API token |
| `ALLOWED_USER_IDS` | yes | | Comma-separated Telegram user IDs |
| `MEALIE_URL` | no | `http://mealie:9000` | Mealie base URL as seen from the bot |
| `BOT_LANGUAGE` | no | per user | Force `en` or `de` for everybody |
| `SHOPPING_LIST` | no | first list | Default list, by name or ID |
| `SHOPPING_CREATE_FOODS` | no | `false` | Create a Mealie food for item names Mealie does not know yet (without a category, so the item lands under *Other* ready for sorting); `false` stores them as a note on the item |
| `FEATURE_SHOPPING` | no | `true` | Enable the shopping list feature |
| `DELETE_COMMANDS` | no | `true` | Delete your `/list`, `/lists`, `/clear`, `/category`, `/categories`, `/version` messages right away, so only the list stays in the chat; set `false` to keep them |
| `DELETE_ITEM_MESSAGES` | no | `true` | Delete your item messages (`2 l milk, eggs`) once the items are on the list; set `false` to keep them |
| `LABEL_EMOJI` | no | built-in table | Emoji per Mealie label, e.g. `Würzmittel=🌶️;Tiere=🐾`; names must match exactly (case does not matter) and win over an emoji in the label name and the built-in keyword table |
| `LABEL_ICONS` | no | `both` | What category buttons show in front of the name: `both` (colour circle and emoji, `🟣 🧂 Würzmittel`), `color` (`🟣 Würzmittel`), `emoji` (`🧂 Würzmittel`) or `none` (`Würzmittel`) |
| `MEALIE_TIMEOUT` | no | `10` | Mealie request timeout in seconds |
| `TZ` | no | UTC | Container time zone, e.g. `Europe/Berlin`; used for the "as of" time and history times |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

Invalid configuration stops the bot at start-up with exit code 2 and a message
that never contains secret values.

## Secret files

Compose file secrets are mounted with the owner and mode of the file on the
host. The bot runs as user ID 10001 inside the container, so the files must be
readable by that ID; otherwise the bot stops with `Cannot read
TELEGRAM_BOT_TOKEN_FILE: Permission denied`. Keep them unreadable for everyone
else:

```sh
mkdir -p secrets
printf '%s' '<telegram bot token>' > secrets/telegram_bot_token
printf '%s' '<mealie api token>' > secrets/mealie_api_token
sudo chown 10001 secrets/*
chmod 0400 secrets/*
```

Do not commit the `secrets/` directory; it is listed in `.gitignore`.

## Category emoji

Category buttons show an emoji picked from the label name: the first keyword
that occurs in the name wins, in German or English (`Obst`, `Fruit` → 🍎;
`Milch`, `Dairy` → 🥛; `Würz`, `Spice`, `Sauce` → 🧂; `Drogerie`,
`Personal Care` → 🧴; `Haushalt`, `Household` → 🧻; `Getränk`, `Drink` → 🥤 and
so on; the full table is in `mealie_bot/i18n/labels.py`). An emoji at the
start of the label name in Mealie (`🧴 Drogerie`) is used as is. A label
without a match shows the colour circle of its Mealie colour instead
(`🟢 Eigenes`); only a label with neither, and items without a label, get 📦.
`LABEL_ICONS` switches the circles, the emojis or both off; it applies to
category buttons, the *Added* and *Sorted* quotes, `/categories` and the
history. With `LABEL_ICONS=emoji` a label without match gets 📦 again, as
before the circles existed. To change or add an emoji, set `LABEL_EMOJI` with
exact label names separated by `;`:

```
LABEL_EMOJI=Würzmittel=🌶️;Tiere=🐾;Sonstiges=🛍️
```
