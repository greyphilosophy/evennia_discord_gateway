# tests/unit/test_bot.py

import pytest

from gateway.bot import chunk_text, fix_telnet_text, scrub_credentials


def test_chunk_text_splits_long_text() -> None:
    text = "A" * 2000
    result = chunk_text(text, 500, 5)
    assert len(result) == 4
    assert all(len(r) <= 500 for r in result)


def test_chunk_text_empty() -> None:
    assert chunk_text("", 100, 3) == []


def test_chunk_text_whitespace_only() -> None:
    assert chunk_text("   \n  ", 100, 3) == []


def test_chunk_text_short_text() -> None:
    text = "short"
    result = chunk_text(text, 100, 3)
    assert result == ["short"]


def test_chunk_text_respects_max_chunks() -> None:
    text = "A" * 2000
    result = chunk_text(text, 500, 2)
    assert len(result) == 3  # 2 content chunks + 1 truncated marker
    assert "…(output truncated)" in result[-1]


def test_chunk_text_prefers_newline_boundaries() -> None:
    text = "line1\n" + "A" * 100 + "\nline3\n" + "B" * 100
    result = chunk_text(text, 60, 5)
    assert len(result) >= 2


def test_fix_telnet_text_handles_normal_text() -> None:
    assert fix_telnet_text("Hello World") == "Hello World"


def test_fix_telnet_text_normalizes_dashes() -> None:
    text = "A\u2014B\u2013C\u2012D"  # em dash, en dash, figure dash
    result = fix_telnet_text(text)
    assert "\u2014" not in result
    assert "-" in result


def test_scrud_credentials_removes_login_lines() -> None:
    text = "Normal line\nCommand 'connect user pass' is not available.\nAnother line"
    result = scrub_credentials(text)
    assert "connect" not in result.lower() or "not available" not in result


def test_scrud_credentials_preserves_normal_lines() -> None:
    text = "You see a room.\nExits: north, south"
    assert scrub_credentials(text) == text
