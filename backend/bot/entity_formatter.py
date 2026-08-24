from dataclasses import dataclass
from difflib import SequenceMatcher
from html import escape, unescape
import re

from bot.logger import logger
from bot.link_rules import (
    ACTION_DELETE,
    ACTION_DOWNGRADE,
    ACTION_KEEP,
    ACTION_REPLACE,
    ACTION_TARGET_LINK,
    find_target_message_url,
    get_link_rules,
    get_rule_key_for_url,
)
from db.crud_templates import get_contact_rule_config


FORMAT_LEVEL_ENTITIES = "entities"
FORMAT_LEVEL_HTML = "html"
FORMAT_LEVEL_PLAIN = "plain"


@dataclass
class TextEdit:
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    old_text: str
    new_text: str
    op_type: str


TELETHON_TO_BOT_TYPES = {
    "MessageEntityBold": "bold",
    "MessageEntityItalic": "italic",
    "MessageEntityUnderline": "underline",
    "MessageEntityStrike": "strikethrough",
    "MessageEntitySpoiler": "spoiler",
    "MessageEntityCode": "code",
    "MessageEntityPre": "pre",
    # Link entities are intentionally downgraded to normal text.
    # MessageEntityUrl keeps the raw URL clickable; MessageEntityTextUrl keeps
    # hidden links such as "我是链接" clickable. Both can preserve spam links.
    # Standalone raw URL lines are removed in content_processor before sending.
    "MessageEntityMention": "mention",
    "MessageEntityHashtag": "hashtag",
    "MessageEntityCashtag": "cashtag",
    "MessageEntityBotCommand": "bot_command",
    "MessageEntityEmail": "email",
    "MessageEntityPhone": "phone_number",
    "MessageEntityCustomEmoji": "custom_emoji",
    "MessageEntityBlockquote": "blockquote",
    "MessageEntityExpandableBlockquote": "expandable_blockquote",
}

BOT_ENTITY_TYPES = {
    *TELETHON_TO_BOT_TYPES.values(),
    "text_link",
    "url",
}


HTML_TAGS = {
    "bold": ("b", "b"),
    "italic": ("i", "i"),
    "underline": ("u", "u"),
    "strikethrough": ("s", "s"),
    "spoiler": ("tg-spoiler", "tg-spoiler"),
    "code": ("code", "code"),
    "pre": ("pre", "pre"),
    "text_link": ("a", "a"),
    "blockquote": ("blockquote", "blockquote"),
    "expandable_blockquote": ("blockquote expandable", "blockquote"),
}


def get_message_text(message):
    return getattr(message, "message", None) or ""


def get_message_entities(message):
    return getattr(message, "entities", None) or []


def pick_source_message(source):
    if isinstance(source, (list, tuple)):
        for message in source:
            if get_message_text(message):
                return message

        return source[0] if source else None

    return source


def utf16_len(text: str) -> int:
    return len((text or "").encode("utf-16-le")) // 2


def utf16_offset_to_py_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 0

    current = 0

    for index, char in enumerate(text or ""):
        char_units = utf16_len(char)

        if current + char_units > offset:
            return index

        current += char_units

        if current == offset:
            return index + 1

    return len(text or "")


def utf16_offset_to_index(text: str, offset: int) -> int:
    return utf16_offset_to_py_index(text, offset)


def py_index_to_utf16_offset(text: str, index: int) -> int:
    index = max(min(int(index or 0), len(text or "")), 0)
    return utf16_len((text or "")[:index])


def entity_to_py_range(text: str, entity):
    offset = int(getattr(entity, "offset", 0) or 0)
    length = int(getattr(entity, "length", 0) or 0)
    start = utf16_offset_to_py_index(text, offset)
    end = utf16_offset_to_py_index(text, offset + length)
    return start, end


def py_range_to_bot_entity_range(text: str, start: int, end: int):
    start = max(min(start, len(text or "")), 0)
    end = max(min(end, len(text or "")), start)
    offset = py_index_to_utf16_offset(text, start)
    length = py_index_to_utf16_offset(text, end) - offset
    return offset, length


def build_text_edits(old_text: str, new_text: str):
    edits = []
    matcher = SequenceMatcher(None, old_text or "", new_text or "", autojunk=False)

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue

        edits.append(
            TextEdit(
                old_start=old_start,
                old_end=old_end,
                new_start=new_start,
                new_end=new_end,
                old_text=(old_text or "")[old_start:old_end],
                new_text=(new_text or "")[new_start:new_end],
                op_type=tag,
            )
        )

    return edits


