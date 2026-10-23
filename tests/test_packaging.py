"""The package build must only pick up ``mealie_bot``.

A local ``secrets/`` directory (recommended for the ``*_FILE`` secrets) sits next
to the package. Without explicit discovery setuptools treats it as a second
top-level package and refuses ``pip install -e .``.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_package_discovery_is_limited_to_mealie_bot() -> None:
    config = _pyproject()
    find = config["tool"]["setuptools"]["packages"]["find"]  # type: ignore[index]
    assert find["include"] == ["mealie_bot*"]
    assert (ROOT / "mealie_bot" / "__init__.py").is_file()


def test_build_backend_is_declared() -> None:
    build = _pyproject()["build-system"]
    assert build["build-backend"] == "setuptools.build_meta"  # type: ignore[index]
