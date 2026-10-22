# mealie-telegram-bot

A Telegram bot that acts as a lightweight front end for a self-hosted
[Mealie](https://mealie.io) instance.

Version 1 is a shopping list helper: send items as a message, tick them off with
a tap, and everyone sees the same list in Mealie and in Telegram. Recipes and
meal plans may follow as separate, optional modules.

* English and German, chosen per user from the Telegram language
* Understands quantities and units: `2 l milk`, `500g flour`, `milk 2l`, `3x lemons`
* Uses Mealie's foods, units and labels, so items land in the right category
* Long polling only: no open port, no web server, no telemetry, no AI calls

The full behaviour is described in [docs/SPEC.md](docs/SPEC.md).

## Usage

| Command | German | What it does |
|---|---|---|
| `/list` | `/liste` | Show open items; tap one to tick it off |
| `/lists` | `/listen` | Choose which shopping list to use |
| `/clear` | `/aufraeumen` | Remove ticked-off items |
| `/help` | `/hilfe` | Show help |

Any other text message is added to the list, one item per line or separated by commas.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and note the token.
2. In Mealie, create an API token for the user the bot should act as
   (user profile → API tokens).
3. Find the Telegram user IDs of everyone who may use the bot
   (for example by messaging [@userinfobot](https://t.me/userinfobot)).
4. Add the service to the Compose stack that runs Mealie; see
   [compose.example.yml](compose.example.yml). Put the two tokens into secret files.

### Configuration

Every variable can also be given as a file via `<NAME>_FILE`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | | Telegram bot token |
| `MEALIE_API_TOKEN` | yes | | Mealie API token |
| `ALLOWED_USER_IDS` | yes | | Comma-separated Telegram user IDs |
| `MEALIE_URL` | no | `http://mealie:9000` | Mealie base URL |
| `BOT_LANGUAGE` | no | per user | Force `en` or `de` |
| `SHOPPING_LIST` | no | first list | Default list, by name or ID |
| `FEATURE_SHOPPING` | no | `true` | Enable the shopping list feature |
| `MEALIE_TIMEOUT` | no | `10` | Mealie request timeout in seconds |
| `LOG_LEVEL` | no | `INFO` | Log level |

## Development

Requires Python 3.12.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt
pip install pre-commit && pre-commit install   # gitleaks + ruff before every commit

ruff check . && ruff format --check .
pytest

# Check the client against your Mealie's OpenAPI document (/openapi.json):
MEALIE_OPENAPI=path/to/openapi.json pytest tests/test_openapi_paths.py
```

Dependencies are declared in `pyproject.toml` and locked with hashes:

```sh
uv pip compile pyproject.toml --python-version 3.12 --generate-hashes --no-header -o requirements.txt
uv pip compile requirements-dev.in --python-version 3.12 --generate-hashes --no-header -o requirements-dev.txt
```

### Adding a language

Copy `mealie_bot/i18n/en.py`, translate messages, command names and unit
spellings, and register it in `mealie_bot/i18n/__init__.py`. The tests check
that the catalog is complete.

### Adding a feature

Create a package under `mealie_bot/features/` that exports a `Feature`, add it to
`available_features()` and to `KNOWN_FEATURES` in `config.py`. It is then
switched with `FEATURE_<NAME>`.

## Contributing

* Conventional Commits; every change as a pull request with tests; squash merge to `main`.
* CI must be green (ruff, pytest, gitleaks, Docker build).
* No personal data in code, tests, examples, commits or pull requests.

## Releases

1. Bump `version` in `pyproject.toml` and `__version__` in `mealie_bot/__init__.py`
   in a pull request and merge it.
2. Tag the merge commit on `main` and push the tag:
   `git tag v0.1.0 && git push origin v0.1.0`.
3. The release workflow runs CI, then publishes
   `ghcr.io/<owner>/mealie-telegram-bot:v0.1.0` (and `:v0.1`). The image digest
   is shown in the workflow summary; deploy by tag and digest.

## License

[MIT](LICENSE)
