import asyncio
import json
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
from bot.content_processor import get_message_text, process_content
from bot.entity_formatter import format_prepared_text
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
from db.crud_listener import sync_clone_task_to_listener_tasks
from db.crud_my_channels import update_my_channel_clone_status


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
    dedupe_written = False
    source_message_url = build_message_url(task.source_channel, source_message_id)

    try:
        formatted_text = format_prepared_text(source_payload, text)
        send_text = formatted_text.get("text") or ""

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

        prepared["plain_text"] = formatted_text.get("plain_text") or text or ""
        prepared["format_level"] = formatted_text.get("format_level")
        prepared["kept_entities_count"] = formatted_text.get("kept_entities_count", 0)
        prepared["dropped_entities_count"] = formatted_text.get("dropped_entities_count", 0)

        if formatted_text.get("entities"):
            prepared["entities"] = formatted_text.get("entities")

        if formatted_text.get("html_text"):
            prepared["html_text"] = formatted_text.get("html_text")

        if formatted_text.get("parse_mode"):
            prepared["parse_mode"] = formatted_text.get("parse_mode")

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

                send_result = await send_queue.send(
                    send_prepared_by_bot,
                    target,
                    prepared,
                    bot_id=getattr(task, "bot_id", None),
                    task_id=task.id,
                    target=target,
                    target_delay=delay,
                    skip_initial_delay=skip_initial_delay and index == 0,
                    stop_event=stop_event,
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
                        text=(prepared.get("text") or "") if not prepared.get("files") else "",
                        caption=(prepared.get("text") or "") if prepared.get("files") else "",
                        bot_id=send_result.get("bot_id") if isinstance(send_result, dict) else getattr(task, "bot_id", None),
                        bot_name=send_result.get("bot_name") if isinstance(send_result, dict) else "",
                        event_type="success",
                        status="success",
                        message="Bot API 已成功发送到目标频道",
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
                            logger.exception(
                                f"目标发送成功，但写入去重失败 | task_id={task.id} | "
                                f"target={target} | source_message_id={source_message_id} | "
                                f"grouped_id={grouped_id} | {e}"
                            )
                            return False

                else:
                    failed_count += 1
                    error = prepared.get("_last_error") or "Bot API 发送失败"

                    logger.warning(
                        f"{target_label}发送失败，继续其他目标 | task_id={task.id} | "
                        f"target={target} | source_message_id={source_message_id} | "
                        f"error={error}"
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
                        message="Bot API 发送失败",
                        error=error,
                    )

            except Exception as e:
                failed_count += 1

                logger.exception(
                    f"发送{target_label}异常，继续其他目标 | task_id={task.id} | "
                    f"target={target} | source_message_id={source_message_id} | {e}"
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
                    error=str(e),
                )

        if sent_count > 0:
            logger.info(
                f"目标分发完成 | task_id={task.id} | "
                f"success={sent_count} | failed={failed_count} | "
                f"dedupe_written={dedupe_written} | "
                f"source_message_id={source_message_id} | grouped_id={grouped_id}"
            )
            return True

        logger.warning(
            f"所有目标发送失败 | task_id={task.id} | "
            f"success={sent_count} | failed={failed_count} | "
            f"dedupe_written={dedupe_written} | "
            f"source_message_id={source_message_id} | "
            f"grouped_id={grouped_id}"
        )
        return False

    except Exception as e:
        logger.exception(
            f"send_to_targets 异常 | task_id={task.id} | "
            f"source_message_id={source_message_id} | grouped_id={grouped_id} | {e}"
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

    latest_task = update_clone_task(task.id, {})

    if latest_task and latest_task.status == "stopped":
        logger.warning(f"克隆任务启动前已是停止状态 | task_id={task.id}")
        return

    client = account_manager.get_client(task.account_id)

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

    latest_task = update_clone_task(task.id, {})

    if latest_task and latest_task.status == "stopped":
        logger.warning(f"克隆任务启动前收到停止状态 | task_id={task.id}")
        return

    update_clone_task(task.id, {"status": "running"})

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

            latest_task = update_clone_task(task.id, {})

            if not latest_task:
                message = (
                    "克隆任务不存在\n"
                    f"任务ID：{task.id}"
                )

                logger.error(message)

                await notify_error(
                    title="克隆任务不存在",
                    detail=message,
                    task_id=task.id,
                )

                return

            if latest_task.status == "paused":
                logger.info(f"克隆已暂停 | task_id={task.id}")
                return

            if latest_task.status == "stopped":
                logger.warning(f"克隆已停止 | task_id={task.id}")
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
                    result = process_content(raw_text, latest_task)

                    if result.get("blocked"):
                        update_clone_progress(task.id, message_id)
                        mark_message_sent(task.id, message_id, None)

                        reason = result.get("reason") or "filtered"
                        skip_message = (
                            "克隆跳过：内容处理后为空"
                            if reason == "empty_after_process"
                            else "克隆跳过：关键词过滤"
                        )
                        logger.warning(
                            f"{skip_message} | task_id={task.id} | "
                            f"message_id={message_id} | reason={reason}"
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
                        result.get("text") or "",
                        delay=latest_task.target_delay,
                        stop_event=stop_event,
                        skip_initial_delay=first_send_pending,
                    )
                    first_send_pending = False

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
                    result = process_content(raw_text, latest_task)

                    if result.get("blocked"):
                        update_clone_progress(task.id, max_id)
                        mark_message_sent(task.id, max_id, grouped_id)

                        reason = result.get("reason") or "filtered"
                        skip_message = (
                            "克隆跳过：相册内容处理后为空"
                            if reason == "empty_after_process"
                            else "克隆跳过：相册关键词过滤"
                        )
                        logger.warning(
                            f"{skip_message} | task_id={task.id} | "
                            f"grouped_id={grouped_id} | last_id={max_id} | reason={reason}"
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
                        result.get("text") or "",
                        delay=latest_task.target_delay,
                        stop_event=stop_event,
                        skip_initial_delay=first_send_pending,
                    )
                    first_send_pending = False

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
                logger.exception(
                    f"克隆单组失败，继续下一组 | task_id={task.id} | {e}"
                )

                # await notify_error(
                #     title="鍏嬮殕鍗曠粍澶辫触",
                #     detail=(
                #         f"浠诲姟ID锛歿task.id}\n"
                #         f"浠诲姟鍚嶏細{task.name}\n"
                #         f"婧愰閬擄細{task.source_channel}\n"
                #         f"閿欒锛歿e}"
                #     ),
                #     task_id=task.id,
                # )

                continue

        if should_stop(stop_event):
            mark_stopped(task.id)
            return

        listener_result = await enter_listener_after_clone(task)

        if not listener_result.get("consistent"):
            update_clone_task(task.id, {"status": "done"})

        updated_channels = update_my_channel_clone_status(
            targets,
            task.source_channel,
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
        message = (
            "克隆失败：源频道异常或链接范围错误\n"
            f"任务ID：{task.id}\n"
            f"任务名称：{task.name}\n"
            f"源频道：{task.source_channel}\n"
            f"错误：{e}"
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
        message = (
            "克隆任务异常\n"
            f"任务ID：{task.id}\n"
            f"任务名称：{task.name}\n"
            f"源频道：{task.source_channel}\n"
            f"错误：{e}"
        )

        logger.exception(message)

        await notify_error(
            title="克隆任务异常",
            detail=message,
            task_id=task.id,
        )

        update_clone_task(task.id, {"status": "error"})
        return

