# Security

The bot is designed to run next to Mealie in a private Compose network with no
inbound port. In short:

* **Reach**: it only talks to the Telegram Bot API (outbound long polling) and
  to `MEALIE_URL`. No web server, no telemetry, no AI services.
* **Access**: only Telegram user IDs in `ALLOWED_USER_IDS` are served; every
  other update is dropped and the user ID is logged so an operator can add it.
* **Secrets**: tokens come from environment variables or `*_FILE` secrets. They
  are hidden in `repr`, redacted by the log handler and never part of error
  messages. gitleaks runs as a pre-commit hook and in CI on the full history.
* **Mealie side**: the bot acts as one Mealie user and can only see that user's
  household. Give it a dedicated user and a token you can revoke.
* **Container**: non-root user, read-only root file system, all capabilities
  dropped, `no-new-privileges`; see [compose.example.yml](../compose.example.yml).
* **Supply chain**: dependencies locked with hashes, base image pinned by
  digest, GitHub Actions pinned by commit SHA, images built with provenance and
  SBOM.

Please report vulnerabilities privately as described in [SECURITY.md](../SECURITY.md),
which also lists the supported versions.
