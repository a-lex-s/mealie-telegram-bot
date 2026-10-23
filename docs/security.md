# Security

The bot is designed to run next to Mealie in a private Compose network with no
inbound port. In short:

* **Reach**: it only talks to the Telegram Bot API (outbound long polling) and
  to `MEALIE_URL`. No web server, no telemetry, no AI services. When Mealie is
  not in the same private network, use an `https://` URL; certificates are
  verified and the API token is sent with every request.
* **Access**: only Telegram user IDs in `ALLOWED_USER_IDS` are served; every
  other update is dropped without a reply. Each unknown user ID is logged once
  per process so an operator can add it; strangers cannot flood the log.
* **Secrets**: tokens come from environment variables or `*_FILE` secrets. They
  are hidden in `repr`, redacted by the log handler and never part of error
  messages. gitleaks runs as a pre-commit hook and in CI on the full history.
* **Mealie side**: the bot acts as one Mealie user and can only see that user's
  household. Give it a dedicated, non-admin user and a token you can revoke.
  Note that the bot only uses the shopping list endpoints, but the token itself
  grants everything that user may do in Mealie; anyone who obtains it, or the
  container it runs in, has those rights.
* **Logs**: the log contains start-up information, Mealie errors without
  headers and, once per unknown sender, the Telegram user ID that was ignored.
  It never contains message texts, item names or tokens. Docker keeps container
  logs on disk; bound them with the `json-file` driver's `max-size` and
  `max-file` options if the host is shared.
* **Container**: non-root user, read-only root file system, all capabilities
  dropped, `no-new-privileges`; see [compose.example.yml](../compose.example.yml).
* **Supply chain**: dependencies locked with hashes, base image pinned by
  digest, GitHub Actions pinned by commit SHA, images built with provenance and
  SBOM.

## If a token leaks

Treat a token as leaked when it appeared in a log, a chat, a screenshot or a
commit, or when a host that held it was compromised.

1. **Telegram**: in [@BotFather](https://t.me/BotFather) run `/revoke` for the
   bot and copy the new token. The old one stops working immediately.
2. **Mealie**: open the bot user's profile in Mealie, delete the API token under
   *API tokens* and create a new one. Check the user's recent activity in Mealie
   (shopping lists, recipes) for changes you did not make.
3. Write both new tokens into the secret files, then restart the container:
   `docker compose up -d --force-recreate mealie-telegram-bot`.
4. If the token was committed, rewriting history is not enough: assume it was
   copied and keep the new tokens.

Please report vulnerabilities privately as described in [SECURITY.md](../SECURITY.md),
which also lists the supported versions.
