import asyncio
import os
import requests
import time
from bot.logger import logger
from utils.proxy_utils import is_production
from utils.proxy_utils import normalize_bot_api_proxy_for_runtime


# =========================
# 这里先写死，后面再放到后台系统设置
# =========================

CONTROL_BOT_TOKEN = os.getenv("CONTROL_BOT_TOKEN", "").strip()
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID", "").strip()

BOT_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT = 60

DEFAULT_BOT_API_PROXY = "http://127.0.0.1:7897"


def get_bot_api_proxies():
    proxy = os.getenv("BOT_API_PROXY") or os.getenv("TELEGRAM_PROXY")

    if not proxy and not is_production():
        proxy = DEFAULT_BOT_API_PROXY

    proxy = normalize_bot_api_proxy_for_runtime(proxy)

    if not proxy:
        return {}

    return {
        "http": proxy,
        "https": proxy,
    }


# 告警限流：同一个 key 在 N 秒内只发送一次
ALERT_COOLDOWN_SECONDS = 300

# key -> last_sent_time
_alert_last_sent = {}

def should_send_alert(key: str) -> bool:
    now = time.time()
    last_time = _alert_last_sent.get(key, 0)

    if now - last_time < ALERT_COOLDOWN_SECONDS:
        logger.warning(
            f"告警限流跳过 | key={key} | "
            f"cooldown={ALERT_COOLDOWN_SECONDS}s"
        )
        return False

    _alert_last_sent[key] = now
    return True


def _send_message_sync(text: str):
    if not CONTROL_BOT_TOKEN or CONTROL_BOT_TOKEN == "你的控制机器人TOKEN":
        logger.warning("告警未发送：CONTROL_BOT_TOKEN 未配置")
        return False

    if not ALERT_CHAT_ID or ALERT_CHAT_ID == "你的私有频道ID或@频道username":
        logger.warning("告警未发送：ALERT_CHAT_ID 未配置")
        return False

    url = f"{BOT_API_BASE}/bot{CONTROL_BOT_TOKEN.strip()}/sendMessage"

    session = requests.Session()
    session.trust_env = False
    response = session.post(
        url,
        data={
            "chat_id": ALERT_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=20,
        proxies=get_bot_api_proxies(),
    )

    try:
        result = response.json()
    except Exception:
        logger.error(f"告警发送失败：返回非 JSON | {response.text}")
        return False

    if not result.get("ok"):
        error_code = result.get("error_code")
        description = result.get("description", "")

        if error_code == 429:
            retry_after = (
                result.get("parameters", {}) or {}
            ).get("retry_after", 60)

            logger.warning(
                f"告警发送触发 Telegram 限流 | "
                f"retry_after={retry_after}s | {description}"
            )
            return False

        logger.error(f"告警发送失败：{result}")
        return False

    return True


async def notify_text(text: str):
    try:
        return await asyncio.to_thread(_send_message_sync, text)
    except Exception as e:
        # 告警本身失败，不要再打印完整 traceback，避免日志爆炸
        logger.warning(f"告警发送失败，已忽略 | {type(e).__name__}: {e}")
        return False

async def notify_error(title: str, detail: str = "", task_id=None, target=None):
    """
    发送错误告警。

    限流规则：
    同一个 title + task_id + target 在 60 秒内只发送一次。
    """
    alert_key = f"{title}:{task_id}:{target}"

    if not should_send_alert(alert_key):
        return False

    lines = [
        "🚨 系统错误告警",
        "",
        f"类型：{title}",
    ]

    if task_id is not None:
        lines.append(f"任务ID：{task_id}")

    if target:
        lines.append(f"目标：{target}")

    if detail:
        lines.extend([
            "",
            "详情：",
            str(detail)[:3000],
        ])

    text = "\n".join(lines)

    return await notify_text(text)

async def notify_task_event(title: str, task_id=None, task_name="", detail=""):
    lines = [
        f"📌 {title}",
    ]

    if task_id is not None:
        lines.append(f"任务ID：{task_id}")

    if task_name:
        lines.append(f"任务名：{task_name}")

    if detail:
        lines.extend([
            "",
            str(detail)[:3000],
        ])

    return await notify_text("\n".join(lines))
