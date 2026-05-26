import os
from urllib.parse import urlparse

from bot.logger import logger


LOCAL_PROXY_HOSTS = {
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "::1",
}


PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def _proxy_to_text(proxy):
    if proxy is None:
        return ""

    if isinstance(proxy, (list, tuple)):
        return ":".join(str(item) for item in proxy if item is not None)

    return str(proxy).strip()


def _proxy_host(proxy):
    if isinstance(proxy, (list, tuple)):
        if len(proxy) >= 3:
            return str(proxy[1]).strip().lower()
        if len(proxy) >= 1:
            return str(proxy[0]).strip().lower()
        return ""

    text = _proxy_to_text(proxy)
    if not text:
        return ""

    parsed = urlparse(text if "://" in text else f"//{text}")
    return (parsed.hostname or "").strip().lower()


def _safe_proxy_text(proxy):
    text = _proxy_to_text(proxy)

    if not text:
        return ""

    parsed = urlparse(text if "://" in text else f"//{text}")

    if parsed.password:
        return text.replace(parsed.password, "***")

    return text


def is_production():
    return os.getenv("APP_ENV", "").strip().lower() == "production"


def is_local_proxy(proxy):
    return _proxy_host(proxy) in LOCAL_PROXY_HOSTS


def normalize_proxy_for_runtime(
    proxy: str | None,
    account_id=None,
    account_name=None,
    label="本地代理",
) -> str | None:
    if not proxy:
        return None

    if not is_production():
        return proxy

    if is_local_proxy(proxy):
        parts = [
            f"生产环境已忽略{label}",
        ]

        if account_id is not None:
            parts.append(f"account_id={account_id}")

        if account_name:
            parts.append(f"account_name={account_name}")

        parts.append(f"proxy={_safe_proxy_text(proxy)}")
        logger.warning(" | ".join(parts))
        return None

    return proxy


def normalize_bot_api_proxy_for_runtime(proxy: str | None) -> str | None:
    return normalize_proxy_for_runtime(proxy, label="本地 Bot API 代理")


def cleanup_local_proxy_env_vars():
    if not is_production():
        return

    for key in PROXY_ENV_KEYS:
        value = os.environ.get(key)

        if not value or not is_local_proxy(value):
            continue

        logger.warning(
            f"生产环境已清理本地代理环境变量 | key={key} | proxy={_safe_proxy_text(value)}"
        )
        os.environ.pop(key, None)
