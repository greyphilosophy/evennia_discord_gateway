# tests/integration/test_installation.py
"""Integration tests for the evennia-discord-gateway.

Tests verify the gateway can be installed, configured, and started correctly.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

import pytest


GATEWAY_CLI = shutil.which("eddg")
HAS_GATEWAY = importlib.util.find_spec("gateway") is not None


@pytest.mark.skipif(not HAS_GATEWAY, reason="Gateway is not installed in this environment")
def test_gateway_module_is_importable() -> None:
    """Verify the gateway package imports cleanly."""
    import gateway
    assert hasattr(gateway, "__file__")


def test_config_requires_discord_token() -> None:
    """Verify config validation rejects missing DISCORD_TOKEN."""
    from gateway.config import _env, load_config

    # Save and clear DISCORD_TOKEN
    saved = os.environ.get("DISCORD_TOKEN")
    os.environ.pop("DISCORD_TOKEN", None)
    try:
        # Force re-read
        with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
            load_config()
    finally:
        if saved:
            os.environ["DISCORD_TOKEN"] = saved


def test_config_with_valid_token() -> None:
    """Verify config loads successfully when DISCORD_TOKEN is set."""
    from gateway.config import load_config

    os.environ["DISCORD_TOKEN"] = "test_token_123"
    cfg = load_config()
    assert cfg.discord_token == "test_token_123"
    assert cfg.evennia_host == "127.0.0.1"
    assert cfg.evennia_port == 4000


def test_stable_password_is_deterministic() -> None:
    """Verify stable_password produces consistent results."""
    from gateway.telnet_session import stable_password

    secret = "my_secret"
    user_id = "1234567890"
    pw1 = stable_password(secret, user_id)
    pw2 = stable_password(secret, user_id)
    assert pw1 == pw2
    assert pw1.startswith("pw_")
    assert len(pw1) > 0


def test_stable_password_differs_per_user() -> None:
    """Verify different users get different passwords."""
    from gateway.telnet_session import stable_password

    secret = "my_secret"
    pw1 = stable_password(secret, "user1")
    pw2 = stable_password(secret, "user2")
    assert pw1 != pw2


def test_gateway_cli_exists() -> None:
    """Verify the 'eddg' CLI command is available."""
    assert GATEWAY_CLI is not None, "eddg CLI command not found"


def test_account_name_generation() -> None:
    """Verify account name generation from Discord user data."""
    from gateway.bot import _account_name_from_discord, _sanitize_ic_name

    # Normal case
    name = _account_name_from_discord("Neko", "123456789012345678")
    assert "Neko" in name
    assert "-" in name

    # Sanitization
    assert _sanitize_ic_name("O'Brien") == "O'Brien"
