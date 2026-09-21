import asyncio
import json
from types import SimpleNamespace

from auth.access import FREE_PLAN_TASK_OVERRIDES, plan_content_processing_enabled
from auth.runtime_access import evaluate_user_runtime_access
from auth.tenant import tenant_scope
from bot.send_queue import send_queue, wait_or_stop
from bot.runtime_queue import runtime_queue_state
from accounts.manager import account_manager
from db.crud_clone import update_clone_progress, update_clone_task
from db.crud_bot import normalize_target_channel
from db.crud_sent import (
    is_message_sent,
    is_album_sent,
    mark_message_sent,
)
from bot.content_processor import (
    compose_content_templates_html,
    get_message_text,
    process_content_async,
)
from bot.entity_formatter import (
    format_prepared_text,
    html_to_plain_text,
    restore_source_links_as_html,
)
from bot.message_links import build_message_url, parse_message_url
from bot.clone_send_events import add_clone_send_event
from bot.handlers import reload_handlers
from bot.listener_catchup import check_latest_content_consistency
from bot.sender import (
    prepare_single_message,
    prepare_album,
    cleanup_prepared,
)

from bot.bot_distributor import send_prepared_by_bot
from bot.logger import logger
from bot.notifier import notify_error, notify_task_event
from bot.qr_filter import find_qr_code_files
from bot.qr_media_policy import filter_qr_media
from db.crud_listener import sync_clone_task_to_listener_tasks
from db.crud_my_channels import update_my_channel_clone_status
from db.database import SessionLocal
from db.models import CloneTask, UserAccount
from utils.redaction import redact_sensitive_text


def get_targets(task):
    """解析多个目标频道"""
    try:
        targets = json.loads(task.target_channels or "[]")

        if not isinstance(targets, list):
            return []

        return [
            normalize_target_channel(target)
            for target in targets
            if normalize_target_channel(target)
        ]

    except Exception:
        return []


def _apply_runtime_content_policy(task, user):
    """Apply the owner's current plan without trusting persisted task fields."""
    role = str(getattr(user, "role", "") or "").strip().lower()
    content_processing_enabled = role == "admin" or plan_content_processing_enabled(
        getattr(user, "plan_tier", None)
    )
    setattr(task, "_runtime_content_processing_enabled", content_processing_enabled)
    if not content_processing_enabled:
        for field, value in FREE_PLAN_TASK_OVERRIDES.items():
            if hasattr(task, field):
                setattr(task, field, value)
    return task


def _clone_content_policy_signature(task):
    return (
        bool(getattr(task, "_runtime_content_processing_enabled", True)),
        *(getattr(task, field, None) for field in FREE_PLAN_TASK_OVERRIDES),
    )


def _clone_route_signature(task):
    return (
        getattr(task, "owner_user_id", None),
        getattr(task, "account_id", None),
        str(getattr(task, "source_channel", "") or ""),
    )


def _passthrough_task_view(task):
    """Build a detached view that cannot apply paid filters or templates."""
    values = {
        key: value
        for key, value in vars(task).items()
        if key != "_sa_instance_state"
    }
    view = SimpleNamespace(**values)
    for field, value in FREE_PLAN_TASK_OVERRIDES.items():
        if hasattr(view, field):
            setattr(view, field, value)
    view._runtime_content_processing_enabled = False
    return view


def load_current_clone_runtime_task(task, *, persist_stop=True):
    """Load a fresh task and owner snapshot and enforce runtime access.

    A running worker may refresh targets, bot selection and delay settings, but
    it must never reuse messages already fetched from a different source route.
    """
    if not isinstance(task, CloneTask):
        # Production workers always pass CloneTask ORM objects. Lightweight
        # test doubles remain compatible with focused sender tests.
        return task

    task_id = getattr(task, "id", None)
    if task_id is None:
        return None

    expected_route = _clone_route_signature(task)
    db = SessionLocal()
    try:
        row = (
            db.query(CloneTask, UserAccount)
            .outerjoin(UserAccount, UserAccount.id == CloneTask.owner_user_id)
            .filter(CloneTask.id == int(task_id))
            .first()
        )
    except Exception as exc:
        logger.error(
            "failed to refresh clone task; stale worker rejected | "
            f"task_id={task_id} | error={redact_sensitive_text(exc)}"
        )
        return None
    finally:
        db.close()

    if not row:
        return None

    current_task, user = row
    if _clone_route_signature(current_task) != expected_route:
        logger.warning(
            "clone source route changed; stale worker rejected | "
            f"task_id={task_id}"
        )
        return None

    if not bool(getattr(current_task, "enabled", False)):
        return None
    if str(getattr(current_task, "status", "") or "") in {
        "paused",
        "stopped",
        "error",
    }:
        return None

    access = evaluate_user_runtime_access(user, "clone_tasks")
    if not access.allowed:
        if persist_stop:
            update_clone_task(current_task.id, {"status": "stopped"})
        logger.warning(
            "clone task blocked by fresh runtime access | "
            f"task_id={current_task.id} | reason={access.reason}"
        )
        return None

    return _apply_runtime_content_policy(current_task, user)


def _passthrough_content_result(raw_text, *, policy_signature=None):
    return {
        "blocked": False,
        "text": raw_text,
        "_runtime_raw_text": raw_text,
        "_runtime_passthrough": True,
        "_runtime_policy_signature": policy_signature,
    }


