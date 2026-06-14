import asyncio
from collections import defaultdict

from telethon import events

from accounts.manager import account_manager
from bot.bot_distributor import send_prepared_by_bot
from bot.content_processor import get_message_text, process_content
from bot.entity_formatter import format_prepared_text
from bot.listener_events import add_listener_send_event
from bot.logger import logger
from bot.message_links import build_message_url
from bot.qr_filter import find_qr_code_files
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
import bot.runtime as runtime


_registered_handlers = []
_registered_listener_groups = []
_album_cache = {}
_album_tasks = {}


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
        logger.warning(
            f"监听相册补拉失败，使用已缓存消息 | "
            f"channel={channel} | grouped_id={grouped_id} | {e}"
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


def task_source_url(task, source_message_id):
    return build_message_url(task.source_channel, source_message_id) or ""


def target_already_sent(task_id, target, source_message_id, grouped_id=None):
    if grouped_id:
        return is_listener_album_sent(task_id, target, grouped_id)

    return is_listener_message_sent(task_id, target, source_message_id)


def should_filter_qr_code(task) -> bool:
    return bool(getattr(task, "filter_qr_code", True))


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

    for task in tasks:
        targets = parse_target_channels(task.target_channels)

        if not targets:
            update_listener_status(
                task.id,
                last_error="target_channels empty",
            )
            continue

        if should_filter_qr_code(task):
            qr_files = find_qr_code_files(prepared.get("files") or [])

            if qr_files:
                event_message = describe_qr_filter(qr_files)
                for target in targets:
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
                        message=event_message,
                    )

                logger.warning(
                    f"监听二维码过滤，跳过发送 | task_id={task.id} | "
                    f"message_id={source_message_id} | grouped_id={grouped_id} | "
                    f"detail={event_message} | files={qr_files}"
                )
                continue

        raw_text = prepared.get("_raw_text") or ""
        result = process_content(raw_text, task)

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

            send_payload = dict(prepared)

            if result.get("parse_mode"):
                send_payload["text"] = result.get("text") or ""
                send_payload["plain_text"] = (
                    result.get("plain_text")
                    or result.get("text")
                    or ""
                )
                send_payload["parse_mode"] = result.get("parse_mode")
                send_payload["html_text"] = result.get("html_text") or result.get("text") or ""
                send_payload["format_level"] = result.get("format_level") or "template_html"
                send_payload["kept_entities_count"] = 0
                send_payload["dropped_entities_count"] = 0
                send_payload.pop("entities", None)
            else:
                formatted_text = format_prepared_text(
                    send_payload.get("_source_payload"),
                    result.get("text") or "",
                    task=task,
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

                send_payload["format_level"] = formatted_text.get("format_level")
                send_payload["kept_entities_count"] = formatted_text.get(
                    "kept_entities_count",
                    0,
                )
                send_payload["dropped_entities_count"] = formatted_text.get(
                    "dropped_entities_count",
                    0,
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
                    send_prepared_by_bot,
                    target,
                    send_payload,
                    bot_id=getattr(task, "bot_id", None),
                    task_id=f"listener:{task.id}",
                    target=target,
                    target_delay=0,
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
                        message="Bot API 已成功发送到目标频道",
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
                    error = send_payload.get("_last_error") or "Bot API 发送失败"
                    update_listener_status(task.id, last_error=error)
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
                        message=f"监听发送失败：{error}",
                        error=error,
                    )
                    logger.warning(
                        f"监听发送失败 | task_id={task.id} | "
                        f"target={target} | message_id={source_message_id} | "
                        f"grouped_id={grouped_id} | error={error}"
                    )

            except Exception as e:
                error = str(e)
                update_listener_status(task.id, last_error=error)
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
                    error=error,
                )
                logger.exception(
                    f"监听发送异常 | task_id={task.id} | "
                    f"target={target} | {error}"
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
        logger.exception(
            f"监听相册处理失败 | grouped_id={grouped_id} | {e}"
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
            error = ""
            if prepared:
                error = prepared.get("error_message") or prepared.get("error") or ""
            logger.warning(
                f"监听单条准备失败 | message_id={message.id} | reason={error or '-'}"
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
        logger.exception(
            f"监听单条处理失败 | message_id={message.id} | {e}"
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
            logger.warning(f"移除旧监听失败：{e}")

    _registered_handlers = []
    _registered_listener_groups = []
    logger.info("旧监听已卸载")


def register_handlers():
    clear_handlers()

    tasks = get_enabled_listener_tasks()
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
            await process_message(
                event.message,
                current_tasks,
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
