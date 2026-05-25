import json

from accounts.manager import account_manager
from db.crud import get_enabled_rules, update_last_message_id

from bot.filters import should_block
from bot.rewriter import rewrite_text
from bot.sender import send_message, send_album
from bot.queue import add_send_task
from bot.logger import logger


def get_message_text(message):
    return message.message or message.text or ""


async def clone_missing_history(limit: int = 500):
    rules = get_enabled_rules()

    for rule in rules:
        client = account_manager.get_client(rule.account_id)

        if not client:
            logger.error(
                f"历史补齐失败，账号不存在：account_id={rule.account_id}"
            )
            continue

        logger.info(
            f"开始补历史 | 源频道={rule.source} | 目标频道={rule.target} | last_id={rule.last_message_id}"
        )

        messages = []

        async for message in client.iter_messages(
            rule.source,
            min_id=rule.last_message_id or 0,
            limit=limit,
            reverse=True
        ):
            messages.append(message)

        grouped_map = {}
        normal_messages = []

        for message in messages:
            if message.grouped_id:
                grouped_map.setdefault(
                    message.grouped_id,
                    []
                ).append(message)
            else:
                normal_messages.append(message)

        processed_count = 0
        max_processed_id = rule.last_message_id or 0

        for message in normal_messages:
            raw_text = get_message_text(message)

            blocked_keywords = json.loads(rule.blocked_keywords or "[]")
            replace_words = json.loads(rule.replace_words or "{}")

            if should_block(raw_text, blocked_keywords):
                logger.warning(
                    f"历史普通消息已过滤：message_id={message.id}"
                )

                update_last_message_id(rule.id, message.id)
                max_processed_id = max(max_processed_id, message.id)
                continue

            final_text = rewrite_text(
                raw_text,
                replace_words,
                rule.footer or ""
            )

            await add_send_task(
                send_message,
                client,
                rule.target,
                message,
                final_text
            )

            update_last_message_id(rule.id, message.id)
            max_processed_id = max(max_processed_id, message.id)
            processed_count += 1

            logger.info(
                f"历史普通消息已加入队列：message_id={message.id}"
            )

        for grouped_id, album_messages in grouped_map.items():
            album_messages.sort(key=lambda msg: msg.id)

            raw_text = ""

            for msg in album_messages:
                text = get_message_text(msg)

                if text:
                    raw_text = text
                    break

            blocked_keywords = json.loads(rule.blocked_keywords or "[]")
            replace_words = json.loads(rule.replace_words or "{}")

            max_id = max(msg.id for msg in album_messages)

            if should_block(raw_text, blocked_keywords):
                logger.warning(
                    f"历史相册已过滤：grouped_id={grouped_id}"
                )

                update_last_message_id(rule.id, max_id)
                max_processed_id = max(max_processed_id, max_id)
                continue

            final_text = rewrite_text(
                raw_text,
                replace_words,
                rule.footer or ""
            )

            await add_send_task(
                send_album,
                client,
                rule.target,
                album_messages,
                final_text
            )

            update_last_message_id(rule.id, max_id)
            max_processed_id = max(max_processed_id, max_id)
            processed_count += len(album_messages)

            logger.info(
                f"历史相册已加入队列：grouped_id={grouped_id} 数量={len(album_messages)} last_id={max_id}"
            )

        logger.info(
            f"历史补齐扫描完成 | 源频道={rule.source} | 本次加入队列={processed_count}条 | 最新last_id={max_processed_id}"
        )