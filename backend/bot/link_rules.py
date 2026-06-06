import json
import re
from urllib.parse import parse_qs, urlparse

from db.database import SessionLocal
from db.models import CloneSendEvent, ListenerSendEvent
from db.crud_templates import get_enabled_template_items_by_group, get_template
from bot.logger import logger


ACTION_TARGET_LINK = "target_link"
ACTION_DOWNGRADE = "downgrade"
ACTION_KEEP = "keep"
ACTION_DELETE = "delete"
ACTION_REPLACE = "replace"

DEFAULT_LINK_RULES = {
    "source_message_link": ACTION_TARGET_LINK,
    "missing_mapping": ACTION_DOWNGRADE,
    "target_channel_link": ACTION_KEEP,
    "external_channel_link": ACTION_DOWNGRADE,
    "username_link": ACTION_DOWNGRADE,
    "bot_link": ACTION_DOWNGRADE,
    "external_url": ACTION_DOWNGRADE,
    "invite_link": ACTION_DOWNGRADE,
}

REPLACEMENT_FIELDS = {
    f"{key}_replacement"
    for key in DEFAULT_LINK_RULES
}

VALID_ACTIONS = {
    ACTION_TARGET_LINK,
    ACTION_DOWNGRADE,
    ACTION_KEEP,
    ACTION_DELETE,
    ACTION_REPLACE,
}


def normalize_action(value, fallback=ACTION_DOWNGRADE):
    value = str(value or "").strip()
    return value if value in VALID_ACTIONS else fallback


def normalize_link_rules(value):
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except Exception:
            value = {}

    if not isinstance(value, dict):
        value = {}

    rules = dict(DEFAULT_LINK_RULES)

    for key in DEFAULT_LINK_RULES:
        if key in value:
            action = normalize_action(value.get(key), DEFAULT_LINK_RULES[key])
            rules[key] = action

    for key in REPLACEMENT_FIELDS:
        rules[key] = str(value.get(key) or "").strip()

    return rules


def get_link_rules(selected_group_id):
    if not selected_group_id:
        return None

    try:
        group = get_template(int(selected_group_id))

        if (
            not group
            or not group.enabled
            or group.type != "link"
            or group.parent_id is not None
        ):
            logger.warning(f"链接配置不可用，跳过 | group_id={selected_group_id}")
            return None

        items = [
            item
            for item in get_enabled_template_items_by_group("link", int(selected_group_id))
            if (item.content or "").strip()
        ]

        if not items:
            rules = normalize_link_rules(group.content)
            logger.info(
                f"链接配置读取完成 | group_id={selected_group_id} | "
                f"source_message_link={rules.get('source_message_link')} | "
                f"missing_mapping={rules.get('missing_mapping')}"
            )
            return rules

        rules = normalize_link_rules(items[0].content)
        logger.info(
            f"链接配置读取完成 | group_id={selected_group_id} | "
            f"item_id={items[0].id} | "
            f"source_message_link={rules.get('source_message_link')} | "
            f"missing_mapping={rules.get('missing_mapping')}"
        )
        return rules
    except Exception as e:
        logger.warning(f"读取链接配置失败，跳过 | group_id={selected_group_id} | {e}")
        return None


def strip_scheme(value):
    text = str(value or "").strip()
    text = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^telegram\.me/", "t.me/", text, flags=re.IGNORECASE)
    return text.strip("/")


def normalize_channel_key(value):
    text = strip_scheme(value).strip()
    if not text:
        return ""

    if text.startswith("@"):
        text = text[1:]

    if text.startswith("-100") and text[4:].isdigit():
        return f"c/{text[4:]}"

    if text.lower().startswith("t.me/"):
        parts = [part for part in text[5:].split("/") if part]
        if len(parts) >= 2 and parts[0] == "c" and parts[1].isdigit():
            return f"c/{parts[1]}"
        return (parts[0] if parts else "").lower()

    if "/" in text:
        text = text.split("/", 1)[0]

    return text.lower()


