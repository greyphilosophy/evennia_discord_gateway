from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = _env(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Config:
    # Discord
    discord_token: str
    # If set, restricts play to DMs only (recommended). If false, the bot will also
    # process messages in guild channels it can see.
    dm_only: bool

    # Evennia Telnet (bind Evennia to localhost for safety; bot can still connect)
    evennia_host: str
    evennia_port: int

    # Session / output
    output_chunk_size: int
    output_max_chunks: int
    idle_timeout_s: int

    # Account provisioning
    # If true, the gateway will auto-create an Evennia account on first contact.
    auto_create_accounts: bool
    # Stable account name prefix. Account name becomes f"{prefix}{discord_user_id}".
    account_prefix: str
    # If true, the bot will attempt to set the in-game "@icname" (nickname) to the
    # user's Discord display name when they first connect.
    auto_set_nickname: bool

    # Security / privacy
    # If true, the bot will warn users that gameplay in public guild channels is public.
    warn_public_play: bool


def load_config() -> Config:
    token = _env("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")

    return Config(
        discord_token=token,
        dm_only=_env_bool("DM_ONLY", True),
        evennia_host=_env("EVENNIA_HOST", "127.0.0.1") or "127.0.0.1",
        evennia_port=_env_int("EVENNIA_PORT", 4000),
        output_chunk_size=_env_int("OUTPUT_CHUNK_SIZE", 1800),
        output_max_chunks=_env_int("OUTPUT_MAX_CHUNKS", 8),
        idle_timeout_s=_env_int("IDLE_TIMEOUT_S", 3600),
        auto_create_accounts=_env_bool("AUTO_CREATE_ACCOUNTS", True),
        account_prefix=_env("ACCOUNT_PREFIX", "discord_") or "discord_",
        auto_set_nickname=_env_bool("AUTO_SET_NICKNAME", True),
        warn_public_play=_env_bool("WARN_PUBLIC_PLAY", True),
    )