def map_range_by_diff(old_text: str, new_text: str, start: int, end: int):
    matcher = SequenceMatcher(None, old_text or "", new_text or "", autojunk=False)
    segments = []
    touched_replace = False

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if old_end <= start or old_start >= end:
            continue

        overlap_start = max(start, old_start)
        overlap_end = min(end, old_end)

        if overlap_start >= overlap_end:
            continue

        if tag == "equal":
            mapped_start = new_start + (overlap_start - old_start)
            mapped_end = new_start + (overlap_end - old_start)
            segments.append((mapped_start, mapped_end))
        elif tag == "replace":
            touched_replace = True

    if touched_replace:
        return None

    if not segments:
        return None

    segments.sort()
    mapped_start = segments[0][0]
    mapped_end = segments[-1][1]

    if mapped_start >= mapped_end:
        return None

    # After deletion, separated old segments may become adjacent in new text.
    cursor = mapped_start
    for seg_start, seg_end in segments:
        if seg_start != cursor:
            return None
        cursor = seg_end

    return mapped_start, mapped_end


def get_entity_type(entity):
    return TELETHON_TO_BOT_TYPES.get(type(entity).__name__)


def is_link_entity(entity):
    return type(entity).__name__ in {"MessageEntityTextUrl", "MessageEntityUrl"}


def link_entity_url(original_text: str, entity):
    if type(entity).__name__ == "MessageEntityTextUrl":
        return str(getattr(entity, "url", "") or "")

    if type(entity).__name__ == "MessageEntityUrl":
        start, end = entity_to_py_range(original_text, entity)
        return (original_text or "")[start:end]

    return ""


def extract_source_link_items(source):
    """Extract visible labels and hidden URLs from the source Telegram message."""
    message = pick_source_message(source)
    if not message:
        return []

    original_text = get_message_text(message)
    items = []
    seen = set()
    for entity in get_message_entities(message):
        if not is_link_entity(entity):
            continue

        start, end = entity_to_py_range(original_text, entity)
        label = (original_text or "")[start:end]
        url = link_entity_url(original_text, entity)
        if not label or not url:
            continue

        line_start = (original_text or "").rfind("\n", 0, start) + 1
        next_line_break = (original_text or "").find("\n", end)
        line_end = next_line_break if next_line_break >= 0 else len(original_text or "")
        line_prefix = (original_text or "")[line_start:start]
        line_text = (original_text or "")[line_start:line_end]

        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "label": label,
            "url": url,
            "line_prefix": line_prefix,
            "line_text": line_text,
        })
    return items


def short_text(value, limit=80):
    text = str(value or "").replace("\n", "\\n")
    return text if len(text) <= limit else f"{text[:limit]}..."


def entity_extra_fields(entity, bot_type: str):
    extra = {}

    if bot_type == "text_link":
        url = getattr(entity, "url", None)
        if not url:
            return None
        extra["url"] = str(url)

    if bot_type == "pre":
        language = getattr(entity, "language", None)
        if language:
            extra["language"] = str(language)

    if bot_type == "custom_emoji":
        custom_emoji_id = (
            getattr(entity, "custom_emoji_id", None)
            or getattr(entity, "document_id", None)
        )
        if not custom_emoji_id:
            return None
        extra["custom_emoji_id"] = str(custom_emoji_id)

    return extra


def validate_bot_entity(text: str, entity: dict) -> bool:
    try:
        offset = int(entity.get("offset", -1))
        length = int(entity.get("length", 0))
    except (TypeError, ValueError):
        return False

    if offset < 0 or length <= 0:
        return False

    if offset + length > utf16_len(text):
        return False

    start = utf16_offset_to_py_index(text, offset)
    end = utf16_offset_to_py_index(text, offset + length)

    if start >= end or not text[start:end]:
        return False

    bot_type = entity.get("type")
    if bot_type not in BOT_ENTITY_TYPES:
        return False

    if bot_type == "text_link" and not entity.get("url"):
        return False

    if bot_type == "custom_emoji" and not entity.get("custom_emoji_id"):
        return False

    return True