async def process_current_clone_content(raw_text, task):
    """Process content against fresh policy and revalidate after awaited AI."""
    current_task = load_current_clone_runtime_task(task, persist_stop=True)
    if current_task is None:
        return None, None

    signature = _clone_content_policy_signature(current_task)
    if not bool(
        getattr(current_task, "_runtime_content_processing_enabled", True)
    ):
        return current_task, _passthrough_content_result(
            raw_text,
            policy_signature=signature,
        )

    with tenant_scope(
        getattr(current_task, "owner_user_id", None),
        is_admin=False,
    ):
        result = await process_content_async(raw_text, current_task)

    refreshed_task = load_current_clone_runtime_task(
        current_task,
        persist_stop=True,
    )
    if refreshed_task is None:
        return None, None

    refreshed_signature = _clone_content_policy_signature(refreshed_task)
    if refreshed_signature != signature:
        logger.warning(
            "clone content policy changed during processing; using original content | "
            f"task_id={refreshed_task.id}"
        )
        return refreshed_task, _passthrough_content_result(
            raw_text,
            policy_signature=refreshed_signature,
        )

    result = dict(result or {})
    result["_runtime_raw_text"] = raw_text
    result["_runtime_passthrough"] = False
    result["_runtime_policy_signature"] = signature
    return refreshed_task, result


def group_messages(messages):
    """把普通消息和相册消息分组"""
    groups = []
    album_map = {}

    for message in messages:
        if message.grouped_id:
            album_map.setdefault(message.grouped_id, []).append(message)
        else:
            groups.append({
                "type": "single",
                "messages": [message],
            })

    for grouped_id, album_messages in album_map.items():
        album_messages.sort(key=lambda msg: msg.id)

        groups.append({
            "type": "album",
            "grouped_id": grouped_id,
            "messages": album_messages,
        })

    groups.sort(key=lambda item: item["messages"][0].id)

    return groups


def get_album_text(messages):
    """Get the first non-empty text from album messages."""
    for message in messages:
        text = get_message_text(message)

        if text:
            return text

    return ""


def should_stop(stop_event):
    """判断是否收到停止信号"""
    return bool(stop_event and stop_event.is_set())


def build_processed_text_payload(result):
    if not result.get("parse_mode"):
        payload = {
            "text": result.get("text") or "",
            "plain_text": result.get("text") or "",
        }
    else:
        payload = {
            "text": result.get("text") or "",
            "plain_text": result.get("plain_text") or result.get("text") or "",
            "parse_mode": result.get("parse_mode"),
            "html_text": result.get("html_text") or result.get("text") or "",
            "format_level": result.get("format_level") or "template_html",
            "kept_entities_count": 0,
            "dropped_entities_count": 0,
        }

    for key in (
        "_runtime_raw_text",
        "_runtime_passthrough",
        "_runtime_policy_signature",
    ):
        if key in result:
            payload[key] = result.get(key)
    return payload


def should_filter_qr_code(task) -> bool:
    return bool(getattr(task, "filter_qr_code", True))


async def _ensure_qr_scan(prepared, task):
    """Keep original files available for cleanup and runtime policy changes."""
    if should_filter_qr_code(task) and "_qr_code_files" not in prepared:
        files = prepared.get("_qr_original_files", prepared.get("files")) or []
        prepared["_qr_code_files"] = (
            await asyncio.to_thread(find_qr_code_files, files) if files else []
        )


def _record_clone_qr_filter(task, target, payload, source_message_id, grouped_id):
    add_clone_send_event(
        task_id=task.id,
        target=target,
        source_message_id=source_message_id,
        grouped_id=grouped_id,
        source_message_url=build_message_url(task.source_channel, source_message_id),
        target_message_url="",
        target_chat_id=target,
        message_type="caption" if payload.get("files") else "text",
        text="",
        caption=payload.get("text") or "",
        bot_id=getattr(task, "bot_id", None),
        event_type="filtered",
        status="filtered",
        message=payload.get("_qr_filter_message") or "二维码消息已过滤",
    )


def describe_qr_filter(qr_files):
    if not qr_files:
        return "二维码过滤：检测到二维码"

    names = [
        str(path).replace("\\", "/").rsplit("/", 1)[-1]
        for path in qr_files[:3]
    ]
    suffix = " 等" if len(qr_files) > 3 else ""
    return f"二维码过滤：检测到二维码文件 {', '.join(names)}{suffix}"


def describe_clone_content_filter(result, *, album=False):
    detail = result.get("filter_detail") or ""

    if detail:
        prefix = "克隆跳过：相册消息被过滤" if album else "克隆跳过：消息被过滤"
        return f"{prefix}：{detail}"

    if result.get("reason") == "empty_after_process":
        return "克隆跳过：相册内容处理后为空" if album else "克隆跳过：内容处理后为空"

    return "克隆跳过：相册关键词过滤" if album else "克隆跳过：关键词过滤"


def mark_stopped(task_id):
    update_clone_task(task_id, {"status": "stopped"})
    logger.warning(f"克隆任务已停止 | task_id={task_id}")


