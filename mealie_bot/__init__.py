"""Telegram bot front end for a self-hosted Mealie instance."""

import os
import re

__version__ = "0.2.0"

# Set by the image build from the VCS_REF build argument (see Dockerfile).
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


def revision() -> str | None:
    """Short commit the image was built from (``VCS_REF``), or None for local
    runs and values that do not look like a commit hash."""
    value = os.environ.get("VCS_REF", "").strip().lower()
    return value[:7] if _COMMIT.match(value) else None
