import asyncio
import re
import secrets
from urllib.parse import urlsplit, urlunsplit

import requests


class NtfyPublishError(RuntimeError):
    def __init__(self, status_code, response_text):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"ntfy HTTP {status_code}: {response_text}")


NTFY_TOPIC_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_ntfy_url(value: str):
    address = (value or "").strip().rstrip("/")
    parsed = urlsplit(address)
    path_parts = [part for part in parsed.path.split("/") if part]

    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not path_parts:
        raise ValueError("请输入完整 ntfy 地址，例如 https://ntfy.sh/your_topic")
    if parsed.query or parsed.fragment:
        raise ValueError("ntfy 地址不能包含查询参数或锚点")

    topic = path_parts[-1]
    server_path = "/" + "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
    server = urlunsplit((parsed.scheme, parsed.netloc, server_path, "", "")).rstrip("/")
    return server, topic


def normalize_ntfy_topic(value: str) -> str:
    topic = (value or "").strip()
    if topic.startswith(("http://", "https://")):
        _, topic = parse_ntfy_url(topic)
    topic = topic.strip().strip("/")
    if not NTFY_TOPIC_PATTERN.fullmatch(topic):
        raise ValueError("ntfy 主题只能包含字母、数字、下划线和短横线，最长 64 个字符")
    return topic


def validate_ntfy_server(server: str) -> str:
    base = (server or "").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("NTFY_SERVER 必须是完整的 http/https 地址")
    if parsed.query or parsed.fragment:
        raise ValueError("NTFY_SERVER 不能包含查询参数或锚点")
    return base


def generate_ntfy_topic(account_id: int) -> str:
    random_key = secrets.token_urlsafe(18).replace("-", "").replace("_", "")
    return f"telegram_{account_id}_{random_key}"


def generate_ntfy_url(server: str, account_id: int) -> str:
    base = validate_ntfy_server(server)
    return f"{base}/{generate_ntfy_topic(account_id)}"


class NtfyClient:
    def __init__(self, server: str, topic: str, timeout: float = 10.0):
        self.server = server.rstrip("/")
        self.topic = topic
        self.timeout = timeout

    @classmethod
    def from_url(cls, ntfy_url: str, timeout: float = 10.0):
        server, topic = parse_ntfy_url(ntfy_url)
        return cls(server, topic, timeout)

    @classmethod
    def from_topic(cls, server: str, topic: str, timeout: float = 10.0):
        return cls(
            validate_ntfy_server(server),
            normalize_ntfy_topic(topic),
            timeout,
        )

    def _publish_sync(self, title: str, message: str, priority: str):
        priority_value = {
            "default": 3,
            "high": 4,
        }.get(priority, 3)
        return requests.post(
            self.server,
            json={
                "topic": self.topic,
                "title": title,
                "message": message,
                "priority": priority_value,
            },
            timeout=self.timeout,
        )

    async def publish(self, title: str, message: str, priority: str) -> int:
        response = await asyncio.to_thread(
            self._publish_sync,
            title,
            message,
            priority,
        )
        if not response.ok:
            raise NtfyPublishError(response.status_code, response.text[:500])
        return response.status_code
