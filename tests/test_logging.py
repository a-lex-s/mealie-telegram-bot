import logging

from mealie_bot.logging_setup import RedactingFilter, setup_logging


def test_redacts_secrets_in_message_and_args():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "token=%s", ("s3cr3t",), None)
    RedactingFilter(["s3cr3t"]).filter(record)
    assert record.getMessage() == "token=***"


def test_setup_logging_redacts_on_the_root_handler(capsys):
    setup_logging("DEBUG", ["s3cr3t", ""])
    logging.getLogger("mealie_bot.something").warning("token=%s", "s3cr3t")
    logging.getLogger("httpx").info("GET http://mealie.example.com/?token=s3cr3t")
    out = capsys.readouterr().out
    assert "token=***" in out and "s3cr3t" not in out
    assert "GET http" not in out  # httpx is quietened to WARNING


def test_redacts_secrets_in_exceptions():
    try:
        raise RuntimeError("bad s3cr3t")
    except RuntimeError:
        import sys

        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
    RedactingFilter(["s3cr3t"]).filter(record)
    assert "s3cr3t" not in record.exc_text
