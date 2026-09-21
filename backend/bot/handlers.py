import asyncio
from collections import defaultdict
from types import SimpleNamespace

from auth.access import FREE_PLAN_TASK_OVERRIDES, plan_content_processing_enabled
from auth.tenant import tenant_scope
from auth.runtime_access import evaluate_user_runtime_access, get_owner_runtime_access

from telethon import events

from accounts.manager import account_manager
from bot.bot_distributor import send_prepared_by_bot
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
from bot.listener_events import add_listener_send_event
from bot.logger import logger
from bot.message_links import build_message_url
from bot.qr_filter import find_qr_code_files
from bot.qr_media_policy import filter_qr_media
from bot.sender import (
    cleanup_prepared,
    prepare_album,
    prepare_single_message,
)
from bot.send_queue import send_queue
from db.crud_listener import (
    get_enabled_listener_tasks,
    is_listener_album_sent,
    is_listener_message_sent,
    mark_listener_message_sent,
    parse_target_channels,
    update_listener_last_received,
    update_listener_status,
)
from db.database import SessionLocal
from db.models import ListenerTask, UserAccount
import bot.runtime as runtime
from utils.redaction import redact_sensitive_text


_registered_handlers = []
_registered_listener_groups = []
_album_cache = {}
_album_tasks = {}
_handler_event_loop = None


async def ensure_client_connected(client):
    if client and hasattr(client, "is_connected") and not client.is_connected():
        await client.connect()


async def fetch_complete_album_messages(client, channel, grouped_id, existing_messages):
    if not grouped_id:
        return existing_messages

    try:
        await ensure_client_connected(client)
        fetched = []

        async for message in client.iter_messages(channel, limit=30):
            if getattr(message, "grouped_id", None) == grouped_id:
                fetched.append(message)

        if not fetched:
            return existing_messages

        merged = {
            message.id: message
            for message in existing_messages
        }

        for message in fetched:
            merged[message.id] = message

        complete_messages = list(merged.values())
        complete_messages.sort(key=lambda msg: msg.id)

        if len(complete_messages) > len(existing_messages):
            logger.info(
                f"监听相册补拉完整消息 | grouped_id={grouped_id} | "
                f"cached={len(existing_messages)} | complete={len(complete_messages)}"
            )

        return complete_messages

    except Exception as e:
        safe_error = redact_sensitive_text(e)
        logger.warning(
            f"监听相册补拉失败，使用已缓存消息 | "
            f"channel={channel} | grouped_id={grouped_id} | {safe_error}"
        )
        return existing_messages


def build_task_groups(tasks):
    groups = defaultdict(list)

    for task in tasks:
        key = (
            task.account_id,
            task.source_channel,
        )
        groups[key].append(task)

    return groups


def get_targets_from_tasks(tasks):
    targets = []

    for task in tasks:
        for target in parse_target_channels(task.target_channels):
            if target not in targets:
                targets.append(target)

    return targets


def get_registered_listener_snapshot():
    return [dict(item) for item in _registered_listener_groups]


def _apply_runtime_content_policy(task, user):
    role = str(getattr(user, "role", "") or "").strip().lower()
    content_processing_enabled = role == "admin" or plan_content_processing_enabled(
        getattr(user, "plan_tier", None)
    )
    setattr(
        task,
        "_runtime_content_processing_enabled",
        content_processing_enabled,
    )
    if not content_processing_enabled:
        for field, value in FREE_PLAN_TASK_OVERRIDES.items():
            if hasattr(task, field):
                setattr(task, field, value)
    return task


