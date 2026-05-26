import os
from urllib.parse import urlparse

from bot.logger import logger


LOCAL_PROXY_HOSTS = {
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "::1",
}


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


def normalize_proxy_for_runtime(proxy: str | None, account_id=None, account_name=None) -> str | None:
    if not proxy:
        return None

    app_env = os.getenv("APP_ENV", "").strip().lower()

    if app_env != "production":
        return proxy

    host = _proxy_host(proxy)

    if host in LOCAL_PROXY_HOSTS:
        parts = [
            "生产环境已忽略本地代理",
        ]

        if account_id is not None:
            parts.append(f"account_id={account_id}")

        if account_name:
            parts.append(f"account_name={account_name}")

        parts.append(f"proxy={_safe_proxy_text(proxy)}")
        logger.warning(" | ".join(parts))
        return None

    return proxy