def build_clone_limit_waiting_meta(task, targets, next_item, wait_seconds):
    messages = next_item.get("messages") or []
    source_message_id = None

    if messages:
        source_message_id = max(message.id for message in messages)

    return {
        "source_type": "clone",
        "task_id": task.id,
        "task_name": task.name,
        "source_channel": task.source_channel,
        "target_channel": ", ".join(targets),
        "source_message_id": source_message_id,
        "grouped_id": next_item.get("grouped_id"),
        "message_type": next_item.get("type") or "",
        "reason": "克隆任务限流等待中",
        "estimated_send_remaining_seconds": wait_seconds,
    }


async def wait_clone_limit_for_next_item(task, targets, next_item, wait_seconds, stop_event=None):
    if not next_item or wait_seconds <= 0:
        return False

    queue_item_id = runtime_queue_state.add_waiting(
        build_clone_limit_waiting_meta(
            task,
            targets,
            next_item,
            wait_seconds,
        )
    )

    try:
        return await wait_or_stop(wait_seconds, stop_event)
    finally:
        runtime_queue_state.remove_waiting(queue_item_id)


async def enter_listener_after_clone(task):
    check_result = await check_latest_content_consistency(task)

    if not check_result.get("consistent"):
        logger.warning(
            f"克隆完成但最新内容未确认一致，暂不进入监听 | "
            f"task_id={task.id} | result={check_result}"
        )
        return check_result

    latest_task = update_clone_task(
        task.id,
        {
            "status": "done",
            "enable_listener": True,
        },
    )

    sync_result = sync_clone_task_to_listener_tasks(latest_task)
    reload_handlers()

    logger.info(
        f"克隆完成并已进入监听 | task_id={task.id} | "
        f"listener_sync={sync_result}"
    )

    return {
        **check_result,
        "listener_sync": sync_result,
    }


def get_clone_message_range(task):
    start_url = getattr(task, "start_message_url", "") or ""
    end_url = getattr(task, "end_message_url", "") or ""

    start_message_id = parse_message_url(start_url) if start_url.strip() else None
    end_message_id = parse_message_url(end_url) if end_url.strip() else None

    if (
        start_message_id is not None
        and end_message_id is not None
        and start_message_id > end_message_id
    ):
        raise ValueError(
            "start_message_url message_id must not be greater than end_message_url message_id"
        )

    return start_message_id, end_message_id


def _refresh_clone_send_state(task, state):
    current_task = load_current_clone_runtime_task(task, persist_stop=True)
    if current_task is None:
        return None

    current_signature = _clone_content_policy_signature(current_task)
    expected_signature = state.get("policy_signature")
    if (
        expected_signature is not None
        and current_signature != expected_signature
    ):
        state["passthrough"] = True
        logger.warning(
            "clone content policy changed before send; using original content | "
            f"task_id={getattr(current_task, 'id', None)}"
        )
    if not bool(
        getattr(current_task, "_runtime_content_processing_enabled", True)
    ):
        state["passthrough"] = True

    state["policy_signature"] = current_signature
    state["task"] = current_task
    return current_task


def _build_clone_target_payload(
    prepared,
    source_payload,
    text,
    task,
    target,
    *,
    raw_text,
    passthrough,
):
    target_prepared = filter_qr_media(prepared, enabled=should_filter_qr_code(task))
    format_task = _passthrough_task_view(task) if passthrough else task

    if passthrough:
        target_formatted_text = format_prepared_text(
            source_payload,
            raw_text,
            task=format_task,
            target=target,
        )
    elif isinstance(text, dict) and text.get("parse_mode"):
        target_formatted_text = dict(text)
        content_html = target_formatted_text.get("content_html")
        restored_html = restore_source_links_as_html(
            source_payload,
            content_html
            if content_html is not None
            else target_formatted_text.get("html_text")
            or target_formatted_text.get("text")
            or "",
            task=task,
            target=target,
        )
        restored_html = compose_content_templates_html(
            target_formatted_text,
            restored_html,
        )
        target_formatted_text["text"] = restored_html
        target_formatted_text["html_text"] = restored_html
        target_formatted_text["plain_text"] = html_to_plain_text(restored_html)
    else:
        processed_text = (
            text.get("text") or ""
            if isinstance(text, dict)
            else text
        )
        target_formatted_text = format_prepared_text(
            source_payload,
            processed_text,
            task=task,
            target=target,
        )

    target_send_text = target_formatted_text.get("text") or ""
    target_prepared["text"] = target_send_text
    target_prepared["plain_text"] = (
        target_formatted_text.get("plain_text") or target_send_text or ""
    )
    target_prepared["format_level"] = target_formatted_text.get("format_level")
    target_prepared["kept_entities_count"] = target_formatted_text.get(
        "kept_entities_count",
        0,
    )
    target_prepared["dropped_entities_count"] = target_formatted_text.get(
        "dropped_entities_count",
        0,
    )

    if target_formatted_text.get("entities"):
        target_prepared["entities"] = target_formatted_text.get("entities")
    else:
        target_prepared.pop("entities", None)

    if target_formatted_text.get("html_text"):
        target_prepared["html_text"] = target_formatted_text.get("html_text")
    else:
        target_prepared.pop("html_text", None)

    if target_formatted_text.get("parse_mode"):
        target_prepared["parse_mode"] = target_formatted_text.get("parse_mode")
    else:
        target_prepared.pop("parse_mode", None)

    return target_prepared


