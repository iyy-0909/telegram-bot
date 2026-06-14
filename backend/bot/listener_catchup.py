from sqlalchemy import func

from accounts.manager import account_manager
from bot.content_processor import get_message_text, process_content
from bot.logger import logger
from bot.sender import cleanup_prepared, prepare_album, prepare_single_message
from db.crud_bot import normalize_target_channel
from db.crud_listener import parse_target_channels
from db.database import SessionLocal
from db.models import ListenerSendEvent


MAX_AUTO_CATCHUP_ITEMS = 500


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


async def get_source_content_items_after(client, channel, after_message_id=0, limit=MAX_AUTO_CATCHUP_ITEMS):
    await ensure_client_connected(client)

    after_message_id = max(int(after_message_id or 0), 0)
    limit = max(min(int(limit or MAX_AUTO_CATCHUP_ITEMS), MAX_AUTO_CATCHUP_ITEMS), 1)
    messages = []

    async for message in client.iter_messages(
        channel,
        min_id=after_message_id,
        limit=limit * 20,
        reverse=True,
    ):
        messages.append(message)

    items = []
    grouped_map = {}
    grouped_order = []

    for message in messages:
        grouped_id = getattr(message, "grouped_id", None)

        if grouped_id:
            key = str(grouped_id)
            if key not in grouped_map:
                grouped_map[key] = []
                grouped_order.append(key)
            grouped_map[key].append(message)
        else:
            items.append({
                "messages": [message],
                "source_message_id": message.id,
                "grouped_id": None,
            })

    for key in grouped_order:
        album_messages = grouped_map[key]
        album_messages.sort(key=lambda item: item.id)
        items.append({
            "messages": album_messages,
            "source_message_id": max(item.id for item in album_messages),
            "grouped_id": getattr(album_messages[-1], "grouped_id", None),
        })

    items.sort(key=lambda item: item["source_message_id"])
    return items[:limit]


def target_lookup_keys(target):
    raw = str(target or "").strip()
    normalized = normalize_target_channel(raw)
    keys = {raw.lower(), normalized.lower()}
    return [key for key in keys if key]


def get_last_success_by_target(task_id, targets):
    db = SessionLocal()
    result = {}

    try:
        for target in targets:
            keys = target_lookup_keys(target)
            if not keys:
                result[target] = None
                continue

            event = (
                db.query(ListenerSendEvent)
                .filter(
                    ListenerSendEvent.task_id == task_id,
                    ListenerSendEvent.status == "success",
                    ListenerSendEvent.source_message_id.isnot(None),
                    func.lower(func.trim(ListenerSendEvent.target)).in_(keys),
                )
                .order_by(
                    ListenerSendEvent.source_message_id.desc(),
                    ListenerSendEvent.id.desc(),
                )
                .first()
            )
            result[target] = event

        return result
    finally:
        db.close()


def build_target_states(task, targets, last_success_map):
    states = []

    for target in targets:
        event = last_success_map.get(target)
        states.append({
            "target": target,
            "last_source_message_id": getattr(event, "source_message_id", None),
            "last_grouped_id": getattr(event, "grouped_id", None),
            "last_target_message_url": getattr(event, "target_message_url", "") or "",
            "last_success_at": str(getattr(event, "created_at", "") or ""),
        })

    return states


def targets_needing_item(target_states, source_message_id):
    targets = []

    for state in target_states:
        last_id = state.get("last_source_message_id") or 0
        if int(source_message_id or 0) > int(last_id or 0):
            targets.append(state["target"])

    return targets


async def build_listener_catchup_plan(task, limit=MAX_AUTO_CATCHUP_ITEMS):
    client = account_manager.get_client(task.account_id)

    if not client:
        return {
            "ok": False,
            "message": f"监听账号不存在：account_id={task.account_id}",
            "targets": [],
            "items": [],
        }

    targets = parse_target_channels(task.target_channels)

    if not targets:
        return {
            "ok": False,
            "message": "目标频道为空",
            "targets": [],
            "items": [],
        }

    last_success_map = get_last_success_by_target(task.id, targets)
    target_states = build_target_states(task, targets, last_success_map)
    known_last_ids = [
        int(state["last_source_message_id"])
        for state in target_states
        if state.get("last_source_message_id")
    ]
    after_message_id = (
        min(known_last_ids)
        if len(known_last_ids) == len(target_states)
        else 0
    )

    try:
        if after_message_id:
            content_items = await get_source_content_items_after(
                client,
                task.source_channel,
                after_message_id=after_message_id,
                limit=limit,
            )
        else:
            content_items = await get_recent_source_content_items(
                client,
                task.source_channel,
                limit=limit,
            )
    except Exception as e:
        logger.warning(
            f"监听一键补齐计划失败：读取源频道异常 | "
            f"task_id={task.id} | source={task.source_channel} | {e}"
        )
        return {
            "ok": False,
            "message": f"读取源频道失败：{e}",
            "targets": target_states,
            "items": [],
        }

    pending_items = []

    for item in content_items:
        source_message_id = item["source_message_id"]
        needed_targets = targets_needing_item(target_states, source_message_id)

        if not needed_targets:
            continue

        pending_items.append({
            "source_message_id": source_message_id,
            "grouped_id": str(item["grouped_id"]) if item.get("grouped_id") else None,
            "targets": needed_targets,
            "_messages": item["messages"],
            "_grouped_id": item.get("grouped_id"),
        })

    public_items = [
        {
            "source_message_id": item["source_message_id"],
            "grouped_id": item["grouped_id"],
            "targets": item["targets"],
        }
        for item in pending_items
    ]

    return {
        "ok": True,
        "message": (
            f"检测到可补齐 {len(pending_items)} 条内容"
            if pending_items
            else "未检测到需要补齐的内容"
        ),
        "task_id": task.id,
        "task_name": task.name,
        "source_channel": task.source_channel,
        "targets": target_states,
        "catchup_count": len(pending_items),
        "after_message_id": after_message_id,
        "limit": limit,
        "items": public_items,
        "_pending_items": pending_items,
    }


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


async def catchup_latest_listener_message_legacy(task, force=True, limit=1):
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
