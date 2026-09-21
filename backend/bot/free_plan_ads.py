import asyncio

from bot.bot_sender import bot_send_text
from bot.logger import logger
from db.crud_advertisements import (
    finish_advertisement_delivery,
    list_due_advertisement_targets,
    reserve_advertisement_delivery,
)
from utils.redaction import redact_sensitive_text


_advertisement_task = None


async def dispatch_due_free_plan_advertisements(now=None):
    sent_count = 0
    failed_count = 0
    for item in list_due_advertisement_targets(now=now):
        delivery_id = reserve_advertisement_delivery(item)
        if not delivery_id:
            continue
        try:
            await bot_send_text(
                item["bot_token"],
                item["target_channel"],
                item["advertisement_text"],
            )
            finish_advertisement_delivery(delivery_id, sent=True)
            sent_count += 1
        except Exception as exc:
            finish_advertisement_delivery(
                delivery_id,
                sent=False,
                error=redact_sensitive_text(exc),
            )
            failed_count += 1
            logger.error(
                "免费版每日广告发送失败 | user_id=%s | bot_id=%s | target=%s | error=%s",
                item["user_id"],
                item["bot_id"],
                item["target_channel"],
                redact_sensitive_text(exc),
            )
    return {"sent": sent_count, "failed": failed_count}


async def free_plan_advertisement_worker():
    while True:
        try:
            await dispatch_due_free_plan_advertisements()
        except Exception as exc:
            logger.error("免费版广告调度异常 | error=%s", redact_sensitive_text(exc))
        await asyncio.sleep(60)


def start_free_plan_advertisement_worker():
    global _advertisement_task
    if _advertisement_task and not _advertisement_task.done():
        return _advertisement_task
    _advertisement_task = asyncio.create_task(free_plan_advertisement_worker())
    return _advertisement_task
