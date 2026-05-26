from db.database import SessionLocal
from db.models import CloneSendEvent
from bot.logger import logger
from utils.time_utils import format_app_time


MAX_EVENTS = 20


def event_to_dict(event):
    return {
        "time": event.time or "",
        "task_id": event.task_id,
        "target": event.target or "",
        "source_message_id": event.source_message_id,
        "grouped_id": event.grouped_id,
        "source_message_url": event.source_message_url or "",
        "target_message_url": event.target_message_url or "",
    }


def prune_clone_send_events(db, limit: int = MAX_EVENTS):
    ids_to_keep = [
        row.id
        for row in db.query(CloneSendEvent.id)
        .order_by(CloneSendEvent.id.desc())
        .limit(limit)
        .all()
    ]

    if ids_to_keep:
        db.query(CloneSendEvent).filter(
            CloneSendEvent.id.notin_(ids_to_keep)
        ).delete(synchronize_session=False)


def add_clone_send_event(
    *,
    task_id,
    target,
    source_message_id,
    grouped_id,
    source_message_url,
    target_message_url,
):
    db = SessionLocal()

    try:
        event = CloneSendEvent(
            time=format_app_time(),
            task_id=task_id,
            target=target or "",
            source_message_id=source_message_id,
            grouped_id=str(grouped_id) if grouped_id else None,
            source_message_url=source_message_url or "",
            target_message_url=target_message_url or "",
        )
        db.add(event)
        db.flush()
        prune_clone_send_events(db)
        db.commit()
        db.refresh(event)
        return event_to_dict(event)

    except Exception as e:
        db.rollback()
        logger.warning(f"写入克隆发送缓存失败，已忽略 | {e}")
        return {
            "time": format_app_time(),
            "task_id": task_id,
            "target": target or "",
            "source_message_id": source_message_id,
            "grouped_id": grouped_id,
            "source_message_url": source_message_url or "",
            "target_message_url": target_message_url or "",
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
        events = (
            db.query(CloneSendEvent)
            .order_by(CloneSendEvent.id.desc())
            .limit(limit)
            .all()
        )
        return [event_to_dict(event) for event in events]

    finally:
        db.close()
