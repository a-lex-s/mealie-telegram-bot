# Contributing

Thanks for helping out. This document explains how to set up a development
environment and what a pull request needs to be merged.

## Ground rules

* Version 1 is a shopping list helper. Recipe and meal plan features are out of
  scope until the shopping list has proven itself in daily use; the module
  structure under `mealie_bot/features/` already leaves room for them.
* The bot talks only to the Telegram Bot API and to `MEALIE_URL`. No other
  network access, no telemetry, no AI calls.
* The repository is public. Never commit personal data: no real names, email
  addresses, domains, host names, IP addresses or Telegram IDs, not even in
  tests, examples, commit messages or pull request text. Use `example.com`,
  placeholder IDs and the names Alice and Bob.
* Never commit secrets. gitleaks runs as a pre-commit hook and in CI.
* Configuration happens only through environment variables and `*_FILE`
  secrets.

## Development setup

Python 3.12 is required.

```sh
python3.12 -m venv .venv
. .venv/bin/activate              # bash/zsh
# source .venv/bin/activate.fish  # fish
pip install --require-hashes -r requirements-dev.txt
pip install pre-commit && pre-commit install
```

Run the checks that CI runs:

```sh
ruff check . && ruff format --check .
mypy
pytest
pip-audit --disable-pip --require-hashes -r requirements.txt
pip-audit --disable-pip --require-hashes -r requirements-dev.txt
zizmor .github/workflows
```

To verify the Mealie client against your own instance, download its OpenAPI
document (`<MEALIE_URL>/openapi.json`) and run:

```sh
MEALIE_OPENAPI=path/to/openapi.json pytest tests/test_openapi_paths.py
```

## Making changes

* Branch from `main` and open a pull request; direct pushes to `main` are not
  used.
* Every change comes with tests. Behaviour changes also update
  [docs/SPEC.md](docs/SPEC.md), which is the source of truth for how the bot
  behaves.
* User-facing text lives in the string catalog under `mealie_bot/i18n/`.
  Add every new message to both `en.py` and `de.py`; the tests check that the
  catalogs are complete. Command names and unit synonyms belong there too.
* Before changing a Mealie API call, check the path and payload against the
  OpenAPI document of the targeted Mealie version (currently 3.29.0).
* Add a line to the "Unreleased" section of [CHANGELOG.md](CHANGELOG.md) for
  anything a user would notice.
* Pin versions. Dependencies are declared in `pyproject.toml` and locked with
  hashes:

  ```sh
  uv pip compile pyproject.toml --python-version 3.12 --generate-hashes --no-header -o requirements.txt
  uv pip compile requirements-dev.in --python-version 3.12 --generate-hashes --no-header -o requirements-dev.txt
  ```

  Run both commands together so the two files agree; CI and the image build
  run `pip check` and fail when locked versions contradict each other.
  GitHub Actions are pinned to commit SHAs and the base image to a digest.

## Commits and pull requests

* Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `build:`, `chore:`, `refactor:`.
  The squash-merge title becomes the changelog entry, so make it descriptive.
* Pull requests are squash-merged into `main`. No merge commits, no force
  pushes to `main`.
* No links to AI sessions or other private resources in commits, pull request
  text or files. A `Co-Authored-By` trailer is fine. `.claude/settings.json`
  configures this for Claude Code; check the pull request text before merging
  because the squash commit takes it over.
* CI must be green: ruff, mypy, pytest, pip-audit, zizmor, gitleaks and the Docker
  build with its Trivy scan.
* Fill in the pull request template; it lists the checks above.

## Adding a language

Copy `mealie_bot/i18n/en.py`, translate the messages, command names and unit
spellings, and register the module in `mealie_bot/i18n/__init__.py`.

## Adding a feature module

Create a package under `mealie_bot/features/` that exports a `Feature`, add it
to `available_features()` and to `KNOWN_FEATURES` in `mealie_bot/config.py`.
The module is then switched on or off with `FEATURE_<NAME>`.

## Releases

See [docs/development.md](docs/development.md#releases). In short: bump
the version in `pyproject.toml` and `mealie_bot/__init__.py`, move the
"Unreleased" changelog entries under the new version, merge, then push the
`vX.Y.Z` tag.
