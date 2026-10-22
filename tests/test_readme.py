"""Checks for README.md, the docs/ pages, compose.example.yml, mockups and screenshots."""

import re
from pathlib import Path
from xml.dom import minidom

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
PAGES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]

_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _relative_links(text: str) -> list[str]:
    links = []
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        links.append(target.split("#", 1)[0])
    return links


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_relative_links_point_to_existing_files(page: Path) -> None:
    links = _relative_links(page.read_text(encoding="utf-8"))
    missing = [link for link in links if not (page.parent / link).exists()]
    assert not missing, f"broken links in {page.name}: {missing}"


def _headings(text: str) -> set[str]:
    return {
        re.sub(r"[^a-z0-9 -]", "", line.lstrip("#").strip().lower()).replace(" ", "-")
        for line in text.splitlines()
        if line.startswith("#")
    }


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_anchor_links_point_to_existing_headings(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    missing = []
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:")) or "#" not in target:
            continue
        path, anchor = target.split("#", 1)
        other = (page.parent / path).read_text(encoding="utf-8") if path else text
        if anchor not in _headings(other):
            missing.append(target)
    assert not missing, f"broken anchors in {page.name}: {missing}"


def test_configuration_page_documents_every_setting() -> None:
    from mealie_bot.config import KNOWN_FEATURES

    page = (ROOT / "docs/configuration.md").read_text(encoding="utf-8")

    names = [
        "TELEGRAM_BOT_TOKEN",
        "MEALIE_API_TOKEN",
        "ALLOWED_USER_IDS",
        "MEALIE_URL",
        "BOT_LANGUAGE",
        "SHOPPING_LIST",
        "DELETE_COMMANDS",
        "DELETE_ITEM_MESSAGES",
        "MEALIE_TIMEOUT",
        "TZ",
        "LOG_LEVEL",
    ] + [f"FEATURE_{name.upper()}" for name in KNOWN_FEATURES]
    for name in names:
        assert f"`{name}`" in page, f"{name} is not documented in docs/configuration.md"


# The views shown in the README. Each one is a real screenshot in docs/screenshots/
# once it exists, otherwise the SVG mockup of the same name in docs/images/.
VIEWS = ["list-collapsed", "list-expanded", "add-items"]
MAX_SCREENSHOT_BYTES = 400_000


@pytest.mark.parametrize("image", sorted((ROOT / "docs/images").glob("*.svg")))
def test_mockups_are_valid_svg_without_external_references(image: Path) -> None:
    text = image.read_text(encoding="utf-8")
    doc = minidom.parseString(text)
    assert doc.documentElement.tagName == "svg"
    assert not re.search(r"<image|href=|url\(|<script", text), "mockups must be self-contained"
    assert image.stem in VIEWS, f"{image.name} is not one of the README views"


@pytest.mark.parametrize("view", VIEWS)
def test_readme_shows_screenshot_or_falls_back_to_mockup(view: str) -> None:
    screenshot = ROOT / "docs/screenshots" / f"{view}.png"
    mockup = ROOT / "docs/images" / f"{view}.svg"
    if screenshot.exists():
        assert f"docs/screenshots/{view}.png" in README, f"README does not use {screenshot.name}"
        assert f"docs/images/{view}.svg" not in README, f"README still uses the mockup for {view}"
    else:
        assert mockup.exists(), f"neither a screenshot nor a mockup exists for {view}"
        assert f"docs/images/{view}.svg" in README, f"README does not use {mockup.name}"


@pytest.mark.parametrize("image", sorted((ROOT / "docs/screenshots").glob("*.png")))
def test_screenshots_are_small_png_files(image: Path) -> None:
    assert image.stem.removesuffix("-dark") in VIEWS, f"{image.name} is not one of the README views"
    assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{image.name} is not a PNG"
    assert image.stat().st_size <= MAX_SCREENSHOT_BYTES, f"{image.name} is larger than 400 kB"


def test_mockups_use_placeholder_names_only() -> None:
    names = {
        m.group(1)
        for image in (ROOT / "docs/images").glob("*.svg")
        for m in re.finditer(r'font-weight="600" fill="#3a9d4a">([^<]+)<', image.read_text("utf-8"))
    }
    assert names <= {"Alice", "Bob"}, names


def test_compose_example_covers_all_deployment_variants() -> None:
    text = (ROOT / "compose.example.yml").read_text(encoding="utf-8")
    # One MEALIE_URL line per variant: same network, standalone over HTTPS, localhost.
    urls = re.findall(r"^\s*#?\s*MEALIE_URL: (\S+)$", text, re.MULTILINE)
    assert urls == [
        "http://mealie:9000",
        "https://mealie.example.com",
        "http://localhost:9000",
    ], urls
    assert re.search(r"^\s*#\s*network_mode: host\b", text, re.MULTILINE)
    assert "@" not in text.replace("@sha256", "")


def test_readme_links_every_docs_page() -> None:
    for page in (ROOT / "docs").glob("*.md"):
        assert f"docs/{page.name}" in README, f"{page.name} is not linked from the README"
