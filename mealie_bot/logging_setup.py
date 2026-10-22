"""Logging setup that keeps secrets out of log output."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable

REDACTED = "***"


class RedactingFilter(logging.Filter):
    """Replaces any configured secret value in a log record with a placeholder."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = tuple(s for s in secrets if s)

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            redacted = redacted.replace(secret, REDACTED)
        if redacted != message:
            record.msg = redacted
            record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            for secret in self._secrets:
                record.exc_text = record.exc_text.replace(secret, REDACTED)
        return True


def setup_logging(level: str, secrets: Iterable[str]) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter(secrets))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Request URLs are logged by httpx at INFO; they carry no secrets, but they are noise.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
