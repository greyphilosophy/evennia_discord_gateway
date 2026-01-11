from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Dict

import discord

from .config import Config
from .db import Database
from .telnet_session import EvenniaTelnetSession, stable_password

# --- ANSI -> Discord formatting ---
# Evennia's telnet output often includes ANSI color/style escape sequences.
# Discord only renders these inside fenced code blocks tagged as `ansi`.
# We therefore wrap output in ```ansi ...``` blocks and chunk in a way that
# avoids splitting inside an escape sequence.

_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _safe_cut_no_partial_ansi(s: str, cut: int) -> int:
    """Return a cut index <= cut that does not split an ANSI escape.

    If the cut would land in the middle of a CSI sequence (ESC [ ... letter),
    we back up to just before the ESC.
    """
    if cut <= 0 or cut >= len(s):
        return cut

    window = s[:cut]
    esc = window.rfind("\x1b")
    if esc == -1:
        return cut

    m = _ANSI_CSI_RE.match(s, esc)
    if m and m.end() <= cut:
        return cut
    return esc


def chunk_ansi_text(text: str, size: int, max_chunks: int) -> list[str]:
    """Chunk text for Discord without splitting ANSI escape sequences."""
    text = (text or "").replace("\r\n", "\n")
    if not text.strip():
        return []

    chunks: list[str] = []
    while text and len(chunks) < max_chunks:
        if len(text) <= size:
            chunks.append(text)
            break

        cut = size
        window = text[:size]

        nl = window.rfind("\n", max(0, size - size // 3))
        if nl != -1 and nl > 0:
            cut = nl + 1

        cut = _safe_cut_no_partial_ansi(text, cut)
        if cut <= 0:
            m = _ANSI_CSI_RE.match(text)
            if m:
                cut = min(m.end(), len(text))
            else:
                cut = min(size, len(text))

        chunks.append(text[:cut])
        text = text[cut:]

    if text and len(chunks) >= max_chunks:
        chunks.append("…(output truncated)")

    return [c.rstrip() for c in chunks if c.strip()]


def wrap_discord_ansi_block(s: str) -> str:
    """Wrap in a Discord ```ansi``` fenced block and ensure a reset at end."""
    s = s or ""
    if not s.endswith("\x1b[0m"):
        s = s + "\x1b[0m"
    return f"```ansi\n{s}\n```"

def _now_ts() -> int:
    return int(time.time())


def _display_name(user: discord.abc.User, message: discord.Message) -> str:
    # Prefer guild display name if present, else username.
    if message.guild and isinstance(message.author, discord.Member):
        return message.author.display_name
    return user.name


def _sanitize_ic_name(name: str) -> str:
    # Keep it simple/safe; Evennia typically allows letters, spaces, apostrophes.
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^A-Za-z0-9 '\-]", "", name)
    return name[:30].strip() or "Adventurer"


def chunk_text(text: str, size: int, max_chunks: int) -> list[str]:
    text = text or ""
    # Discord hates empty messages
    if not text.strip():
        return []

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # Fix fancy hyphens
    text = text.translate({
        ord("\u2010"): ord("-"),
        ord("\u2011"): ord("-"),
        ord("\u2012"): ord("-"),
        ord("\u2013"): ord("-"),
        ord("\u2014"): ord("-"),
        ord("\u2212"): ord("-"),
    })

    chunks = []
    while text and len(chunks) < max_chunks:
        if len(text) <= size:
            chunks.append(text)
            break

        # Try to split on a newline within the last third of the chunk.
        cut = size
        window = text[:size]
        nl = window.rfind("\n", max(0, size - size // 3))
        if nl != -1 and nl > 0:
            cut = nl + 1

        chunks.append(text[:cut])
        text = text[cut:]

    if text and len(chunks) >= max_chunks:
        chunks.append("…(output truncated)")

    # Trim trailing whitespace per chunk
    return [c.rstrip() for c in chunks if c.strip()]

def fix_telnet_text(s: str) -> str:
    """
    Fix mojibake caused by non-UTF8 bytes in a stream we attempted to decode as UTF-8.
    With surrogateescape enabled, we can round-trip the original bytes and decode them
    as cp1252 when UTF-8 produces too many replacement chars.
    """
    if not s:
        return s

    # Recover original bytes (including any surrogateescaped bytes)
    raw = s.encode("utf-8", "surrogateescape")

    # Try UTF-8 first (what we want)
    utf8 = raw.decode("utf-8", "replace")

    # Also try cp1252 (common for smart punctuation)
    cp1252 = raw.decode("cp1252", "replace")

    # Pick the version with fewer replacement characters
    best = utf8 if utf8.count("�") <= cp1252.count("�") else cp1252

    # Normalize common dash variants to plain hyphen for Discord consistency
    best = best.translate({
        ord("\u2010"): ord("-"),  # hyphen
        ord("\u2011"): ord("-"),  # non-breaking hyphen
        ord("\u2012"): ord("-"),  # figure dash
        ord("\u2013"): ord("-"),  # en dash
        ord("\u2014"): ord("-"),  # em dash
        ord("\u2212"): ord("-"),  # minus sign
    })
    return best

class GatewayBot(discord.Client):
    def __init__(self, config: Config, db: Database):
        intents = discord.Intents.default()
        # We need message content to interpret commands.
        intents.message_content = True

        super().__init__(intents=intents)
        self.config = config
        self.db = db

        # discord_user_id -> telnet session
        self.sessions: Dict[str, EvenniaTelnetSession] = {}

        # Password derivation secret (required)
        self.gateway_secret = os.getenv("GATEWAY_SECRET")
        if not self.gateway_secret:
            raise RuntimeError("GATEWAY_SECRET is required (used to derive stable Evennia passwords)")

        # Optional nickname set command template
        # Example: "@icname {name}" or "@rename me={name}"
        self.nick_cmd_template = os.getenv("NICK_COMMAND_TEMPLATE", "").strip()

    async def on_ready(self):
        print(f"GatewayBot logged in as {self.user} (dm_only={self.config.dm_only})")

    async def on_message(self, message: discord.Message):
        # Ignore bots (including ourselves)
        if message.author.bot:
            return

        # DM-only restriction
        if self.config.dm_only and message.guild is not None:
            return

        # Optional warning for public play
        if (not self.config.dm_only) and self.config.warn_public_play and message.guild is not None:
            # One-time gentle warning per user per process (not persisted)
            if not getattr(message.author, "_eddg_warned", False):
                try:
                    setattr(message.author, "_eddg_warned", True)
                except Exception:
                    pass
                await message.reply(
                    "Heads up: you’re playing in a public channel — other people can read your game history here.",
                    mention_author=False,
                )

        content = (message.content or "").strip()
        if not content:
            return

        # Local help
        if content.lower() in {"help", "?", "commands"}:
            await self._send_chunks(
                message,
                """Commands:
- logout: end your current session
- whoami: show your mapped Evennia account
- Anything else is sent to the MUD as a command.

Notes:
- Your Discord account is mapped 1:1 to a single Evennia account.
- Output may be split into multiple messages.
""",
            )
            return

        discord_id = str(message.author.id)
        acct = f"{self.config.account_prefix}{discord_id}"
        pwd = stable_password(self.gateway_secret, discord_id)
        disp = _display_name(message.author, message)

        # Persist mapping (1:1)
        self.db.upsert_user(discord_id, acct, pwd, _now_ts(), last_discord_name=disp)

        # Session control
        if content.lower() == "logout":
            await self._logout(discord_id, message)
            return

        if content.lower() == "whoami":
            await self._send_chunks(message, f"Evennia account: `{acct}`")
            return

        # Ensure telnet session
        sess = self.sessions.get(discord_id)
        if not sess:
            sess = EvenniaTelnetSession(
                host=self.config.evennia_host,
                port=self.config.evennia_port,
                idle_timeout_s=self.config.idle_timeout_s,
            )
            self.sessions[discord_id] = sess

        try:
            # Login / auto-create
            login_result = await sess.ensure_logged_in(
                account=acct,
                password=pwd,
                auto_create=self.config.auto_create_accounts,
            )

            if login_result.created_account:
                await self._send_chunks(message, "Created your new game account. Welcome!\n")

                # Optional nickname set
                if self.config.auto_set_nickname and self.nick_cmd_template:
                    ic = _sanitize_ic_name(disp)
                    nick_cmd = self.nick_cmd_template.format(name=ic)
                    await sess.run_command(nick_cmd)

            # Send command
            out = await sess.run_command(content)

            # If Evennia echoed nothing, don't spam
            if out.strip():
                await self._send_chunks(message, out)
            else:
                # Some commands produce no output; give a subtle ack
                await message.add_reaction("✅")

        except Exception as e:
            await self._send_chunks(message, f"Gateway error: {e}")

    async def _logout(self, discord_id: str, message: discord.Message):
        sess = self.sessions.pop(discord_id, None)
        if sess:
            try:
                await sess.close()
            except Exception:
                pass
        await self._send_chunks(message, "Logged out.")

    async def _send_chunks(self, message: discord.Message, text: str):
        text = text or ""
        text = fix_telnet_text(text)

        # If the output contains ANSI, prefer Discord's ```ansi``` rendering.
        if "\x1b[" in text:
            fence_overhead = len("```ansi\n") + len("\n```")
            inner_size = max(200, self.config.output_chunk_size - fence_overhead)
            raw_chunks = chunk_ansi_text(text, inner_size, self.config.output_max_chunks)
            chunks = [wrap_discord_ansi_block(c) for c in raw_chunks]
        else:
            chunks = chunk_text(text, self.config.output_chunk_size, self.config.output_max_chunks)

        if not chunks:
            return

        first = True
        for c in chunks:
            if first:
                await message.reply(c, mention_author=False)
                first = False
            else:
                await message.channel.send(c)
                await asyncio.sleep(0.25)