def dedupe_entities(entities):
    seen = set()
    result = []

    for entity in entities:
        key = tuple(sorted(entity.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(entity)

    return result


def map_entities_to_bot(original_text: str, processed_text: str, entities):
    kept = []
    dropped = 0

    for entity in entities or []:
        try:
            bot_type = get_entity_type(entity)
            if not bot_type:
                dropped += 1
                continue

            original_start, original_end = entity_to_py_range(original_text, entity)
            if original_start >= original_end:
                dropped += 1
                continue

            mapped = map_range_by_diff(
                original_text,
                processed_text,
                original_start,
                original_end,
            )

            if not mapped:
                dropped += 1
                continue

            new_start, new_end = mapped
            offset, length = py_range_to_bot_entity_range(
                processed_text,
                new_start,
                new_end,
            )
            extra = entity_extra_fields(entity, bot_type)

            if extra is None:
                dropped += 1
                continue

            bot_entity = {
                "type": bot_type,
                "offset": offset,
                "length": length,
                **extra,
            }

            if validate_bot_entity(processed_text, bot_entity):
                kept.append(bot_entity)
            else:
                dropped += 1

        except Exception as e:
            dropped += 1
            logger.debug(f"entity mapping dropped one entity | {e}")

    return dedupe_entities(
        sorted(
            kept,
            key=lambda item: (item["offset"], -item["length"], item["type"]),
        )
    ), dropped


def remove_ranges(text: str, ranges):
    if not ranges:
        return text or "", []

    merged = []
    for start, end in sorted(ranges):
        start = max(0, min(start, len(text or "")))
        end = max(start, min(end, len(text or "")))
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    parts = []
    cursor = 0
    for start, end in merged:
        parts.append((text or "")[cursor:start])
        cursor = end
    parts.append((text or "")[cursor:])
    return "".join(parts), merged


def map_index_after_deletions(index: int, delete_ranges):
    shift = 0
    for start, end in delete_ranges or []:
        if index >= end:
            shift += end - start
        elif index > start:
            return None
    return index - shift


def map_range_after_deletions(start: int, end: int, delete_ranges):
    new_start = map_index_after_deletions(start, delete_ranges)
    new_end = map_index_after_deletions(end, delete_ranges)

    if new_start is None or new_end is None or new_start >= new_end:
        return None

    return new_start, new_end


def resolve_link_action(task, target, rules, url):
    rule_key, parsed = get_rule_key_for_url(url, task, target)
    action = rules.get(rule_key, ACTION_DOWNGRADE)
    resolved_url = ""

    if action == ACTION_TARGET_LINK:
        if parsed.get("kind") == "message_link":
            resolved_url = find_target_message_url(
                getattr(task, "id", None),
                parsed.get("message_id"),
                target,
            )

        if resolved_url:
            return ACTION_TARGET_LINK, resolved_url, rule_key

        missing_action = rules.get("missing_mapping", ACTION_DOWNGRADE)
        if missing_action == ACTION_REPLACE:
            replacement_url = str(
                rules.get("missing_mapping_replacement") or ""
            ).strip()
            if replacement_url:
                return ACTION_REPLACE, replacement_url, "missing_mapping"
            return ACTION_DOWNGRADE, "", "missing_mapping"

        return missing_action, "", "missing_mapping"

    if action == ACTION_REPLACE:
        replacement_url = str(rules.get(f"{rule_key}_replacement") or "").strip()
        if replacement_url:
            return ACTION_REPLACE, replacement_url, rule_key
        return ACTION_DOWNGRADE, "", rule_key

    return action, "", rule_key


def html_to_plain_text(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value or ""))


def _rewrite_matching_anchors(
    html_text,
    label,
    action,
    url="",
    *,
    source_url="",
    match_by_url=False,
):
    matched = False
    anchor_pattern = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)

    def replace_anchor(match):
        nonlocal matched
        body = match.group(1)
        visible = html_to_plain_text(body)
        existing_url = _anchor_href(match.group(0)) if match_by_url else ""
        expected_urls = {
            str(candidate or "").strip().casefold()
            for candidate in (url, source_url)
            if str(candidate or "").strip()
        }
        url_matches = (
            bool(existing_url)
            and existing_url.casefold() in expected_urls
        )
        if match_by_url:
            is_match = url_matches
        else:
            is_match = visible == label
        if not is_match:
            return match.group(0)

        matched = True
        if action == ACTION_DELETE:
            return ""
        if action == ACTION_DOWNGRADE:
            return body
        safe_url = escape(url, quote=True)
        return f'<a href="{safe_url}">{body}</a>'

    return anchor_pattern.sub(replace_anchor, html_text or ""), matched