def _load_current_persisted_listener_tasks(tasks, *, persist_stop=True):
    """Load task and owner state in one fresh database snapshot.

    Handler closures intentionally keep only task identities.  Every incoming
    message resolves those identities again so a downgrade cannot keep using a
    detached paid-plan ORM object with stale filters, templates or AI settings.
    """
    task_refs = {
        int(task.id): task
        for task in tasks or []
        if isinstance(task, ListenerTask) and getattr(task, "id", None) is not None
    }
    if not task_refs:
        return []

    db = SessionLocal()
    try:
        rows = (
            db.query(ListenerTask, UserAccount)
            .outerjoin(
                UserAccount,
                UserAccount.id == ListenerTask.owner_user_id,
            )
            .filter(ListenerTask.id.in_(tuple(task_refs)))
            .all()
        )
    except Exception as exc:
        logger.error(
            "failed to refresh listener tasks; stale handlers rejected | "
            f"task_ids={sorted(task_refs)} | error={redact_sensitive_text(exc)}"
        )
        return []
    finally:
        db.close()

    current_by_id = {int(task.id): (task, user) for task, user in rows}
    allowed = []
    for task_id, stale_task in task_refs.items():
        current = current_by_id.get(task_id)
        if not current:
            continue
        task, user = current
        if not bool(getattr(task, "enabled", False)):
            continue

        # A handler registered for an old route must never process a message
        # after that task was moved to another account/source.
        if (
            getattr(stale_task, "account_id", None) != getattr(task, "account_id", None)
            or str(getattr(stale_task, "source_channel", "") or "")
            != str(getattr(task, "source_channel", "") or "")
        ):
            continue

        access = evaluate_user_runtime_access(user, "listener_tasks")
        if not access.allowed:
            if persist_stop:
                update_listener_status(
                    task.id,
                    enabled=False,
                    status="stopped",
                    last_error=access.message,
                )
            logger.warning(
                "listener task blocked by fresh runtime access | "
                f"task_id={task.id} | reason={access.reason}"
            )
            continue

        allowed.append(_apply_runtime_content_policy(task, user))
    return allowed


def filter_runtime_allowed_listener_tasks(tasks, *, persist_stop=True):
    allowed = []
    persisted_tasks = [
        task for task in tasks or [] if isinstance(task, ListenerTask)
    ]
    allowed.extend(
        _load_current_persisted_listener_tasks(
            persisted_tasks,
            persist_stop=persist_stop,
        )
    )
    for task in tasks or []:
        if isinstance(task, ListenerTask):
            continue
        # Lightweight test doubles remain compatible; production listener tasks
        # always take the fresh persisted path above.
        if not hasattr(task, "owner_user_id"):
            allowed.append(task)
            continue
        access = get_owner_runtime_access(
            getattr(task, "owner_user_id", None),
            "listener_tasks",
        )
        if access.allowed:
            allowed.append(task)
            continue
        if persist_stop:
            update_listener_status(
                task.id,
                enabled=False,
                status="stopped",
                last_error=access.message,
            )
        logger.warning(
            "listener task blocked by runtime access | "
            f"task_id={task.id} | reason={access.reason}"
        )
    return allowed


def _content_policy_signature(task):
    return (
        bool(getattr(task, "_runtime_content_processing_enabled", True)),
        *(
            getattr(task, field, None)
            for field in FREE_PLAN_TASK_OVERRIDES
        ),
    )


async def process_current_listener_content(raw_text, task):
    """Process against fresh policy and revalidate after any awaited AI call."""
    current_task = task
    for _attempt in range(2):
        signature = _content_policy_signature(current_task)
        if not bool(
            getattr(current_task, "_runtime_content_processing_enabled", True)
        ):
            # Free-plan delivery is a strict 1:1 content pass-through.  Bypass
            # the entire filtering/replacement/template/AI pipeline.
            result = {"blocked": False, "text": raw_text}
        else:
            with tenant_scope(
                getattr(current_task, "owner_user_id", None),
                is_admin=False,
            ):
                result = await process_content_async(raw_text, current_task)

        refreshed = filter_runtime_allowed_listener_tasks(
            [current_task],
            persist_stop=True,
        )
        if not refreshed:
            return None, None
        latest_task = refreshed[0]
        if _content_policy_signature(latest_task) == signature:
            return latest_task, result
        current_task = latest_task

    # Repeated concurrent policy changes fail closed to original content.  This
    # keeps delivery available while guaranteeing no paid processing leaks into
    # a newly-free account.
    logger.warning(
        "listener content policy changed repeatedly; using original content | "
        f"task_id={getattr(current_task, 'id', None)}"
    )
    return current_task, {"blocked": False, "text": raw_text}


