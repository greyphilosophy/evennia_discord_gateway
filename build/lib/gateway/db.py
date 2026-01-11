from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  discord_user_id TEXT PRIMARY KEY,
  evennia_account TEXT NOT NULL,
  evennia_password TEXT NOT NULL,
  created_ts INTEGER NOT NULL,
  last_seen_ts INTEGER NOT NULL,
  last_discord_name TEXT
);
"""


@dataclass
class UserRecord:
    discord_user_id: str
    evennia_account: str
    evennia_password: str
    created_ts: int
    last_seen_ts: int
    last_discord_name: str | None


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def get_user(self, discord_user_id: str) -> Optional[UserRecord]:
        cur = self._conn.execute(
            "SELECT * FROM users WHERE discord_user_id = ?", (str(discord_user_id),)
        )
        row = cur.fetchone()
        if not row:
            return None
        return UserRecord(
            discord_user_id=row["discord_user_id"],
            evennia_account=row["evennia_account"],
            evennia_password=row["evennia_password"],
            created_ts=row["created_ts"],
            last_seen_ts=row["last_seen_ts"],
            last_discord_name=row["last_discord_name"],
        )

    def upsert_user(
        self,
        discord_user_id: str,
        evennia_account: str,
        evennia_password: str,
        now_ts: int,
        last_discord_name: str | None = None,
    ) -> UserRecord:
        existing = self.get_user(discord_user_id)
        if existing:
            self._conn.execute(
                """
                UPDATE users
                SET evennia_account = ?, evennia_password = ?, last_seen_ts = ?, last_discord_name = ?
                WHERE discord_user_id = ?
                """,
                (
                    evennia_account,
                    evennia_password,
                    now_ts,
                    last_discord_name,
                    str(discord_user_id),
                ),
            )
            self._conn.commit()
            return self.get_user(discord_user_id)  # type: ignore

        self._conn.execute(
            """
            INSERT INTO users (discord_user_id, evennia_account, evennia_password, created_ts, last_seen_ts, last_discord_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(discord_user_id),
                evennia_account,
                evennia_password,
                now_ts,
                now_ts,
                last_discord_name,
            ),
        )
        self._conn.commit()
        return self.get_user(discord_user_id)  # type: ignore
