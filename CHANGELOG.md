# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.2.0] - 2026-10-24

### Added

- Categories from the chat: `Ketchup → Condiments` (also `->`, `=>`, `>`;
  several products with commas, one category per line) puts products into a
  Mealie label for good. The bot asks once before it creates a category or when
  a similarly named food exists, creates unknown foods, updates the items on
  the list, shows a *Sorted* quote and supports *Undo*.
- `/category` (`/kategorie`) creates a category, `/categories`
  (`/kategorien`) lists them with their number of products and what has no
  category yet.
- Category buttons show the label's colour from Mealie as a circle
  (`🟣 🧂 Condiments`); a label without an emoji match shows just its circle
  instead of 📦. An emoji at the start of a label name in Mealie is used as
  its emoji.
- `/version` shows the running version and, in release images, the short
  commit. It is not listed in the command menu, and its answer is deleted
  the next time the list is shown. The start-up log line shows the commit too.
- `LABEL_ICONS` (`both`, `color`, `emoji`, `none`) chooses what is shown in
  front of category names.
- *🏷️ Sort (n)* under an open *Other* turns the list message into a picker
  that goes through the uncategorised items one by one: one button per
  category (suggested ones first), *New category…* with a reply prompt,
  *Skip* and *Back to the list*; *Undo* reverts the whole round. For a note
  that looks like an existing product it asks "did you mean" first.
- `SHOPPING_CREATE_FOODS` (default `false`) creates a Mealie food without a
  category for unknown item names, so they can be sorted later; *Undo*
  deletes them again.
- Old history entries are folded into one *Earlier changes* message per chat
  after `HISTORY_FOLD_HOURS` (default 24, `0` off, at most 47), so the chat
  holds that message, the recent entries and the list.

### Changed

- The docs no longer promise recipe and meal plan modules: the bot focuses on
  shopping lists, contributions for more are welcome. The README has a short
  roadmap section that points to the project board and the milestones;
  `.github/CONTRIBUTING.md` describes the workflow from issue to release.
- The README screenshots show the category colour circles and the *Sort*
  button.
- A change in one chat no longer fetches the list again for every other chat
  that shows it: the other live messages are rendered from the list the
  changing chat just loaded.
- CI checks every Mealie API path and request field the bot uses against a
  trimmed copy of the Mealie 3.29.0 OpenAPI document in `tests/data/`
  (`scripts/trim_openapi.py` refreshes it); before, the test was skipped
  unless `MEALIE_OPENAPI` was set.
- CI measures branch coverage and fails below the threshold in
  `pyproject.toml`, checks layer boundaries with import-linter and checks that
  pull request titles follow Conventional Commits.

## [0.1.0] - 2026-10-23

First release: the shopping list helper.

### Added

