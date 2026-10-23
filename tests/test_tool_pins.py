"""The gitleaks version is pinned twice; both pins must agree.

Dependabot updates neither .pre-commit-config.yaml nor the CI download, so
this test turns a forgotten pin into a failing check instead of silent drift.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_gitleaks_pins_match():
    pre_commit = (ROOT / ".pre-commit-config.yaml").read_text()
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    hook = re.search(r"gitleaks/gitleaks\n(?:.*\n)*?\s+rev: v(\S+)", pre_commit)
    workflow = re.search(r"GITLEAKS_VERSION: (\S+)", ci)
    assert hook and workflow
    assert hook.group(1) == workflow.group(1)
