import logging

from mealie_bot.logging_setup import RedactingFilter


def test_redacts_secrets_in_message_and_args():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "token=%s", ("s3cr3t",), None)
    RedactingFilter(["s3cr3t"]).filter(record)
    assert record.getMessage() == "token=***"


def test_redacts_secrets_in_exceptions():
    try:
        raise RuntimeError("bad s3cr3t")
    except RuntimeError:
        import sys

        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
    RedactingFilter(["s3cr3t"]).filter(record)
    assert "s3cr3t" not in record.exc_text
