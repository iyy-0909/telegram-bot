import json
import re
from urllib.parse import urlparse


def normalize_channel_identifier(value):
    text = str(value or "").strip()

    if not text:
        return ""

    if text.startswith("-100") or re.fullmatch(r"-?\d+", text):
        return text

    text = text.replace("https://", "").replace("http://", "")

    if text.startswith("telegram.me/"):
        text = "t.me/" + text[len("telegram.me/"):]

    if text.startswith("t.me/"):
        path = urlparse("https://" + text).path.strip("/")
        parts = [part for part in path.split("/") if part]

        if len(parts) >= 2 and parts[0] == "c" and parts[1].isdigit():
            return f"-100{parts[1]}"

        if parts:
            return normalize_channel_identifier(parts[0])

    if text.startswith("@"):
        text = text[1:]

    if "/" in text:
        text = text.split("/", 1)[0]

    text = text.strip()

    if not text:
        return ""

    if re.fullmatch(r"[A-Za-z0-9_]{4,32}", text):
        return f"@{text}"

    return text


def normalize_channel_list(value):
    if isinstance(value, list):
        items = value
    else:
        text = str(value or "").strip()
        if not text:
            items = []
        else:
            try:
                parsed = json.loads(text)
                items = parsed if isinstance(parsed, list) else [text]
            except Exception:
                items = re.split(r"[\n,，]+", text)

    result = []
    seen = set()

    for item in items:
        channel = normalize_channel_identifier(item)
        key = channel.lower()

        if not channel or key in seen:
            continue

        seen.add(key)
        result.append(channel)

    return result


def normalize_channel_list_json(value):
    return json.dumps(normalize_channel_list(value), ensure_ascii=False)