def _replace_first_visible_text(html_text, label, replacement):
    if not label:
        return html_text or "", False

    parts = re.split(r"(<[^>]+>)", html_text or "")
    anchor_depth = 0
    escaped_label = escape(label)

    for index, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("<"):
            if re.match(r"<a\b", part, re.IGNORECASE):
                anchor_depth += 1
            elif re.match(r"</a\b", part, re.IGNORECASE):
                anchor_depth = max(anchor_depth - 1, 0)
            continue
        if anchor_depth:
            continue

        for needle in (escaped_label, label):
            position = part.find(needle)
            if position < 0:
                continue
            parts[index] = (
                part[:position]
                + replacement
                + part[position + len(needle):]
            )
            return "".join(parts), True

    return html_text or "", False


def _downgrade_prefix_candidates(line_prefix):
    prefix = str(line_prefix or "")
    clean_prefix = prefix.rstrip()
    if not clean_prefix:
        return [], ""

    without_bullet = re.sub(r"^[\s•·▪◦*\-]+", "", clean_prefix)
    candidates = []
    for value in (clean_prefix, without_bullet):
        for candidate in (
            value,
            value.replace(":", "："),
            value.replace("：", ":"),
        ):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

    if clean_prefix.endswith((":", "：")):
        separator = ""
    elif prefix[-1:].isspace():
        separator = " "
    else:
        separator = " "
    return candidates, separator


def _restore_missing_downgraded_label(html_text, item):
    """Keep a downgraded link's visible label even when AI omitted it."""
    label = str(item.get("label") or "")
    if not label:
        return html_text or "", False

    if label in html_to_plain_text(html_text):
        return html_text or "", True

    candidates, separator = _downgrade_prefix_candidates(
        item.get("line_prefix")
    )
    for prefix in candidates:
        restored, matched = _replace_first_visible_text(
            html_text,
            prefix,
            f"{escape(prefix)}{separator}{escape(label)}",
        )
        if matched:
            return restored, True

    return html_text or "", False


CONTACT_LINK_KEYWORDS = (
    "联系",
    "点击",
    "咨询",
    "客服",
    "预约",
    "预订",
    "订台",
    "报名",
    "私聊",
    "添加",
)


def is_protected_contact_link(item):
    context = str(item.get("line_text") or item.get("line_prefix") or "")
    normalized = re.sub(r"\s+", "", context).casefold()
    return any(keyword in normalized for keyword in CONTACT_LINK_KEYWORDS)


def should_suppress_source_link_restore(item, task, contact_rule_config=None):
    """Do not re-add a source link removed by the task's contact cleanup."""
    if not task or not bool(getattr(task, "remove_contact_lines", True)):
        return False

    from bot.content_processor import should_remove_line

    contact_rule_config = contact_rule_config or get_contact_rule_config(
        getattr(task, "selected_contact_template_group_id", None)
    )
    line_text = str(item.get("line_text") or "")

    if should_remove_line(line_text, contact_rule_config):
        return True

    # Telegram hidden links do not expose their URL in message.message. Treat
    # their entity URL the same as a visible URL when the selected contact rule
    # is configured to remove links.
    return bool(contact_rule_config.get("remove_links", True) and item.get("url"))


def _anchor_href(anchor_html):
    match = re.search(
        r"\bhref\s*=\s*(['\"])(?P<url>.*?)\1",
        anchor_html or "",
        re.IGNORECASE | re.DOTALL,
    )
    return unescape(match.group("url")).strip() if match else ""


def _has_equivalent_contact_anchor(html_text, item):
    source_url = str(item.get("url") or "").strip().casefold()
    source_label = str(item.get("label") or "")
    anchor_pattern = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
    for match in anchor_pattern.finditer(html_text or ""):
        existing_url = _anchor_href(match.group(0)).casefold()
        visible_label = html_to_plain_text(match.group(1))
        if (source_url and existing_url == source_url) or visible_label == source_label:
            return True
    return False


