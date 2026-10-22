# Configuration

All configuration comes from environment variables. Every variable can instead
be read from a file by setting `<NAME>_FILE` (Docker or Compose secrets).

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | | Telegram bot token |
| `MEALIE_API_TOKEN` | yes | | Mealie API token |
| `ALLOWED_USER_IDS` | yes | | Comma-separated Telegram user IDs |
| `MEALIE_URL` | no | `http://mealie:9000` | Mealie base URL as seen from the bot |
| `BOT_LANGUAGE` | no | per user | Force `en` or `de` for everybody |
| `SHOPPING_LIST` | no | first list | Default list, by name or ID |
| `FEATURE_SHOPPING` | no | `true` | Enable the shopping list feature |
| `DELETE_COMMANDS` | no | `true` | Delete your `/list`, `/lists`, `/clear` messages once handled; set `false` to keep them |
| `MEALIE_TIMEOUT` | no | `10` | Mealie request timeout in seconds |
| `TZ` | no | UTC | Container time zone, e.g. `Europe/Berlin`; used for the "as of" time and history times |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

Invalid configuration stops the bot at start-up with exit code 2 and a message
that never contains secret values.
