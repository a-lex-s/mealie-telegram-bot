"""The PR title check accepts Conventional Commits and nothing else."""

import re
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "pr-title.yml"


def pattern() -> str:
    match = re.search(r"pattern='([^']+)'", WORKFLOW.read_text(encoding="utf-8"))
    assert match, "pattern not found in pr-title.yml"
    return match.group(1)


@pytest.mark.parametrize(
    ("title", "ok"),
    [
        ("fix(shopping): keep the note", True),
        ("feat: add a /version command", True),
        ("build(deps): bump httpx", True),
        ("ci(deps): bump the actions group", True),
        ("feat!: drop Python 3.11", True),
        ("Update stuff", False),
        ("feat: ", False),
        ("docs:no space", False),
        ("Feat: capitalised type", False),
    ],
)
def test_title_pattern(title: str, ok: bool) -> None:
    # grep -E, exactly as the workflow runs it.
    result = subprocess.run(
        ["grep", "-Eq", pattern()], input=title, text=True, check=False, capture_output=True
    )
    assert (result.returncode == 0) is ok
