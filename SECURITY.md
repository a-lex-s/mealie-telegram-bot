# Security Policy

## Supported versions

Only the latest release (the newest `v*` tag) and the `main` branch receive
security fixes.

## Reporting a vulnerability

Please do not open a public issue for security problems.

Use GitHub's private vulnerability reporting instead:
[Report a vulnerability](https://github.com/a-lex-s/mealie-telegram-bot/security/advisories/new).
This creates a private draft advisory that only the maintainers can see.

If you cannot use GitHub, email <a-lex-s-393168336@proton.me> instead.

Include what you found, how to reproduce it and which version or commit is
affected. You should get a first response within a week. Once a fix is
released, the advisory is published and you are credited unless you prefer
not to be.

## Scope and design notes

The bot is meant to run next to Mealie in a private Compose network with no
inbound port. It talks only to the Telegram Bot API and to `MEALIE_URL`.

* Access is limited to the Telegram user IDs in `ALLOWED_USER_IDS`; everyone
  else is ignored.
* Tokens are read from environment variables or `*_FILE` secrets and are never
  logged.
* The container runs as a non-root user with a read-only root filesystem.
* Dependencies and the base image are pinned by hash; secrets are scanned with
  gitleaks in CI.

How to rotate the tokens after a leak is described in
[docs/security.md](docs/security.md).

Reports about the Mealie server itself belong to the
[Mealie project](https://github.com/mealie-recipes/mealie/security).
