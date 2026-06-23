import re


TELEGRAM_NAME_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([^/?#\s]+)",
    re.IGNORECASE,
)


def build_channel_search_terms(value):
    text = str(value or "").strip()

    if not text:
        return []

    lowered = text.lower()
    terms = {text, lowered}
    name = extract_telegram_name(text)

    if name:
        terms.update(
            {
                name,
                name.lower(),
                f"@{name}",
                f"@{name.lower()}",
                f"t.me/{name}",
                f"t.me/{name.lower()}",
                f"https://t.me/{name}",
                f"https://t.me/{name.lower()}",
            }
        )
    elif text.startswith("@") and len(text) > 1:
        name = text[1:].strip()
        terms.update(
            {
                name,
                name.lower(),
                f"t.me/{name}",
                f"https://t.me/{name}",
            }
        )
    elif re.fullmatch(r"[A-Za-z0-9_]{4,}", text):
        terms.update(
            {
                f"@{text}",
                f"@{lowered}",
                f"t.me/{text}",
                f"https://t.me/{text}",
            }
        )

    return [term for term in terms if term]


def extract_telegram_name(value):
    match = TELEGRAM_NAME_RE.search(str(value or "").strip())

    if not match:
        return ""

    name = match.group(1).strip().lstrip("@")

    if not name or name.startswith("+") or name.lower() == "c":
        return ""

    return name
