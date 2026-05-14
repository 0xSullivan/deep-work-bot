from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)


START_DEEP_WORK = "start_deep_work"
CANCEL_DEEP_WORK = "cancel_deep_work"
STATUS = "status"

ACTIVE_TEXT = "In deep work"
INACTIVE_TEXT = "Available"
BOT_NAME = "Focus Status Bot"


@dataclass(frozen=True)
class NotifyTarget:
    chat_id: int
    message_thread_id: int | None = None


@dataclass
class Session:
    name: str
    expires_at: datetime
    task: asyncio.Task[None]


@dataclass
class BotState:
    known_users: dict[int, str]
    active_sessions: dict[int, Session]
    duration_minutes: int
    notify_targets: list[NotifyTarget]


def load_config() -> tuple[str, int, list[NotifyTarget]]:
    load_dotenv(Path("config.env"))

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required. Add it to config.env or the environment.")

    try:
        duration_minutes = int(os.getenv("DEEP_WORK_DURATION_MINUTES", "25"))
    except ValueError as exc:
        raise RuntimeError("DEEP_WORK_DURATION_MINUTES must be a positive integer.") from exc
    if duration_minutes <= 0:
        raise RuntimeError("DEEP_WORK_DURATION_MINUTES must be a positive integer.")

    targets = parse_notify_targets(
        os.getenv("NOTIFY_CHAT_IDS", ""),
        os.getenv("NOTIFY_TOPIC_TARGETS", ""),
    )
    return token, duration_minutes, targets


def parse_notify_targets(chat_ids: str, topic_targets: str) -> list[NotifyTarget]:
    targets: list[NotifyTarget] = []

    for raw_chat_id in split_csv(chat_ids):
        try:
            targets.append(NotifyTarget(chat_id=int(raw_chat_id)))
        except ValueError as exc:
            raise RuntimeError(f"Invalid NOTIFY_CHAT_IDS entry: {raw_chat_id}") from exc

    for raw_target in split_csv(topic_targets):
        try:
            chat_id, thread_id = raw_target.split(":", maxsplit=1)
            targets.append(NotifyTarget(chat_id=int(chat_id), message_thread_id=int(thread_id)))
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid NOTIFY_TOPIC_TARGETS entry: {raw_target}. "
                "Expected chat_id:message_thread_id."
            ) from exc

    return targets


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def get_state(context: ContextTypes.DEFAULT_TYPE) -> BotState:
    return context.application.bot_data["state"]


def display_name(update: Update) -> str:
    user = update.effective_user
    if user is None:
        return "Unknown user"
    if user.full_name:
        return user.full_name
    if user.username:
        return f"@{user.username}"
    return str(user.id)


def remember_user(update: Update, state: BotState) -> tuple[int, str]:
    user = update.effective_user
    if user is None:
        raise RuntimeError("Telegram update does not include a user.")
    name = display_name(update)
    state.known_users[user.id] = name
    return user.id, name


def keyboard(is_active: bool) -> InlineKeyboardMarkup:
    primary_button = (
        InlineKeyboardButton("Cancel Deep Work", callback_data=CANCEL_DEEP_WORK)
        if is_active
        else InlineKeyboardButton("Start Deep Work", callback_data=START_DEEP_WORK)
    )
    return InlineKeyboardMarkup(
        [
            [primary_button, InlineKeyboardButton("Status", callback_data=STATUS)],
        ]
    )


def format_home(session: Session | None) -> str:
    lines = [
        f"<b>{BOT_NAME}</b>",
        "",
        f"Status: <b>{ACTIVE_TEXT if session else INACTIVE_TEXT}</b>",
    ]
    if session:
        lines.extend(
            [
                f"Remaining: {format_remaining(session.expires_at)}",
                f"Ends: {format_end_time(session.expires_at)}",
            ]
        )
    return "\n".join(lines)


def format_help(session: Session | None) -> str:
    lines = [
        f"<b>{BOT_NAME}</b>",
        "",
        "Use the buttons to update your availability or view team status.",
        "",
        f"Status: <b>{ACTIVE_TEXT if session else INACTIVE_TEXT}</b>",
    ]
    if session:
        lines.extend(
            [
                f"Remaining: {format_remaining(session.expires_at)}",
                f"Ends: {format_end_time(session.expires_at)}",
            ]
        )
    return "\n".join(lines)


def format_status(state: BotState) -> str:
    if not state.known_users:
        return "<b>Deep Work Status</b>\n\nNo known users yet."

    active_users: list[str] = []
    available_users: list[str] = []
    for user_id, name in sorted(state.known_users.items(), key=lambda item: item[1].casefold()):
        session = state.active_sessions.get(user_id)
        if session:
            line = (
                f"- {escape(name)}: {format_remaining(session.expires_at)}, "
                f"ends {format_end_time(session.expires_at)}"
            )
            active_users.append(line)
        else:
            line = f"- {escape(name)}"
            available_users.append(line)

    lines = ["<b>Deep Work Status</b>"]
    if active_users:
        lines.extend(["", f"<b>{ACTIVE_TEXT}</b>", *active_users])
    if available_users:
        lines.extend(["", f"<b>{INACTIVE_TEXT}</b>", *available_users])
    return "\n".join(lines)