def _wrap_value_after_contact_prefix(html_text, prefixes, url):
    parts = re.split(r"(<[^>]+>)", html_text or "")
    anchor_depth = 0
    safe_url = escape(url, quote=True)
    for index, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("<"):
            if re.match(r"<a\b", part, re.IGNORECASE):
                anchor_depth += 1
            elif re.match(r"</a\b", part, re.IGNORECASE):
                anchor_depth = max(anchor_depth - 1, 0)
            continue
        if anchor_depth:
            continue

        for prefix in prefixes:
            for needle in (escape(prefix), prefix):
                prefix_at = part.find(needle)
                if prefix_at < 0:
                    continue
                value_start = prefix_at + len(needle)
                line_end = part.find("\n", value_start)
                if line_end < 0:
                    line_end = len(part)
                raw_value = part[value_start:line_end]
                leading_length = len(raw_value) - len(raw_value.lstrip())
                trailing_length = len(raw_value) - len(raw_value.rstrip())
                value_end = len(raw_value) - trailing_length if trailing_length else len(raw_value)
                visible_value = raw_value[leading_length:value_end]
                if not visible_value:
                    continue

                leading = raw_value[:leading_length]
                trailing = raw_value[value_end:]
                wrapped_value = (
                    f'{leading}<a href="{safe_url}">{visible_value}</a>{trailing}'
                )
                parts[index] = (
                    part[:value_start]
                    + wrapped_value
                    + part[line_end:]
                )
                return "".join(parts), True

    return html_text or "", False


def _restore_missing_contact_anchor(html_text, item, anchor_html):
    label = str(item.get("label") or "")
    restored, wrapped = _replace_first_visible_text(
        html_text,
        label,
        anchor_html,
    )
    if wrapped:
        return restored, True

    candidates, separator = _downgrade_prefix_candidates(
        item.get("line_prefix")
    )
    restored, wrapped = _wrap_value_after_contact_prefix(
        html_text,
        candidates,
        _anchor_href(anchor_html),
    )
    if wrapped:
        return restored, True

    for prefix in candidates:
        restored, matched = _replace_first_visible_text(
            html_text,
            prefix,
            f"{escape(prefix)}{separator}{anchor_html}",
        )
        if matched:
            return restored, True

    return html_text or "", False


def _contact_anchor_fallback(item, anchor_html):
    candidates, separator = _downgrade_prefix_candidates(
        item.get("line_prefix")
    )
    if not candidates:
        return anchor_html
    return f"{escape(candidates[0])}{separator}{anchor_html}"


def _is_short_contact_prefix(value):
    plain = html_to_plain_text(value).strip()
    if not plain or len(plain) > 24:
        return False
    if not any(keyword in plain for keyword in CONTACT_LINK_KEYWORDS):
        return False
    sentence_body = plain.rstrip("：:➡️→-— ")
    return not bool(re.search(r"[，。！？；,.!?;]", sentence_body))


def _finish_text_before_contact(value):
    text = str(value or "").rstrip()
    text = re.sub(r"[，,、；;：:]$", "", text).rstrip()
    plain = html_to_plain_text(text).rstrip()
    if plain and not re.search(r"[。.!！?？]$", plain):
        text = f"{text}。"
    return text


def _clean_text_after_contact(value):
    text = str(value or "").strip()
    return re.sub(r"^[，,、；;：:\s]+", "", text)


def _normalize_one_contact_anchor_line(html_text, item):
    source_url = str(item.get("url") or "").strip().casefold()
    source_label = str(item.get("label") or "")
    anchor_pattern = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
    selected = None
    for match in anchor_pattern.finditer(html_text or ""):
        existing_url = _anchor_href(match.group(0)).casefold()
        visible_label = html_to_plain_text(match.group(1))
        if (source_url and existing_url == source_url) or visible_label == source_label:
            selected = match
            break
    if not selected:
        return html_text or ""

    line_start = (html_text or "").rfind("\n", 0, selected.start()) + 1
    next_line_break = (html_text or "").find("\n", selected.end())
    line_end = next_line_break if next_line_break >= 0 else len(html_text or "")
    before_anchor = (html_text or "")[line_start:selected.start()]
    after_anchor = (html_text or "")[selected.end():line_end]
    if not before_anchor.strip() and not after_anchor.strip():
        return html_text or ""

    anchor_html = selected.group(0)
    lines = []
    if before_anchor.strip() and _is_short_contact_prefix(before_anchor):
        lines.append(f"{before_anchor.rstrip()}{anchor_html}")
    else:
        finished_before = _finish_text_before_contact(before_anchor)
        if finished_before:
            lines.append(finished_before)
        lines.append(anchor_html)

    cleaned_after = _clean_text_after_contact(after_anchor)
    if cleaned_after:
        if re.fullmatch(r"[。.!！?？]+", cleaned_after):
            lines[-1] = f"{lines[-1]}{cleaned_after}"
        else:
            lines.append(cleaned_after)

    replacement = "\n".join(lines)
    return (
        (html_text or "")[:line_start]
        + replacement
        + (html_text or "")[line_end:]
    )


