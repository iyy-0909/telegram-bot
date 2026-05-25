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
    update_listener_status,
)
import bot.runtime as runtime


_registered_handlers = []
_album_cache = {}
_album_tasks = {}


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


def task_source_url(task, source_message_id):
    return build_message_url(task.source_channel, source_message_id) or ""


def target_already_sent(task_id, target, source_message_id, grouped_id=None):
    if grouped_id:
        return is_listener_album_sent(task_id, target, grouped_id)

    return is_listener_message_sent(task_id, target, source_message_id)


async def send_prepared_to_tasks(
    prepared,
    tasks,
    source_message_id,
    grouped_id=None,
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

        raw_text = prepared.get("_raw_text") or ""
        result = process_content(raw_text, task)

        if result.get("blocked"):
            for target in targets:
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    target=target,
                    source_message_id=source_message_id,
                    grouped_id=grouped_id,
                    source_message_url=task_source_url(task, source_message_id),
                    status="filtered",
                    message="监听消息被过滤",
                )

            logger.warning(
                f"监听消息被过滤 | task_id={task.id} | "
                f"message_id={source_message_id} | grouped_id={grouped_id}"
            )
            continue

        for target in targets:
            if target_already_sent(
                task.id,
                target,
                source_message_id,
                grouped_id,
            ):
                add_listener_send_event(
                    task_id=task.id,
                    task_name=task.name,
                    target=target,
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
            formatted_text = format_prepared_text(
                send_payload.get("_source_payload"),
                result.get("text") or "",
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
                send_result = await send_queue.send(
                    send_prepared_by_bot,
                    target,
                    send_payload,
                    bot_id=getattr(task, "bot_id", None),
                    task_id=f"listener:{task.id}",
                    target=target,
                    target_delay=0,
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

                    add_listener_send_event(
                        task_id=task.id,
                        task_name=task.name,
                        target=target,
                        source_message_id=source_message_id,
                        grouped_id=grouped_id,
                        source_message_url=task_source_url(task, source_message_id),
                        target_message_url=target_url,
                        status="success",
                        message="Bot API 已成功发送到目标频道",
                        bot_id=bot_id,
                        bot_name=bot_name,
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
                        target=target,
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
                    target=target,
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

    _album_cache.pop(album_key, None)
    _album_tasks.pop(album_key, None)

    if not messages:
        return

    messages.sort(key=lambda msg: msg.id)

    raw_text = ""

    for msg in messages:
        text = get_message_text(msg)

        if text:
            raw_text = text
            break

    max_message_id = max(msg.id for msg in messages)
    prepared = None

    try:
        prepared = await prepare_album(messages, raw_text)
        prepared["_raw_text"] = raw_text
        prepared["_source_payload"] = messages

        if not prepared or not prepared.get("ok"):
            logger.warning(
                f"监听相册准备失败 | grouped_id={grouped_id} | "
                f"message_ids={[msg.id for msg in messages]}"
            )
            return

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
        prepared = await prepare_single_message(message, raw_text)
        prepared["_raw_text"] = raw_text
        prepared["_source_payload"] = message

        if not prepared or not prepared.get("ok"):
            logger.warning(
                f"监听单条准备失败 | message_id={message.id}"
            )
            return

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
    global _registered_handlers

    for client, handler, builder in _registered_handlers:
        try:
            client.remove_event_handler(handler, builder)
        except Exception as e:
            logger.warning(f"移除旧监听失败：{e}")

    _registered_handlers = []
    logger.info("旧监听已卸载")


def register_handlers():
    clear_handlers()

    tasks = get_enabled_listener_tasks()
    task_groups = build_task_groups(tasks)

    for (account_id, source), group_tasks in task_groups.items():
        listen_client = account_manager.get_client(account_id)

        if not listen_client:
            logger.error(f"监听账号不存在：account_id={account_id}")
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
        logger.info(
            f"已注册监听 | account_id={account_id} | "
            f"source={source} | targets={targets}"
        )

    logger.info(f"已注册 {len(_registered_handlers)} 条聚合监听")


def reload_handlers():
    logger.info("开始热更新监听规则")
    register_handlers()
    logger.info("监听规则热更新完成")