def format_notification(title: str, detail: str | None = None) -> str:
    lines = [f"<b>{escape(title)}</b>"]
    if detail:
        lines.append(escape(detail))
    return "\n".join(lines)


def format_remaining(expires_at: datetime) -> str:
    remaining_seconds = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    remaining_minutes = max(1, (remaining_seconds + 59) // 60)
    unit = "minute" if remaining_minutes == 1 else "minutes"
    return f"{remaining_minutes} {unit}"


def format_end_time(expires_at: datetime) -> str:
    local_end = expires_at.astimezone()
    local_now = datetime.now(UTC).astimezone()
    if local_end.date() == local_now.date():
        return local_end.strftime("%H:%M")
    return local_end.strftime("%Y-%m-%d %H:%M")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(context)
    user_id, _ = remember_user(update, state)
    session = state.active_sessions.get(user_id)
    await update.effective_message.reply_text(
        format_home(session),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard(session is not None),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(context)
    user_id, _ = remember_user(update, state)
    session = state.active_sessions.get(user_id)
    await update.effective_message.reply_text(
        format_help(session),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard(session is not None),
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(context)
    user_id, _ = remember_user(update, state)
    await update.effective_message.reply_text(
        format_status(state),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard(user_id in state.active_sessions),
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    state = get_state(context)
    user_id, _ = remember_user(update, state)

    if query.data == START_DEEP_WORK:
        await start_deep_work(update, context)
    elif query.data == CANCEL_DEEP_WORK:
        await cancel_deep_work(update, context)
    elif query.data == STATUS:
        await edit_message_text(
            query,
            format_status(state),
            reply_markup=keyboard(user_id in state.active_sessions),
        )


async def start_deep_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    state = get_state(context)
    user_id, name = remember_user(update, state)

    existing_session = state.active_sessions.get(user_id)
    if existing_session is not None:
        existing_session.task.cancel()

    expires_at = datetime.now(UTC) + timedelta(minutes=state.duration_minutes)
    task = context.application.create_task(expire_session(context.application, user_id))
    state.active_sessions[user_id] = Session(name=name, expires_at=expires_at, task=task)

    await notify_targets(
        context.application,
        state,
        format_notification(
            f"{name} started deep work",
            f"Duration: {state.duration_minutes} minutes.\n"
            f"Remaining: {format_remaining(expires_at)}.\n"
            f"Ends: {format_end_time(expires_at)}.",
        ),
    )
    await edit_message_text(
        query,
        format_home(state.active_sessions[user_id]),
        reply_markup=keyboard(is_active=True),
    )


async def cancel_deep_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    state = get_state(context)
    user_id, name = remember_user(update, state)

    session = state.active_sessions.pop(user_id, None)
    if session is not None:
        session.task.cancel()
        await notify_targets(
            context.application,
            state,
            format_notification(f"{name} canceled deep work"),
        )
        message = format_home(None)
    else:
        message = "\n".join(
            [
                f"<b>{BOT_NAME}</b>",
                "",
                "No active deep work session.",
                f"Status: <b>{INACTIVE_TEXT}</b>",
            ]
        )

    await edit_message_text(query, message, reply_markup=keyboard(is_active=False))


async def expire_session(application: Application, user_id: int) -> None:
    state: BotState = application.bot_data["state"]
    try:
        session = state.active_sessions[user_id]
        sleep_seconds = max(0.0, (session.expires_at - datetime.now(UTC)).total_seconds())
        await asyncio.sleep(sleep_seconds)
        current_session = state.active_sessions.get(user_id)
        if current_session is not session:
            return
        state.active_sessions.pop(user_id, None)
        await notify_targets(
            application,
            state,
            format_notification(f"{session.name}'s deep work session ended"),
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Failed to expire deep work session for user_id=%s", user_id)


async def notify_targets(application: Application, state: BotState, text: str) -> None:
    for target in state.notify_targets:
        try:
            await application.bot.send_message(
                chat_id=target.chat_id,
                message_thread_id=target.message_thread_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            logging.exception("Failed to notify Telegram target %s", target)


async def edit_message_text(
    query: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    try:
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


def build_application() -> Application:
    token, duration_minutes, notify_targets = load_config()
    application = ApplicationBuilder().token(token).build()
    application.bot_data["state"] = BotState(
        known_users={},
        active_sessions={},
        duration_minutes=duration_minutes,
        notify_targets=notify_targets,
    )
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(handle_button))
    return application


def main() -> None:
    load_dotenv(Path("config.env"))
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
