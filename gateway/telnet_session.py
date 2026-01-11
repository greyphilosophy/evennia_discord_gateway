from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from typing import Optional

import telnetlib3


@dataclass
class TelnetResult:
    text: str
    created_account: bool = False


class EvenniaTelnetSession:
    """
    One telnet connection to Evennia.

    We intentionally do NOT try to perfectly parse Evennia's login prompts.
    Instead we use Evennia's command-style login:
      - connect <account> <password>
      - create <account> <password>

    This works with Evennia's default UnloggedinCmdSet.
    """

    def __init__(self, host: str, port: int, idle_timeout_s: int = 3600):
        self.host = host
        self.port = port
        self.idle_timeout_s = idle_timeout_s
        self.reader: Optional[telnetlib3.TelnetReader] = None
        self.writer: Optional[telnetlib3.TelnetWriter] = None
        self._lock = asyncio.Lock()
        self._last_io = time.time()

    def is_connected(self) -> bool:
        return self.writer is not None and not self.writer.is_closing()

    def is_idle(self) -> bool:
        return (time.time() - self._last_io) > self.idle_timeout_s

    async def close(self):
        if self.writer and not self.writer.is_closing():
            self.writer.close()
        self.reader = None
        self.writer = None

    async def connect(self):
        if self.is_connected():
            return
        self.reader, self.writer = await telnetlib3.open_connection(
            host=self.host,
            port=self.port,
            shell=None,
            encoding="utf-8",
            encoding_errors="surrogateescape",
            connect_minwait=0.1,
            connect_maxwait=1.0,
        )
        # Drain banner
        await self._read_quiescent(0.6)

    async def ensure_logged_in(
        self,
        account: str,
        password: str,
        auto_create: bool,
    ) -> TelnetResult:
        """Ensure we're connected and authenticated."""
        async with self._lock:
            await self.connect()
            created = False

            # Try connect first
            await self._send_line(f"connect {account} {password}")
            out = await self._read_quiescent(0.8)

            if self._looks_logged_in(out):
                return TelnetResult(text=out, created_account=False)

            if not auto_create:
                return TelnetResult(text=out, created_account=False)

            # Try create then connect
            await self._send_line(f"create {account} {password}")
            out2 = await self._read_quiescent(0.9)
            created = self._looks_like_create_success(out2)

            await self._send_line(f"connect {account} {password}")
            out3 = await self._read_quiescent(0.8)

            return TelnetResult(text=(out + out2 + out3), created_account=created)

    async def run_command(self, cmd: str) -> str:
        """Run a single command and return resulting text."""
        cmd = (cmd or "").rstrip("\n")
        if not cmd:
            return ""
        async with self._lock:
            if not self.is_connected():
                await self.connect()
            await self._send_line(cmd)
            return await self._read_quiescent(0.6)

    # -------- internals --------

    async def _send_line(self, line: str):
        assert self.writer is not None
        self.writer.write(line + "\n")
        await self.writer.drain()
        self._last_io = time.time()

    async def _read_quiescent(self, total_wait: float) -> str:
        """
        Read until the stream is quiet for a short period, capped by total_wait.
        This is intentionally fuzzy because telnet output is bursty.
        """
        assert self.reader is not None
        out = []
        deadline = time.time() + total_wait
        while time.time() < deadline:
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=0.12)
            except asyncio.TimeoutError:
                chunk = ""
            if chunk:
                out.append(chunk)
                self._last_io = time.time()
                # extend slightly when new data arrives
                deadline = max(deadline, time.time() + 0.18)
            else:
                await asyncio.sleep(0.03)
        return "".join(out)

    @staticmethod
    def _looks_logged_in(text: str) -> bool:
        low = (text or "").lower()
        # Heuristics: Evennia often announces "Connected" or shows a room name, etc.
        if "you become" in low:
            return True
        if "connected" in low and "connect" not in low:
            return True
        if "exits:" in low or "you see:" in low:
            return True
        return False

    @staticmethod
    def _looks_like_create_success(text: str) -> bool:
        low = (text or "").lower()
        return "created" in low and "account" in low


def stable_password(secret: str, discord_user_id: str) -> str:
    """Derive a stable per-user password from a gateway secret."""
    # Not cryptographic auth against Discord; just ensures we don't have to store raw passwords.
    # Evennia passwords can contain many chars; keep it simple.
    import hashlib

    h = hashlib.sha256((secret + ":" + str(discord_user_id)).encode("utf-8")).hexdigest()
    return "pw_" + h[:20]


def random_password() -> str:
    return "pw_" + secrets.token_urlsafe(18)