- Social preview image for the GitHub repository in `docs/avatar/`.
- Profile picture for the bot (`docs/avatar/bot-avatar.svg`, PNG export for
  BotFather's `/setuserpic`).
- Shopping list helper: add items by message, list and tick off items with
  inline buttons, choose a list, remove ticked-off items after confirmation.
- Quantity and unit parsing (`2 l milk`, `500g flour`, `3x lemons`, `1 1/2 l`,
  numbered lists) mapped to Mealie foods, units and labels.
- English and German, chosen per user from the Telegram language or forced
  with `BOT_LANGUAGE`; bot description in the Telegram profile, expandable
  tips in `/start` and `/help`.
- Tidy chat: one live list message per chat that taps update in place and
  that `/list`, `/clear` and new items re-send at the bottom;
  `/list`, `/lists` and `/clear` messages are deleted before handling
  (`DELETE_COMMANDS`), and so are messages that
  added items once the items are on the list (`DELETE_ITEM_MESSAGES`), while
  failed ones stay; old list messages turn into compact history entries (who
  added, ticked off or removed what, grouped by 15 minutes).
- List message with progress bar, collapsible categories, short names packed
  into shared button rows, `name · quantity` labels, ticked-off items in an
  expandable quote (at most 20 listed, the rest counted) and an "as of" time
  (`TZ`); category headers and item buttons share the 80-button budget so the
  keyboard stays within Telegram's limits.
- Robust error replies: Mealie answers that are not JSON and list messages
  that Telegram rejects both end in a short message instead of silence.
- Updates in one chat are handled one after another, list messages remember
  the list they show, and a tap on a message from before a restart keeps its
  view.
- Category buttons stand out: blue header buttons with an emoji per label
  (keyword table in German and English, overridable with `LABEL_EMOJI`),
  green *Done* and red *Undo* / *Remove* buttons.
- Text polish: singular/plural forms in both languages, consistent emoji in
  toasts and history (`✅` ticked off, `🔁` put back), German texts address the
  user as "du", error texts are marked with `⚠️`, the command menu lists the
  list commands before `/help`.
- List message polish: status line `n open · m done · HH:MM` (bar and done
  count only once something is ticked off, bar never rounds a done or open
  item away), category buttons `🧂 Label (n) ▸`, item rows packed in list
  order, fractions shown as `½`, a single added item shown inline, *Undo* in
  the default colour, *Remove* in the control row once everything is bought,
  *Cancel* left of *Yes, remove*, history items written as typed with a date
  for other days, the active list coloured in `/lists`.
- Less flicker: commands are deleted before the list is shown, item messages
  are deleted before the list moves down, opening a category needs no Mealie
  round trip, *Refresh* answers with a toast, `/lists` shows its chooser in the
  list message with a *Cancel*
  button (and just names the list when there is only one), and the bot's own
  error messages are deleted once the list is shown again.
- Adding items shows the updated list with an "Added" quote and an Undo button
  that deletes the created items and restores merged quantities; toasts for
  button taps and "typing…" while Mealie is asked.
- Access limited to `ALLOWED_USER_IDS`; configuration through environment
  variables and `*_FILE` secrets; one retry for idempotent Mealie requests
  after connection errors.
- Docker image for linux/amd64 published to GHCR on `v*` tags.
- Community files: security policy, contributing guide, code of conduct,
  issue and pull request templates.
- Release hardening: GitHub release with generated notes and SPDX SBOM, signed
  build provenance attestation, OCI image labels; mypy, pip-audit, zizmor,
  Trivy and OpenSSF Scorecard in CI.

### Changed

- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `SECURITY.md` live in `.github/`,
  where GitHub still picks them up, so the repository root is shorter.

- The README shows real screenshots instead of the SVG mockups.
- The progress bar sits on its own line above the status line
  `n open · m done · HH:MM` instead of in front of it.
- A change made in one chat re-renders the live list messages of the other
  chats on the same list, and is recorded in their histories too; in a private
  chat the owner's own name is left out of the history.
- Categories follow the order set for the list in Mealie instead of being
  alphabetical; the list chosen with `/lists` belongs to the chat, not the user.
- The 15-minute history window counts from the latest change of an entry.
- Documentation covers the group chat set-up (privacy mode off, bot as admin).
- Foods are loaded once and cached for 10 minutes (reloaded on a miss after a
  minute) instead of searching Mealie per entry, so exact matches are no
  longer limited to the first 20 search results.
- An unknown unit no longer prevents the food match: `2 Netz Tomaten` becomes
  the food *Tomaten* with the note `Netz` and keeps its category.
- The numbering of pasted lists (`1. milk`, `2) eggs`) is ignored.

- Release workflow: the tag is checked against the package version and `main`
  before CI runs, the GitHub release is created or updated so that a re-run
  succeeds, no `latest` tag is pushed, and every CI job has a timeout.
- Docs and Compose example explain that secret files must be readable by
  UID 10001 and why the image has no healthcheck.
- Dependabot groups action updates and development tools into one pull
  request each; pre-commit runs ruff and zizmor from the virtual environment
  so the versions match CI; a test keeps both gitleaks pins in step; release
  notes are grouped by label and skip Dependabot.

### Fixed

- `pip install -e .` no longer fails with "Multiple top-level packages" when a
  `secrets/` directory exists in the checkout; packaging is limited to
  `mealie_bot`.
- `/list`, `/lists` and `/clear` always send the list as a new message instead
  of editing the old one. After the user cleared the chat history, the old
  message still existed on the bot's side, the edit succeeded unseen and no
  list appeared until the bot was restarted. A live message that is gone on
  both sides is forgotten when a sync from the other chat hits it.
- *Undo* keeps its data when Mealie is unreachable, so the tap can be repeated.
- Old list messages that Telegram no longer lets the bot delete (after 48
  hours) are rewritten into a stub without buttons instead of lingering.
- Toasts are cut to Telegram's 200 characters.
- A hint for unknown commands and non-text messages (photos, voice messages).

### Security

- Pin `pydantic` below 2.14 as aiogram requires; the two lock files agree
  again and `pip check` runs in CI and in the image build.
- The image no longer contains pip, setuptools or wheel.
- Narrower gitleaks allowlist: lines mentioning `example.com` are no longer
  skipped wholesale.
- Access control runs on the dispatcher's update observer and therefore covers
  every update type, not only messages and button taps.
- Unknown user IDs are logged once per process instead of once per message,
  so strangers cannot flood the log.
- A crash is logged through the redacting log handler (exit code 1) instead of
  an unfiltered traceback on stderr.
- Input limits for item messages: at most 50 entries, 200 characters per
  entry, quantities between 0 and 10 000; control and invisible characters are
  stripped. Over the limit the bot replies instead of asking Mealie.
- IDs from button data are validated before they are used in a Mealie request
  path.

[Unreleased]: https://github.com/a-lex-s/mealie-telegram-bot/compare/v0.2.0...main
[0.2.0]: https://github.com/a-lex-s/mealie-telegram-bot/releases/tag/v0.2.0
[0.1.0]: https://github.com/a-lex-s/mealie-telegram-bot/releases/tag/v0.1.0
