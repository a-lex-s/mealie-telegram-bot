# Development

Setting up the environment, running the checks, adding a language or a feature
module and the pull request rules are described in
[CONTRIBUTING.md](../.github/CONTRIBUTING.md). This page covers running the bot itself
on your machine and cutting a release.

## Running locally

Requires Python 3.12 and a virtual environment with the dependencies installed
(see [CONTRIBUTING.md](../.github/CONTRIBUTING.md#development-setup)). The same commands
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
[docs/screenshots/README.md](screenshots/README.md). The bot's profile picture
lives in `docs/avatar/`: `bot-avatar.svg` is the source, `bot-avatar.png`
(640×640) is what you upload in BotFather with `/setuserpic`. The GitHub
social preview (`social-preview.svg`, rendered to `social-preview.png` at
1280×640) reuses the same drawing; upload the PNG under *Settings → General →
Social preview*. Both PNGs are rendered with a headless Chromium screenshot of
the SVG, so they need no extra tooling.

## Releases

Only final versions are released (`vX.Y.Z`); pre-release tags such as
`v0.2.0-rc1` fail the version check because PEP 440 spells them differently.

1. Bump `version` in `pyproject.toml` and `__version__` in `mealie_bot/__init__.py`,
   move the "Unreleased" entries of [CHANGELOG.md](../CHANGELOG.md) under the
   new version with a dated heading, add the `[X.Y.Z]` link at the bottom and
   point `[Unreleased]` at `compare/vX.Y.Z...main`. Merge that pull request and
   wait for CI on `main` to pass (a new advisory found by pip-audit or Trivy
   would also stop the release).
2. Tag the squash-merge commit on `main` and push the tag. Do not create the
   release in the GitHub UI; the workflow creates it.

   ```sh
   git fetch origin main
   git tag -a v0.1.0 -m "v0.1.0" origin/main
   git push origin v0.1.0
   ```

3. The release workflow checks that the tag matches the version in
   `pyproject.toml` and points to a commit on `main`, runs CI, then publishes
   `ghcr.io/a-lex-s/mealie-telegram-bot:v0.1.0` (and `:v0.1`, `linux/amd64`, no
   `latest`) with OCI labels, a BuildKit SBOM and a signed build provenance
   attestation. It then creates the GitHub release with generated notes, the
   image digest and the SPDX SBOM (`sbom.spdx.json`) attached. The job summary
   prints every tag with its digest; deploy by tag and digest. Attestation
   manifests show up as `unknown/unknown` entries in the GHCR package view,
   that is expected.
4. If the workflow fails before the image is pushed, fix the cause, delete the
   tag (`git push --delete origin v0.1.0 && git tag -d v0.1.0`) and tag again.
   If only the release job fails, use "Re-run failed jobs"; the release step
   updates an existing release instead of failing. Avoid "Re-run all jobs"
   after a successful run, it rebuilds the image and moves the tags to a new
   digest.
5. After the first release, open the package settings on GHCR and set the
   package to public (new packages start private) so that deployments can pull
   without a token.
6. Verify an image before deploying it:
   `gh attestation verify oci://ghcr.io/a-lex-s/mealie-telegram-bot:v0.1.0 --owner a-lex-s`.

The CI workflow also runs weekly so new advisories (pip-audit, Trivy) show up
without a code change, and the OpenSSF Scorecard workflow reports to code
scanning.
