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
  i18n/                string catalogs (en = reference, de = complete), label emoji table
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
| `DELETE_ITEM_MESSAGES` | no | `true` | Delete the user's item messages once the items were added; the history entry records them |
| `LABEL_EMOJI` | no | keyword table | Emoji per Mealie label name, `Name=🌶️;Other=🐾`; overrides the built-in keyword table (6.4) |
| `MEALIE_TIMEOUT` | no | `10` | HTTP timeout for Mealie requests in seconds |
| `TZ` | no | UTC | Time zone of the container; used for the "as of" time in list messages and history entries |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

The Mealie token acts as one Mealie user; everything the bot adds appears in
Mealie as done by that user. Its household determines which lists are visible.

## 4. Access control

* Only updates from users in `ALLOWED_USER_IDS` are processed. The check runs
  on the dispatcher's update observer, so it covers every update type, not only
  messages and button taps. Everything else is dropped without a reply and
  without a Telegram API call; the user ID is logged once per process at
  WARNING level so an operator can add it, and a stranger cannot flood the log.
* The bot is meant for private chats. In groups, Telegram's privacy mode only
  delivers commands, so adding items by plain text does not work there.

## 5. Languages

* All user-facing text lives in the catalogs under `mealie_bot/i18n/`:
  messages, command names with menu descriptions, and unit synonyms.
* English is the default and reference catalog; German is complete. Tests fail
  if a catalog misses a key or uses different placeholders.
* A key may have a `<key>.one` variant that is used when the `count` argument
  is exactly 1 (`1 item removed` / `3 items removed`).
* The German catalog addresses the user informally and in the singular (du).
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

The command menu lists the feature commands first (`/list`, `/clear`, `/lists`)
and `/help` last. It, the bot description and the short description ("What can this
bot do?") are published per language at start-up (`setMyCommands`,
`setMyDescription`, `setMyShortDescription`).

With `DELETE_COMMANDS=true` (default) the bot deletes the user's `/list`,
`/lists` and `/clear` messages before it shows the list, so the chat holds
the list and the history instead of a trail of commands, and the live list
message (6.4) is still the last message and is edited in place instead of
being sent again. `/start` and `/help` are never deleted.