def channel_keys(value):
    key = normalize_channel_key(value)
    if not key:
        return set()
    return {key}


def parse_tg_url(url):
    text = str(url or "").strip()
    if not text:
        return {"kind": "external_url"}

    lower = text.lower()

    if lower.startswith("tg://resolve"):
        parsed = urlparse(text)
        domain = (parse_qs(parsed.query).get("domain") or [""])[0]
        return classify_tme_path(domain)

    if lower.startswith("tg://user"):
        return {"kind": "username_link"}

    if lower.startswith("mailto:") or lower.startswith("tel:"):
        return {"kind": "username_link"}

    stripped = strip_scheme(text)
    if stripped.lower().startswith("t.me/"):
        return classify_tme_path(stripped[5:])

    return {"kind": "external_url"}


def classify_tme_path(path):
    parts = [part for part in str(path or "").strip("/").split("/") if part]

    if not parts:
        return {"kind": "external_url"}

    first = parts[0]
    first_lower = first.lower()

    if first.startswith("+") or first_lower == "joinchat":
        return {"kind": "invite_link"}

    if first_lower == "c" and len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
        return {
            "kind": "message_link",
            "channel_key": f"c/{parts[1]}",
            "message_id": int(parts[2]),
        }

    if len(parts) >= 2 and parts[1].isdigit():
        return {
            "kind": "message_link",
            "channel_key": first_lower,
            "message_id": int(parts[1]),
        }

    if first_lower.endswith("bot"):
        return {"kind": "bot_link", "channel_key": first_lower}

    return {"kind": "username_link", "channel_key": first_lower}


def get_rule_key_for_url(url, task, target):
    parsed = parse_tg_url(url)
    kind = parsed.get("kind")

    if kind == "message_link":
        source_keys = channel_keys(getattr(task, "source_channel", ""))
        target_keys = channel_keys(target)
        link_key = parsed.get("channel_key") or ""

        if link_key in source_keys:
            return "source_message_link", parsed

        if link_key in target_keys:
            return "target_channel_link", parsed

        return "external_channel_link", parsed

    return kind or "external_url", parsed


def find_target_message_url(task_id, source_message_id, target):
    if not task_id or not source_message_id or not target:
        logger.info(
            f"目标链接映射查询跳过 | task_id={task_id} | "
            f"source_message_id={source_message_id} | target={target}"
        )
        return ""

    db = SessionLocal()
    try:
        clone_event = (
            db.query(CloneSendEvent)
            .filter(
                CloneSendEvent.task_id == int(task_id),
                CloneSendEvent.source_message_id == int(source_message_id),
                CloneSendEvent.target == target,
                CloneSendEvent.status == "success",
                CloneSendEvent.target_message_url != "",
            )
            .order_by(CloneSendEvent.id.desc())
            .first()
        )
        if clone_event and clone_event.target_message_url:
            logger.info(
                f"目标链接映射命中克隆记录 | task_id={task_id} | "
                f"source_message_id={source_message_id} | target={target} | "
                f"url={clone_event.target_message_url}"
            )
            return clone_event.target_message_url

        listener_event = (
            db.query(ListenerSendEvent)
            .filter(
                ListenerSendEvent.task_id == int(task_id),
                ListenerSendEvent.source_message_id == int(source_message_id),
                ListenerSendEvent.target == target,
                ListenerSendEvent.status == "success",
                ListenerSendEvent.target_message_url != "",
            )
            .order_by(ListenerSendEvent.id.desc())
            .first()
        )
        if listener_event and listener_event.target_message_url:
            logger.info(
                f"目标链接映射命中监听记录 | task_id={task_id} | "
                f"source_message_id={source_message_id} | target={target} | "
                f"url={listener_event.target_message_url}"
            )
            return listener_event.target_message_url

        logger.info(
            f"目标链接映射未命中 | task_id={task_id} | "
            f"source_message_id={source_message_id} | target={target}"
        )
        return ""
    finally:
        db.close()
