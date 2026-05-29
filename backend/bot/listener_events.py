from db.database import SessionLocal
from db.models import ListenerSendEvent
from bot.logger import logger
from bot.notifier import send_control_alert
from utils.time_utils import format_app_time


MAX_EVENTS = 200
LISTENER_CONTROL_NOTIFY_SKIP_TYPES = {
    "success",
    "received",
    "prepared",
    "sending",
}


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


async def notify_listener_event(event):
    event_type = (event.get("event_type") or event.get("status") or "").strip()

    if event_type in LISTENER_CONTROL_NOTIFY_SKIP_TYPES:
        return False

    detail_lines = [
        f"任务：{event.get('task_name') or '-'}",
        f"源频道：{event.get('source_channel') or '-'}",
        f"目标频道：{event.get('target') or '-'}",
        f"源消息ID：{event.get('source_message_id') or '-'}",
    ]

    if event.get("grouped_id"):
        detail_lines.append(f"相册ID：{event.get('grouped_id')}")

    if event.get("source_message_url"):
        detail_lines.append(f"源链接：{event.get('source_message_url')}")

    if event.get("target_message_url"):
        detail_lines.append(f"目标链接：{event.get('target_message_url')}")

    if event.get("message"):
        detail_lines.extend(["", f"说明：{event.get('message')}"])

    if event.get("error"):
        detail_lines.extend(["", f"错误：{event.get('error')}"])

    level = "error" if event_type in {"failed", "error", "account_error"} else "warning"

    return await send_control_alert(
        title=f"监听记录：{event_type or '非成功'}",
        message="\n".join(detail_lines),
        level=level,
        context={
            "alert_key": (
                f"listener:{event_type}:"
                f"{event.get('task_id')}:"
                f"{event.get('target')}:"
                f"{event.get('source_message_id')}:"
                f"{event.get('grouped_id')}:"
                f"{event.get('time')}"
            ),
            "module": "listener",
            "task_id": event.get("task_id"),
            "channel": event.get("source_channel"),
            "target": event.get("target"),
            "bot_name": event.get("bot_name"),
        },
    )


def notify_listener_event_background(event):
    try:
        import asyncio

        loop = asyncio.get_running_loop()
        loop.create_task(notify_listener_event(event))
    except RuntimeError:
        try:
            import asyncio

            asyncio.run(notify_listener_event(event))
        except Exception as e:
            logger.warning(f"监听记录云台通知失败，已忽略 | {e}")
    except Exception as e:
        logger.warning(f"监听记录云台通知失败，已忽略 | {e}")


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
        payload = event_to_dict(event)
        notify_listener_event_background(payload)
        return payload

    except Exception as e:
        db.rollback()
        logger.warning(f"写入监听发送缓存失败，已忽略 | {e}")
        payload = {
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
        notify_listener_event_background(payload)
        return payload

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
