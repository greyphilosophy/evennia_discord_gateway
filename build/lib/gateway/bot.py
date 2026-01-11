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
        chunks = chunk_text(text, self.config.output_chunk_size, self.config.output_max_chunks)
        if not chunks:
            return
        # Reply to the triggering message to keep threads clean
        first = True
        for c in chunks:
            if first:
                await message.reply(c, mention_author=False)
                first = False
            else:
                await message.channel.send(c)
                await asyncio.sleep(0.25)
