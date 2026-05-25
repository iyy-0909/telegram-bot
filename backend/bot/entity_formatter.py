from dataclasses import dataclass
from difflib import SequenceMatcher
from html import escape

from bot.logger import logger


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
    if bot_type not in set(TELETHON_TO_BOT_TYPES.values()):
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


def format_prepared_text(source, processed_text: str):
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
        text_edits = build_text_edits(original_text, plain_text)

        bot_entities, dropped = map_entities_to_bot(
            original_text,
            plain_text,
            original_entities,
        )

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