def _listener_route_signature(task):
    return (
        getattr(task, "owner_user_id", None),
        getattr(task, "account_id", None),
        str(getattr(task, "source_channel", "") or ""),
    )


def _listener_passthrough_task_view(task):
    """Return a detached task view that cannot apply paid transformations."""
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


def _refresh_listener_send_state(task, state):
    """Refresh route, access and content policy immediately before sending."""
    current = filter_runtime_allowed_listener_tasks(
        [state.get("task") or task],
        persist_stop=True,
    )
    if not current:
        return None

    current_task = current[0]
    expected_route = state.get("route_signature")
    current_route = _listener_route_signature(current_task)
    if expected_route is not None and current_route != expected_route:
        logger.warning(
            "listener source route changed before send; stale payload rejected | "
            f"task_id={getattr(current_task, 'id', None)}"
        )
        return None

    current_signature = _content_policy_signature(current_task)
    expected_signature = state.get("policy_signature")
    if expected_signature is not None and current_signature != expected_signature:
        state["passthrough"] = True
        logger.warning(
            "listener content policy changed before send; using original content | "
            f"task_id={getattr(current_task, 'id', None)}"
        )
    if not bool(
        getattr(current_task, "_runtime_content_processing_enabled", True)
    ):
        state["passthrough"] = True

    state["policy_signature"] = current_signature
    state["route_signature"] = current_route
    state["task"] = current_task
    return current_task


def _build_listener_target_payload(
    prepared,
    result,
    task,
    target,
    *,
    raw_text,
    passthrough,
):
    send_payload = filter_qr_media(prepared, enabled=should_filter_qr_code(task))
    source_payload = send_payload.get("_source_payload")
    format_task = _listener_passthrough_task_view(task) if passthrough else task

    if passthrough:
        formatted_text = format_prepared_text(
            source_payload,
            raw_text,
            task=format_task,
            target=target,
        )
        send_payload["text"] = formatted_text.get("text") or ""
        send_payload["plain_text"] = formatted_text.get("plain_text") or raw_text
        if formatted_text.get("parse_mode"):
            send_payload["parse_mode"] = formatted_text.get("parse_mode")
        else:
            send_payload.pop("parse_mode", None)
        if formatted_text.get("entities"):
            send_payload["entities"] = formatted_text.get("entities")
        else:
            send_payload.pop("entities", None)
        if formatted_text.get("html_text"):
            send_payload["html_text"] = formatted_text.get("html_text")
        else:
            send_payload.pop("html_text", None)
        send_payload["format_level"] = formatted_text.get("format_level")
        send_payload["kept_entities_count"] = formatted_text.get(
            "kept_entities_count",
            0,
        )
        send_payload["dropped_entities_count"] = formatted_text.get(
            "dropped_entities_count",
            0,
        )
        return send_payload

    if result.get("parse_mode"):
        content_html = result.get("content_html")
        formatted_html = restore_source_links_as_html(
            source_payload,
            content_html
            if content_html is not None
            else result.get("html_text") or result.get("text") or "",
            task=format_task,
            target=target,
        )
        formatted_html = compose_content_templates_html(result, formatted_html)
        send_payload["text"] = formatted_html
        send_payload["plain_text"] = html_to_plain_text(formatted_html)
        send_payload["parse_mode"] = result.get("parse_mode")
        send_payload["html_text"] = formatted_html
        send_payload["format_level"] = result.get("format_level") or "template_html"
        send_payload["kept_entities_count"] = 0
        send_payload["dropped_entities_count"] = 0
        send_payload.pop("entities", None)
        return send_payload

    formatted_text = format_prepared_text(
        source_payload,
        result.get("text") or "",
        task=format_task,
        target=target,
    )
    send_payload["text"] = formatted_text.get("text") or ""
    send_payload["plain_text"] = (
        formatted_text.get("plain_text")
        or result.get("text")
        or ""
    )
    if formatted_text.get("parse_mode"):
        send_payload["parse_mode"] = formatted_text.get("parse_mode")
    else:
        send_payload.pop("parse_mode", None)
    if formatted_text.get("entities"):
        send_payload["entities"] = formatted_text.get("entities")
    else:
        send_payload.pop("entities", None)
    if formatted_text.get("html_text"):
        send_payload["html_text"] = formatted_text.get("html_text")
    else:
        send_payload.pop("html_text", None)
    send_payload["format_level"] = formatted_text.get("format_level")
    send_payload["kept_entities_count"] = formatted_text.get(
        "kept_entities_count",
        0,
    )
    send_payload["dropped_entities_count"] = formatted_text.get(
        "dropped_entities_count",
        0,
    )
    return send_payload


