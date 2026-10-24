# Specification

This document is the reference for what the bot does. When the behaviour of the
code changes, this file changes in the same pull request.

## 1. Goal and scope

A Telegram bot that serves as a lightweight front end for a self-hosted
[Mealie](https://mealie.io) instance (developed against Mealie **v3.29.0**).

* The bot covers **shopping lists only**. It replaces a dedicated shopping
  list app for a small household (two people): add items by sending a message,
  tick them off with a tap, everyone sees the same list in Mealie and Telegram.
* Recipes and meal plans are **not planned** right now; open issues for them
  can be picked up by contributors.

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
| `SHOPPING_CREATE_FOODS` | no | `false` | Create a Mealie food (without a category) for an item name Mealie does not know, instead of storing the name as a note (6.3) |
| `FEATURE_SHOPPING` | no | `true` | Enable the shopping list feature |
| `DELETE_COMMANDS` | no | `true` | Delete the user's `/list`, `/lists`, `/clear`, `/category`, `/categories` and `/version` messages once handled, so only the list stays in the chat |
| `DELETE_ITEM_MESSAGES` | no | `true` | Delete the user's item messages once the items were added; the history entry records them |
| `LABEL_EMOJI` | no | keyword table | Emoji per Mealie label name, `Name=🌶️;Other=🐾`; overrides an emoji in the label name and the built-in keyword table (6.4) |
| `LABEL_ICONS` | no | `both` | What is shown in front of category names: `both`, `color`, `emoji` or `none` (6.4) |
| `HISTORY_FOLD_HOURS` | no | `24` | History entries older than this many hours are folded into one history message (6.6); `0` turns it off, at most `47` |
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
* The bot works in a private chat per person or in one group that both people
  share. The code keeps its state per chat either way (see 6.4 and 6.6).
* In a group, Telegram's privacy mode delivers only commands to the bot. For
  plain-text items, turn privacy mode off for the bot in @BotFather
  (`/setprivacy`) before adding it to the group; for `DELETE_COMMANDS` and
  `DELETE_ITEM_MESSAGES` the bot must be a group administrator allowed to
  delete messages. The allow list applies to the sender of each message, not
  to the group.

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
| start | `/start` | `/start` | Short greeting, then one introduction per enabled feature (shopping: example message and an expandable tips block) |
| help | `/help` | `/hilfe` | Short intro, then one usage section per enabled feature |
| version | `/version` | `/version` | Package version and, if the image was built with `VCS_REF`, the short commit (7 characters); the version alone otherwise (local runs, or a value that is not a commit hash). Not in the command menu |
| list | `/list` | `/liste` | Show the active list |
| lists | `/lists` | `/listen` | Choose the active list |
| clear | `/clear` | `/aufraeumen` | Delete all ticked-off items of the active list, after confirmation |
| category | `/category` | `/kategorie` | Create a category (Mealie label), see 6.8 |
| categories | `/categories` | `/kategorien` | Show all categories with their number of products, see 6.8 |

The command menu lists the feature commands first (`/list`, `/clear`, `/lists`,
`/category`, `/categories`) and `/help` last. It, the bot description and the short description ("What can this
bot do?") are published per language at start-up (`setMyCommands`,
`setMyDescription`, `setMyShortDescription`).

With `DELETE_COMMANDS=true` (default) the bot deletes the user's `/list`,
`/lists`, `/clear`, `/category`, `/categories` and `/version` messages before it
shows the list or the answer, so the chat holds
the list and the history instead of a trail of commands. `/start` and `/help`
are never deleted. The `/version` answer, like the bot's other info replies,
is deleted the next time the list is shown.

With `DELETE_ITEM_MESSAGES=true` (default) a plain text message is deleted as
soon as its items are in Mealie, before the list is shown (see 6.3); the
history entry records what was added. A message the bot could not parse or add
stays in the chat so the user can fix and resend it. If Telegram refuses the
deletion (e.g. in a group where the bot may not delete others' messages), the
message simply stays and the list is sent again below it.

### 6.2 Active list

The active list of a chat is, in this order: the list picked with `/lists` in
that chat, the list named by `SHOPPING_LIST`, the first list by name. The
choice made with `/lists` belongs to the chat (so in a group both people work
on the same list), is kept in memory and resets when the bot restarts. If Mealie
has no shopping list, the bot says so; it never creates lists.

`/lists` renders a chooser into the live list message (6.4): one button per
list, the active one coloured blue, and **✕ Cancel**, which shows the list
again. Choosing a list shows that list in the same message. With a single list
in Mealie there is nothing to choose; the bot just names it
(`📋 There is only the list <b>Groceries</b>.`).

### 6.3 Adding items

Any text message that is not a command adds items to the active list, except
a line with an arrow (sorting, 6.8) and a reply to the sort picker's name
prompt (6.8).

* Entries are separated by line breaks, semicolons or commas. A comma between
  two digits is a decimal separator (`1,5 l Milch` is one entry).
* Leading bullets (`-`, `•`, `*`) and the numbering of a pasted list (`1.`,
  `2)`) are ignored.
* Each entry may carry a quantity and a unit, in front or at the end:
  `2 l milk`, `500g flour`, `milk 2l`, `milk 2 l`, `3x lemons`, `3 x lemons`,
  `lemons x3`, `eggs 6`. Quantities may be decimals with `.` or `,`, fractions
  like `1/2`, `½ ¼ ¾ ⅓ ⅔`, or mixed numbers like `1 1/2` and `2 ½`.
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
4. Without a food match the text becomes the item's `note`. With
   `SHOPPING_CREATE_FOODS=true` the bot instead creates a food with that name
   and no label (`POST /api/foods`, once per name and message) and the item
   references it, so it shows up under "Other" ready for sorting (6.8); an
   unknown unit still goes into the note. If the bulk request then fails, the
   foods created for it are deleted again. Adding items never creates units;
   sorting a product into a category (6.8) always creates a missing food.

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
  then the button turns back into *Refresh*. Undo also deletes foods the
  message created (`SHOPPING_CREATE_FOODS`), after the items, even if another
  item started using such a food in the meantime; a food Mealie refuses to
  delete is logged and skipped. Undo data belongs to that list
  message and is dropped when the message is replaced or the bot restarts. If
  Mealie cannot be reached when Undo is tapped, the data is kept and the tap
  can be repeated.

### 6.4 The live list message

Each chat has one *live* list message. It is the single place where the list
is shown; taps and changes from the other chat edit it in place.

* `/list`, `/lists`, `/clear` and adding items send the list anew at the
  bottom of the chat; the old message becomes a history entry or is deleted
  (6.6). Commands never edit the old message in place: when the user has
  cleared the chat history on their side, that message still exists for the
  bot and an edit would succeed without anyone seeing it. Sending anew is
  what makes `/list` bring the list back after a cleared chat, without a
  restart. Taps (ticking off, categories, Refresh, Undo, Remove, choosing a
  list) edit the tapped message in place.
* If a live message was deleted on both sides (Telegram answers "message to
  edit not found" to a sync from the other chat), the bot forgets it; the
  next command sends a new one.
* A list message remembers which list it shows. Taps on it refresh that list,
  even if someone has since chosen another list with `/lists` in that chat; a
  tap on a message from before a restart falls back to the chat's active list.
* Updates in one chat are handled one after another (a lock per chat), so two
  taps or two texts at the same time cannot produce two live messages or
  race on the same item.
* Text: `🛒 <b>list</b>`, a progress bar in monospace on its own line
  (`▰▰▰▱▱▱▱▱▱▱`, ten cells, ticked-off share of all items; anything done fills
  at least one cell, anything open leaves at least one empty), below it the
  status line `n open · m done · <i>HH:MM</i>` (container local time). Before
  the first item is ticked off there is no bar and the line is just
  `n open · <i>HH:MM</i>` without done count. Ticked-off items follow in an expandable quote **Done**, struck
  through. Empty list: "The list is empty." plus `<i>As of HH:MM</i>`; everything
  ticked off: "🎉 All bought.".
* Quantities: whole numbers as such, pure fractions as `½ ¼ ¾ ⅓ ⅔`, everything
  else with at most two decimals (`1,5` in German, `1.5` in English).
* Keyboard: one header button per label (`🧂 Label (n) ▸` collapsed,
  `🧂 Label (n) ▾` expanded). Labels follow the order set for the list in
  Mealie (`labelSettings`, the same order as in Mealie's list view); labels
  without a position come after them alphabetically, unlabelled items are last
  as "Other". All categories start collapsed; tapping a header toggles it for that
  message. A list with a single category shows its items directly without a
  header. Below the items of an open "Other" sits a green **🏷️ Sort (n)**
  button that opens the sort picker (6.8).
* Header buttons are coloured blue (Bot API button `style` `primary`), item
  buttons and **Undo** / **Refresh** keep the default colour, **Done (m)** is
  green (`success`) and reads just **Done** without colour while nothing is
  ticked off, **Remove** and **Yes, remove** are red (`danger`). Clients that
  predate button styles show plain buttons. When everything is ticked off,
  **Remove (m)** joins the control row.
* Each category is shown as `colour circle · emoji · name`
  (`🟣 🧂 Würzmittel`), the same in headers, the "Added" and "Sorted" quotes,
  `/categories` and the history:
  * The colour circle (🔴 🟠 🟡 🟢 🔵 🟣 🟤 ⚫ ⚪) is the nearest match for the
    label's colour in Mealie. Mealie's default grey (`#959595`), other greys and
    unreadable values give no circle.
  * The emoji comes from `LABEL_EMOJI` (exact label name), else from an emoji
    at the start of the label's own name in Mealie (`🧴 Drogerie`, shown once),
    else from a keyword table in `mealie_bot/i18n/labels.py` (German and
    English keywords, case-insensitive substring match, first match wins;
    e.g. "Obst & Gemüse" and "Fruit" → 🍎, "Würzmittel" and "Spices" → 🧂).
  * A label with a colour but no emoji match shows just its circle
    (`🟢 Eigenes`), so own categories need no configuration. Only a label with
    neither, and items without a label ("Other"), get 📦.
  * `LABEL_ICONS` switches parts off: `both` (default) as above, `color` shows
    only circles (`🟣 Würzmittel`, nothing without a colour), `emoji` only
    emojis (`🧂 Würzmittel`, 📦 without a match), `none` just the name.
* Items of an expanded category are buttons labelled `name · quantity`
  (`Mehl · 500 g`; quantity 1 without unit is omitted; texts longer than 40
  characters are cut with `…`). Rows are filled in list order: a row takes the
  next item as long as all its items allow that many per row (three of at most
  10 characters, two of at most 18 characters, longer names alone). Items
  without a food use their note as name.
* Tapping an item ticks it off in Mealie, answers with a toast (`✅ Mehl · 500 g`,
  cut to Telegram's 200 characters) and refreshes the message in place.
* **Done (m)** switches the message to the ticked-off items (newest first), with
  the same button packing, headed `✅ <b>Done</b> · m`; tapping one puts it back
  (toast "🔁 … is open again"). **🛒 Open (n)** switches back, **Remove (m)**
  asks for confirmation.
* **Refresh** reloads the list and answers with a toast (`🔄 Refreshed`).
  Changes made in Mealie show up on refresh or with the next action; there is
  no push notification. Opening or closing a category re-renders from the
  items fetched last, without asking Mealie, so the time in the status line
  stays that of the last fetch.
* A change made through the bot in one chat (items added, ticked off, put
  back, removed or undone) also re-renders the live messages of the other
  chats the bot knows since its start, if they show the same list: quietly,
  in place and in each chat's language. The other person sees the current
  list when they look at the chat; no message is sent and nothing beeps.
  The other chats are rendered from the list the changing chat fetched right
  after the change, so a change costs one list request however many chats
  show the list; if that fetch failed, each chat fetches on its own.
* Item buttons, category headers and the Sort button share a budget of 80
  buttons (Telegram allows 100 per message); items beyond it are counted in the text. Quotes
  (*Added*, *Done*, the removal question) list at most 20 items and count the
  rest, so the message stays below Telegram's 4096 characters.
* If an item no longer exists when tapped, the bot says so in a toast and refreshes.
* After a restart the bot knows nothing about earlier list messages. Their
  buttons still work: a tap re-renders that message in the view the button
  belonged to (open or done), with all categories collapsed.

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
  put back, removed, undone, sorted into a category or a category created),
  the old message is rewritten into a compact history entry: `📜 <b>list</b>`
  followed by one line per change, `<i>HH:MM · first name</i> ➕ items` (`✅`
  ticked off, `🔁` put back, `🧹 n items removed`, `↩️ n items undone`,
  `🏷️ Ketchup → 🟣 🧂 Würzmittel`, `🏷️ new category 🔵 🧻 Haushalt`). In a private chat the owner's own
  name is left out (`<i>HH:MM</i> ➕ items`); the other person's name and every
  name in a group stay. Consecutive changes of the same kind by the same person
  are merged into one line; items are written as one would type them
  (`500 g Mehl`); at most 8 item names are listed per line and 12 lines per
  entry. Changes from a day other than the one the entry is written on carry
  their date before the time (`01.10. 21:12` in German, `Oct 01 21:12` in
  English).
* Changes are recorded in the history of every chat that shows the same list,
  so both people's histories are complete.
* If the latest change in the previous history entry is less than 15 minutes
  old, the new changes are appended to that entry instead and the old list
  message is deleted.
* If nothing changed, the old list message is deleted.
* Telegram lets bots delete messages for 48 hours only. If deleting fails,
  the old list message is rewritten into a stub without buttons instead
  (`📜 list` / "↓ The current list is further down.").

History entries therefore accumulate above the live list and move up as the
chat grows. The history lives in memory and starts fresh after a restart.

**Folding old entries** (`HISTORY_FOLD_HOURS`, default 24, `0` off, at most 47):

* An entry is folded once its last change is that many hours old, or at the
  latest 47 hours after Telegram created the message (it was a list message
  before; bots can delete messages for 48 hours only).
* Folding deletes the entry and appends its lines to one history message per
  chat, headed `📜 <b>Earlier changes</b>`, with the list name as a bold line
  whenever it changes and the date before every time (`Jan 01 21:12`). Bots
  may edit their own messages without a time limit, so this message grows in
  place; it keeps the newest lines that fit into one Telegram message.
* The first fold rewrites the oldest due entry into that message instead of
  sending a new one, so nothing appears below the live list. If the user
  deleted the history message, the next fold starts a new one the same way.
* The check runs whenever the list is shown and every 10 minutes, so entries
  of a quiet chat are folded in time too. The chat then holds at most the
  history message, the entries younger than the setting and the live list.
* Only the bot's own history entries are deleted, never user messages, the
  live list or the stubs of 6.6. A delete or edit that fails is logged once
  (`INFO`) and the entry is left alone.
* Entries written before a restart are not known to the bot and stay in the
  chat until the bot keeps its state across restarts. The same goes for the
  history message: after a restart the next fold starts a second one.

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

A command no feature knows (`/foo`) gets "I do not know that command", and a
message without text (photo, voice message, sticker) gets "I only understand
text", each with a pointer to `/help`.

### 6.8 Categories

Categories are Mealie labels. A product's category is the label of its food
in Mealie, so sorting works on the food and holds for every future purchase;
items of the active list follow right away.

**Sorting by text.** A line `products → category` sorts products:
`Ketchup → Würzmittel`, `Senf, Mayo -> Würzmittel`, `Spülmittel > Haushalt`.
The arrow may be `→`, `->`, `=>` or `>`; one category per line, several lines
per message, at most 50 products in all, separated like entries (6.3); a
quantity in front of a product is ignored. A message is treated as sorting as soon as it contains an
arrow. A line without products, without a category or with two arrows is
answered with an example and stays in the chat. A category name is at most
40 characters long.

For every line the bot resolves the category, then each product:

1. The category is looked up among all labels, case-insensitively, with and
   without a leading emoji (`Drogerie` finds `🧴 Drogerie`). If it does not
   exist, the bot asks once: **➕ Create X**, **Use Y** when a label with a
   similar name exists (difflib ratio ≥ 0.75, catches typos like `Würzmitel`),
   and **✕ Cancel**. A created label gets a colour that matches its emoji
   (`LABEL_COLORS` in `labels.py`), else Mealie's default.
2. Each product is looked up among all foods (6.3). If it does not exist but a
   food with a similar name does, the bot asks **Yes, Ketchup** / **➕ No,
   create Ketchap** / **✕ Cancel**; without a similar food it is created
   without asking. Questions are asked one after the other in a single bot
   message that is edited for the next question and deleted at the end.
   Cancel deletes the question and leaves the user's line in the chat. A
   question nobody answered is deleted the next time the list is shown. A tap
   on a question that is no longer open (answered already, dropped, or asked
   before a restart) is answered with a toast and the question is deleted. If
   Mealie fails after an answer, the answer is kept and the question can be
   tapped again.
3. Then Mealie is updated: a new food is created with the label (`POST
   /api/foods`), an existing food gets the label (`PUT /api/foods/{id}`, the
   whole food sent back with only `labelId` changed), items of the active
   list that carry the food get the label, and items that carry the product
   only as a note are linked to the food (`foodId`, `labelId`, empty `note`;
   `display` is left out so Mealie recomputes it). Nothing is written for a
   product that already is in that category.

The user's line is deleted like an item message (`DELETE_ITEM_MESSAGES`), the
list is shown again with the sorted products' categories expanded and a
**Sorted** quote (`<b>Ketchup</b> · <i>🟣 🧂 Würzmittel</i>`), and the history
records `🏷️ Ketchup → 🟣 🧂 Würzmittel`. **Undo** restores the items, puts
the foods' previous labels back and deletes the foods the sorting created; a
category created on the way stays (it is harmless in Mealie).

**Sorting with buttons.** **🏷️ Sort (n)** under an open "Other" turns the
list message into a picker, like the list chooser (6.2): no new message in the
chat. It goes through the open items without a label in list order, one at a
time: `🏷️ <b>Sort</b> · 1 of 3`, `<b>Ketchup</b> · <i>Which category?</i>`,
one blue button per label two to a row, then **➕ New category…** (green),
**⏭ Skip** and **✕ Back to the list**. At most 77 labels are shown, so the
keyboard stays within the 80-button budget; the text names how many more
exist and points to the arrow syntax.

* Label order is a suggestion only: labels whose emoji the keyword table also
  finds in the product name come first (`Milch` → 🥛 → *Milchprodukte*), then
  the list's own category order (6.4), then the rest by name.
* A label tap sorts the item exactly like `item → label` (step 3 above, on the
  item's food or, for a note, on a food with that name, created if missing),
  answers with a toast (`✅ Ketchup → 🟣 🧂 Würzmittel`), records the history
  line and shows the next item. Other chats on the list are synced (6.4).
  For a note whose name only resembles an existing food (`Ketschup`), the
  picker asks first, in place, as step 3 does: **Yes, Ketchup** (green) /
  **➕ No, create Ketschup** / **↩️ Other category** (back to the label
  buttons). Items that were ticked off, deleted or sorted elsewhere in the meantime are
  skipped.
* **➕ New category…** sends one prompt that asks for the name as a reply
  (Telegram `ForceReply`, `selective`; in a group it mentions the person who
  tapped, so only their keyboard opens). The reply is not an item message: the
  bot finds or creates the label (like `/category`), sorts the current item
  into it, deletes the prompt and the reply (`DELETE_ITEM_MESSAGES`) and edits
  the picker in place. A name longer than 40 characters is answered and the
  prompt stays open.
* After the last item, or on **Back to the list**, the message shows the list
  again with the sorted categories expanded, a **Sorted** quote and **Undo**
  for everything sorted in this round (as for the arrow syntax). Back also
  deletes an open name prompt. A tap on a picker that is closed or from before
  a restart is answered with a toast and the list is shown.

**Commands.** `/category Name` creates a label (with its emoji in the name if
typed, `/category 🧴 Drogerie`; invisible characters are dropped); if it
exists, the bot says so. Without a name the bot shows the usage. These replies
are deleted the next time the list is shown. `/categories` answers with one line per label
(`🟣 🧂 Würzmittel · 12` = number of foods) sorted by name, and a last line
with the number of foods without a label and of open items without a label on
the active list; that message is deleted the next time the list is shown, like
an error message. Labels and foods are cached like units and reloaded on a
miss (6.3), on every `/categories` and after every change the bot makes.

The bot never decides a category on its own: no keyword guessing and no AI, only
the questions above.

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
| Labels (categories) | `GET /api/groups/labels?perPage=-1&orderBy=name&orderDirection=asc` |
| Create a label | `POST /api/groups/labels` (`MultiPurposeLabelCreate`: `name`, `color`) |
| Create a food with its label | `POST /api/foods` (`CreateIngredientFood`: `name`, `labelId`) |
| Change a food's label | `PUT /api/foods/{item_id}` (whole `CreateIngredientFood`, only `labelId` changed; substitutions sent back as `substituteFoodId`/`note`) |
| Undo a created food | `DELETE /api/foods/{item_id}` |

`PUT` replaces the whole item, so the bot reads the item first and sends back
all fields of `ShoppingListItemUpdate` (`shoppingListId`, `quantity`, `note`,
`display`, `checked`, `position`, `foodId`, `labelId`, `unitId`, `extras`,
`recipeReferences`) with only `checked` changed.

`tests/test_openapi_paths.py` checks every path and method in the client, and
the fields of the request bodies above, against
`tests/data/mealie-openapi-3.29.0.json`, a copy of the v3.29.0 document trimmed
to what the bot uses (`scripts/trim_openapi.py` refreshes it). A call missing
from that file fails the test. `MEALIE_OPENAPI` points the test at another
OpenAPI file, for example one exported from a newer instance.

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
  import-linter (layer contracts in `pyproject.toml`), pytest with branch
  coverage and a minimum (`fail_under`), pip-audit on both lock files, zizmor on the workflows, gitleaks on the
  full history and a Docker build with a smoke test and a Trivy scan
  (CRITICAL/HIGH, fixed only) on every push to `main`, every pull request and
  weekly on a schedule. Pull request titles are checked against Conventional
  Commits, since the squash-merge commit takes the title. An OpenSSF Scorecard workflow uploads its results to
  code scanning.
* A tag `vX.Y.Z` first checks that the tag matches the version in
  `pyproject.toml` and points to a commit on `main`, runs CI, then builds and
  pushes `ghcr.io/<owner>/mealie-telegram-bot:vX.Y.Z` (and `vX.Y`, `linux/amd64`
  only, no `latest` tag) with OCI labels, BuildKit provenance and SBOM, and a
  GitHub build provenance attestation pushed to the registry. A GitHub release
  is created, or updated on a re-run, with generated notes, the image digest
  and the SPDX SBOM attached. The commit is also passed to the image as the
  `VCS_REF` build argument, which `/version` and the start-up log line show.
  Every job has a timeout.
* Deployment happens elsewhere: the image is pulled by tag and digest into a
  Compose stack that shares a network with Mealie. See `compose.example.yml`.
* The container runs as UID 10001 with a read-only root file system and no
  inbound port. There is no `HEALTHCHECK`: a long-polling bot has no cheap
  check that says more than "process alive"; `restart: unless-stopped`
  handles crashes.

## 10. Later

What is planned, and the order, lives on the
[project board](https://github.com/users/a-lex-s/projects/2) and in the
[milestones](https://github.com/a-lex-s/mealie-telegram-bot/milestones). A
larger feature gets its own section in this document before it is built.