async def _send_clone_prepared_with_runtime_guard(
    target,
    target_prepared,
    *,
    task,
    state,
    source_payload,
    text,
    raw_text,
):
    """Final network-boundary guard, including waits inside SendQueue."""
    current_task = _refresh_clone_send_state(state.get("task") or task, state)
    if current_task is None:
        return False
    source_prepared = state.get("qr_source_prepared") or target_prepared
    await _ensure_qr_scan(source_prepared, current_task)
    current_task = _refresh_clone_send_state(current_task, state)
    if current_task is None:
        return False
    if isinstance(current_task, CloneTask) and target not in get_targets(current_task):
        logger.warning(
            "clone target removed before send; skipped | "
            f"task_id={current_task.id} | target={target}"
        )
        return False

    actual_payload = _build_clone_target_payload(
        source_prepared,
        source_payload,
        text,
        current_task,
        target,
        raw_text=raw_text,
        passthrough=bool(state.get("passthrough")),
    )
    target_prepared.clear()
    target_prepared.update(actual_payload)
    if target_prepared.get("_qr_filter_blocked"):
        return {"filtered": True, "message": target_prepared.get("_qr_filter_message")}
    return await send_prepared_by_bot(
        target,
        target_prepared,
        bot_id=getattr(current_task, "bot_id", None),
    )