With `DELETE_ITEM_MESSAGES=true` (default) a plain text message is deleted as
soon as its items are in Mealie, before the list is shown (see 6.3); the
history entry records what was added. A message the bot could not parse or add
stays in the chat so the user can fix and resend it. If Telegram refuses the
deletion (e.g. in a group where the bot may not delete others' messages), the
message simply stays and the list is sent again below it.

### 6.2 Active list

The active list of a user is, in this order: the list the user picked with
`/lists`, the list named by `SHOPPING_LIST`, the first list by name. The choice
made with `/lists` is kept in memory and resets when the bot restarts. If Mealie
has no shopping list, the bot says so; it never creates lists.

`/lists` renders a chooser into the live list message (6.4): one button per
list, the active one coloured blue, and **✕ Cancel**, which shows the list
again. Choosing a list shows that list in the same message. With a single list
in Mealie there is nothing to choose; the bot just names it
(`📋 There is only the list <b>Groceries</b>.`).

### 6.3 Adding items

Any text message that is not a command adds items to the active list.

* Entries are separated by line breaks, semicolons or commas. A comma between
  two digits is a decimal separator (`1,5 l Milch` is one entry).
* Leading bullets (`-`, `•`, `*`) and the numbering of a pasted list (`1.`,
  `2)`) are ignored.
* Each entry may carry a quantity and a unit, in front or at the end:
  `2 l milk`, `500g flour`, `milk 2l`, `milk 2 l`, `3x lemons`, `3 x lemons`,
  `lemons x3`, `eggs 6`. Quantities may be decimals with `.` or `,`, fractions
  like `1/2`, or `½ ¼ ¾ ⅓ ⅔`.
* A word is only treated as a unit if it is a known spelling: either from the
  unit synonyms in the catalogs (all languages) or a name, plural, abbreviation
  or alias of a unit in Mealie. A unit glued to a number must also be known, so
  `7up` stays a name.
* Without a quantity the item gets quantity 1 (Mealie's default). A number
  that is zero, negative or above 10 000 is not a quantity and stays part of
  the name.
* Input limits: control and invisible characters (zero-width, bidi marks) are
  removed first. A message with more than 50 entries or an entry longer than
  200 characters is rejected with a short reply and nothing is sent to Mealie;
  the message stays so the user can split or shorten it.
* IDs carried in button data (`item_id`, `list_id`) are only used when they
  consist of letters, digits and hyphens; a forged ID is answered silently.

Matching against Mealie (per entry):

1. **Unit**: the typed unit is looked up among Mealie units (name, plural name,
   abbreviation, plural abbreviation, aliases; case-insensitive). If that fails,
   all synonyms of the same catalog unit are tried (`litre` → Mealie unit `Liter`).
   Units are cached for 10 minutes.
2. **Food**: the entry's name is looked up among all Mealie foods; only an
   exact, case-insensitive match on name, plural name or alias counts. A match
   sets `foodId` and the food's label (`labelId`), which gives the item its
   category. Foods are cached for 10 minutes like the units; a miss on a cache
   older than a minute reloads them once, so a food just created in Mealie is
   found.
3. If a unit was typed but no Mealie unit matches, the unit goes into the
   item's `note` and the food is still matched (`2 Netz Tomaten` → food
   *Tomaten*, note `Netz`, quantity 2). Without a food match the whole text
   becomes the note (`Netz Tomaten`), so nothing typed is lost.
4. Without a food match the text becomes the item's `note`. The bot never
   creates foods or units in Mealie.

All entries of one message are created in a single bulk request. Mealie itself
merges a new item into an existing unchecked item with the same food/unit/note
and reports both in the response (`createdItems`, `updatedItems`).

While Mealie is asked, the bot shows "typing…". It then shows the list (6.4)
directly below the user's message with:

* an expandable quote **Added (n)** listing what Mealie stored, as
  `<b>name</b> · <i>quantity · emoji label</i>`, so merges and categories are
  visible; a single entry is shown inline as `➕ <b>Added:</b> …` without a quote;
* the categories of the added items expanded;
* an **Undo** button in place of *Refresh*. Undo deletes the created items and
  restores the previous version of merged items (quantity before the merge),
  then the button turns back into *Refresh*. Undo data belongs to that list
  message and is dropped when the message is replaced or the bot restarts.

### 6.4 The live list message

Each chat has one *live* list message. It is the single place where the list
is shown; the bot edits it in place instead of posting new messages.

* `/list`, choosing a list, adding items and the confirmation flow all render
  into the live message. If anything was posted below it since (a user
  message, an error), the list is sent again at the bottom of the chat and the
  old message becomes a history entry or is deleted (6.6).
* A list message remembers which list it shows. Taps on it refresh that list,
  even if the person tapping has since chosen another list with `/lists`; a
  tap on a message from before a restart falls back to the active list.
* Updates in one chat are handled one after another (a lock per chat), so two
  taps or two texts at the same time cannot produce two live messages or
  race on the same item.
* Text: `🛒 <b>list</b>`, a status line `n open · m done · <i>HH:MM</i>`
  (container local time) preceded by a progress bar in monospace
  (`▰▰▰▱▱▱▱▱▱▱`, ten cells, ticked-off share of all items; anything done fills
  at least one cell, anything open leaves at least one empty). Before the first
  item is ticked off the line is just `n open · <i>HH:MM</i>` without bar or
  done count. Ticked-off items follow in an expandable quote **Done**, struck
  through. Empty list: "The list is empty." plus `<i>As of HH:MM</i>`; everything
  ticked off: "🎉 All bought.".
* Quantities: whole numbers as such, pure fractions as `½ ¼ ¾ ⅓ ⅔`, everything
  else with at most two decimals (`1,5` in German, `1.5` in English).
* Keyboard: one header button per label (`🧂 Label (n) ▸` collapsed,
  `🧂 Label (n) ▾` expanded), labels alphabetical with unlabelled items last as
  "Other". All categories start collapsed; tapping a header toggles it for that
  message. A list with a single category shows its items directly without a
  header.
* Header buttons are coloured blue (Bot API button `style` `primary`), item
  buttons and **Undo** / **Refresh** keep the default colour, **Done (m)** is
  green (`success`) and reads just **Done** without colour while nothing is
  ticked off, **Remove** and **Yes, remove** are red (`danger`). Clients that
  predate button styles show plain buttons. When everything is ticked off,
  **Remove (m)** joins the control row.
* Each category gets an emoji from a keyword table in `mealie_bot/i18n/labels.py`
  (German and English keywords, case-insensitive substring match on the label
  name, first match wins; e.g. "Obst & Gemüse" and "Fruit" → 🍎, "Würzmittel"
  and "Spices" → 🧂, "Drogerie" → 🧴). Labels without a match and items
  without a label get 📦. `LABEL_EMOJI` maps exact label names to an emoji and
  wins over the table. The same emoji appears in the "Added" quote.
* Items of an expanded category are buttons labelled `name · quantity`
  (`Mehl · 500 g`; quantity 1 without unit is omitted; texts longer than 40
  characters are cut with `…`). Rows are filled in list order: a row takes the
  next item as long as all its items allow that many per row (three of at most
  10 characters, two of at most 18 characters, longer names alone). Items
  without a food use their note as name.
* Tapping an item ticks it off in Mealie, answers with a toast (`✅ Mehl · 500 g`)
  and refreshes the message in place.
* **Done (m)** switches the message to the ticked-off items (newest first), with
  the same button packing, headed `✅ <b>Done</b> · m`; tapping one puts it back
  (toast "🔁 … is open again"). **🛒 Open (n)** switches back, **Remove (m)**
  asks for confirmation.
* **Refresh** reloads the list and answers with a toast (`🔄 Refreshed`).
  Changes made in Mealie or by the other person show up on refresh or with the
  next action; there is no push notification. Opening or closing a category
  re-renders from the items fetched last, without asking Mealie, so the time
  in the status line stays that of the last fetch.
* Item buttons and category headers share a budget of 80 buttons (Telegram
  allows 100 per message); items beyond it are counted in the text. Quotes
  (*Added*, *Done*, the removal question) list at most 20 items and count the
  rest, so the message stays below Telegram's 4096 characters.
* If an item no longer exists when tapped, the bot says so in a toast and refreshes.

### 6.5 Removing ticked-off items

`/clear` and **Remove (m)** show a confirmation in the list message:
`🧹 Remove <b>m</b> ticked-off items for good?`, the ticked-off items struck
through one per line in a quote, the hint that this also deletes them in
Mealie, and the buttons **✕ Cancel** / **Yes, remove**. *Yes* deletes them
in Mealie and shows the open list with a toast; *Cancel* just shows the open
list. With nothing to remove, the done view is shown instead.

### 6.6 History

When the live list moves to the bottom of the chat, the previous list message
is not simply deleted:

* If anything changed since the last history entry (items added, ticked off,
  put back, removed or undone), the old message is rewritten into a compact
  history entry: `📜 <b>list</b>` followed by one line per change,
  `<i>HH:MM · first name</i> ➕ items` (`✅` ticked off, `🔁` put back,
  `🧹 n items removed`, `↩️ n items undone`). Consecutive changes of the same kind by the
  same person are merged into one line; items are written as one would type
  them (`500 g Mehl`); at most 8 item names are listed per line and 12 lines
  per entry. Changes from a day other than the one the entry is written on
  carry their date before the time (`01.10. 21:12` in German, `Oct 01 21:12`
  in English).
* If the previous history entry is less than 15 minutes old, the new changes
  are appended to that entry instead and the old list message is deleted.
* If nothing changed, the old list message is deleted.

History entries therefore accumulate above the live list and move up as the
chat grows. The history lives in memory and starts fresh after a restart.

### 6.7 Errors

If Mealie cannot be reached, returns an error or answers with something that is
not JSON (for example a maintenance page from a reverse proxy), the user gets a
short message ("⚠️ Mealie is not reachable right now") for commands and text,
deleted again the next time the list is shown successfully, or an alert-style
toast for button taps; details go to the log without tokens. If Telegram
rejects the list message itself, the user is told so instead of getting no
answer. Requests that are
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
| Foods | `GET /api/foods?perPage=-1` |
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
  them, HTTP errors are reported without request headers. A crash is logged
  through the same handler (exit code 1) instead of an unfiltered traceback.
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
* A tag `vX.Y.Z` first checks that the tag matches the version in
  `pyproject.toml` and points to a commit on `main`, runs CI, then builds and
  pushes `ghcr.io/<owner>/mealie-telegram-bot:vX.Y.Z` (and `vX.Y`, `linux/amd64`
  only, no `latest` tag) with OCI labels, BuildKit provenance and SBOM, and a
  GitHub build provenance attestation pushed to the registry. A GitHub release
  is created, or updated on a re-run, with generated notes, the image digest
  and the SPDX SBOM attached. Every job has a timeout.
* Deployment happens elsewhere: the image is pulled by tag and digest into a
  Compose stack that shares a network with Mealie. See `compose.example.yml`.
* The container runs as UID 10001 with a read-only root file system and no
  inbound port. There is no `HEALTHCHECK`: a long-polling bot has no cheap
  check that says more than "process alive"; `restart: unless-stopped`
  handles crashes.

## 10. Later (not in version 1)

* `features/recipes`: search recipes, add a recipe's ingredients to the list.
* `features/mealplan`: show and edit the week's meal plan.
* Possibly: remember the active list, history and undo data across restarts,
  notify the other person about changes.
