import pytest

import mealie_bot
from mealie_bot.config import ConfigError, Settings

BASE = {
    "TELEGRAM_BOT_TOKEN": "telegram-placeholder",
    "MEALIE_API_TOKEN": "mealie-placeholder",
    "ALLOWED_USER_IDS": "1001, 1002",
}


def test_defaults():
    settings = Settings.from_env(BASE)
    assert settings.mealie_url == "http://mealie:9000"
    assert settings.allowed_user_ids == {1001, 1002}
    assert settings.delete_commands is True
    assert settings.label_emoji == {}
    assert settings.label_icons == "both"
    assert settings.delete_item_messages is True
    assert settings.features == {"shopping"}
    assert settings.bot_language is None
    assert settings.log_level == "INFO"


def test_secrets_not_in_repr():
    assert "placeholder" not in repr(Settings.from_env(BASE))


def test_file_secrets(tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("from-file\n")
    env = {**BASE, "MEALIE_API_TOKEN_FILE": str(token_file)}
    del env["MEALIE_API_TOKEN"]
    assert Settings.from_env(env).mealie_token == "from-file"


def test_value_and_file_conflict(tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("x")
    with pytest.raises(ConfigError, match="not both"):
        Settings.from_env({**BASE, "MEALIE_API_TOKEN_FILE": str(token_file)})


def test_missing_file_does_not_leak_content(tmp_path):
    with pytest.raises(ConfigError, match="Cannot read"):
        Settings.from_env({**BASE, "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_BOT_TOKEN_FILE": "/nope"})


@pytest.mark.parametrize("missing", ["TELEGRAM_BOT_TOKEN", "MEALIE_API_TOKEN", "ALLOWED_USER_IDS"])
def test_required(missing):
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        Settings.from_env(env)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ALLOWED_USER_IDS", "abc"),
        ("ALLOWED_USER_IDS", " , "),
        ("MEALIE_URL", "mealie:9000"),
        ("BOT_LANGUAGE", "xx"),
        ("FEATURE_SHOPPING", "maybe"),
        ("LOG_LEVEL", "LOUD"),
        ("MEALIE_TIMEOUT", "-1"),
        ("MEALIE_TIMEOUT", "soon"),
        ("LABEL_ICONS", "circles"),
    ],
)
def test_invalid(key, value):
    with pytest.raises(ConfigError):
        Settings.from_env({**BASE, key: value})


@pytest.mark.parametrize("value", ["true", "1", "YES", "on"])
def test_true_spellings(value):
    assert Settings.from_env({**BASE, "DELETE_COMMANDS": value}).delete_commands is True


def test_options():
    settings = Settings.from_env(
        {
            **BASE,
            "MEALIE_URL": "https://mealie.example.com/",
            "BOT_LANGUAGE": "DE",
            "FEATURE_SHOPPING": "false",
            "SHOPPING_LIST": "Groceries",
            "LOG_LEVEL": "debug",
            "DELETE_COMMANDS": "no",
            "DELETE_ITEM_MESSAGES": "0",
            "LABEL_EMOJI": "Würzmittel=🌶️; Tiere = 🐾 ;broken;=🙂",
            "LABEL_ICONS": "Color",
        }
    )
    assert settings.label_icons == "color"
    assert settings.label_emoji == {"würzmittel": "🌶️", "tiere": "🐾"}
    assert settings.delete_commands is False
    assert settings.delete_item_messages is False
    assert settings.mealie_url == "https://mealie.example.com"
    assert settings.bot_language == "de"
    assert settings.features == frozenset()
    assert settings.shopping_list == "Groceries"
    assert settings.log_level == "DEBUG"


def test_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    import mealie_bot

    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == mealie_bot.__version__


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", None),
        ("0123456789ABCDEF0123456789abcdef01234567", "0123456"),
        ("abc1234", "abc1234"),
        ("abc12", None),
        ("main", None),
        ("<b>0123456", None),
    ],
)
def test_revision_is_a_short_commit_or_none(monkeypatch, value, expected):
    monkeypatch.setenv("VCS_REF", value)
    assert mealie_bot.revision() == expected
