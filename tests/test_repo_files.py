"""Sanity checks for the community and repository metadata files."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

COMMUNITY_FILES = [
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
]


@pytest.mark.parametrize("name", COMMUNITY_FILES)
def test_file_exists_and_is_not_empty(name: str) -> None:
    path = ROOT / name
    assert path.is_file(), f"{name} is missing"
    assert path.read_text(encoding="utf-8").strip(), f"{name} is empty"


def test_changelog_has_unreleased_section() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.startswith("# Changelog")
    assert "## [Unreleased]" in text


def test_codeowners_entries_are_well_formed() -> None:
    lines = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines()
    rules = [line for line in lines if line.strip() and not line.startswith("#")]
    assert rules, "CODEOWNERS has no rules"
    for rule in rules:
        pattern, *owners = rule.split()
        assert pattern
        assert owners, f"rule without owner: {rule!r}"
        for owner in owners:
            assert re.fullmatch(r"@[\w.-]+(/[\w.-]+)?", owner), owner


PROJECT_CONTACT = "a-lex-s-393168336@proton.me"


def test_security_policy_uses_private_reporting() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "/security/advisories/new" in text


@pytest.mark.parametrize("name", ["SECURITY.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md"])
def test_only_the_project_contact_address_is_used(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    assert emails <= {PROJECT_CONTACT}, emails


def test_issue_forms_have_name_description_and_body() -> None:
    for name in ("bug_report.yml", "feature_request.yml"):
        text = (ROOT / ".github/ISSUE_TEMPLATE" / name).read_text(encoding="utf-8")
        for key in ("name:", "description:", "body:"):
            assert re.search(rf"^{key}", text, re.MULTILINE), f"{name} lacks {key}"
