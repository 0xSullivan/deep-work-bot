# Deep Work Telegram Bot

A simple Telegram bot that lets people mark themselves as unavailable for deep work. When someone starts or cancels a focus session, the bot notifies one or more configured Telegram targets so teammates know not to interrupt them.

## Purpose

The bot keeps a lightweight, in-memory list of users and their current deep work status. It is intentionally stateless: no database, custom user profiles, or persistent history.

## Workflow

1. A user starts the bot.
2. If the user is not in deep work mode, the bot shows:
   - `Start Deep Work`: starts a deep work session.
   - `Status`: shows every known user's current status.
3. If the user is already in deep work mode, the bot shows:
   - `Cancel Deep Work`: ends the user's current deep work session.
   - `Status`: shows every known user's current status.
4. When a user starts deep work:
   - The bot stores their status in memory.
   - The bot sends a notification to every configured Telegram target.
   - The session automatically expires after the configured duration.
5. If a user starts deep work again while already active, the bot resets their timer to the configured default duration.
6. When a user cancels deep work, the bot clears their status and sends a cancellation notification to every configured target.

## Status Rules

- `Status` shows all users known to the running bot process.
- A user is identified by their Telegram display name.
- No custom names are stored.
- All state is kept in memory and is lost when the bot restarts.

## Telegram Targets

The bot can notify multiple Telegram targets. Each target is configured with environment variables and may be a:

- Group
- Channel
- Forum topic

For forum topics, configure both the chat ID and the topic/message thread ID.

## Configuration

Create `config.env` for local configuration and keep `config.example.env` committed as a template.

Recommended variables:

```env
BOT_TOKEN=123456:telegram-bot-token
DEEP_WORK_DURATION_MINUTES=25

# Comma-separated target chat IDs.
# These may point to groups or channels.
NOTIFY_CHAT_IDS=-1001234567890,-1009876543210

# Optional comma-separated forum topic targets.
# Format: chat_id:message_thread_id
NOTIFY_TOPIC_TARGETS=-1001234567890:42,-1009876543210:7
```

## Implementation Guide

- Use Python.
- Use `python-telegram-bot` unless there is a strong reason to choose another SDK.
- Keep the implementation simple and short.
- Keep all runtime state in memory.
- Use `config.env` for secrets and local settings.
- Include `config.example.env` with placeholder values.
- Do not commit real bot tokens or private chat IDs.

## Bot Text

- Bot name: `Focus Status Bot`
- Start button: `Start Deep Work`
- Cancel button: `Cancel Deep Work`
- Status button: `Status`
- Active state: `In deep work`
- Inactive state: `Available`
- Start notification: `{user} started deep work for {minutes} minutes.`
- Cancel notification: `{user} canceled deep work.`
- Expiry notification: `{user}'s deep work session ended.`

## Expected Files

```text
.
├── config.example.env
├── config.env
├── main.py
├── pyproject.toml
└── readme.md
```

## Notes

- Because the bot is stateless, restarting it clears all known users and active sessions.
- Automatically expired sessions should be removed from memory.
- Starting a new deep work session while one is already active should replace the old timer.
