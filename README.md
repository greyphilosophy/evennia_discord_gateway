# evennia-discord-gateway

A **Discord-first gateway** for **Evennia** MUDs.

Players interact by **DMing a Discord bot**. The bot maintains a **local telnet session** to your Evennia server (one per Discord user) and forwards messages as in-game commands. Output is returned to Discord, automatically chunked to fit message limits.

This project is designed for the “no port-forwarding” pattern:
- Your Evennia telnet port binds to **localhost only**
- Discord becomes the public access layer

---

## Features

- **Discord DM interface** (default: DM-only)
- **No slash commands required**
- **1:1 mapping**: each Discord account maps to a single Evennia account
- **Auto-create / auto-connect** using Evennia’s `create` + `connect`
- **ANSI output rendered in Discord** via fenced ```ansi code blocks
- **Robust text decoding** to avoid mojibake (smart punctuation / “���” issues)
- **Output chunking** (splits long output into multiple Discord messages)

---

## Requirements

- Python 3.10+ (tested on 3.12)
- An Evennia server reachable via telnet from the machine running the gateway
- A Discord bot token with **Message Content Intent** enabled

---

## Quickstart

### 1) Bind Evennia telnet to localhost only

In your Evennia `server/conf/settings.py` (or your settings override), bind telnet to loopback:

```python
TELNET_INTERFACES = [("127.0.0.1", 4000)]
````

This prevents remote telnet connections; only local processes can connect.

> You can also disable web client/websocket if you want, but it’s optional.

---

### 2) Create and invite the Discord bot

1. Go to the Discord Developer Portal → Applications → New Application
2. Add a **Bot**
3. Enable **Privileged Gateway Intent**:

   * ✅ Message Content Intent
4. Invite the bot to your server using OAuth2 URL Generator:

   * Scope: `bot`
   * Permissions: View Channels / Send Messages (minimum)
5. Copy the bot token

> Note: “Installing the app” is not the same as inviting the bot user. Make sure you invite with scope `bot`.

---

### 3) Install and run the gateway

From the repo directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install .
```

Set required environment variables:

```bash
export DISCORD_TOKEN='...'
export GATEWAY_SECRET='...'
```

Optional (defaults shown):

```bash
export EVENNIA_HOST='127.0.0.1'
export EVENNIA_PORT='4000'
export DM_ONLY='true'
export OUTPUT_CHUNK_SIZE='1800'
export OUTPUT_MAX_CHUNKS='8'
```

Run:

```bash
eddg
```

---

## Using a `.env` file (recommended)

You can store config in a `.env` file (do not commit it). Example:

```env
DISCORD_TOKEN=your_token_here
GATEWAY_SECRET=your_long_random_secret_here
EVENNIA_HOST=127.0.0.1
EVENNIA_PORT=4000
DM_ONLY=true
OUTPUT_CHUNK_SIZE=1800
OUTPUT_MAX_CHUNKS=8
```

Load it into your shell before starting:

```bash
set -a
source .env
set +a
eddg
```

> Keep `GATEWAY_SECRET` stable. Changing it will prevent existing accounts from auto-connecting.

---

## How account mapping works

* The gateway uses Discord’s stable `author.id` as the identity key.
* The Evennia account name becomes:

```
{ACCOUNT_PREFIX}{discord_user_id}
```

Defaults:

* `ACCOUNT_PREFIX = "discord_"`

Passwords:

* A stable per-user password is derived from `GATEWAY_SECRET` + Discord user id.
* Users never need to know the password (they connect through Discord).

This ensures:

* Each Discord account maps to exactly one Evennia account
* The gateway can reconnect users without storing plaintext passwords

---

## How to play

In a **DM** to the bot (or in guild channels if enabled), send normal Evennia commands:

* `look` (or `l`)
* `help`
* `say hello`
* etc.

The gateway forwards the message as the player’s in-game command and relays output back to Discord.

---

## DM-only vs guild channel play

* **DM-only (default)**: `DM_ONLY=true`
  The bot only responds in DMs. This is the recommended mode.

* **Guild/public**: `DM_ONLY=false`
  The bot will respond in server channels too. **History in those channels is public.**

---

## Output formatting

* Evennia often sends ANSI color/style codes over telnet.
* Discord can render ANSI only inside a fenced code block tagged `ansi`.
* The gateway wraps ANSI output in ```ansi blocks and chunks output safely.

---

## Limitations / assumptions (v1)

* Uses Evennia’s default unauthenticated commands:

  * `create <account> <password>`
  * `connect <account> <password>`
    If your game changes these, update the gateway login flow accordingly.
* The gateway is a telnet client; it ignores many telnet option negotiations (GMCP/MCCP/etc.). This is normal for v1.

---

## Troubleshooting

**Bot is online but doesn’t respond**

* Ensure Message Content Intent is enabled in the Developer Portal
* Confirm you are DMing the bot (DM-only is default)
* If testing in a server, set `DM_ONLY=false`

**Bot doesn’t show up in my server**

* Make sure you invited with OAuth2 scope `bot` (not just “installed the app”)

**Connection errors to Evennia**

* Confirm Evennia is running
* Confirm `TELNET_INTERFACES` includes `("127.0.0.1", 4000)`
* Confirm `EVENNIA_HOST`/`EVENNIA_PORT` match your Evennia telnet listener

---

## License

MIT

