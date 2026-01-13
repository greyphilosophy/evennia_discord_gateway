# gateway/telnet_session.py
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
        self.did_rename = False
        self._reader_task: Optional[asyncio.Task] = None
        self._buf = ""                       # accumulated incoming text
        self._buf_event = asyncio.Event()    # signals new data arrived
        self._command_mode = False           # True while run_command is collecting output
        self.on_ambient_text = None  # type: Optional[callable]
        self.authenticated = False

    def is_connected(self) -> bool:
        return self.writer is not None and not self.writer.is_closing()

    def is_idle(self) -> bool:
        return (time.time() - self._last_io) > self.idle_timeout_s

    async def set_ambient_handler(self, handler):
        self.on_ambient_text = handler

        # If we already have buffered text and we're not in command mode,
        # flush it immediately so it doesn't get eaten by the next command read.
        if handler and self._buf and not self._command_mode:
            text = self._buf
            self._buf = ""
            self._buf_event.clear()
            await handler(text)


    async def close(self):
        # Stop background reader
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._reader_task = None

        # Close writer/socket
        if self.writer and not self.writer.is_closing():
            self.writer.close()

        self.reader = None
        self.writer = None

        # Clear buffers
        self._buf = ""
        self._buf_event.clear()
        self._command_mode = False

        self.authenticated = False

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
        self.authenticated = False

        # Start background reader FIRST so _read_quiescent can drain from buffer reliably.
        if not self._reader_task or self._reader_task.done():
            self._reader_task = asyncio.create_task(self._reader_loop())

        # Drain banner / initial burst
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
            if self.authenticated:
                return TelnetResult(text="", created_account=False)

            # Non-destructive peek: don't drain _buf (or you'll eat ambient output)
            try:
                await asyncio.wait_for(self._buf_event.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass

            probe = self._buf  # <-- do NOT clear
            if self._looks_logged_in(probe):
                self.authenticated = True
                return TelnetResult(text="", created_account=False)

            created = False

            # Try connect first
            await self._send_line(f"connect {account} {password}")
            out = await self._read_quiescent(0.8)

            if self._looks_logged_in(out):
                self.authenticated = True
                return TelnetResult(text="", created_account=False)

            if not auto_create:
                return TelnetResult(text=out, created_account=False)

            # Try create then connect
            await self._send_line(f"create {account} {password}")
            out2 = await self._read_quiescent(0.9)
            created = self._looks_like_create_success(out2)

            await self._send_line(f"connect {account} {password}")
            out3 = await self._read_quiescent(0.8)

            if self._looks_logged_in(out3):
                self.authenticated = True
                return TelnetResult(text="", created_account=created)

            return TelnetResult(text=(out + out2 + out3), created_account=created)

    async def run_command(self, cmd: str) -> str:
        cmd = (cmd or "").rstrip("\n")
        if not cmd:
            return ""
        async with self._lock:
            if not self.is_connected():
                await self.connect()

            self._command_mode = True
            try:
                await self._send_line(cmd)
                return await self._read_quiescent(0.6)
            finally:
                self._command_mode = False

    async def _reader_loop(self):
        assert self.reader is not None
        try:
            while self.is_connected():
                chunk = await self.reader.read(4096)
                if not chunk:
                    await asyncio.sleep(0.05)
                    continue
                self._last_io = time.time()
                self._buf += chunk
                if (not self._command_mode) and self.on_ambient_text:
                    # Drain buffer immediately to avoid duplicate sending
                    text = self._buf
                    self._buf = ""
                    self._buf_event.clear()
                    await self.on_ambient_text(text)

                self._buf_event.set()
        except asyncio.CancelledError:
            raise
        except Exception:
            # connection likely dropped; let connect()/run_command handle reconnect
            pass

    # -------- internals --------

    async def _send_line(self, line: str):
        assert self.writer is not None
        self.writer.write(line + "\n")
        await self.writer.drain()
        self._last_io = time.time()

    async def _read_quiescent(self, total_wait: float) -> str:
        out = []
        deadline = time.time() + total_wait

        while time.time() < deadline:
            # wait briefly for new data
            timeout = min(0.12, max(0.0, deadline - time.time()))
            try:
                await asyncio.wait_for(self._buf_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass

            # consume buffer if any
            if self._buf:
                out.append(self._buf)
                self._buf = ""
                self._buf_event.clear()
                self._last_io = time.time()
                deadline = max(deadline, time.time() + 0.18)
            else:
                self._buf_event.clear()
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

    @staticmethod
    def _looks_like_already_in_game(text: str) -> bool:
        low = (text or "").lower()
        return ("command 'connect" in low or "command 'create" in low) and "not available" in low

def stable_password(secret: str, discord_user_id: str) -> str:
    """Derive a stable per-user password from a gateway secret."""
    # Not cryptographic auth against Discord; just ensures we don't have to store raw passwords.
    # Evennia passwords can contain many chars; keep it simple.
    import hashlib

    h = hashlib.sha256((secret + ":" + str(discord_user_id)).encode("utf-8")).hexdigest()
    return "pw_" + h[:20]


def random_password() -> str:
    return "pw_" + secrets.token_urlsafe(18)
