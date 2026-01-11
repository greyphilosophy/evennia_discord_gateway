# evennia-discord-gateway

A **Discord-only access gateway** for **Evennia** MUDs.

- Players talk to a Discord bot.
- The bot maintains a **local telnet session** to Evennia (one per Discord user).
- Each Discord user is mapped **1:1** to a single Evennia account.
- No slash commands required.
- Output is automatically **chunked** to Discord message limits.

This project is designed for the pattern you described:
- The MUD itself stays off the public internet (no port-forwarding required).
- Discord becomes the public access layer.

> Why telnet?
> Because it lets this gateway work with *any* Evennia game without modifying the game.
> Just bind telnet to localhost and run the gateway on the same machine.

---

## Quickstart

### 1) Run Evennia telnet on localhost only

In your Evennia `server/conf/settings.py` (or `server/conf/settings.py` override), bind telnet to loopback:

```python
# Only accept telnet from local machine
TELNET_INTERFACES = [("127.0.0.1", 4000)]

# Optional: disable public webclient if you don't need it
# WEBSOCKET_CLIENT_ENABLED = False
# WEBCLIENT_ENABLED = False
```

Now only processes on the same machine can connect.

### 2) Create a Discord bot

Create a bot at the Discord Developer Portal, invite it to your server, and enable:
- **MESSAGE CONTENT INTENT** (privileged intent)

*(DM-only mode is the default and recommended.)*

### 3) Configure and run the gateway

```bash
cd evennia-discord-gateway
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install .

export DISCORD_TOKEN='...'
export GATEWAY_SECRET='a-long-random-string'

# Where your Evennia telnet listens (localhost by default)
export EVENNIA_HOST='127.0.0.1'
export EVENNIA_PORT='4000'

# Optional: set an in-game "nickname" command to run on first connect
# If Evennia already provides @icname or similar, use it. Otherwise, add your own command.
# export NICK_COMMAND_TEMPLATE='@icname {name}'

# Optional: allow play in guild channels (public). Default is DM-only.
# export DM_ONLY='false'

eddg
```

---

## How account mapping works

- The gateway uses Discord's stable `author.id` as the identity.
- The Evennia account name becomes:

```
{ACCOUNT_PREFIX}{discord_user_id}
```

Defaults:
- `ACCOUNT_PREFIX = "discord_"`

Passwords:
- The gateway derives a stable per-user password using `GATEWAY_SECRET`.
- Users never need to know it (since they only connect through Discord).

This ensures:
- Each Discord account maps to exactly one Evennia account.
- The gateway can reconnect users without storing plaintext passwords.

---

## Player commands

In a DM to the bot (or in guild channels if `DM_ONLY=false`):

- `help` — show local help
- `whoami` — show your mapped Evennia account
- `logout` — close your telnet session
- Anything else — forwarded as a normal in-game command

---

## Output chunking

The bot splits long output into multiple Discord messages.

Env vars:
- `OUTPUT_CHUNK_SIZE` (default `1800`)
- `OUTPUT_MAX_CHUNKS` (default `8`)

If output exceeds the max, it will append a truncation notice.

---

## Public play vs private play

- In **DM-only mode** (`DM_ONLY=true`), game history stays in the user's DMs.
- If you allow guild channel play (`DM_ONLY=false`), everything in that channel is public.

---

## Limitations (v1)

- This gateway does not (yet) attempt to interpret prompts, paging, or ANSI color.
- It relies on Evennia's default unlogged-in commands:
  - `create <account> <password>`
  - `connect <account> <password>`

If your game customized those, you may need to adapt the login commands.

---

## License

MIT
