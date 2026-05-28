import asyncio
import time

from bot.bot_sender import BotApiError, request_post
from bot.control_config import control_config
from bot.logger import logger
from utils.time_utils import format_app_time


ALERT_COOLDOWN_SECONDS = 300
LEVEL_ORDER = {
    "info": 10,
    "warning": 20,
    "error": 30,
}

_alert_last_sent = {}
_missing_token_logged = False
_missing_chat_logged = False


def should_send_alert(key: str) -> bool:
    now = time.time()
    last_time = _alert_last_sent.get(key, 0)

    if now - last_time < ALERT_COOLDOWN_SECONDS:
        logger.warning(
            f"告警限流跳过 | key={key} | cooldown={ALERT_COOLDOWN_SECONDS}s"
        )
        return False

    _alert_last_sent[key] = now
    return True


def should_notify_level(level, min_level):
    return LEVEL_ORDER.get(level, 30) >= LEVEL_ORDER.get(min_level, 30)


def _send_message_sync(text: str, thread_id: str = ""):
    global _missing_token_logged
    global _missing_chat_logged

    config = control_config()

    if not config["enabled"] or not config["alerts_enabled"]:
        return False

    if not config["token"]:
        if not _missing_token_logged:
            _missing_token_logged = True
            logger.warning("CONTROL_BOT_TOKEN 未配置，云台告警通知已禁用。")
        return False

    if not config["chat_id"]:
        if not _missing_chat_logged:
            _missing_chat_logged = True
            logger.warning("CONTROL_CHAT_ID 未配置，云台告警通知已禁用。")
        return False

    data = {
        "chat_id": config["chat_id"],
        "text": text,
        "disable_web_page_preview": True,
    }

    target_thread_id = thread_id or config.get("alert_thread_id") or ""
    if target_thread_id:
        data["message_thread_id"] = target_thread_id

    try:
        request_post(config["token"], "sendMessage", data, None)
        return True
    except BotApiError as e:
        logger.warning(f"云台告警发送失败，已忽略 | {e}")
        return False


async def notify_text(text: str):
    try:
        return await asyncio.to_thread(_send_message_sync, text)
    except Exception as e:
        logger.warning(f"云台告警发送失败，已忽略 | {type(e).__name__}: {e}")
        return False


async def send_control_alert(title: str, message: str, level: str = "error", context=None):
    config = control_config()
    level = (level or "error").lower()

    if not should_notify_level(level, config.get("notify_level", "error")):
        return False

    context = context or {}
    key = f"{title}:{level}:{context.get('task_id')}:{context.get('target')}"
    if not should_send_alert(key):
        return False

    lines = [
        f"【{title}】",
        f"级别：{level.upper()}",
        f"时间：{format_app_time()}",
    ]

    for label, key_name in [
        ("模块", "module"),
        ("任务ID", "task_id"),
        ("频道", "channel"),
        ("目标", "target"),
        ("Bot", "bot_name"),
    ]:
        value = context.get(key_name)
        if value not in (None, ""):
            lines.append(f"{label}：{value}")

    if message:
        lines.extend(["", "详情：", str(message)[:3000]])

    return await notify_text("\n".join(lines))


async def notify_error(title: str, detail: str = "", task_id=None, target=None):
    return await send_control_alert(
        title=title,
        message=detail,
        level="error",
        context={
            "task_id": task_id,
            "target": target,
        },
    )


async def notify_task_event(title: str, task_id=None, task_name="", detail=""):
    return await send_control_alert(
        title=title,
        message=detail,
        level="info",
        context={
            "task_id": task_id,
            "task_name": task_name,
        },
    )