async def _send_listener_prepared_with_runtime_guard(
    target,
    send_payload,
    *,
    task,
    state,
    prepared,
    result,
    raw_text,
):
    """Final network-boundary guard, including waits inside SendQueue."""
    current_task = _refresh_listener_send_state(task, state)
    if current_task is None:
        return False
    await _ensure_qr_scan(prepared, current_task)
    current_task = _refresh_listener_send_state(current_task, state)
    if current_task is None:
        return False
    if target not in parse_target_channels(current_task.target_channels):
        logger.info(
            "listener target removed before send; skipped | "
            f"task_id={current_task.id} | target={target}"
        )
        return False

    actual_payload = _build_listener_target_payload(
        prepared,
        result,
        current_task,
        target,
        raw_text=raw_text,
        passthrough=bool(state.get("passthrough")),
    )
    send_payload.clear()
    send_payload.update(actual_payload)
    if send_payload.get("_qr_filter_blocked"):
        return {"filtered": True, "message": send_payload.get("_qr_filter_message")}
    return await send_prepared_by_bot(
        target,
        send_payload,
        bot_id=getattr(current_task, "bot_id", None),
    )


def task_source_url(task, source_message_id):
    return build_message_url(task.source_channel, source_message_id) or ""


def target_already_sent(task_id, target, source_message_id, grouped_id=None):
    if grouped_id:
        return is_listener_album_sent(task_id, target, grouped_id)

    return is_listener_message_sent(task_id, target, source_message_id)


def should_filter_qr_code(task) -> bool:
    return bool(getattr(task, "filter_qr_code", True))


async def _ensure_qr_scan(prepared, task):
    """Cache detection only; never remove files from the shared source payload."""
    if should_filter_qr_code(task) and "_qr_code_files" not in prepared:
        files = prepared.get("_qr_original_files", prepared.get("files")) or []
        prepared["_qr_code_files"] = (
            await asyncio.to_thread(find_qr_code_files, files) if files else []
        )


