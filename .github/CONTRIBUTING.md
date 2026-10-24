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

The tests and `python -m mealie_bot` run from the repository root without
installing the package. `pip install -e .` works as well; it only picks up
`mealie_bot`, so a local `secrets/` directory does not get in the way.

The ruff and zizmor hooks run the versions from `requirements-dev.txt` inside
the virtual environment, so pre-commit and CI always agree. gitleaks is the
only hook with its own pin; it must match `GITLEAKS_VERSION` in
`.github/workflows/ci.yml` (a test checks this). Dependabot keeps the Python
tools, the base image and the actions current; bump gitleaks by hand in both
places.

Run the checks that CI runs:

```sh
ruff check . && ruff format --check .
mypy
lint-imports
pytest --cov
pip-audit --disable-pip --require-hashes -r requirements.txt
pip-audit --disable-pip --require-hashes -r requirements-dev.txt
zizmor .github/workflows
```

`pytest --cov` fails when branch coverage of `mealie_bot` drops below
`fail_under` in `pyproject.toml` (the measured value, rounded down; raise it
when coverage grows). `lint-imports` checks the layer boundaries declared in
`pyproject.toml`: the shopping parser and service do not import aiogram, the
Mealie client imports neither features nor Telegram code, and feature modules
do not import each other.

`tests/test_openapi_paths.py` checks every Mealie path the client calls, and
the fields the bot sends, against a trimmed copy of the Mealie OpenAPI document
in `tests/data/`. To check against your own instance instead, download its
document (`<MEALIE_URL>/openapi.json`) and run:

```sh
MEALIE_OPENAPI=path/to/openapi.json pytest tests/test_openapi_paths.py
```

After adding or changing a Mealie call, or when moving to a new Mealie version,
refresh the trimmed copy from the full document and commit it:

```sh
python scripts/trim_openapi.py path/to/openapi.json
```

The script fails if the client calls a path the document does not have. For a
new Mealie version, also update the file name in `tests/test_openapi_paths.py`
and [docs/compatibility.md](../docs/compatibility.md).

## Making changes

* Branch from `main` and open a pull request; direct pushes to `main` are not
  used.
* Every change comes with tests. Behaviour changes also update
  [docs/SPEC.md](../docs/SPEC.md), which is the source of truth for how the bot
  behaves.
* User-facing text lives in the string catalog under `mealie_bot/i18n/`.
  Add every new message to both `en.py` and `de.py`; the tests check that the
  catalogs are complete. Command names and unit synonyms belong there too.
* Before changing a Mealie API call, check the path and payload against the
  OpenAPI document of the targeted Mealie version (currently 3.29.0) and
  refresh `tests/data/` as described above.
* Add a line to the "Unreleased" section of [CHANGELOG.md](../CHANGELOG.md) for
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
  `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `build:`, `chore:`, `refactor:`,
  `perf:`, `style:`, `revert:`, with an optional scope such as `feat(shopping):`.
  The squash-merge title becomes the changelog entry, so make it descriptive.
  The *PR title* check fails for a pull request title that does not follow
  this format.
* Pull requests are squash-merged into `main`. No merge commits, no force
  pushes to `main`.
* No links to AI sessions or other private resources in commits, pull request
  text or files. A `Co-Authored-By` trailer is fine. `.claude/settings.json`
  configures this for Claude Code; check the pull request text before merging
  because the squash commit takes it over.
* CI must be green: ruff, mypy, import-linter, pytest with coverage, pip-audit,
  zizmor, gitleaks, the PR title check and the Docker build with its Trivy scan.
* Fill in the pull request template; it lists the checks above.

## Adding a language

Copy `mealie_bot/i18n/en.py`, translate the messages, command names and unit
spellings, and register the module in `mealie_bot/i18n/__init__.py`.

## Adding a feature module

Create a package under `mealie_bot/features/` that exports a `Feature`, add it
to `available_features()` and to `KNOWN_FEATURES` in `mealie_bot/config.py`.
The module is then switched on or off with `FEATURE_<NAME>`. A `Feature` names
its menu commands and two catalog keys, `start_key` and `help_key`, whose texts
become the module's sections of `/start` and `/help` (the core only adds a
greeting and the help intro).

## Releases

See [docs/development.md](../docs/development.md#releases). In short: bump
the version in `pyproject.toml` and `mealie_bot/__init__.py`, move the
"Unreleased" changelog entries under the new version, merge, then push the
`vX.Y.Z` tag.
