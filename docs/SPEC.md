# Specification

This document is the reference for what the bot does. When the behaviour of the
code changes, this file changes in the same pull request.

## 1. Goal and scope

A Telegram bot that serves as a lightweight front end for a self-hosted
[Mealie](https://mealie.io) instance (developed against Mealie **v3.29.0**).

* **Version 1** covers shopping lists only. It replaces a dedicated shopping
  list app for a small household (two people): add items by sending a message,
  tick them off with a tap, everyone sees the same list in Mealie and Telegram.
* Recipes and meal plans are **out of scope** until version 1 is in daily use.
  The code structure leaves room for them as separate feature modules.

Non-goals: no AI calls, no telemetry, no web server, no network access other
than the Telegram Bot API and `MEALIE_URL`. Mealie is not forked or patched.

## 2. Architecture

```
mealie_bot/
  __main__.py          entry point (python -m mealie_bot)
  config.py            settings from environment variables / *_FILE secrets
  logging_setup.py     logging with secret redaction
  i18n/                string catalogs (en = reference, de = complete)
  mealie/client.py     shared async Mealie API client (httpx)
  telegram/            dispatcher wiring, access control, language middleware
  features/
    shopping/          feature module: parser, service, rendering, chat state, handlers
    (recipes/, mealplan/ later)
```

* One repository and one image for all features.
* Each feature module exports a `Feature` (name, menu commands, help text,
  router factory) and can be disabled via `FEATURE_<NAME>=false`.
* Telegram updates are received by **long polling**; the container exposes no port.

## 3. Configuration

All configuration comes from environment variables. Every variable can instead
be read from a file by setting `<NAME>_FILE` (Docker/Compose secrets). Setting
both `<NAME>` and `<NAME>_FILE` is an error. Invalid configuration stops the
bot at start-up with exit code 2 and a message that never contains secret values.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | | Bot token from @BotFather |
| `MEALIE_API_TOKEN` | yes | | Long-lived Mealie API token (user profile → API tokens) |
| `ALLOWED_USER_IDS` | yes | | Comma-separated Telegram user IDs allowed to use the bot |
| `MEALIE_URL` | no | `http://mealie:9000` | Base URL of Mealie, as seen from the bot container |
| `BOT_LANGUAGE` | no | per user | Force one language (`en`, `de`) for everybody |
| `SHOPPING_LIST` | no | first list | Default shopping list, by name (case-insensitive) or ID |
| `FEATURE_SHOPPING` | no | `true` | Enable the shopping list feature |
| `DELETE_COMMANDS` | no | `true` | Delete the user's `/list`, `/lists` and `/clear` messages once handled, so only the list stays in the chat |
| `MEALIE_TIMEOUT` | no | `10` | HTTP timeout for Mealie requests in seconds |
| `TZ` | no | UTC | Time zone of the container; used for the "as of" time in list messages and history entries |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

The Mealie token acts as one Mealie user; everything the bot adds appears in
Mealie as done by that user. Its household determines which lists are visible.

## 4. Access control

* Only updates from users in `ALLOWED_USER_IDS` are processed. Everything else
  is dropped without a reply; the user ID is logged at WARNING level so an
  operator can add it.
* The bot is meant for private chats. In groups, Telegram's privacy mode only
  delivers commands, so adding items by plain text does not work there.

## 5. Languages

* All user-facing text lives in the catalogs under `mealie_bot/i18n/`:
  messages, command names with menu descriptions, and unit synonyms.
* English is the default and reference catalog; German is complete. Tests fail
  if a catalog misses a key or uses different placeholders.
* Language per user comes from Telegram's `language_code` (`de-AT` → `de`);
  unknown languages fall back to English. `BOT_LANGUAGE` overrides it for all users.
* Commands are registered in the Telegram menu per language. Every spelling of a
  command works for every user (e.g. `/list` and `/liste`).

## 6. Shopping list feature

### 6.1 Commands

| Key | English | German | Action |
|---|---|---|---|
| start | `/start` | `/start` | Short introduction with an expandable tips block |
| help | `/help` | `/hilfe` | Usage help of all enabled features |
| list | `/list` | `/liste` | Show the active list |
| lists | `/lists` | `/listen` | Choose the active list |
| clear | `/clear` | `/aufraeumen` | Delete all ticked-off items of the active list, after confirmation |

The command menu, the bot description and the short description ("What can this
bot do?") are published per language at start-up (`setMyCommands`,
`setMyDescription`, `setMyShortDescription`).

With `DELETE_COMMANDS=true` (default) the bot deletes the user's `/list`,
`/lists` and `/clear` messages after they have been handled, so the chat holds
the list and the history instead of a trail of commands. `/start`, `/help` and
plain text messages that add items are never deleted.

### 6.2 Active list

The active list of a user is, in this order: the list the user picked with
`/lists`, the list named by `SHOPPING_LIST`, the first list by name. The choice
made with `/lists` is kept in memory and resets when the bot restarts. If Mealie
has no shopping list, the bot says so; it never creates lists.

`/lists` shows one button per list, the active one marked with `●`. Choosing a
list turns that message into the live list message (see 6.4).

### 6.3 Adding items

Any text message that is not a command adds items to the active list.

* Entries are separated by line breaks, semicolons or commas. A comma between
  two digits is a decimal separator (`1,5 l Milch` is one entry).
* Leading bullets (`-`, `•`, `*`) are ignored.
* Each entry may carry a quantity and a unit, in front or at the end:
  `2 l milk`, `500g flour`, `milk 2l`, `milk 2 l`, `3x lemons`, `3 x lemons`,
  `lemons x3`, `eggs 6`. Quantities may be decimals with `.` or `,`, fractions
  like `1/2`, or `½ ¼ ¾ ⅓ ⅔`.
* A word is only treated as a unit if it is a known spelling: either from the
  unit synonyms in the catalogs (all languages) or a name, plural, abbreviation
  or alias of a unit in Mealie. A unit glued to a number must also be known, so
  `7up` stays a name.
* Without a quantity the item gets quantity 1 (Mealie's default).

Matching against Mealie (per entry):

1. **Unit**: the typed unit is looked up among Mealie units (name, plural name,
   abbreviation, plural abbreviation, aliases; case-insensitive). If that fails,
   all synonyms of the same catalog unit are tried (`litre` → Mealie unit `Liter`).
   Units are cached for 10 minutes.
2. If a unit was typed but no Mealie unit matches, the entry is stored as a
   note only (`kg Mehl`), so nothing typed is lost.
3. **Food**: Mealie foods are searched by the entry's name; only an exact,
   case-insensitive match on name, plural name or alias counts. A match sets
   `foodId` and the food's label (`labelId`), which gives the item its category.
4. Without a food match the text becomes the item's `note`. The bot never
   creates foods or units in Mealie.

All entries of one message are created in a single bulk request. Mealie itself
merges a new item into an existing unchecked item with the same food/unit/note
and reports both in the response (`createdItems`, `updatedItems`).

While Mealie is asked, the bot shows "typing…". It then shows the list (6.4)
directly below the user's message with:

* an expandable quote **Added (n)** listing what Mealie stored, as
  `<b>name</b> <i>quantity</i> · label`, so merges and categories are visible;
* the categories of the added items expanded;
* an **Undo** button in place of *Refresh*. Undo deletes the created items and
  restores the previous version of merged items (quantity before the merge),
  then the button turns back into *Refresh*. Undo data is kept in memory for
  the current list message only.

### 6.4 The live list message

Each chat has one *live* list message. It is the single place where the list
is shown; the bot edits it in place instead of posting new messages.

* `/list`, choosing a list, adding items and the confirmation flow all render
  into the live message. If anything was posted below it since (a user
  message, an error), the list is sent again at the bottom of the chat and the
  old message becomes a history entry or is deleted (6.6).
* Text: `🛒 <b>list</b>`, a progress bar in monospace (`▰▰▰▱▱▱▱▱▱▱`, ten cells,
  ticked-off share of all items) with `n open · m done`, an expandable quote
  **Done (m)** with the ticked-off items struck through, and `<i>As of HH:MM</i>`
  (container local time). Empty list: "Nothing to buy. 🎉"; everything ticked
  off: "Everything bought. 🎉".
* Keyboard: one header button per label (`▸ Label · n` collapsed, `▾ Label · n`
  expanded), labels alphabetical with unlabelled items last as "Other". All
  categories start collapsed; tapping a header toggles it for that message. A
  list with a single category shows its items directly without a header.
* Items of an expanded category are buttons labelled `name · quantity`
  (`Mehl · 500 g`; quantity 1 without unit is omitted). Short names share a
  row (up to three of at most 10 characters, two of at most 18 characters),
  longer names get their own row. Items without a food use their note as name.
* Tapping an item ticks it off in Mealie, answers with a toast (`✓ Mehl · 500 g`)
  and refreshes the message in place.
* **Done (m)** switches the message to the ticked-off items (newest first), with
  the same button packing; tapping one puts it back (toast "… is back on the
  list"). **Open (n)** switches back, **Remove (m)** asks for confirmation.
* **Refresh** reloads the list. Changes made in Mealie or by the other person
  show up on refresh or with the next action; there is no push notification.
* At most 80 items are shown as buttons (Telegram allows 100 per message); the
  rest is counted in the text.
* If an item no longer exists when tapped, the bot says so in a toast and refreshes.

### 6.5 Removing ticked-off items

`/clear` and **Remove (m)** show a confirmation in the list message: the
ticked-off items struck through in a quote, the hint that this deletes them
from Mealie, and the buttons **Yes, remove** / **Cancel**. *Yes* deletes them
in Mealie and shows the open list with a toast; *Cancel* just shows the open
list. With nothing to remove, the done view is shown instead.

### 6.6 History

When the live list moves to the bottom of the chat, the previous list message
is not simply deleted:

* If anything changed since the last history entry (items added, ticked off,
  put back, removed or undone), the old message is rewritten into a compact
  history entry: `<i>📜 list</i>` followed by one line per change,
  `<i>HH:MM · first name</i> ➕ items` (`✅` ticked off, `↩️` put back,
  `🧹 n removed`, `↩️ n undone`). Consecutive changes of the same kind by the
  same person are merged into one line; at most 8 item names are listed per
  line and 12 lines per entry.
* If the previous history entry is less than 15 minutes old, the new changes
  are appended to that entry instead and the old list message is deleted.
* If nothing changed, the old list message is deleted.

History entries therefore accumulate above the live list and move up as the
chat grows. The history lives in memory and starts fresh after a restart.

### 6.7 Errors

If Mealie cannot be reached or returns an error, the user gets a short message
("Mealie is not reachable right now") for commands and text, or an alert-style
toast for button taps; details go to the log without tokens. Requests that are
safe to repeat (`GET`, `PUT`, `DELETE`) are retried once after half a second on
connection errors; `POST` (bulk create) is not, to avoid duplicates. The bot
starts even if Mealie is down and retries with each user action.

## 7. Mealie API usage

Verified against the OpenAPI document of Mealie v3.29.0. Authentication:
`Authorization: Bearer <MEALIE_API_TOKEN>`.

| Purpose | Method and path |
|---|---|
| Start-up check | `GET /api/app/about`, `GET /api/users/self` |
| All shopping lists | `GET /api/households/shopping/lists?perPage=-1&orderBy=name&orderDirection=asc` |
| One list with items | `GET /api/households/shopping/lists/{item_id}` (`listItems`) |
| Read one item | `GET /api/households/shopping/items/{item_id}` |
| Add items | `POST /api/households/shopping/items/create-bulk` (array of `ShoppingListItemCreate`; the response `ShoppingListItemsCollectionOut` with `createdItems`/`updatedItems` feeds the "Added" quote and Undo) |
| Tick off / put back | `PUT /api/households/shopping/items/{item_id}` (`ShoppingListItemUpdate`) |
| Delete ticked-off items, undo added items | `DELETE /api/households/shopping/items?ids=…&ids=…` |
| Find foods | `GET /api/foods?search=…&perPage=20` |
| Units | `GET /api/units?perPage=-1` |

`PUT` replaces the whole item, so the bot reads the item first and sends back
all fields of `ShoppingListItemUpdate` (`shoppingListId`, `quantity`, `note`,
`display`, `checked`, `position`, `foodId`, `labelId`, `unitId`, `extras`,
`recipeReferences`) with only `checked` changed.

`tests/test_openapi_paths.py` checks every path in the client against an
OpenAPI file when `MEALIE_OPENAPI` points to one.

## 8. Security and privacy

* No secrets in the repository; gitleaks runs as a pre-commit hook and in CI.
* Tokens are never logged: settings hide them in `repr`, the log handler redacts
  them, HTTP errors are reported without request headers.
* Container runs as an unprivileged user, works with a read-only root file
  system, and needs no capabilities and no inbound port.
* The repository is public: no personal data (domains, names, Telegram IDs,
  hosts, IPs) in code, tests, examples, commits or pull requests.

## 9. Build, release and deployment

* Python 3.12, aiogram 3, httpx. Dependencies are pinned with hashes in
  `requirements.txt` (generated from `pyproject.toml`); the base image is pinned
  by digest; GitHub Actions are pinned by commit SHA.
* CI (GitHub-hosted `ubuntu-latest` runners only) runs ruff, mypy (strict),
  pytest, pip-audit on both lock files, zizmor on the workflows, gitleaks on the
  full history and a Docker build with a smoke test and a Trivy scan
  (CRITICAL/HIGH, fixed only) on every push to `main`, every pull request and
  weekly on a schedule. An OpenSSF Scorecard workflow uploads its results to
  code scanning.
* A tag `vX.Y.Z` runs CI again, checks that the tag matches the version in
  `pyproject.toml`, then builds and pushes
  `ghcr.io/<owner>/mealie-telegram-bot:vX.Y.Z` (and `vX.Y`, `linux/amd64` only)
  with OCI labels, BuildKit provenance and SBOM, and a GitHub build provenance
  attestation pushed to the registry. A GitHub release is created with generated
  notes, the image digest and the SPDX SBOM attached.
* Deployment happens elsewhere: the image is pulled by tag and digest into a
  Compose stack that shares a network with Mealie. See `compose.example.yml`.

## 10. Later (not in version 1)

* `features/recipes`: search recipes, add a recipe's ingredients to the list.
* `features/mealplan`: show and edit the week's meal plan.
* Possibly: remember the active list, history and undo data across restarts,
  notify the other person about changes.
