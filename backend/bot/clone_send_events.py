from db.database import SessionLocal
from db.models import CloneSendEvent
from bot.logger import logger
from utils.time_utils import format_app_time


MAX_EVENTS = 50


def event_to_dict(event):
    return {
        "time": event.time or "",
        "task_id": event.task_id,
        "target": event.target or "",
        "source_message_id": event.source_message_id,
        "target_chat_id": getattr(event, "target_chat_id", "") or "",
        "target_message_id": getattr(event, "target_message_id", None),
        "grouped_id": event.grouped_id,
        "source_message_url": event.source_message_url or "",
        "target_message_url": event.target_message_url or "",
        "event_type": getattr(event, "event_type", "") or "",
        "status": getattr(event, "status", "") or "",
        "message": getattr(event, "message", "") or "",
        "error": getattr(event, "error", "") or "",
        "message_type": getattr(event, "message_type", "") or "",
        "text": getattr(event, "text", "") or "",
        "caption": getattr(event, "caption", "") or "",
        "bot_id": getattr(event, "bot_id", None),
        "bot_name": getattr(event, "bot_name", "") or "",
    }


def prune_clone_send_events(db, limit: int = MAX_EVENTS):
    # 发送记录也是批量历史编辑的数据来源，不能再自动删除旧记录。
    return


def normalize_grouped_id(grouped_id):
    return str(grouped_id) if grouped_id else None


def find_existing_event(db, *, task_id, target, source_message_id, grouped_id):
    query = db.query(CloneSendEvent).filter(
        CloneSendEvent.task_id == task_id,
        CloneSendEvent.target == (target or ""),
    )

    grouped_id = normalize_grouped_id(grouped_id)

    if grouped_id:
        query = query.filter(CloneSendEvent.grouped_id == grouped_id)
    elif source_message_id:
        query = query.filter(
            CloneSendEvent.source_message_id == source_message_id,
            CloneSendEvent.grouped_id.is_(None),
        )
    else:
        query = query.filter(
            CloneSendEvent.source_message_id.is_(None),
            CloneSendEvent.grouped_id.is_(None),
        )

    return query.order_by(CloneSendEvent.id.desc()).first()


def apply_event_fields(
    event,
    *,
    task_id,
    target,
    source_message_id,
    grouped_id,
    source_message_url,
    target_message_url,
    target_chat_id,
    target_message_id,
    message_type,
    text,
    caption,
    bot_id,
    bot_name,
    event_type,
    status,
    message,
    error,
):
    event.time = format_app_time()
    event.task_id = task_id
    event.target = target or ""
    event.source_message_id = source_message_id
    event.target_chat_id = target_chat_id or target or ""
    event.target_message_id = target_message_id
    event.grouped_id = normalize_grouped_id(grouped_id)
    event.source_message_url = source_message_url or ""
    event.target_message_url = target_message_url or ""
    event.event_type = event_type or status or ""
    event.status = status or event_type or ""
    event.message = message or ""
    event.error = error or ""
    event.message_type = message_type or ""
    event.text = text or ""
    event.caption = caption or ""
    event.bot_id = bot_id
    event.bot_name = bot_name or ""


def add_clone_send_event(
    *,
    task_id,
    target,
    source_message_id,
    grouped_id,
    source_message_url,
    target_message_url,
    target_chat_id="",
    target_message_id=None,
    message_type="",
    text="",
    caption="",
    bot_id=None,
    bot_name="",
    event_type="success",
    status="success",
    message="",
    error="",
):
    db = SessionLocal()

    try:
        event = find_existing_event(
            db,
            task_id=task_id,
            target=target,
            source_message_id=source_message_id,
            grouped_id=grouped_id,
        )

        if event is None:
            event = CloneSendEvent(task_id=task_id)
            db.add(event)

        apply_event_fields(
            event,
            task_id=task_id,
            target=target,
            source_message_id=source_message_id,
            grouped_id=grouped_id,
            source_message_url=source_message_url,
            target_message_url=target_message_url,
            target_chat_id=target_chat_id,
            target_message_id=target_message_id,
            message_type=message_type,
            text=text,
            caption=caption,
            bot_id=bot_id,
            bot_name=bot_name,
            event_type=event_type,
            status=status,
            message=message,
            error=error,
        )
        db.flush()
        prune_clone_send_events(db)
        db.commit()
        db.refresh(event)
        return event_to_dict(event)

    except Exception as e:
        db.rollback()
        logger.warning(f"写入克隆发送记录失败，已忽略 | {e}")
        return {
            "time": format_app_time(),
            "task_id": task_id,
            "target": target or "",
            "source_message_id": source_message_id,
            "target_chat_id": target_chat_id or target or "",
            "target_message_id": target_message_id,
            "grouped_id": grouped_id,
            "source_message_url": source_message_url or "",
            "target_message_url": target_message_url or "",
            "event_type": event_type or status or "",
            "status": status or event_type or "",
            "message": message or "",
            "error": error or "",
            "message_type": message_type or "",
            "text": text or "",
            "caption": caption or "",
            "bot_id": bot_id,
            "bot_name": bot_name or "",
        }

    finally:
        db.close()


def get_clone_send_events(limit: int = MAX_EVENTS):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = MAX_EVENTS

    if limit < 1:
        limit = MAX_EVENTS

    limit = min(limit, MAX_EVENTS)
    db = SessionLocal()

    try:
        rows = (
            db.query(CloneSendEvent)
            .order_by(CloneSendEvent.id.desc())
            .limit(limit * 3)
            .all()
        )
        events = []
        seen = set()

        for event in rows:
            key = (
                event.task_id,
                event.target or "",
                normalize_grouped_id(event.grouped_id) or event.source_message_id,
            )
            if key in seen:
                continue

            seen.add(key)
            events.append(event_to_dict(event))

            if len(events) >= limit:
                break

        return events

    finally:
        db.close()
