# tests/unit/test_config.py

import os
import pytest

from gateway.config import _env, _env_int, _env_bool, load_config


def test_env_returns_value_from_env_var() -> None:
    os.environ["TEST_VAR"] = "hello"
    assert _env("TEST_VAR") == "hello"
    assert _env("TEST_VAR", "default") == "hello"


def test_env_returns_default_when_missing() -> None:
    os.environ["TEST_VAR"] = "hello"
    assert _env("NONEXISTENT", "default") == "default"
    assert _env("NONEXISTENT") is None


def test_env_trims_whitespace() -> None:
    os.environ["TEST_VAR"] = "  hello  "
    assert _env("TEST_VAR") == "hello"


def test_env_returns_default_for_empty_string() -> None:
    os.environ["TEST_VAR"] = "  "
    assert _env("TEST_VAR", "default") == "default"


def test_env_int_parses_correctly() -> None:
    os.environ["PORT"] = "4000"
    assert _env_int("PORT", 2000) == 4000


def test_env_int_returns_default_on_missing() -> None:
    assert _env_int("MISSING", 2000) == 2000


def test_env_int_returns_default_on_invalid() -> None:
    os.environ["PORT"] = "abc"
    assert _env_int("PORT", 2000) == 2000


def test_env_bool_returns_true_for_truthy_values() -> None:
    for val in ["1", "true", "yes", "y", "on"]:
        os.environ["TEST_BOOL"] = val
        assert _env_bool("TEST_BOOL", False) is True


def test_env_bool_returns_false_for_falsy_values() -> None:
    for val in ["0", "false", "no", "n", "off"]:
        os.environ["TEST_BOOL"] = val
        assert _env_bool("TEST_BOOL", True) is False


def test_env_bool_returns_default_when_missing() -> None:
    assert _env_bool("MISSING_BOOL", True) is True


def test_load_config_requires_discord_token() -> None:
    os.environ["DISCORD_TOKEN"] = "tok123"
    cfg = load_config()
    assert cfg.discord_token == "tok123"
    assert cfg.dm_only is True
    assert cfg.evennia_host == "127.0.0.1"
    assert cfg.evennia_port == 4000


def test_load_config_raises_on_missing_discord_token() -> None:
    os.environ.pop("DISCORD_TOKEN", None)
    with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
        load_config()


def test_load_config_respects_env_overrides() -> None:
    os.environ["DISCORD_TOKEN"] = "tok456"
    os.environ["EVENNIA_HOST"] = "192.168.1.1"
    os.environ["EVENNIA_PORT"] = "4001"
    os.environ["DM_ONLY"] = "false"
    os.environ["OUTPUT_CHUNK_SIZE"] = "2000"
    os.environ["IDLE_TIMEOUT_S"] = "7200"
    os.environ["AUTO_CREATE_ACCOUNTS"] = "false"
    os.environ["ACCOUNT_PREFIX"] = "mud_"
    os.environ["AUTO_SET_NICKNAME"] = "false"
    os.environ["WARN_PUBLIC_PLAY"] = "false"

    cfg = load_config()
    assert cfg.discord_token == "tok456"
    assert cfg.dm_only is False
    assert cfg.evennia_host == "192.168.1.1"
    assert cfg.evennia_port == 4001
    assert cfg.output_chunk_size == 2000
    assert cfg.idle_timeout_s == 7200
    assert cfg.auto_create_accounts is False
    assert cfg.account_prefix == "mud_"
    assert cfg.auto_set_nickname is False
    assert cfg.warn_public_play is False
