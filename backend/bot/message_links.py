import re
from typing import Any, Iterable


MESSAGE_ID_PATTERN = re.compile(r"/(\d+)(?:\?.*)?$")


def parse_message_url(value: str):
    """
    Extract a Telegram message_id from common message link formats.

    Supported examples:
    - https://t.me/channel_username/123
    - https://t.me/c/123456789/123
    - t.me/channel_username/123
    - @channel_username/123
    """
    text = (value or "").strip()

    if not text:
        return None

    if text.startswith("@") and "/" in text:
        text = text[1:]

    match = MESSAGE_ID_PATTERN.search(text)

    if not match:
        raise ValueError(f"invalid Telegram message link: {value}")

    message_id = int(match.group(1))

    if message_id < 1:
        raise ValueError(f"invalid Telegram message_id: {value}")

    return message_id


def build_message_url(channel: str, message_id: int):
    try:
        message_id = int(message_id)
    except (TypeError, ValueError):
        return None

    if message_id < 1:
        return None

    value = (channel or "").strip()

    if not value:
        return None

    if value.startswith("@"):
        return f"https://t.me/{value[1:]}/{message_id}"

    if value.startswith("-100") and value[4:].isdigit():
        return f"https://t.me/c/{value[4:]}/{message_id}"

    if value.startswith("https://t.me/") or value.startswith("http://t.me/"):
        path = value.split("t.me/", 1)[1].strip("/")
        parts = [part for part in path.split("/") if part]

        if len(parts) >= 2 and parts[0] == "c" and parts[1].isdigit():
            return f"https://t.me/c/{parts[1]}/{message_id}"

        if parts and parts[0] != "c":
            return f"https://t.me/{parts[0]}/{message_id}"

    if value.startswith("t.me/"):
        path = value.split("t.me/", 1)[1].strip("/")
        parts = [part for part in path.split("/") if part]

        if len(parts) >= 2 and parts[0] == "c" and parts[1].isdigit():
            return f"https://t.me/c/{parts[1]}/{message_id}"

        if parts and parts[0] != "c":
            return f"https://t.me/{parts[0]}/{message_id}"

    if re.fullmatch(r"[A-Za-z0-9_]{5,}", value):
        return f"https://t.me/{value}/{message_id}"

    return None


def extract_message_ids(bot_api_result: Any):
    ids = []

    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get("message_id"), int):
                ids.append(value["message_id"])

            for item in value.values():
                visit(item)

        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(bot_api_result)

    return ids


def build_message_urls(channel: str, message_ids: Iterable[int]):
    return [
        build_message_url(channel, message_id)
        for message_id in message_ids
        if build_message_url(channel, message_id)
    ]