def _record_listener_qr_filter(task, target, payload, source_message_id, grouped_id):
    add_listener_send_event(
        task_id=task.id,
        task_name=task.name,
        event_type="filtered",
        source_channel=task.source_channel,
        target=target,
        account_id=task.account_id,
        source_message_id=source_message_id,
        grouped_id=grouped_id,
        source_message_url=task_source_url(task, source_message_id),
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


def describe_content_filter(result):
    detail = result.get("filter_detail") or ""
    if detail:
        return f"监听消息被过滤：{detail}"

    if result.get("reason") == "empty_after_process":
        return "内容处理后为空，已跳过"

    return "监听消息被过滤"


async def send_prepared_to_tasks(
    prepared,
    tasks,
    source_message_id,
    grouped_id=None,
    force=False,
    queue_source_type="listener",
    queue_reason=None,
):
    success_count = 0

    tasks = filter_runtime_allowed_listener_tasks(tasks, persist_stop=True)

    for task in tasks:
        targets = parse_target_channels(task.target_channels)

        if not targets:
            update_listener_status(
                task.id,
                last_error="target_channels empty",
            )
            continue

        await _ensure_qr_scan(prepared, task)
        refreshed = filter_runtime_allowed_listener_tasks([task], persist_stop=True)
        if not refreshed:
            continue
        task = refreshed[0]
        targets = parse_target_channels(task.target_channels)
        qr_payload = filter_qr_media(prepared, enabled=should_filter_qr_code(task))
        if qr_payload.get("_qr_filter_blocked"):
            for target in targets:
                _record_listener_qr_filter(
                    task, target, qr_payload, source_message_id, grouped_id,
                )
            continue

        raw_text = prepared.get("_raw_text") or ""
        task, result = await process_current_listener_content(raw_text, task)
        if task is None:
            continue
        targets = parse_target_channels(task.target_channels)
        if not targets:
            update_listener_status(
                task.id,
                last_error="target_channels empty",
            )
            continue

        if result.get("blocked"):
            reason = result.get("reason") or "filtered"
            is_empty_after_process = reason == "empty_after_process"
            event_type = "empty" if is_empty_after_process else "filtered"
            event_message = describe_content_filter(result)

            for target in targets:
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    event_type=event_type,
                    source_channel=task.source_channel,
                    target=target,
                    account_id=task.account_id,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id,
                    source_message_url=task_source_url(task, source_message_id),
                    status=event_type,
                    message=event_message,
                )

            logger.warning(
                f"{event_message} | task_id={task.id} | "
                f"message_id={source_message_id} | grouped_id={grouped_id} | "
                f"reason={reason} | keyword={result.get('filter_keyword') or ''}"
            )
            continue

        send_state = {
            "policy_signature": _content_policy_signature(task),
            "route_signature": _listener_route_signature(task),
            "passthrough": not bool(
                getattr(task, "_runtime_content_processing_enabled", True)
            ),
            "task": task,
        }

        for target in targets:
            if (not force) and target_already_sent(
                task.id,
                target,
                source_message_id,
                grouped_id,
            ):
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    event_type="deduped",
                    source_channel=task.source_channel,
                    target=target,
                    account_id=task.account_id,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id,
                    source_message_url=task_source_url(task, source_message_id),
                    status="deduped",
                    message="监听消息已发送，跳过去重目标",
                )
                logger.info(
                    f"监听跳过去重目标 | task_id={task.id} | "
                    f"target={target} | message_id={source_message_id} | "
                    f"grouped_id={grouped_id}"
                )
                continue

            send_payload = _build_listener_target_payload(
                prepared,
                result,
                task,
                target,
                raw_text=raw_text,
                passthrough=bool(send_state.get("passthrough")),
            )

            try:
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    event_type="sending",
                    source_channel=task.source_channel,
                    target=target,
                    account_id=task.account_id,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id,
                    source_message_url=task_source_url(task, source_message_id),
                    status="sending",
                    message="准备发送到目标频道",
                )

                send_result = await send_queue.send(
                    _send_listener_prepared_with_runtime_guard,
                    target,
                    send_payload,
                    task_id=f"listener:{task.id}",
                    target=target,
                    target_delay=0,
                    owner_user_id=getattr(task, "owner_user_id", None),
                    task=task,
                    state=send_state,
                    prepared=prepared,
                    result=result,
                    raw_text=raw_text,
                    queue_meta={
                        "source_type": queue_source_type,
                        "task_id": task.id,
                        "task_name": task.name,
                        "source_channel": task.source_channel,
                        "target_channel": target,
                        "source_message_id": source_message_id,
                        "grouped_id": grouped_id,
                        "message_type": "caption" if send_payload.get("files") else "text",
                        "reason": queue_reason or "等待全局发送队列",
                    },
                )

                if isinstance(send_result, dict) and send_result.get("filtered"):
                    _record_listener_qr_filter(
                        send_state.get("task") or task,
                        target,
                        send_payload,
                        source_message_id,
                        grouped_id,
                    )
                    continue

                if send_result:
                    success_count += 1
                    mark_listener_message_sent(
                        task.id,
                        target,
                        source_message_id,
                        grouped_id,
                    )
                    update_listener_status(
                        task.id,
                        status="running",
                        last_error="",
                    )

                    target_url = ""
                    bot_id = None
                    bot_name = ""

                    if isinstance(send_result, dict):
                        target_url = send_result.get("target_message_url") or ""
                        bot_id = send_result.get("bot_id")
                        bot_name = send_result.get("bot_name") or ""
                        target_ids = send_result.get("target_message_ids") or []
                        target_message_id = target_ids[0] if target_ids else None
                    else:
                        target_message_id = None

                    add_listener_send_event(
                        task_id=task.id,
                        task_name=task.name,
                        event_type="success",
                        source_channel=task.source_channel,
                        target=target,
                        account_id=task.account_id,
                        source_message_id=source_message_id,
                        target_message_id=target_message_id,
                        grouped_id=grouped_id,
                        source_message_url=task_source_url(task, source_message_id),
                        target_message_url=target_url,
                        status="success",
                        message=(
                            "Bot API 已成功发送到目标频道"
                            + (f"；{send_payload['_qr_filter_message']}"
                               if send_payload.get("_qr_removed_files") else "")
                        ),
                        bot_id=bot_id,
                        bot_name=bot_name,
                        target_chat_id=target,
                        message_type="caption" if send_payload.get("files") else "text",
                        text=(send_payload.get("text") or "") if not send_payload.get("files") else "",
                        caption=(send_payload.get("text") or "") if send_payload.get("files") else "",
                    )

                    logger.info(
                        f"监听发送成功 | task_id={task.id} | "
                        f"target={target} | message_id={source_message_id} | "
                        f"grouped_id={grouped_id} | "
                        f"source_message_url={task_source_url(task, source_message_id)} | "
                        f"target_message_url={target_url}"
                    )
                else:
                    safe_error = redact_sensitive_text(
                        send_payload.get("_last_error") or "Bot API 发送失败"
                    )
                    update_listener_status(task.id, last_error=safe_error)
                    add_listener_send_event(
                        task_id=task.id,
                        task_name=task.name,
                        event_type="failed",
                        source_channel=task.source_channel,
                        target=target,
                        account_id=task.account_id,
                        source_message_id=source_message_id,
                        grouped_id=grouped_id,
                        source_message_url=task_source_url(task, source_message_id),
                        status="error",
                        message=f"监听发送失败：{safe_error}",
                        error=safe_error,
                    )
                    logger.warning(
                        f"监听发送失败 | task_id={task.id} | "
                        f"target={target} | message_id={source_message_id} | "
                        f"grouped_id={grouped_id} | error={safe_error}"
                    )

            except Exception as e:
                safe_error = redact_sensitive_text(e)
                update_listener_status(task.id, last_error=safe_error)
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    event_type="failed",
                    source_channel=task.source_channel,
                    target=target,
                    account_id=task.account_id,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id,
                    source_message_url=task_source_url(task, source_message_id),
                    status="error",
                    message="监听发送异常",
                    error=safe_error,
                )
                logger.exception(
                    f"监听发送异常 | task_id={task.id} | "
                    f"target={target} | {safe_error}"
                )

    return success_count > 0


