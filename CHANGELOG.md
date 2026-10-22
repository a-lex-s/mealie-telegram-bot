# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Shopping list helper: add items by message, list and tick off items with
  inline buttons, choose a list, remove ticked-off items.
- Quantity and unit parsing (`2 l milk`, `500g flour`, `3x lemons`) mapped to
  Mealie foods, units and labels.
- English and German, chosen per user from the Telegram language or forced
  with `BOT_LANGUAGE`.
- Access limited to `ALLOWED_USER_IDS`; configuration through environment
  variables and `*_FILE` secrets.
- Docker image for linux/amd64 published to GHCR on `v*` tags.
- Community files: security policy, contributing guide, code of conduct,
  issue and pull request templates.

[Unreleased]: https://github.com/a-lex-s/mealie-telegram-bot/commits/main
