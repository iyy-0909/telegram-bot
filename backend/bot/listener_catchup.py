from accounts.manager import account_manager
from bot.content_processor import get_message_text, process_content
from bot.logger import logger
from bot.sender import cleanup_prepared, prepare_album, prepare_single_message
from db.crud_listener import parse_target_channels


def normalize_compare_text(value: str) -> str:
    lines = [line.strip() for line in (value or "").splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def get_target_message_text(message):
    return (
        getattr(message, "message", None)
        or getattr(message, "text", None)
        or ""
    )


def message_has_media(message) -> bool:
    return bool(getattr(message, "media", None))


async def ensure_client_connected(client):
    if hasattr(client, "is_connected") and not client.is_connected():
        await client.connect()


async def get_latest_message(client, channel):
    await ensure_client_connected(client)

    async for message in client.iter_messages(channel, limit=1):
        return message

    return None


async def get_latest_source_messages(client, channel):
    latest = await get_latest_message(client, channel)

    if not latest:
        return []

    grouped_id = getattr(latest, "grouped_id", None)

    if not grouped_id:
        return [latest]

    messages = []

    async for message in client.iter_messages(channel, limit=20):
        if getattr(message, "grouped_id", None) == grouped_id:
            messages.append(message)

    messages.sort(key=lambda item: item.id)
    return messages or [latest]


async def get_recent_source_content_items(client, channel, limit=1):
    await ensure_client_connected(client)

    limit = max(min(int(limit or 1), 100), 1)
    fetch_limit = max(limit * 20, 20)
    recent_messages = []

    async for message in client.iter_messages(channel, limit=fetch_limit):
        recent_messages.append(message)

    items = []
    seen_grouped_ids = set()

    for message in recent_messages:
        grouped_id = getattr(message, "grouped_id", None)

        if grouped_id:
            grouped_key = str(grouped_id)

            if grouped_key in seen_grouped_ids:
                continue

            seen_grouped_ids.add(grouped_key)
            messages = [
                item
                for item in recent_messages
                if getattr(item, "grouped_id", None) == grouped_id
            ]
            messages.sort(key=lambda item: item.id)
        else:
            messages = [message]

        items.append({
            "messages": messages,
            "source_message_id": max(item.id for item in messages),
            "grouped_id": grouped_id,
        })

        if len(items) >= limit:
            break

    items.sort(key=lambda item: item["source_message_id"])
    return items


def compare_latest_content(source_text, source_has_media, target_text, target_has_media):
    if source_text != target_text:
        return False, "源频道和目标频道最新文本不一致"

    if source_has_media or target_has_media:
        return False, "最新内容包含媒体，无法仅通过文本安全判断一致"

    return True, "一致"


async def check_latest_content_consistency(task):
    """
    Check whether the latest source content matches the latest target content.

    Kept for API compatibility. The admin catchup flow no longer depends on
    this check before asking the user for a catchup count.
    """
    client = account_manager.get_client(task.account_id)

    if not client:
        return {
            "ok": False,
            "consistent": False,
            "message": f"监听账号不存在：account_id={task.account_id}",
            "targets": [],
        }

    targets = parse_target_channels(task.target_channels)

    if not targets:
        return {
            "ok": False,
            "consistent": False,
            "message": "目标频道为空",
            "targets": [],
        }

    try:
        source_message = await get_latest_message(client, task.source_channel)
    except Exception as e:
        logger.warning(
            f"监听补齐检测失败：读取源频道异常 | "
            f"task_id={task.id} | source={task.source_channel} | {e}"
        )
        return {
            "ok": False,
            "consistent": False,
            "message": f"读取源频道失败：{e}",
            "targets": [],
        }

    if not source_message:
        return {
            "ok": False,
            "consistent": False,
            "message": "源频道没有可读取内容",
            "targets": [],
        }

    raw_source_text = get_message_text(source_message)
    processed = process_content(raw_source_text, task)
    source_text = normalize_compare_text(processed.get("text") or "")
    source_has_media = message_has_media(source_message)

    target_results = []
    all_consistent = True

    for target in targets:
        try:
            target_message = await get_latest_message(client, target)
        except Exception as e:
            logger.warning(
                f"监听补齐检测失败：读取目标频道异常 | "
                f"task_id={task.id} | target={target} | {e}"
            )
            target_results.append({
                "target": target,
                "consistent": False,
                "message": f"读取目标频道失败：{e}",
                "source_message_id": source_message.id,
                "target_message_id": None,
            })
            all_consistent = False
            continue

        if not target_message:
            target_results.append({
                "target": target,
                "consistent": False,
                "message": "目标频道没有可读取内容",
                "source_message_id": source_message.id,
                "target_message_id": None,
            })
            all_consistent = False
            continue

        target_text = normalize_compare_text(get_target_message_text(target_message))
        target_has_media = message_has_media(target_message)
        consistent, message = compare_latest_content(
            source_text,
            source_has_media,
            target_text,
            target_has_media,
        )

        if not consistent:
            all_consistent = False

        target_results.append({
            "target": target,
            "consistent": consistent,
            "message": message,
            "source_message_id": source_message.id,
            "target_message_id": target_message.id,
            "source_has_media": source_has_media,
            "target_has_media": target_has_media,
        })

    return {
        "ok": True,
        "consistent": all_consistent,
        "message": (
            "源频道和目标频道最新内容一致"
            if all_consistent
            else "存在目标频道最新内容不一致"
        ),
        "source_channel": task.source_channel,
        "source_message_id": source_message.id,
        "source_has_media": source_has_media,
        "targets": target_results,
    }


async def catchup_latest_listener_message(task, force=True, limit=1):
    client = account_manager.get_client(task.account_id)

    if not client:
        return {
            "ok": False,
            "message": f"监听账号不存在：account_id={task.account_id}",
        }

    targets = parse_target_channels(task.target_channels)

    if not targets:
        return {
            "ok": False,
            "message": "目标频道为空",
        }

    try:
        content_items = await get_recent_source_content_items(
            client,
            task.source_channel,
            limit=limit,
        )
    except Exception as e:
        logger.warning(
            f"监听补齐失败：读取源频道异常 | "
            f"task_id={task.id} | source={task.source_channel} | {e}"
        )
        return {
            "ok": False,
            "message": f"读取源频道失败：{e}",
        }

    if not content_items:
        return {
            "ok": False,
            "message": "源频道没有可读取内容",
        }

    from bot.handlers import send_prepared_to_tasks

    requested_limit = max(min(int(limit or 1), 100), 1)
    sent_count = 0
    failed_count = 0
    results = []
    force_send = True

    for item in content_items:
        messages = item["messages"]
        source_message_id = item["source_message_id"]
        grouped_id = item["grouped_id"]
        prepared = None
        raw_text = ""

        for message in messages:
            text = get_message_text(message)
            if text:
                raw_text = text
                break

        try:
            if grouped_id and len(messages) > 1:
                prepared = await prepare_album(messages, raw_text)
                source_payload = messages
            else:
                prepared = await prepare_single_message(messages[-1], raw_text)
                source_payload = messages[-1]

            if not prepared or not prepared.get("ok"):
                failed_count += 1
                results.append({
                    "source_message_id": source_message_id,
                    "grouped_id": str(grouped_id) if grouped_id else None,
                    "ok": False,
                    "message": "内容准备失败，未发送",
                })
                continue

            prepared["_raw_text"] = raw_text
            prepared["_source_payload"] = source_payload

            sent = await send_prepared_to_tasks(
                prepared=prepared,
                tasks=[task],
                source_message_id=source_message_id,
                grouped_id=grouped_id,
                force=force_send,
            )

            if sent:
                sent_count += 1
            else:
                failed_count += 1

            results.append({
                "source_message_id": source_message_id,
                "grouped_id": str(grouped_id) if grouped_id else None,
                "ok": bool(sent),
                "message": "已补齐发送" if sent else "未发送，可能发送失败或内容被过滤",
            })

        except Exception as e:
            failed_count += 1
            logger.exception(
                f"listener catchup failed | task_id={task.id} | "
                f"source_message_id={source_message_id} | {e}"
            )
            results.append({
                "source_message_id": source_message_id,
                "grouped_id": str(grouped_id) if grouped_id else None,
                "ok": False,
                "message": f"补齐失败：{e}",
            })

        finally:
            if prepared:
                cleanup_prepared(prepared)

    return {
        "ok": sent_count > 0 and failed_count == 0,
        "message": (
            f"已补齐发送 {sent_count} 条"
            if failed_count == 0
            else f"补齐完成：成功 {sent_count} 条，失败 {failed_count} 条"
        ),
        "requested": requested_limit,
        "processed": len(content_items),
        "sent_count": sent_count,
        "failed_count": failed_count,
        "force": force_send,
        "results": results,
    }
