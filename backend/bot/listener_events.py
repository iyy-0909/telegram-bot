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
        "account_id": getattr(event, "account_id", None),
        "account_name": getattr(event, "account_name", "") or "",
        "source_message_id": event.source_message_id,
        "target_message_id": getattr(event, "target_message_id", None),
        "grouped_id": event.grouped_id,
        "source_message_url": event.source_message_url or "",
        "target_message_url": event.target_message_url or "",
        "status": event.status or "",
        "message": event.message or "",
        "error": event.error or "",
        "bot_id": event.bot_id,
        "bot_name": event.bot_name or "",
    }


def prune_listener_send_events(db, limit: int = MAX_EVENTS):
    ids_to_keep = [
        row.id
        for row in db.query(ListenerSendEvent.id)
        .order_by(ListenerSendEvent.id.desc())
        .limit(limit)
        .all()
    ]

    if ids_to_keep:
        db.query(ListenerSendEvent).filter(
            ListenerSendEvent.id.notin_(ids_to_keep)
        ).delete(synchronize_session=False)


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
):
    db = SessionLocal()

    try:
        event = ListenerSendEvent(
            time=format_app_time(),
            task_id=task_id,
            task_name=task_name or "",
            event_type=event_type or status or "",
            source_channel=source_channel or "",
            target=target or "",
            account_id=account_id,
            account_name=account_name or "",
            source_message_id=source_message_id,
            target_message_id=target_message_id,
            grouped_id=str(grouped_id) if grouped_id else None,
            source_message_url=source_message_url or "",
            target_message_url=target_message_url or "",
            status=status or "",
            message=message or "",
            error=error or "",
            bot_id=bot_id,
            bot_name=bot_name or "",
        )
        db.add(event)
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
            "account_id": account_id,
            "account_name": account_name,
            "source_message_id": source_message_id,
            "target_message_id": target_message_id,
            "grouped_id": grouped_id,
            "source_message_url": source_message_url,
            "target_message_url": target_message_url,
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
        events = (
            db.query(ListenerSendEvent)
            .order_by(ListenerSendEvent.id.desc())
            .limit(limit)
            .all()
        )
        return [event_to_dict(event) for event in events]

    finally:
        db.close()