def restore_source_links_as_html(source, processed_html: str, task=None, target=None):
    """Restore source hidden links after AI changed text positions.

    Link-template actions are still honored. Kept links are reattached by their
    exact visible label; links omitted by AI are appended in a compact list.
    """
    link_items = extract_source_link_items(source)
    if not link_items:
        return processed_html or ""

    selected_group_id = getattr(task, "selected_link_template_group_id", None) if task else None
    rules = get_link_rules(selected_group_id)
    remove_source_contacts = bool(
        task and getattr(task, "remove_contact_lines", True)
    )
    contact_rule_config = (
        get_contact_rule_config(
            getattr(task, "selected_contact_template_group_id", None)
        )
        if remove_source_contacts
        else None
    )
    restored_html = processed_html or ""
    missing_kept_links = []
    missing_downgraded_labels = []
    restored_count = 0
    downgraded_count = 0
    restored_downgraded_count = 0
    deleted_count = 0
    suppressed_contact_count = 0

    for item in link_items:
        label = item["label"]
        source_url = item["url"]
        if should_suppress_source_link_restore(
            item,
            task,
            contact_rule_config,
        ):
            suppressed_contact_count += 1
            logger.info(
                "旧联系方式链接已由内容处理删除，跳过源链接恢复 | task_id=%s target=%s url=%s",
                getattr(task, "id", None) if task else None,
                target,
                short_text(source_url, 140),
            )
            continue

        protected_contact = is_protected_contact_link(item)
        if rules:
            action, resolved_url, _rule_key = resolve_link_action(
                task,
                target,
                rules,
                source_url,
            )
        else:
            action, resolved_url = ACTION_KEEP, ""

        if protected_contact and action in {ACTION_DOWNGRADE, ACTION_DELETE}:
            logger.info(
                "联系类点击链接跳过删除/降级 | task_id=%s target=%s rule=%s original_action=%s url=%s",
                getattr(task, "id", None) if task else None,
                target,
                _rule_key if rules else "default_keep",
                action,
                short_text(source_url, 140),
            )
            action = ACTION_KEEP

        if (
            protected_contact
            and action == ACTION_KEEP
            and _has_equivalent_contact_anchor(restored_html, item)
        ):
            restored_count += 1
            continue

        final_url = resolved_url or source_url
        restored_html, anchor_matched = _rewrite_matching_anchors(
            restored_html,
            label,
            action,
            final_url,
            source_url=source_url,
            match_by_url=protected_contact,
        )

        if action == ACTION_DELETE:
            if not anchor_matched:
                restored_html, _removed = _replace_first_visible_text(
                    restored_html,
                    label,
                    "",
                )
            deleted_count += 1
            continue

        if action == ACTION_DOWNGRADE or action not in {
            ACTION_KEEP,
            ACTION_TARGET_LINK,
            ACTION_REPLACE,
        }:
            restored_html, label_preserved = _restore_missing_downgraded_label(
                restored_html,
                item,
            )
            if label_preserved:
                restored_downgraded_count += 1
            else:
                missing_downgraded_labels.append(escape(label))
            downgraded_count += 1
            continue

        if anchor_matched:
            restored_count += 1
            continue

        anchor_html = f'<a href="{escape(final_url, quote=True)}">{escape(label)}</a>'
        if protected_contact:
            restored_html, wrapped = _restore_missing_contact_anchor(
                restored_html,
                item,
                anchor_html,
            )
        else:
            restored_html, wrapped = _replace_first_visible_text(
                restored_html,
                label,
                anchor_html,
            )
        if wrapped:
            restored_count += 1
        else:
            missing_kept_links.append(
                _contact_anchor_fallback(item, anchor_html)
                if protected_contact
                else anchor_html
            )

    if missing_downgraded_labels:
        label_block = "\n".join(missing_downgraded_labels)
        restored_html = f"{restored_html.rstrip()}\n\n{label_block}"
        restored_downgraded_count += len(missing_downgraded_labels)

    if missing_kept_links:
        if len(missing_kept_links) == 1:
            link_block = missing_kept_links[0]
        else:
            link_block = "<b>🔗 相关链接</b>\n" + "\n".join(
                f"• {anchor}" for anchor in missing_kept_links
            )
        restored_html = f"{restored_html.rstrip()}\n\n{link_block}"
        restored_count += len(missing_kept_links)

    for item in link_items:
        if is_protected_contact_link(item):
            restored_html = _normalize_one_contact_anchor_line(
                restored_html,
                item,
            )

    restored_html = re.sub(r"[ \t]+\n", "\n", restored_html)
    restored_html = re.sub(r"\n{3,}", "\n\n", restored_html).strip()
    logger.info(
        "AI/HTML 原链接恢复 | task_id=%s target=%s total=%s restored=%s downgraded=%s downgraded_preserved=%s deleted=%s suppressed_contact=%s appended=%s",
        getattr(task, "id", None) if task else None,
        target,
        len(link_items),
        restored_count,
        downgraded_count,
        restored_downgraded_count,
        deleted_count,
        suppressed_contact_count,
        len(missing_kept_links),
    )
    return restored_html


