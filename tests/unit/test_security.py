# tests/unit/test_security.py

import pytest

from gateway.bot import _account_name_from_discord, _sanitize_ic_name


def test_sanitize_ic_name_removes_special_chars() -> None:
    result = _sanitize_ic_name("Héllö! World")
    assert result == "Hll World"


def test_sanitize_ic_name_keeps_apostrophes() -> None:
    result = _sanitize_ic_name("O'Brien")
    assert result == "O'Brien"


def test_sanitize_ic_name_truncates_to_30() -> None:
    result = _sanitize_ic_name("A" * 50)
    assert len(result) == 30


def test_sanitize_ic_name_defaults_on_empty() -> None:
    assert _sanitize_ic_name("") == "Adventurer"


def test_account_name_includes_suffix() -> None:
    result = _account_name_from_discord("Neko", "123456789012345678")
    assert "Neko" in result
    assert result.endswith("-5678")


def test_account_name_truncates_correctly() -> None:
    long_name = "A" * 30
    result = _account_name_from_discord(long_name, "0000")
    assert len(result) <= 30


def test_account_name_sanitizes_input() -> None:
    result = _account_name_from_discord("C@t!", "1234")
    assert "@" not in result
    assert "!" not in result