async def flush_album(album_key):
    cache_data = _album_cache.get(album_key)

    if not cache_data:
        return

    messages = cache_data["messages"]
    tasks = cache_data["tasks"]
    grouped_id = cache_data["grouped_id"]
    account_id = album_key[0]
    source = album_key[1]

    _album_cache.pop(album_key, None)
    _album_tasks.pop(album_key, None)

    if not messages:
        return

    client = account_manager.get_client(account_id)
    if client:
        messages = await fetch_complete_album_messages(
            client,
            source,
            grouped_id,
            messages,
        )

    messages.sort(key=lambda msg: msg.id)

    raw_text = ""

    for msg in messages:
        text = get_message_text(msg)

        if text:
            raw_text = text
            break

    if not raw_text:
        logger.warning(
            f"监听相册未找到 caption | grouped_id={grouped_id} | "
            f"message_ids={[msg.id for msg in messages]}"
        )

    max_message_id = max(msg.id for msg in messages)
    prepared = None

    try:
        for task in tasks:
            add_listener_send_event(
                task_id=task.id,
                task_name=task.name,
                event_type="received",
                source_channel=task.source_channel,
                target="",
                account_id=task.account_id,
                source_message_id=max_message_id,
                grouped_id=grouped_id,
                source_message_url=task_source_url(task, max_message_id),
                status="received",
                message=f"收到源频道相册，共 {len(messages)} 条",
            )

        prepared = await prepare_album(messages, raw_text)
        prepared["_raw_text"] = raw_text
        prepared["_source_payload"] = messages

        if not prepared or not prepared.get("ok"):
            logger.warning(
                f"监听相册准备失败 | grouped_id={grouped_id} | "
                f"message_ids={[msg.id for msg in messages]}"
            )
            return

        for task in tasks:
            add_listener_send_event(
                task_id=task.id,
                task_name=task.name,
                event_type="prepared",
                source_channel=task.source_channel,
                target="",
                account_id=task.account_id,
                source_message_id=max_message_id,
                grouped_id=grouped_id,
                source_message_url=task_source_url(task, max_message_id),
                status="prepared",
                message="相册内容准备完成",
            )

        await send_prepared_to_tasks(
            prepared=prepared,
            tasks=tasks,
            source_message_id=max_message_id,
            grouped_id=grouped_id,
        )

        logger.info(
            f"监听相册处理完成 | grouped_id={grouped_id} | "
            f"数量={len(messages)} | last_id={max_message_id}"
        )

    except Exception as e:
        safe_error = redact_sensitive_text(e)
        logger.exception(
            f"监听相册处理失败 | grouped_id={grouped_id} | {safe_error}"
        )

    finally:
        if prepared:
            cleanup_prepared(prepared)


