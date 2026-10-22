# Development

Setting up the environment, running the checks, adding a language or a feature
module and the pull request rules are described in
[CONTRIBUTING.md](../CONTRIBUTING.md). This page covers running the bot itself
on your machine and cutting a release.

## Running locally

Requires Python 3.12 and a virtual environment with the dependencies installed
(see [CONTRIBUTING.md](../CONTRIBUTING.md#development-setup)). The same commands
work under WSL.

Put the tokens into `secrets/telegram_bot_token` and `secrets/mealie_api_token`
(the `secrets/` directory is ignored by git) and start the bot against a Mealie
on `localhost`. With bash or zsh:

```sh
. .venv/bin/activate
export TELEGRAM_BOT_TOKEN_FILE=./secrets/telegram_bot_token
export MEALIE_API_TOKEN_FILE=./secrets/mealie_api_token
export MEALIE_URL=http://localhost:9000
export ALLOWED_USER_IDS=123456789
python -m mealie_bot
```

With fish:

```fish
source .venv/bin/activate.fish
set -x TELEGRAM_BOT_TOKEN_FILE ./secrets/telegram_bot_token
set -x MEALIE_API_TOKEN_FILE ./secrets/mealie_api_token
set -x MEALIE_URL http://localhost:9000
set -x ALLOWED_USER_IDS 123456789
python -m mealie_bot
```

To run the container instead of the venv against a Mealie on `localhost`, use
the commented variant in [compose.example.yml](../compose.example.yml)
(`network_mode: host`).

To check the Mealie client against your own instance, download
`<MEALIE_URL>/openapi.json` and run:

```sh
MEALIE_OPENAPI=path/to/openapi.json pytest tests/test_openapi_paths.py
```

## Screenshots

The images in the README come from `docs/screenshots/`; how to take them with
placeholder data only is described in
[docs/screenshots/README.md](screenshots/README.md). Until a screenshot exists,
the README shows the SVG mockup from `docs/images/`.

## Releases

1. Bump `version` in `pyproject.toml` and `__version__` in `mealie_bot/__init__.py`,
   move the "Unreleased" entries of [CHANGELOG.md](../CHANGELOG.md) under the
   new version, and merge that pull request.
2. Tag the merge commit on `main` and push the tag:
   `git tag v0.1.0 && git push origin v0.1.0`.
3. The release workflow runs CI, checks that the tag matches the version in
   `pyproject.toml`, then publishes
   `ghcr.io/a-lex-s/mealie-telegram-bot:v0.1.0` (and `:v0.1`, `linux/amd64`)
   with OCI labels, a BuildKit SBOM and a signed build provenance attestation.
   It then creates a GitHub release with generated notes, the image digest and
   the SPDX SBOM (`sbom.spdx.json`) attached. Deploy by tag and digest.
4. Verify an image before deploying it:
   `gh attestation verify oci://ghcr.io/a-lex-s/mealie-telegram-bot:v0.1.0 --owner a-lex-s`.

The CI workflow also runs weekly so new advisories (pip-audit, Trivy) show up
without a code change, and the OpenSSF Scorecard workflow reports to code
scanning.
