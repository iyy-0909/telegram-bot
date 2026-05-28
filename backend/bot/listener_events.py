from db.database import SessionLocal
from db.models import ListenerSendEvent
from bot.logger import logger
from utils.time_utils import format_app_time


MAX_EVENTS = 200


def event_to_dict(event):
    return {
        "time": event.time or "",
        "task_id": event.task_id,
        "task_name": event.task_name or "",
        "event_type": getattr(event, "event_type", "") or event.status or "",
        "source_channel": getattr(event, "source_channel", "") or "",
        "target": event.target or "",
        "target_chat_id": getattr(event, "target_chat_id", "") or "",
        "account_id": getattr(event, "account_id", None),
        "account_name": getattr(event, "account_name", "") or "",
        "source_message_id": event.source_message_id,
        "target_message_id": getattr(event, "target_message_id", None),
        "grouped_id": event.grouped_id,
        "source_message_url": event.source_message_url or "",
        "target_message_url": event.target_message_url or "",
        "message_type": getattr(event, "message_type", "") or "",
        "text": getattr(event, "text", "") or "",
        "caption": getattr(event, "caption", "") or "",
        "status": event.status or "",
        "message": event.message or "",
        "error": event.error or "",
        "bot_id": event.bot_id,
        "bot_name": event.bot_name or "",
    }


def prune_listener_send_events(db, limit: int = MAX_EVENTS):
    # 发送记录现在也是批量历史编辑的数据来源，不能再自动删除旧记录。
    return


def apply_event_fields(event, *, task_id, task_name, target, source_message_id,
                       event_type, source_channel, account_id, account_name,
                       target_message_id, grouped_id, source_message_url,
                       target_message_url, status, message, error, bot_id, bot_name,
                       target_chat_id="", message_type="", text="", caption=""):
    event.time = format_app_time()
    event.task_id = task_id
    event.task_name = task_name or ""
    event.event_type = event_type or status or ""
    event.source_channel = source_channel or ""
    event.target = target or ""
    event.target_chat_id = target_chat_id or target or ""
    event.account_id = account_id
    event.account_name = account_name or ""
    event.source_message_id = source_message_id
    event.target_message_id = target_message_id
    event.grouped_id = str(grouped_id) if grouped_id else None
    event.source_message_url = source_message_url or ""
    event.target_message_url = target_message_url or ""
    event.message_type = message_type or ""
    event.text = text or ""
    event.caption = caption or ""
    event.status = status or ""
    event.message = message or ""
    event.error = error or ""
    event.bot_id = bot_id
    event.bot_name = bot_name or ""


def normalize_grouped_id(grouped_id):
    return str(grouped_id) if grouped_id else None


def listener_event_content_key(event):
    grouped_id = normalize_grouped_id(getattr(event, "grouped_id", None))
    source_channel = getattr(event, "source_channel", "") or ""

    if grouped_id:
        return (
            getattr(event, "task_id", None),
            source_channel,
            "album",
            grouped_id,
        )

    source_message_id = getattr(event, "source_message_id", None)
    if source_message_id:
        return (
            getattr(event, "task_id", None),
            source_channel,
            "message",
            source_message_id,
        )

    return (
        getattr(event, "task_id", None),
        "task",
    )


def find_existing_content_event(db, *, task_id, source_channel, source_message_id, grouped_id):
    grouped_id = normalize_grouped_id(grouped_id)
    query = db.query(ListenerSendEvent).filter(ListenerSendEvent.task_id == task_id)

    if source_channel:
        query = query.filter(ListenerSendEvent.source_channel == source_channel)

    if grouped_id:
        query = query.filter(ListenerSendEvent.grouped_id == grouped_id)
    elif source_message_id:
        query = query.filter(
            ListenerSendEvent.source_message_id == source_message_id,
            ListenerSendEvent.grouped_id.is_(None),
        )
    else:
        query = query.filter(
            ListenerSendEvent.source_message_id.is_(None),
            ListenerSendEvent.grouped_id.is_(None),
        )

    return query.order_by(ListenerSendEvent.id.desc()).first()


def add_listener_send_event(
    *,
    task_id,
    task_name,
    target,
    source_message_id,
    event_type="success",
    source_channel="",
    account_id=None,
    account_name="",
    target_message_id=None,
    grouped_id=None,
    source_message_url="",
    target_message_url="",
    status="success",
    message="",
    error="",
    bot_id=None,
    bot_name="",
    target_chat_id="",
    message_type="",
    text="",
    caption="",
):
    db = SessionLocal()

    try:
        event = find_existing_content_event(
            db,
            task_id=task_id,
            source_channel=source_channel or "",
            source_message_id=source_message_id,
            grouped_id=grouped_id,
        )

        if event is None:
            event = ListenerSendEvent(task_id=task_id)
            db.add(event)

        apply_event_fields(
            event,
            task_id=task_id,
            task_name=task_name,
            target=target,
            source_message_id=source_message_id,
            event_type=event_type,
            source_channel=source_channel,
            account_id=account_id,
            account_name=account_name,
            target_message_id=target_message_id,
            grouped_id=grouped_id,
            source_message_url=source_message_url,
            target_message_url=target_message_url,
            status=status,
            message=message,
            error=error,
            bot_id=bot_id,
            bot_name=bot_name,
            target_chat_id=target_chat_id,
            message_type=message_type,
            text=text,
            caption=caption,
        )
        db.flush()
        prune_listener_send_events(db)
        db.commit()
        db.refresh(event)
        return event_to_dict(event)

    except Exception as e:
        db.rollback()
        logger.warning(f"写入监听发送缓存失败，已忽略 | {e}")
        return {
            "time": format_app_time(),
            "task_id": task_id,
            "task_name": task_name,
            "event_type": event_type or status or "",
            "source_channel": source_channel,
            "target": target,
            "target_chat_id": target_chat_id or target or "",
            "account_id": account_id,
            "account_name": account_name,
            "source_message_id": source_message_id,
            "target_message_id": target_message_id,
            "grouped_id": grouped_id,
            "source_message_url": source_message_url,
            "target_message_url": target_message_url,
            "message_type": message_type or "",
            "text": text or "",
            "caption": caption or "",
            "status": status,
            "message": message,
            "error": error,
            "bot_id": bot_id,
            "bot_name": bot_name,
        }

    finally:
        db.close()


def get_listener_send_events(limit: int = MAX_EVENTS):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = MAX_EVENTS

    limit = max(1, min(limit, MAX_EVENTS))
    db = SessionLocal()

    try:
        rows = (
            db.query(ListenerSendEvent)
            .order_by(ListenerSendEvent.id.desc())
            .limit(limit)
            .all()
        )
        events = []
        seen_content_keys = set()

        for event in rows:
            key = listener_event_content_key(event)
            if key in seen_content_keys:
                continue

            seen_content_keys.add(key)
            events.append(event_to_dict(event))

        return events

    finally:
        db.close()