async def send_to_targets(
    client,
    task,
    targets,
    source_message_id,
    grouped_id,
    message_type,
    source_payload,
    text,
    delay: int = 2,
    stop_event=None,
    skip_initial_delay=False,
):
    """
    发送到多个目标频道。

    每个目标独立发送，单个目标失败不影响其他目标。
    任意目标发送成功后写入 sent_messages，finally 统一清理临时文件。
    """
    if isinstance(text, dict) and "_runtime_raw_text" in text:
        raw_text = text.get("_runtime_raw_text")
    elif message_type == "album":
        raw_text = get_album_text(source_payload)
    else:
        raw_text = getattr(source_payload, "message", None)
        if raw_text is None:
            raw_text = (
                text.get("plain_text") or text.get("text") or ""
                if isinstance(text, dict)
                else text or ""
            )
    if raw_text is None:
        raw_text = ""

    state = {
        "policy_signature": (
            text.get("_runtime_policy_signature")
            if isinstance(text, dict)
            else None
        ),
        "passthrough": bool(
            isinstance(text, dict) and text.get("_runtime_passthrough")
        ),
        "task": task,
    }
    current_task = _refresh_clone_send_state(task, state)
    if current_task is None:
        return False
    task = current_task
    if state["policy_signature"] is None:
        state["policy_signature"] = _clone_content_policy_signature(task)
    if isinstance(task, CloneTask):
        targets = get_targets(task)

    if not targets:
        logger.warning(f"目标频道为空 | task_id={task.id}")
        return False

    # 去重判断
    if message_type == "album":
        if is_album_sent(task.id, grouped_id):
            logger.warning(
                f"跳过重复相册 | task_id={task.id} | grouped_id={grouped_id}"
            )
            return False
    else:
        if is_message_sent(task.id, source_message_id):
            logger.warning(
                f"跳过重复消息 | task_id={task.id} | "
                f"source_message_id={source_message_id}"
            )
            return False

    prepared = None
    sent_count = 0
    failed_count = 0
    filtered_count = 0
    dedupe_written = False
    source_message_url = build_message_url(task.source_channel, source_message_id)

    try:
        if state["passthrough"]:
            send_text = raw_text
        elif isinstance(text, dict):
            send_text = text.get("text") or ""
        else:
            send_text = text or ""

        # Prepare media only once and reuse it for all targets.
        if message_type == "album":
            prepared = await prepare_album(source_payload, send_text)
        else:
            prepared = await prepare_single_message(source_payload, send_text)

        if not prepared or not prepared.get("ok"):
            logger.warning(
                f"消息准备失败，跳过 | task_id={task.id} | "
                f"source_message_id={source_message_id} | grouped_id={grouped_id}"
            )
            return False

        state["qr_source_prepared"] = prepared

        # Media preparation can download for a long time. Refresh task, owner,
        # plan and targets immediately after that await.
        current_task = _refresh_clone_send_state(state.get("task") or task, state)
        if current_task is None:
            return False
        task = current_task
        targets = get_targets(task) if isinstance(task, CloneTask) else targets
        if not targets:
            logger.warning(f"目标频道为空 | task_id={task.id}")
            return False

        await _ensure_qr_scan(prepared, task)
        current_task = _refresh_clone_send_state(state.get("task") or task, state)
        if current_task is None:
            return False
        task = current_task
        targets = get_targets(task) if isinstance(task, CloneTask) else targets
        if not targets:
            return False
        qr_payload = filter_qr_media(prepared, enabled=should_filter_qr_code(task))
        if qr_payload.get("_qr_filter_blocked"):
            mark_message_sent(
                task_id=task.id,
                source_message_id=source_message_id,
                grouped_id=grouped_id if message_type == "album" else None,
            )
            for target in targets:
                _record_clone_qr_filter(
                    task, target, qr_payload, source_message_id, grouped_id,
                )
            return "filtered"

        scheduled_targets = set(targets)
        for index, target in enumerate(targets):
            target_label = "主目标" if index == 0 else "附加目标"

            try:
                if should_stop(stop_event):
                    logger.warning(
                        f"收到停止信号，停止发送剩余目标 | "
                        f"task_id={task.id} | source_message_id={source_message_id}"
                    )
                    break

                logger.info(
                    f"开始发送{target_label} | task_id={task.id} | "
                    f"target={target} | source_message_id={source_message_id}"
                )

                current_task = _refresh_clone_send_state(
                    state.get("task") or task,
                    state,
                )
                if current_task is None:
                    return False
                task = current_task
                latest_targets = (
                    get_targets(task)
                    if isinstance(task, CloneTask)
                    else targets
                )
                for latest_target in latest_targets:
                    if latest_target not in scheduled_targets:
                        targets.append(latest_target)
                        scheduled_targets.add(latest_target)
                if isinstance(task, CloneTask) and target not in latest_targets:
                    logger.info(
                        "clone target removed before queue; skipped | "
                        f"task_id={task.id} | target={target}"
                    )
                    continue

                target_prepared = _build_clone_target_payload(
                    prepared,
                    source_payload,
                    text,
                    task,
                    target,
                    raw_text=raw_text,
                    passthrough=bool(state.get("passthrough")),
                )

                send_result = await send_queue.send(
                    _send_clone_prepared_with_runtime_guard,
                    target,
                    target_prepared,
                    task_id=task.id,
                    target=target,
                    target_delay=getattr(task, "target_delay", delay),
                    owner_user_id=getattr(task, "owner_user_id", None),
                    skip_initial_delay=skip_initial_delay and index == 0,
                    stop_event=stop_event,
                    task=task,
                    state=state,
                    source_payload=source_payload,
                    text=text,
                    raw_text=raw_text,
                    queue_meta={
                        "source_type": "clone",
                        "task_id": task.id,
                        "task_name": task.name,
                        "source_channel": task.source_channel,
                        "target_channel": target,
                        "source_message_id": source_message_id,
                        "grouped_id": grouped_id,
                        "message_type": message_type,
                    },
                )

                # The queue itself may await global delay or retries. Refresh
                # once more before recording any post-send state or next target.
                post_send_task = _refresh_clone_send_state(
                    state.get("task") or task,
                    state,
                )
                if post_send_task is None:
                    return False
                task = post_send_task
                if isinstance(task, CloneTask):
                    for latest_target in get_targets(task):
                        if latest_target not in scheduled_targets:
                            targets.append(latest_target)
                            scheduled_targets.add(latest_target)

                if isinstance(send_result, dict) and send_result.get("filtered"):
                    filtered_count += 1
                    _record_clone_qr_filter(
                        task, target, target_prepared, source_message_id, grouped_id,
                    )
                    continue

                if send_result:
                    sent_count += 1
                    target_message_url = None
                    target_message_urls = []
                    target_message_ids = []

                    if isinstance(send_result, dict):
                        target_message_url = send_result.get("target_message_url")
                        target_message_urls = send_result.get("target_message_urls") or []
                        target_message_ids = send_result.get("target_message_ids") or []

                    logger.info(
                        f"{target_label}发送成功 | task_id={task.id} | "
                        f"target={target} | source_message_id={source_message_id} | "
                        f"source_message_url={source_message_url or ''} | "
                        f"target_message_ids={target_message_ids} | "
                        f"target_message_url={target_message_url or ''} | "
                        f"target_message_urls={target_message_urls}"
                    )

                    add_clone_send_event(
                        task_id=task.id,
                        target=target,
                        source_message_id=source_message_id,
                        grouped_id=grouped_id,
                        source_message_url=source_message_url,
                        target_message_url=target_message_url,
                        target_chat_id=target,
                        target_message_id=target_message_ids[0] if target_message_ids else None,
                        message_type="caption" if prepared.get("files") else "text",
                        text=(target_prepared.get("text") or "") if not prepared.get("files") else "",
                        caption=(target_prepared.get("text") or "") if prepared.get("files") else "",
                        bot_id=send_result.get("bot_id") if isinstance(send_result, dict) else getattr(task, "bot_id", None),
                        bot_name=send_result.get("bot_name") if isinstance(send_result, dict) else "",
                        event_type="success",
                        status="success",
                        message=(
                            "Bot API 已成功发送到目标频道"
                            + (f"；{target_prepared['_qr_filter_message']}"
                               if target_prepared.get("_qr_removed_files") else "")
                        ),
                    )

                    if not dedupe_written:
                        try:
                            mark_message_sent(
                                task_id=task.id,
                                source_message_id=source_message_id,
                                grouped_id=grouped_id if message_type == "album" else None,
                            )

                            dedupe_written = True

                            logger.info(
                                f"目标发送成功并写入去重 | task_id={task.id} | "
                                f"target={target} | source_message_id={source_message_id} | "
                                f"grouped_id={grouped_id} | "
                                f"source_message_url={source_message_url or ''} | "
                                f"target_message_url={target_message_url or ''}"
                            )

                        except Exception as e:
                            safe_error = redact_sensitive_text(e)
                            logger.exception(
                                f"目标发送成功，但写入去重失败 | task_id={task.id} | "
                                f"target={target} | source_message_id={source_message_id} | "
                                f"grouped_id={grouped_id} | {safe_error}"
                            )
                            return False

                else:
                    failed_count += 1
                    safe_error = redact_sensitive_text(
                        target_prepared.get("_last_error") or "Bot API 发送失败"
                    )

                    logger.warning(
                        f"{target_label}发送失败，继续其他目标 | task_id={task.id} | "
                        f"target={target} | source_message_id={source_message_id} | "
                        f"error={safe_error}"
                    )
                    add_clone_send_event(
                        task_id=task.id,
                        target=target,
                        source_message_id=source_message_id,
                        grouped_id=grouped_id,
                        source_message_url=source_message_url,
                        target_message_url="",
                        target_chat_id=target,
                        message_type="caption" if prepared.get("files") else "text",
                        text=(target_prepared.get("text") or "") if not prepared.get("files") else "",
                        caption=(target_prepared.get("text") or "") if prepared.get("files") else "",
                        bot_id=getattr(task, "bot_id", None),
                        event_type="failed",
                        status="failed",
                        message="Bot API 发送失败",
                        error=safe_error,
                    )

            except Exception as e:
                failed_count += 1
                safe_error = redact_sensitive_text(e)

                logger.exception(
                    f"发送{target_label}异常，继续其他目标 | task_id={task.id} | "
                    f"target={target} | source_message_id={source_message_id} | {safe_error}"
                )
                add_clone_send_event(
                    task_id=task.id,
                    target=target,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id,
                    source_message_url=source_message_url,
                    target_message_url="",
                    target_chat_id=target,
                    message_type="caption" if prepared.get("files") else "text",
                    text=(prepared.get("text") or "") if not prepared.get("files") else "",
                    caption=(prepared.get("text") or "") if prepared.get("files") else "",
                    bot_id=getattr(task, "bot_id", None),
                    event_type="failed",
                    status="failed",
                    message="克隆发送异常",
                    error=safe_error,
                )

        if sent_count > 0:
            logger.info(
                f"目标分发完成 | task_id={task.id} | "
                f"success={sent_count} | failed={failed_count} | "
                f"dedupe_written={dedupe_written} | "
                f"source_message_id={source_message_id} | grouped_id={grouped_id}"
            )
            return True

        if filtered_count > 0 and failed_count == 0:
            if not dedupe_written:
                mark_message_sent(
                    task_id=task.id,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id if message_type == "album" else None,
                )
            return "filtered"

        logger.warning(
            f"所有目标发送失败 | task_id={task.id} | "
            f"success={sent_count} | failed={failed_count} | "
            f"dedupe_written={dedupe_written} | "
            f"source_message_id={source_message_id} | "
            f"grouped_id={grouped_id}"
        )
        return False

    except Exception as e:
        safe_error = redact_sensitive_text(e)
        logger.exception(
            f"send_to_targets 异常 | task_id={task.id} | "
            f"source_message_id={source_message_id} | grouped_id={grouped_id} | {safe_error}"
        )
        return False

    finally:
        if prepared:
            cleanup_prepared(prepared)


