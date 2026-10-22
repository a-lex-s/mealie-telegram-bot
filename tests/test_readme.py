"""Checks for README.md, compose.example.yml and the mockup images."""

import re
from pathlib import Path
from xml.dom import minidom

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")

# Files that live in a separate pull request; links to them are allowed to dangle
# until that pull request is merged.
COMMUNITY_FILES = {"SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "CHANGELOG.md"}

_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _relative_links() -> list[str]:
    links = []
    for target in _LINK.findall(README):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        links.append(target.split("#", 1)[0])
    return links


def test_relative_links_point_to_existing_files() -> None:
    links = _relative_links()
    assert links, "README has no relative links"
    missing = [link for link in links if link not in COMMUNITY_FILES and not (ROOT / link).exists()]
    assert not missing, f"broken links in README: {missing}"


def test_anchor_links_point_to_existing_headings() -> None:
    headings = {
        re.sub(r"[^a-z0-9 -]", "", line.lstrip("#").strip().lower()).replace(" ", "-")
        for line in README.splitlines()
        if line.startswith("#")
    }
    anchors = [t[1:] for t in _LINK.findall(README) if t.startswith("#")]
    assert anchors
    missing = [a for a in anchors if a not in headings]
    assert not missing, f"broken anchors in README: {missing}"


def test_readme_documents_every_setting() -> None:
    from mealie_bot.config import KNOWN_FEATURES

    names = [
        "TELEGRAM_BOT_TOKEN",
        "MEALIE_API_TOKEN",
        "ALLOWED_USER_IDS",
        "MEALIE_URL",
        "BOT_LANGUAGE",
        "SHOPPING_LIST",
        "MEALIE_TIMEOUT",
        "LOG_LEVEL",
    ] + [f"FEATURE_{name.upper()}" for name in KNOWN_FEATURES]
    for name in names:
        assert f"`{name}`" in README, f"{name} is not documented in README"


@pytest.mark.parametrize("image", sorted((ROOT / "docs/images").glob("*.svg")))
def test_mockups_are_valid_svg_without_external_references(image: Path) -> None:
    text = image.read_text(encoding="utf-8")
    doc = minidom.parseString(text)
    assert doc.documentElement.tagName == "svg"
    assert not re.search(r"<image|href=|url\(|<script", text), "mockups must be self-contained"
    assert image.name in README, f"{image.name} is not used in the README"


def test_mockups_use_placeholder_names_only() -> None:
    names = {
        m.group(1)
        for image in (ROOT / "docs/images").glob("*.svg")
        for m in re.finditer(r'font-weight="600" fill="#3a9d4a">([^<]+)<', image.read_text("utf-8"))
    }
    assert names <= {"Alice", "Bob"}, names


def test_compose_example_has_localhost_variant() -> None:
    text = (ROOT / "compose.example.yml").read_text(encoding="utf-8")
    assert "MEALIE_URL: http://mealie:9000" in text
    assert "# network_mode: host" in text.replace("#   network_mode", "# network_mode")
    assert "http://localhost:9000" in text
    assert "@" not in text.replace("@sha256", "")
