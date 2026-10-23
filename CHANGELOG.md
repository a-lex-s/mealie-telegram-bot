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

### Added

- Shopping list helper: add items by message, list and tick off items with
  inline buttons, choose a list, remove ticked-off items after confirmation.
- Quantity and unit parsing (`2 l milk`, `500g flour`, `3x lemons`) mapped to
  Mealie foods, units and labels.
- English and German, chosen per user from the Telegram language or forced
  with `BOT_LANGUAGE`; bot description in the Telegram profile, expandable
  tips in `/start` and `/help`.
- Tidy chat: one live list message per chat that is edited in place and
  re-sent at the bottom when needed; `/list`, `/lists` and `/clear` messages
  are deleted after handling (`DELETE_COMMANDS`), and so are messages that
  added items once the items are on the list (`DELETE_ITEM_MESSAGES`), while
  failed ones stay; old list messages turn into compact history entries (who
  added, ticked off or removed what, grouped by 15 minutes).
- List message with progress bar, collapsible categories, short names packed
  into shared button rows, `name · quantity` labels, ticked-off items in an
  expandable quote and an "as of" time (`TZ`).
- Category buttons stand out: blue header buttons with an emoji per label
  (keyword table in German and English, overridable with `LABEL_EMOJI`),
  green *Done* and red *Undo* / *Remove* buttons.
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

[Unreleased]: https://github.com/a-lex-s/mealie-telegram-bot/commits/main
