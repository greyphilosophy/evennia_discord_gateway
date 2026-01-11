from __future__ import annotations

import os
from pathlib import Path

from .bot import GatewayBot
from .config import load_config
from .db import Database


def main():
    cfg = load_config()

    db_path = os.getenv("DB_PATH", "./data/users.sqlite3")
    db = Database(Path(db_path))

    bot = GatewayBot(cfg, db)
    try:
        bot.run(cfg.discord_token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