async def clone_task(task, stop_event=None):
    """执行克隆任务"""

    if should_stop(stop_event):
        mark_stopped(task.id)
        return

    latest_task = load_current_clone_runtime_task(task, persist_stop=True)

    if latest_task is None:
        logger.warning(f"克隆任务启动前运行权限不可用 | task_id={task.id}")
        return
    task = latest_task

    client = account_manager.get_client(task.account_id)

    if not client:
        logger.info(
            f"克隆任务按需加载采集账号 | task_id={task.id} | account_id={task.account_id}"
        )
        loaded = await account_manager.load_account(task.account_id)
        client = account_manager.get_client(task.account_id) if loaded else None

        latest_task = load_current_clone_runtime_task(task, persist_stop=True)
        if latest_task is None:
            return
        task = latest_task

    if not client:
        message = (
            "克隆失败：账号不存在\n"
            f"任务ID：{task.id}\n"
            f"任务名称：{task.name}\n"
            f"账号ID：{task.account_id}"
        )

        logger.error(message)

        await notify_error(
            title="克隆任务失败：账号不存在",
            detail=message,
            task_id=task.id,
        )

        update_clone_task(task.id, {"status": "error"})
        return

    latest_task = load_current_clone_runtime_task(task, persist_stop=True)
    if latest_task is None:
        return
    task = latest_task
    targets = get_targets(task)

    if not targets:
        message = (
            "克隆失败：目标频道为空\n"
            f"任务ID：{task.id}\n"
            f"任务名称：{task.name}\n"
            f"源频道：{task.source_channel}"
        )

        logger.error(message)

        await notify_error(
            title="克隆任务失败：目标频道为空",
            detail=message,
            task_id=task.id,
        )

        update_clone_task(task.id, {"status": "error"})
        return

    if should_stop(stop_event):
        mark_stopped(task.id)
        return

    latest_task = load_current_clone_runtime_task(task, persist_stop=True)

    if latest_task is None:
        logger.warning(f"克隆任务启动前收到停止或权限状态 | task_id={task.id}")
        return
    task = latest_task

    update_clone_task(task.id, {"status": "running"})
    latest_task = load_current_clone_runtime_task(task, persist_stop=True)
    if latest_task is None:
        return
    task = latest_task
    targets = get_targets(task)

    logger.info(
        f"开始克隆 | task_id={task.id} | "
        f"{task.source_channel} -> {targets} | "
        f"last_message_id={task.last_message_id}"
    )

    await notify_task_event(
        title="克隆任务开始",
        task_id=task.id,
        task_name=task.name,
        detail=(
            f"源频道：{task.source_channel}\n"
            f"目标频道：{targets}\n"
            f"进度：{task.last_message_id}"
        ),
    )

    latest_task = load_current_clone_runtime_task(task, persist_stop=True)
    if latest_task is None:
        return
    task = latest_task
    targets = get_targets(task)

    try:
        messages = []

        last_message_id = task.last_message_id or 0
        iter_limit = None
        start_message_id, end_message_id = get_clone_message_range(task)
        min_message_id = last_message_id

        if start_message_id:
            min_message_id = max(min_message_id, start_message_id - 1)

        max_message_id = end_message_id + 1 if end_message_id else 0

        logger.info(
            f"clone range | task_id={task.id} | "
            f"start_message_id={start_message_id} | end_message_id={end_message_id} | "
            f"last_message_id={last_message_id} | min_id={min_message_id} | "
            f"max_id={max_message_id}"
        )

        async for message in client.iter_messages(
            task.source_channel,
            min_id=min_message_id,
            max_id=max_message_id,
            limit=iter_limit,
            reverse=True,
        ):
            if should_stop(stop_event):
                logger.warning(f"克隆停止 | task_id={task.id}")
                mark_stopped(task.id)
                return

            messages.append(message)

        if not messages:
            if should_stop(stop_event):
                mark_stopped(task.id)
                return

            latest_task = load_current_clone_runtime_task(task, persist_stop=True)
            if latest_task is None:
                return
            task = latest_task

            listener_result = await enter_listener_after_clone(task)

            if not listener_result.get("consistent"):
                update_clone_task(task.id, {"status": "done"})

            logger.info(
                f"没有需要克隆的新消息 | task_id={task.id}"
            )

            await notify_task_event(
                title="克隆任务无新内容",
                task_id=task.id,
                task_name=task.name,
                detail=f"源频道：{task.source_channel}",
            )

            return

        groups = group_messages(messages)
        first_send_pending = True

        logger.info(
            f"克隆扫描完成 | task_id={task.id} | "
            f"原始消息={len(messages)} | 内容组={len(groups)}"
        )

        for index, item in enumerate(groups):
            if should_stop(stop_event):
                logger.warning(f"克隆停止 | task_id={task.id}")
                mark_stopped(task.id)
                return

            latest_task = load_current_clone_runtime_task(
                task,
                persist_stop=True,
            )

            if not latest_task:
                logger.warning(
                    f"克隆任务运行状态或权限已变化 | task_id={task.id}"
                )
                return

            task = latest_task
            targets = get_targets(latest_task)
            if not targets:
                logger.warning(f"目标频道为空 | task_id={task.id}")
                return

            content_delay = max(int(latest_task.single_delay or 1), 1)
            next_item = groups[index + 1] if index + 1 < len(groups) else None

            try:
                # =========================
                # 单条消息
                # =========================
                if item["type"] == "single":
                    message = item["messages"][0]
                    message_id = message.id

                    if is_message_sent(task.id, message_id):
                        logger.info(
                            f"跳过重复消息 | task_id={task.id} | "
                            f"message_id={message_id}"
                        )

                        update_clone_progress(task.id, message_id)
                        continue

                    raw_text = get_message_text(message)
                    latest_task, result = await process_current_clone_content(
                        raw_text,
                        latest_task,
                    )
                    if latest_task is None:
                        return
                    task = latest_task
                    targets = get_targets(latest_task)
                    if not targets:
                        logger.warning(f"目标频道为空 | task_id={task.id}")
                        return

                    if result.get("blocked"):
                        update_clone_progress(task.id, message_id)
                        mark_message_sent(task.id, message_id, None)

                        reason = result.get("reason") or "filtered"
                        skip_message = describe_clone_content_filter(result)
                        logger.warning(
                            f"{skip_message} | task_id={task.id} | "
                            f"message_id={message_id} | reason={reason} | "
                            f"keyword={result.get('filter_keyword') or ''}"
                        )

                        continue

                    sent_ok = await send_to_targets(
                        client,
                        latest_task,
                        targets,
                        message_id,
                        None,
                        "single",
                        message,
                        build_processed_text_payload(result),
                        delay=latest_task.target_delay,
                        stop_event=stop_event,
                        skip_initial_delay=first_send_pending,
                    )
                    first_send_pending = False

                    latest_task = load_current_clone_runtime_task(
                        latest_task,
                        persist_stop=True,
                    )
                    if latest_task is None:
                        return
                    task = latest_task
                    targets = get_targets(latest_task)

                    if should_stop(stop_event):
                        mark_stopped(task.id)
                        return

                    if sent_ok:
                        update_clone_progress(task.id, message_id)

                        logger.info(
                            f"克隆单条处理完成 | task_id={task.id} | "
                            f"message_id={message_id}"
                        )

                    if await wait_clone_limit_for_next_item(
                        latest_task,
                        targets,
                        next_item,
                        content_delay,
                        stop_event,
                    ):
                        mark_stopped(task.id)
                        return

                    continue

                # =========================
                # 相册消息
                # =========================
                if item["type"] == "album":
                    album_messages = item["messages"]
                    grouped_id = item.get("grouped_id")

                    if not album_messages:
                        continue

                    max_id = max(message.id for message in album_messages)

                    if is_album_sent(task.id, grouped_id):
                        logger.info(
                            f"跳过重复相册 | task_id={task.id} | "
                            f"grouped_id={grouped_id} | last_id={max_id}"
                        )

                        update_clone_progress(task.id, max_id)
                        continue

                    raw_text = get_album_text(album_messages)
                    latest_task, result = await process_current_clone_content(
                        raw_text,
                        latest_task,
                    )
                    if latest_task is None:
                        return
                    task = latest_task
                    targets = get_targets(latest_task)
                    if not targets:
                        logger.warning(f"目标频道为空 | task_id={task.id}")
                        return

                    if result.get("blocked"):
                        update_clone_progress(task.id, max_id)
                        mark_message_sent(task.id, max_id, grouped_id)

                        reason = result.get("reason") or "filtered"
                        skip_message = describe_clone_content_filter(result, album=True)
                        logger.warning(
                            f"{skip_message} | task_id={task.id} | "
                            f"grouped_id={grouped_id} | last_id={max_id} | reason={reason} | "
                            f"keyword={result.get('filter_keyword') or ''}"
                        )

                        continue

                    sent_ok = await send_to_targets(
                        client,
                        latest_task,
                        targets,
                        max_id,
                        grouped_id,
                        "album",
                        album_messages,
                        build_processed_text_payload(result),
                        delay=latest_task.target_delay,
                        stop_event=stop_event,
                        skip_initial_delay=first_send_pending,
                    )
                    first_send_pending = False

                    latest_task = load_current_clone_runtime_task(
                        latest_task,
                        persist_stop=True,
                    )
                    if latest_task is None:
                        return
                    task = latest_task
                    targets = get_targets(latest_task)

                    if should_stop(stop_event):
                        mark_stopped(task.id)
                        return

                    if sent_ok:
                        update_clone_progress(task.id, max_id)

                        logger.info(
                            f"克隆相册处理完成 | task_id={task.id} | "
                            f"grouped_id={grouped_id} | 数量={len(album_messages)} | "
                            f"last_id={max_id}"
                        )

                    if await wait_clone_limit_for_next_item(
                        latest_task,
                        targets,
                        next_item,
                        content_delay,
                        stop_event,
                    ):
                        mark_stopped(task.id)
                        return

                    continue

            except Exception as e:
                safe_error = redact_sensitive_text(e)
                logger.exception(
                    f"克隆单组失败，继续下一组 | task_id={task.id} | {safe_error}"
                )

                # await notify_error(
                #     title="克隆单组失败",
                #     detail=(
                #         f"任务ID：{task.id}\n"
                #         f"任务名称：{task.name}\n"
                #         f"源频道：{task.source_channel}\n"
                #         f"错误：{safe_error}"
                #     ),
                #     task_id=task.id,
                # )

                continue

        if should_stop(stop_event):
            mark_stopped(task.id)
            return

        latest_task = load_current_clone_runtime_task(task, persist_stop=True)
        if latest_task is None:
            return
        task = latest_task
        targets = get_targets(task)

        listener_result = await enter_listener_after_clone(task)

        if not listener_result.get("consistent"):
            update_clone_task(task.id, {"status": "done"})

        latest_task = load_current_clone_runtime_task(task, persist_stop=False)
        if latest_task is not None:
            task = latest_task
            targets = get_targets(task)

        updated_channels = update_my_channel_clone_status(
            targets,
            task.source_channel,
            owner_user_id=getattr(task, "owner_user_id", None),
        )

        logger.info(f"克隆完成 | task_id={task.id}")
        logger.info(
            f"我的频道克隆状态已更新 | task_id={task.id} | "
            f"source={task.source_channel} | count={updated_channels}"
        )

        await notify_task_event(
            title="克隆任务完成",
            task_id=task.id,
            task_name=task.name,
            detail=f"源频道：{task.source_channel}",
        )

        return

    except ValueError as e:
        safe_error = redact_sensitive_text(e)
        message = redact_sensitive_text(
            "克隆失败：源频道异常或链接范围错误\n"
            f"任务ID：{task.id}\n"
            f"任务名称：{task.name}\n"
            f"源频道：{task.source_channel}\n"
            f"错误：{safe_error}"
        )

        logger.error(message)

        await notify_error(
            title="克隆任务失败：源频道异常",
            detail=message,
            task_id=task.id,
        )

        update_clone_task(task.id, {"status": "error"})
        return

    except Exception as e:
        safe_error = redact_sensitive_text(e)
        message = redact_sensitive_text(
            "克隆任务异常\n"
            f"任务ID：{task.id}\n"
            f"任务名称：{task.name}\n"
            f"源频道：{task.source_channel}\n"
            f"错误：{safe_error}"
        )

        logger.exception(message)

        await notify_error(
            title="克隆任务异常",
            detail=message,
            task_id=task.id,
        )

        update_clone_task(task.id, {"status": "error"})
        return