def apply_link_rules_to_text(original_text: str, processed_text: str, entities, task=None, target=None):
    selected_group_id = getattr(task, "selected_link_template_group_id", None) if task else None
    rules = get_link_rules(selected_group_id)

    if not rules:
        return processed_text or "", None

    task_id = getattr(task, "id", None) if task else None
    link_entity_count = sum(1 for entity in entities or [] if is_link_entity(entity))
    logger.info(
        f"链接规则开始处理 | task_id={task_id} | target={target} | "
        f"group_id={selected_group_id} | original_len={len(original_text or '')} | "
        f"processed_len={len(processed_text or '')} | entities={len(entities or [])} | "
        f"link_entities={link_entity_count}"
    )

    if not link_entity_count:
        logger.info(
            f"链接规则未发现链接实体 | task_id={task_id} | target={target} | "
            f"text={short_text(original_text)}"
        )

    link_decisions = []
    delete_ranges = []

    for entity in entities or []:
        if not is_link_entity(entity):
            continue

        original_start, original_end = entity_to_py_range(original_text, entity)
        mapped = map_range_by_diff(
            original_text,
            processed_text,
            original_start,
            original_end,
        )
        if not mapped:
            logger.info(
                f"链接实体位置映射失败 | task_id={task_id} | target={target} | "
                f"entity_type={type(entity).__name__} | "
                f"range={original_start}-{original_end} | "
                f"text={short_text((original_text or '')[original_start:original_end])}"
            )
            continue

        url = link_entity_url(original_text, entity)
        action, resolved_url, rule_key = resolve_link_action(task, target, rules, url)
        logger.info(
            f"链接规则决策 | task_id={task_id} | target={target} | "
            f"entity_type={type(entity).__name__} | rule={rule_key} | "
            f"action={action} | text={short_text((original_text or '')[original_start:original_end])} | "
            f"url={short_text(url, 140)} | resolved_url={short_text(resolved_url, 140)}"
        )

        if action == ACTION_DELETE:
            delete_ranges.append(mapped)
            continue

        if action in {ACTION_KEEP, ACTION_TARGET_LINK, ACTION_REPLACE}:
            link_decisions.append(
                {
                    "range": mapped,
                    "url": resolved_url or url,
                    "rule_key": rule_key,
                }
            )

    final_text, merged_delete_ranges = remove_ranges(processed_text, delete_ranges)
    link_entities = []

    for decision in link_decisions:
        mapped = map_range_after_deletions(
            decision["range"][0],
            decision["range"][1],
            merged_delete_ranges,
        )
        if not mapped:
            continue

        offset, length = py_range_to_bot_entity_range(final_text, mapped[0], mapped[1])
        entity = {
            "type": "text_link",
            "offset": offset,
            "length": length,
            "url": decision["url"],
        }
        if validate_bot_entity(final_text, entity):
            link_entities.append(entity)
        else:
            logger.info(
                f"链接实体生成后校验失败 | task_id={task_id} | target={target} | "
                f"offset={offset} | length={length} | url={short_text(decision['url'], 140)}"
            )

    logger.info(
        f"链接规则处理完成 | task_id={task_id} | target={target} | "
        f"delete_ranges={len(delete_ranges)} | generated_link_entities={len(link_entities)} | "
        f"final_len={len(final_text or '')}"
    )

    return final_text, link_entities


