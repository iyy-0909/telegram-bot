"""Content activity is separate from channel metadata edits and permission checks."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_

from db.database import SessionLocal
from db.models import BotAccount, MyChannel


def utc_naive(value):
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def activity_fields(last_content_at, now=None):
    if not last_content_at:
        return {"last_content_at": "", "update_status": "unknown"}
    last_content_at = utc_naive(last_content_at)
    now = utc_naive(now or datetime.now(timezone.utc))
    return {
        "last_content_at": last_content_at.isoformat() + "Z",
        "update_status": "error" if now - last_content_at > timedelta(days=5) else "enabled",
    }


def record_channel_content(owner_user_id, *, chat_id=None, username=None, date=None):
    if not owner_user_id or not isinstance(date, datetime):
        return 0
    conditions = []
    if chat_id:
        conditions.append(MyChannel.chat_id == str(chat_id))
    if username:
        conditions.append(func.lower(MyChannel.username) == "@" + str(username).lstrip("@").lower())
    if not conditions:
        return 0
    date = utc_naive(date)
    with SessionLocal() as db:
        count = db.query(MyChannel).filter(
            MyChannel.owner_user_id == int(owner_user_id),
            or_(*conditions),
            or_(MyChannel.last_content_at.is_(None), MyChannel.last_content_at < date),
        ).update({MyChannel.last_content_at: date}, synchronize_session=False)
        db.commit()
        return count


def record_bot_content(token, result):
    messages = result if isinstance(result, list) else [result]
    messages = [message for message in messages if isinstance(message, dict)
                and (message.get("chat") or {}).get("type") == "channel"
                and message.get("date")]
    if not messages:
        return
    with SessionLocal() as db:
        owners = db.query(BotAccount.owner_user_id).filter(BotAccount.token == token).distinct().all()
    for (owner_id,) in owners:
        for message in messages:
            chat = message["chat"]
            record_channel_content(owner_id, chat_id=chat.get("id"), username=chat.get("username"),
                                   date=datetime.fromtimestamp(message["date"], timezone.utc))
