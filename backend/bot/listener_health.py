import asyncio
import os
import time
from datetime import datetime, timedelta

from sqlalchemy import func

from accounts.manager import account_manager
from bot.listener_catchup import get_recent_source_content_items
from bot.logger import logger
from bot.message_links import build_message_url
from bot.notifier import send_control_alert
from db.crud_bot import normalize_target_channel
from db.crud_listener import get_enabled_listener_tasks, parse_target_channels
from db.database import SessionLocal
from db.models import ListenerSendEvent


STALE_SECONDS = int(os.getenv("LISTENER_STALE_ALERT_SECONDS", str(2 * 24 * 60 * 60)))
CHECK_INTERVAL_SECONDS = int(os.getenv("LISTENER_HEALTH_CHECK_INTERVAL_SECONDS", "1800"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("LISTENER_STALE_ALERT_COOLDOWN_SECONDS", str(6 * 60 * 60)))

_listener_health_task = None
_alert_last_sent = {}


def utcnow():
    return datetime.utcnow()


def is_stale(task):
    timestamp = getattr(task, "last_received_at", None) or getattr(task, "created_at", None)
    if not timestamp:
        return True
    return utcnow() - timestamp > timedelta(seconds=STALE_SECONDS)


def target_lookup_keys(target):
    raw = str(target or "").strip()
    normalized = normalize_target_channel(raw)
    keys = {raw.lower(), normalized.lower()}
    return [key for key in keys if key]


def should_alert(key):
    now = time.time()
    last = _alert_last_sent.get(key, 0)
    if now - last < ALERT_COOLDOWN_SECONDS:
        return False
    _alert_last_sent[key] = now
    return True


def event_summary(event):
    if not event:
        return "没有找到该源消息的监听事件，实时监听可能没有收到这条源频道更新"

    parts = [
        f"最近事件：{event.event_type or event.status or '-'}",
        f"状态：{event.status or '-'}",
        f"时间：{event.created_at or '-'}",
    ]

    if event.target:
        parts.append(f"目标：{event.target}")
    if event.message:
        parts.append(f"说明：{event.message}")
    if event.error:
        parts.append(f"错误：{event.error}")

    return "\n".join(parts)


def analyze_unsent_reason(db, task, target, source_message_id, grouped_id):
    keys = target_lookup_keys(target)
    query = db.query(ListenerSendEvent).filter(
        ListenerSendEvent.task_id == task.id,
        ListenerSendEvent.source_message_id == source_message_id,
    )

    if grouped_id:
        query = query.filter(ListenerSendEvent.grouped_id == str(grouped_id))
    else:
        query = query.filter(ListenerSendEvent.grouped_id.is_(None))

    exact_events = query.order_by(ListenerSendEvent.id.desc()).all()

    target_events = [
        event
        for event in exact_events
        if not keys or (event.target or "").strip().lower() in keys
    ]
    event = target_events[0] if target_events else (exact_events[0] if exact_events else None)

    if event:
        event_type = (event.event_type or event.status or "").lower()
        if event_type in {"filtered", "empty"}:
            return f"源最新内容被过滤或处理为空。\n{event_summary(event)}"
        if event_type in {"failed", "error", "account_error"} or (event.error or ""):
            return f"监听收到后发送失败。\n{event_summary(event)}"
        if event_type in {"received", "prepared", "sending"}:
            return f"监听收到但没有成功发送记录，可能卡在准备/发送链路。\n{event_summary(event)}"
        if event_type == "deduped":
            return f"该目标被去重跳过，但未找到成功映射，建议检查去重记录。\n{event_summary(event)}"

    recent_event = (
        db.query(ListenerSendEvent)
        .filter(ListenerSendEvent.task_id == task.id)
        .order_by(ListenerSendEvent.id.desc())
        .first()
    )

    details = [
        "没有找到源最新内容的成功发送记录。",
        "可能原因：任务创建晚于源最新消息、监听未收到实时更新、账号更新流异常、目标 Bot 权限异常，或发送事件未写入。",
    ]

    if recent_event:
        details.extend(["", "该任务最近事件：", event_summary(recent_event)])
    else:
        details.append("该任务没有任何监听事件记录。")

    return "\n".join(details)


def find_success_event(db, task_id, target, source_message_id, grouped_id):
    keys = target_lookup_keys(target)
    query = db.query(ListenerSendEvent).filter(
        ListenerSendEvent.task_id == task_id,
        ListenerSendEvent.source_message_id == source_message_id,
        ListenerSendEvent.status == "success",
        func.lower(func.trim(ListenerSendEvent.target)).in_(keys),
    )

    if grouped_id:
        query = query.filter(ListenerSendEvent.grouped_id == str(grouped_id))
    else:
        query = query.filter(ListenerSendEvent.grouped_id.is_(None))

    return query.order_by(ListenerSendEvent.id.desc()).first()


async def inspect_stale_task(task):
    targets = parse_target_channels(task.target_channels)
    if not targets:
        return

    client = account_manager.get_client(task.account_id)
    if not client:
        await send_task_alert(
            task=task,
            title="监听任务账号未加载",
            level="error",
            message=f"监听任务超过 2 天未监听，且账号未加载：account_id={task.account_id}",
            alert_key=f"listener-health:account:{task.id}",
        )
        return

    try:
        items = await get_recent_source_content_items(client, task.source_channel, limit=1)
    except Exception as e:
        await send_task_alert(
            task=task,
            title="监听任务读取源频道失败",
            level="error",
            message=f"监听任务超过 2 天未监听，读取源频道失败：{e}",
            alert_key=f"listener-health:read-source:{task.id}",
        )
        return

    if not items:
        await send_task_alert(
            task=task,
            title="监听任务源频道无内容",
            level="warning",
            message="监听任务超过 2 天未监听，且源频道没有可读取内容，请确认源频道状态。",
            alert_key=f"listener-health:empty-source:{task.id}",
        )
        return

    item = items[-1]
    source_message_id = item["source_message_id"]
    grouped_id = item.get("grouped_id")
    source_url = build_message_url(task.source_channel, source_message_id) or ""

    db = SessionLocal()
    try:
        missing_targets = []
        sent_targets = []

        for target in targets:
            success = find_success_event(
                db,
                task.id,
                target,
                source_message_id,
                grouped_id,
            )
            if success:
                sent_targets.append((target, success))
            else:
                reason = analyze_unsent_reason(
                    db,
                    task,
                    target,
                    source_message_id,
                    grouped_id,
                )
                missing_targets.append((target, reason))

        if missing_targets:
            lines = [
                "监听任务最后监听超过 2 天，且源频道最新内容没有发送到部分目标。",
                f"任务：{task.name or '-'}",
                f"源频道：{task.source_channel}",
                f"源最新消息ID：{source_message_id}",
                f"相册ID：{grouped_id or '-'}",
                f"源链接：{source_url or '-'}",
                f"最后监听：{task.last_received_at or '从未监听到'}",
                "",
                "未发送目标与原因：",
            ]
            for target, reason in missing_targets:
                lines.extend([f"- {target}", reason[:1200]])

            await send_task_alert(
                task=task,
                title="监听任务疑似漏发",
                level="error",
                message="\n".join(lines),
                alert_key=f"listener-health:missing:{task.id}:{source_message_id}:{grouped_id or ''}",
                target=", ".join(target for target, _ in missing_targets),
            )
            return

        target_lines = [
            f"{target} -> {event.target_message_url or '-'}"
            for target, event in sent_targets
        ]
        message = "\n".join([
            "监听任务最后监听超过 2 天，但源频道最新内容已发送到目标频道。",
            "请确认源频道是否长时间没有更新，或该任务是否需要继续保留。",
            f"任务：{task.name or '-'}",
            f"源频道：{task.source_channel}",
            f"源最新消息ID：{source_message_id}",
            f"相册ID：{grouped_id or '-'}",
            f"源链接：{source_url or '-'}",
            f"最后监听：{task.last_received_at or '从未监听到'}",
            "",
            "目标映射：",
            *target_lines,
        ])
        await send_task_alert(
            task=task,
            title="监听任务长时间未更新",
            level="warning",
            message=message,
            alert_key=f"listener-health:stale-sent:{task.id}:{source_message_id}:{grouped_id or ''}",
        )
    finally:
        db.close()


async def send_task_alert(task, title, level, message, alert_key, target=""):
    if not should_alert(alert_key):
        return False

    return await send_control_alert(
        title=title,
        message=message,
        level=level,
        context={
            "alert_key": alert_key,
            "module": "listener_health",
            "task_id": task.id,
            "channel": task.source_channel,
            "target": target,
        },
    )


async def listener_health_worker():
    logger.info("Listener health worker started")

    while True:
        try:
            tasks = get_enabled_listener_tasks()
            for task in tasks:
                if is_stale(task):
                    await inspect_stale_task(task)
        except Exception as e:
            logger.warning(f"监听任务健康检查失败，已忽略 | {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start_listener_health_worker():
    global _listener_health_task
    if _listener_health_task and not _listener_health_task.done():
        return _listener_health_task
    _listener_health_task = asyncio.create_task(listener_health_worker())
    return _listener_health_task
