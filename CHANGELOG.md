# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Fixed

- *Undo* keeps its data when Mealie is unreachable, so the tap can be repeated.
- Old list messages that Telegram no longer lets the bot delete (after 48
  hours) are rewritten into a stub without buttons instead of lingering.
- Toasts are cut to Telegram's 200 characters.
- A hint for unknown commands and non-text messages (photos, voice messages).

### Changed

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

### Added

- Profile picture for the bot (`docs/avatar/bot-avatar.svg`, PNG export for
  BotFather's `/setuserpic`).
- Shopping list helper: add items by message, list and tick off items with
  inline buttons, choose a list, remove ticked-off items after confirmation.
- Quantity and unit parsing (`2 l milk`, `500g flour`, `3x lemons`, `1 1/2 l`,
  numbered lists) mapped to Mealie foods, units and labels.
- English and German, chosen per user from the Telegram language or forced
  with `BOT_LANGUAGE`; bot description in the Telegram profile, expandable
  tips in `/start` and `/help`.
- Tidy chat: one live list message per chat that `/list` and `/clear` edit in
  place and that is re-sent at the bottom when something else was posted;
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
- Less flicker: commands are deleted before the list is shown so the live
  message is edited in place, item messages are deleted before the list moves
  down, opening a category needs no Mealie round trip, *Refresh* answers with
  a toast, `/lists` renders its chooser into the live message with a *Cancel*
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

- Release workflow: the tag is checked against the package version and `main`
  before CI runs, the GitHub release is created or updated so that a re-run
  succeeds, no `latest` tag is pushed, and every CI job has a timeout.
- Docs and Compose example explain that secret files must be readable by
  UID 10001 and why the image has no healthcheck.
- Dependabot groups action updates and development tools into one pull
  request each; pre-commit runs ruff and zizmor from the virtual environment
  so the versions match CI; a test keeps both gitleaks pins in step; release
  notes are grouped by label and skip Dependabot.

[Unreleased]: https://github.com/a-lex-s/mealie-telegram-bot/commits/main