async def album_timeout(album_key, wait_seconds):
    await asyncio.sleep(wait_seconds)

    if album_key in _album_cache:
        await flush_album(album_key)


async def process_message(message, tasks, source):
    if runtime.IS_SYNCING_HISTORY:
        logger.info(
            f"历史补齐中，跳过实时消息 | message_id={message.id}"
        )
        return

    update_listener_last_received([task.id for task in tasks])

    grouped_id = message.grouped_id

    if grouped_id:
        album_key = (
            tasks[0].account_id,
            source,
            grouped_id,
        )

        if album_key not in _album_cache:
            _album_cache[album_key] = {
                "messages": [],
                "tasks": tasks,
                "grouped_id": grouped_id,
            }

        _album_cache[album_key]["messages"].append(message)

        logger.info(
            f"监听缓存相册媒体 | grouped_id={grouped_id} | "
            f"message_id={message.id} | tasks={len(tasks)}"
        )

        if album_key not in _album_tasks:
            wait_seconds = max(
                int(getattr(tasks[0], "album_wait_seconds", 3) or 3),
                1,
            )
            _album_tasks[album_key] = asyncio.create_task(
                album_timeout(album_key, wait_seconds)
            )

        return

    raw_text = get_message_text(message)
    prepared = None

    try:
        for task in tasks:
            add_listener_send_event(
                task_id=task.id,
                task_name=task.name,
                event_type="received",
                source_channel=task.source_channel,
                target="",
                account_id=task.account_id,
                source_message_id=message.id,
                source_message_url=task_source_url(task, message.id),
                status="received",
                message="收到源频道新消息",
            )

        prepared = await prepare_single_message(message, raw_text)

        if not prepared or not prepared.get("ok"):
            safe_error = ""
            if prepared:
                safe_error = redact_sensitive_text(
                    prepared.get("error_message") or prepared.get("error") or ""
                )
            logger.warning(
                f"监听单条准备失败 | message_id={message.id} | reason={safe_error or '-'}"
            )
            return

        prepared["_raw_text"] = raw_text
        prepared["_source_payload"] = message

        for task in tasks:
            add_listener_send_event(
                task_id=task.id,
                task_name=task.name,
                event_type="prepared",
                source_channel=task.source_channel,
                target="",
                account_id=task.account_id,
                source_message_id=message.id,
                source_message_url=task_source_url(task, message.id),
                status="prepared",
                message="内容准备完成",
            )

        await send_prepared_to_tasks(
            prepared=prepared,
            tasks=tasks,
            source_message_id=message.id,
        )

        logger.info(
            f"监听单条处理完成 | message_id={message.id} | "
            f"tasks={len(tasks)}"
        )

    except Exception as e:
        safe_error = redact_sensitive_text(e)
        logger.exception(
            f"监听单条处理失败 | message_id={message.id} | {safe_error}"
        )

    finally:
        if prepared:
            cleanup_prepared(prepared)


