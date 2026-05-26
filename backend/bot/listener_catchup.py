from accounts.manager import account_manager
from bot.content_processor import get_message_text, process_content
from bot.logger import logger
from db.crud_listener import parse_target_channels


def normalize_compare_text(value: str) -> str:
    lines = [
        line.strip()
        for line in (value or "").splitlines()
    ]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def get_target_message_text(message):
    return (
        getattr(message, "message", None)
        or getattr(message, "text", None)
        or ""
    )


async def get_latest_message(client, channel):
    if hasattr(client, "is_connected") and not client.is_connected():
        await client.connect()

    async for message in client.iter_messages(channel, limit=1):
        return message

    return None


async def check_latest_content_consistency(task):
    """
    Check whether the latest source content matches the latest target content.

    This is a conservative text/caption comparison. Media binary comparison is
    intentionally not attempted because the target side is sent through Bot API.
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
        consistent = source_text == target_text

        if not consistent:
            all_consistent = False

        target_results.append({
            "target": target,
            "consistent": consistent,
            "message": "一致" if consistent else "源频道和目标频道最新文本不一致",
            "source_message_id": source_message.id,
            "target_message_id": target_message.id,
        })

    return {
        "ok": True,
        "consistent": all_consistent,
        "message": "源频道和目标频道最新内容一致" if all_consistent else "存在目标频道最新内容不一致",
        "source_channel": task.source_channel,
        "source_message_id": source_message.id,
        "targets": target_results,
    }
