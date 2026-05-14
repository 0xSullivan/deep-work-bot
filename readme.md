# Deep Work Telegram Bot

Focus Status Bot is a small Telegram bot that lets teammates mark themselves as unavailable for deep work. When someone starts, cancels, or reaches the end of a focus session, the bot notifies the configured Telegram chats, channels, or forum topics.

The bot is intentionally stateless. It stores known users and active sessions only in memory, so restarting the process clears all status.

## Features

- Compact inline controls for `Start Deep Work`, `Cancel Deep Work`, and `Status`.
- `/start`, `/help`, and `/status` commands.
- In-memory tracking of every user who has interacted with the running bot process.
- Automatic session expiry after `DEEP_WORK_DURATION_MINUTES`.
- Starting deep work again while active resets the timer.
- Notifications to multiple Telegram chats, channels, and forum topics.

## Requirements

- Python 3.13 or newer.
- A Telegram bot token from BotFather.
- The bot must be added to every target group, channel, or forum topic it should notify.
- For channels, the bot needs permission to post messages.

## Setup

Install dependencies with your preferred Python tool. With `uv`:

```bash
uv sync
```

Or with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

Create local configuration:

```bash
cp config.example.env config.env
```

Edit `config.env` with your real values. Do not commit `config.env`.

## Configuration

```env
BOT_TOKEN=123456:telegram-bot-token
DEEP_WORK_DURATION_MINUTES=25

# Comma-separated target chat IDs for groups or channels.
NOTIFY_CHAT_IDS=-1001234567890,-1009876543210

# Optional comma-separated forum topic targets.
# Format: chat_id:message_thread_id
NOTIFY_TOPIC_TARGETS=-1001234567890:42,-1009876543210:7

# Optional Python logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
LOG_LEVEL=INFO
```

`BOT_TOKEN` is required. `DEEP_WORK_DURATION_MINUTES` must be a positive integer.

`NOTIFY_CHAT_IDS` and `NOTIFY_TOPIC_TARGETS` may be left empty for local testing, but no start, cancel, or expiry notifications will be sent until at least one target is configured.

Forum topic targets require both the parent chat ID and the topic message thread ID in `chat_id:message_thread_id` format.

## Running

With `uv`:

```bash
uv run python main.py
```

With an activated virtual environment:

```bash
python main.py
```

The bot uses long polling. Stop it with `Ctrl-C`.

## Usage

Open a chat with the bot and send `/start`.

If you are available, the bot shows:

- `Start Deep Work`
- `Status`

If you are already in deep work mode, the bot shows:

- `Cancel Deep Work`
- `Status`

The main bot message is a compact status panel:

```text
Focus Status Bot

Status: Available
```

After starting deep work, it changes to:

```text
Focus Status Bot

Status: In deep work
Remaining: 25 minutes
Ends: 14:30
```

`Status` shows every user known to the current running process, grouped by availability:

```text
Deep Work Status

In deep work
- Ada Lovelace: 18 minutes, ends 14:30

Available
- Grace Hopper
```

Users are identified by their Telegram display name. If a display name is unavailable, the bot falls back to username or Telegram user ID.

## Notification Text

- Start:
  ```text
  {user} started deep work
  Duration: {minutes} minutes.
  Remaining: {minutes} minutes.
  Ends: 14:30.
  ```
- Cancel: `{user} canceled deep work`
- Expiry: `{user}'s deep work session ended`

## Runtime Behavior

- All state is kept in memory.
- Restarting the bot clears known users and active sessions.
- Expired sessions are removed from memory.
- Starting a new session while already active cancels the old timer and starts a fresh one.
- Cancelling with no active session only updates the user's own bot message; no cancellation notification is sent.
- Notification failures are logged and do not stop the bot.

## Project Files

```text
.
├── config.example.env
├── config.env
├── main.py
├── pyproject.toml
└── readme.md
```

`config.env` is local-only and ignored by git.