def clear_handlers():
    global _registered_handlers, _registered_listener_groups

    for client, handler, builder in _registered_handlers:
        try:
            client.remove_event_handler(handler, builder)
        except Exception as e:
            safe_error = redact_sensitive_text(e)
            logger.warning(f"移除旧监听失败：{safe_error}")

    _registered_handlers = []
    _registered_listener_groups = []
    logger.info("旧监听已卸载")


def register_handlers():
    global _handler_event_loop

    try:
        _handler_event_loop = asyncio.get_running_loop()
    except RuntimeError:
        # Unit tests and maintenance scripts may register without an event loop.
        # Keep the last live application loop if one was already captured.
        pass

    clear_handlers()

    tasks = filter_runtime_allowed_listener_tasks(
        get_enabled_listener_tasks(),
        persist_stop=True,
    )
    task_groups = build_task_groups(tasks)

    for (account_id, source), group_tasks in task_groups.items():
        listen_client = account_manager.get_client(account_id)

        if not listen_client:
            logger.error(f"监听账号不存在：account_id={account_id}")
            for task in group_tasks:
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    event_type="account_error",
                    source_channel=task.source_channel,
                    target="",
                    account_id=task.account_id,
                    source_message_id=None,
                    status="error",
                    message="监听账号不存在或未加载",
                    error=f"account_id={account_id}",
                )
            continue

        builder = events.NewMessage(chats=source)

        async def handler(
            event,
            current_tasks=group_tasks,
            current_source=source,
        ):
            active_tasks = filter_runtime_allowed_listener_tasks(
                current_tasks,
                persist_stop=True,
            )
            if not active_tasks:
                return
            await process_message(
                event.message,
                active_tasks,
                current_source,
            )

        listen_client.add_event_handler(handler, builder)
        _registered_handlers.append((listen_client, handler, builder))

        targets = get_targets_from_tasks(group_tasks)
        _registered_listener_groups.append({
            "account_id": account_id,
            "source": source,
            "task_ids": [task.id for task in group_tasks],
            "targets": targets,
        })
        logger.info(
            f"已注册监听 | account_id={account_id} | "
            f"source={source} | targets={targets}"
        )

    logger.info(f"已注册 {len(_registered_handlers)} 条聚合监听")


def reload_handlers():
    logger.info("开始热更新监听规则")
    register_handlers()
    logger.info("监听规则热更新完成")


async def _reload_handlers_on_event_loop():
    reload_handlers()


def request_reload_handlers(timeout_seconds=5):
    """Reload on the bot event loop even when called by a sync API worker."""
    target_loop = _handler_event_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is not None and current_loop is target_loop:
        reload_handlers()
        return True

    if (
        target_loop is not None
        and target_loop.is_running()
        and not target_loop.is_closed()
    ):
        future = asyncio.run_coroutine_threadsafe(
            _reload_handlers_on_event_loop(),
            target_loop,
        )
        try:
            future.result(timeout=max(float(timeout_seconds or 0), 0.1))
            return True
        except TimeoutError:
            logger.warning("listener handler reload scheduled but not completed in time")
            return False
        except Exception as exc:
            logger.error(
                "listener handler reload failed | "
                f"error={redact_sensitive_text(exc)}"
            )
            return False

    try:
        reload_handlers()
        return True
    except Exception as exc:
        logger.error(
            "listener handler reload failed without application loop | "
            f"error={redact_sensitive_text(exc)}"
        )
        return False