def html_tag_for_entity(entity: dict):
    bot_type = entity.get("type")

    if bot_type == "text_link":
        url = escape(entity.get("url", ""), quote=True)
        return f'a href="{url}"', "a"

    if bot_type == "custom_emoji":
        emoji_id = escape(entity.get("custom_emoji_id", ""), quote=True)
        if not emoji_id:
            return None
        return f'tg-emoji emoji-id="{emoji_id}"', "tg-emoji"

    return HTML_TAGS.get(bot_type)


def render_bot_entities_as_html(text: str, entities) -> str:
    if not text:
        return ""

    starts = {}
    ends = {}

    for entity in entities or []:
        if not validate_bot_entity(text, entity):
            continue

        tags = html_tag_for_entity(entity)
        if not tags:
            continue

        start = utf16_offset_to_py_index(text, entity["offset"])
        end = utf16_offset_to_py_index(text, entity["offset"] + entity["length"])
        open_tag, close_tag = tags
        starts.setdefault(start, []).append((end, open_tag))
        ends.setdefault(end, []).append((start, close_tag))

    parts = []

    for index, char in enumerate(text):
        for _end, open_tag in sorted(
            starts.get(index, []),
            key=lambda item: item[0],
            reverse=True,
        ):
            parts.append(f"<{open_tag}>")

        parts.append(escape(char))

        for _start, close_tag in sorted(
            ends.get(index + 1, []),
            key=lambda item: item[0],
            reverse=True,
        ):
            parts.append(f"</{close_tag}>")

    return "".join(parts)


def render_entities_as_html(text: str, entities) -> str:
    bot_entities, _dropped = map_entities_to_bot(text, text, entities)
    return render_bot_entities_as_html(text, bot_entities) if bot_entities else escape(text)


def format_prepared_text(source, processed_text: str, task=None, target=None):
    plain_text = processed_text or ""

    if not plain_text:
        return {
            "text": "",
            "plain_text": "",
            "format_level": FORMAT_LEVEL_PLAIN,
            "kept_entities_count": 0,
            "dropped_entities_count": 0,
        }

    try:
        message = pick_source_message(source)
        original_text = get_message_text(message) if message else ""
        original_entities = get_message_entities(message) if message else []
        plain_text, link_entities = apply_link_rules_to_text(
            original_text,
            plain_text,
            original_entities,
            task=task,
            target=target,
        )
        text_edits = build_text_edits(original_text, plain_text)

        bot_entities, dropped = map_entities_to_bot(
            original_text,
            plain_text,
            [
                entity
                for entity in original_entities
                if not (link_entities is not None and is_link_entity(entity))
            ],
        )
        if link_entities is not None:
            bot_entities = dedupe_entities([*bot_entities, *link_entities])

        if bot_entities:
            html_text = render_bot_entities_as_html(plain_text, bot_entities)
            result = {
                "text": plain_text,
                "plain_text": plain_text,
                "entities": bot_entities,
                "html_text": html_text or escape(plain_text),
                "format_level": FORMAT_LEVEL_ENTITIES,
                "kept_entities_count": len(bot_entities),
                "dropped_entities_count": dropped,
                "text_edits": [edit.__dict__ for edit in text_edits],
            }
        else:
            result = {
                "text": escape(plain_text),
                "plain_text": plain_text,
                "parse_mode": "HTML",
                "html_text": escape(plain_text),
                "format_level": FORMAT_LEVEL_HTML,
                "kept_entities_count": 0,
                "dropped_entities_count": dropped,
                "text_edits": [edit.__dict__ for edit in text_edits],
            }

        if dropped or bot_entities:
            logger.debug(
                f"entity formatter result | level={result['format_level']} | "
                f"kept={result['kept_entities_count']} | "
                f"dropped={result['dropped_entities_count']} | "
                f"edits={len(text_edits)}"
            )

        return result

    except Exception as e:
        logger.warning(f"entity formatter failed, fallback to HTML | {e}")

        return {
            "text": escape(plain_text),
            "plain_text": plain_text,
            "parse_mode": "HTML",
            "html_text": escape(plain_text),
            "format_level": FORMAT_LEVEL_HTML,
            "fallback_reason": str(e),
            "kept_entities_count": 0,
            "dropped_entities_count": 0,
        }
