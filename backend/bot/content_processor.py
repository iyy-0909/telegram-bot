import json
import re
from html import escape, unescape

from bot.logger import logger
from db.crud_templates import get_contact_rule_config, get_filter_keywords, pick_template_content


TEXT_LIMIT = 4096
CAPTION_SAFE_LIMIT = 1024
URL_PATTERN = re.compile(
    r"(?i)\b(?:https?://|www\.|t\.me/|telegram\.me/)[^\s]+"
)
ALLOWED_TEMPLATE_TAG_RE = re.compile(
    r"</?(?:b|strong|i|em|u|s|strike|del|code|pre|tg-spoiler|blockquote|a)(?:\s[^>]*)?>",
    re.IGNORECASE,
)
SIMPLE_TEMPLATE_TAG_RE = re.compile(
    r"</?(?:b|strong|i|em|u|s|strike|del|code|pre|tg-spoiler|blockquote)>",
    re.IGNORECASE,
)
LINK_OPEN_TAG_RE = re.compile(
    r"<a\s+href=(['\"])(?P<url>https?://[^'\"]+|tg://[^'\"]+|t\.me/[^'\"]+|telegram\.me/[^'\"]+)\1>",
    re.IGNORECASE,
)
LINK_CLOSE_TAG_RE = re.compile(r"</a>", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"</?[^>]+>")


def get_message_text(message):
    """获取 Telegram 消息文本或 caption。"""
    return message.message or ""


def load_json(value, default):
    if not value:
        return default

    if isinstance(value, (list, dict)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return default


def has_phone_number(line: str) -> bool:
    if not line:
        return False

    phone_pattern = re.compile(
        r"(?<!\d)"
        r"(?:\+?86[-\s]?)?"
        r"1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}"
        r"(?!\d)"
    )
    return bool(phone_pattern.search(line))


def has_link(line: str) -> bool:
    if not line:
        return False

    lower_line = line.lower()
    link_keywords = [
        "http://",
        "https://",
        "www.",
        "t.me/",
        "telegram.me/",
    ]
    return any(keyword in lower_line for keyword in link_keywords)


def is_standalone_url_line(line: str) -> bool:
    if not line:
        return False

    text = line.strip()

    if not text:
        return False

    match = URL_PATTERN.fullmatch(text)
    return bool(match)


def has_telegram_username(line: str) -> bool:
    if not line:
        return False

    username_pattern = re.compile(r"@[a-zA-Z0-9][a-zA-Z0-9_]*\b")
    return bool(username_pattern.search(line))


def has_contact_keyword(line: str) -> bool:
    if not line:
        return False

    lower_line = line.lower()
    contact_keywords = [
        "微信",
        "微信号",
        "微",
        "vx",
        "v信",
        "wechat",
        "we chat",
        "wx",
        "电话",
        "手机",
        "联系",
        "联系方式",
        "客服",
        "tg",
        "telegram",
        "纸飞机",
        "飞机",
    ]
    return any(keyword in lower_line for keyword in contact_keywords)


def should_remove_line(line: str) -> bool:
    return (
        has_phone_number(line)
        or has_link(line)
        or has_telegram_username(line)
        or has_contact_keyword(line)
    )


def has_contact_keyword(line: str, keywords=None) -> bool:
    if not line:
        return False

    lower_line = line.lower()
    contact_keywords = keywords or []
    return any(str(keyword).lower() in lower_line for keyword in contact_keywords)


def has_custom_regex(line: str, patterns) -> bool:
    if not line or not patterns:
        return False

    for pattern in patterns:
        try:
            if re.search(str(pattern), line, re.IGNORECASE):
                return True
        except re.error as e:
            logger.warning(f"联系方式删除正则无效，已跳过 | pattern={pattern} | {e}")

    return False


def should_remove_line(line: str, config=None) -> bool:
    config = config or {}
    return (
        (config.get("remove_phone", True) and has_phone_number(line))
        or (config.get("remove_links", True) and has_link(line))
        or (config.get("remove_usernames", True) and has_telegram_username(line))
        or (
            config.get("remove_keywords", True)
            and has_contact_keyword(line, config.get("keywords"))
        )
        or has_custom_regex(line, config.get("custom_regex"))
    )


def compact_blank_lines(text: str) -> str:
    if not text:
        return ""

    result_lines = []
    previous_empty = False

    for line in text.splitlines():
        current_empty = not line.strip()

        if current_empty and previous_empty:
            continue

        result_lines.append(line)
        previous_empty = current_empty

    return "\n".join(result_lines).strip()


def remove_contact_lines(text: str, config=None) -> str:
    if not text:
        return ""

    clean_lines = [
        line
        for line in text.splitlines()
        if not should_remove_line(line, config)
    ]
    return compact_blank_lines("\n".join(clean_lines))


def remove_standalone_url_lines(text: str) -> str:
    if not text:
        return ""

    clean_lines = [
        line
        for line in text.splitlines()
        if not is_standalone_url_line(line)
    ]
    return compact_blank_lines("\n".join(clean_lines))


def apply_replace_words(text: str, replace_words: dict) -> str:
    if not text or not replace_words:
        return text or ""

    for old, new in replace_words.items():
        if old:
            text = text.replace(str(old), str(new))

    return text


def parse_replace_config(value):
    config = load_json(value, {})

    if not isinstance(config, dict):
        return {}, []

    if isinstance(config.get("rules"), list):
        replace_words = {}
        delete_lines = []

        for rule in config.get("rules") or []:
            if not isinstance(rule, dict) or rule.get("enabled", True) is False:
                continue

            match = str(rule.get("match") or "").strip()
            if not match:
                continue

            if rule.get("type") == "delete_line":
                delete_lines.append(match)
            else:
                replace_words[match] = str(rule.get("value") or "")

        return replace_words, delete_lines

    if "replace" in config or "delete_lines" in config:
        replace_words = config.get("replace") or {}
        delete_lines = config.get("delete_lines") or []
        return (
            replace_words if isinstance(replace_words, dict) else {},
            delete_lines if isinstance(delete_lines, list) else [],
        )

    return config, []


def remove_lines_by_keywords(text: str, keywords: list) -> str:
    if not text or not keywords:
        return text or ""

    clean_keywords = [
        str(keyword).strip()
        for keyword in keywords
        if str(keyword).strip()
    ]

    if not clean_keywords:
        return text

    clean_lines = [
        line
        for line in text.splitlines()
        if not any(keyword in line for keyword in clean_keywords)
    ]
    return compact_blank_lines("\n".join(clean_lines))


def find_blocked_keyword(text: str, blocked_keywords: list) -> str:
    if not text or not blocked_keywords:
        return ""

    for keyword in blocked_keywords:
        keyword = str(keyword).strip()

        if keyword and keyword in text:
            return keyword

    return ""


def normalize_keyword_items(value) -> list:
    keywords = load_json(value, [])

    if not isinstance(keywords, list):
        return []

    return [
        str(keyword).strip()
        for keyword in keywords
        if str(keyword or "").strip()
    ]


def find_required_keyword(text: str, required_keywords: list) -> str:
    if not text or not required_keywords:
        return ""

    normalized_text = str(text).casefold()

    for keyword in required_keywords:
        keyword = str(keyword).strip()

        if keyword and keyword.casefold() in normalized_text:
            return keyword

    return ""


def format_keyword_preview(keywords: list, limit: int = 5) -> str:
    clean_keywords = [
        str(keyword).strip()
        for keyword in keywords
        if str(keyword or "").strip()
    ]

    if not clean_keywords:
        return ""

    preview = " / ".join(clean_keywords[:limit])
    if len(clean_keywords) > limit:
        preview = f"{preview} 等"
    return preview


def is_blocked(text: str, blocked_keywords: list) -> bool:
    return bool(find_blocked_keyword(text, blocked_keywords))


def blocked_keyword_result(text: str, keyword: str, stage: str):
    return {
        "blocked": True,
        "text": text,
        "reason": "keyword",
        "filter_keyword": keyword,
        "filter_stage": stage,
        "filter_detail": f"命中关键词“{keyword}”",
    }


def append_footer(text: str, footer: str) -> str:
    text = text or ""
    footer = footer or ""

    if not footer.strip():
        return text.strip()

    if not text.strip():
        return footer.strip()

    return f"{text.strip()}\n\n{footer.strip()}"


def join_content_parts(parts) -> str:
    clean_parts = [
        str(part).strip()
        for part in parts
        if str(part or "").strip()
    ]
    return compact_blank_lines("\n\n".join(clean_parts))


def join_content_template_parts(
    head: str,
    content: str,
    body: str,
    footer: str,
    footer_leading_blank_line: bool = True,
) -> str:
    """拼接内容模板；Footer 可选择保留空行或紧接上一段。"""
    content_before_footer = join_content_parts([head, content, body])
    clean_footer = str(footer or "").strip()

    if not clean_footer:
        return content_before_footer

    if not content_before_footer:
        return clean_footer

    separator = "\n\n" if footer_leading_blank_line else "\n"
    return compact_blank_lines(
        f"{content_before_footer.rstrip()}{separator}{clean_footer}"
    )


def has_template_html(text: str) -> bool:
    return bool(text and ALLOWED_TEMPLATE_TAG_RE.search(text))


def sanitize_template_html(text: str) -> str:
    text = text or ""
    placeholders = []

    def stash(tag: str) -> str:
        key = f"__TG_TEMPLATE_HTML_TAG_{len(placeholders)}__"
        placeholders.append((key, tag))
        return key

    def keep_link_open(match):
        url = escape(match.group("url"), quote=True)
        return stash(f'<a href="{url}">')

    text = LINK_OPEN_TAG_RE.sub(keep_link_open, text)
    text = LINK_CLOSE_TAG_RE.sub(lambda _match: stash("</a>"), text)
    text = SIMPLE_TEMPLATE_TAG_RE.sub(lambda match: stash(match.group(0).lower()), text)
    text = escape(text)

    for key, tag in placeholders:
        text = text.replace(escape(key), tag)

    return text


def strip_html_tags(text: str) -> str:
    return unescape(HTML_TAG_RE.sub("", text or ""))


def trim_to_telegram_limit(text: str, limit: int = CAPTION_SAFE_LIMIT) -> str:
    text = text or ""

    if len(text) <= limit:
        return text

    logger.warning(
        f"内容超过 Telegram 安全长度，已截断 | length={len(text)} | limit={limit}"
    )
    return text[: max(limit - 1, 0)].rstrip()


def get_template_part(task, template_type: str) -> str:
    enabled_field = f"use_random_{template_type}"
    group_field = f"selected_{template_type}_template_group_id"
    selected_field = f"selected_{template_type}_template_id"

    if not getattr(task, enabled_field, False):
        return ""

    selected_group_id = getattr(task, group_field, None)
    selected_id = getattr(task, selected_field, None)
    return pick_template_content(template_type, selected_id, selected_group_id)


def apply_content_templates(text: str, task) -> str:
    try:
        head = get_template_part(task, "head")
        body = get_template_part(task, "body")
        footer = get_template_part(task, "footer")
        return join_content_template_parts(
            head,
            text,
            body,
            footer,
            getattr(task, "footer_leading_blank_line", True) is not False,
        )
    except Exception as e:
        logger.warning(f"内容模板拼接失败，保留原文 | {e}")
        return text or ""


def apply_content_templates_with_format(text: str, task, text_is_html: bool = False):
    try:
        head = get_template_part(task, "head")
        body = get_template_part(task, "body")
        footer = get_template_part(task, "footer")
        template_parts = [head, body, footer]

        if text_is_html or any(has_template_html(part) for part in template_parts):
            head_html = sanitize_template_html(head)
            content_html = sanitize_template_html(text) if text_is_html else escape(text or "")
            body_html = sanitize_template_html(body)
            footer_html = sanitize_template_html(footer)
            footer_leading_blank_line = (
                getattr(task, "footer_leading_blank_line", True) is not False
            )
            html_text = join_content_template_parts(
                head_html,
                content_html,
                body_html,
                footer_html,
                footer_leading_blank_line,
            )
            html_text = trim_to_telegram_limit(html_text)

            return {
                "text": html_text,
                "plain_text": strip_html_tags(html_text),
                "parse_mode": "HTML",
                "html_text": html_text,
                "format_level": "ai_html" if text_is_html else "template_html",
                # 发送前只对正文应用原文链接规则，模板会在链接处理后再拼回。
                "content_html": content_html,
                "template_head_html": head_html,
                "template_body_html": body_html,
                "template_footer_html": footer_html,
                "footer_leading_blank_line": footer_leading_blank_line,
            }

        return {
            "text": join_content_template_parts(
                head,
                text,
                body,
                footer,
                getattr(task, "footer_leading_blank_line", True) is not False,
            ),
        }

    except Exception as e:
        logger.warning(f"内容模板拼接失败，保留原文 | {e}")
        return {
            "text": text or "",
        }


def compose_content_templates_html(result, content_html: str) -> str:
    """在正文链接处理完成后拼接模板，避免模板链接被原文链接规则降级。"""
    if "content_html" not in result:
        return content_html or ""

    return trim_to_telegram_limit(join_content_template_parts(
        result.get("template_head_html") or "",
        content_html or "",
        result.get("template_body_html") or "",
        result.get("template_footer_html") or "",
        result.get("footer_leading_blank_line", True),
    ))


def normalize_collected_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("＃", "#")
    text = re.sub(
        r"#[" r"\s" r"\u00A0" r"\u200B" r"\u200C" r"\u200D" r"\uFEFF" r"]+",
        "#",
        text,
    )
    return text


def has_meaningful_rewrite_input(text: str) -> bool:
    """Require at least one Chinese character or Latin letter before AI rewrite."""
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text or ""))


def process_content(raw_text: str, task, apply_templates: bool = True):
    text = normalize_collected_text(raw_text or "")

    required_keywords = normalize_keyword_items(
        getattr(task, "listen_required_keywords", "[]")
    )
    if required_keywords and not find_required_keyword(text, required_keywords):
        return {
            "blocked": True,
            "text": text,
            "reason": "required_keyword_missing",
            "filter_stage": "before_cleanup",
            "filter_detail": f"未命中只监听内容：{format_keyword_preview(required_keywords)}",
        }

    blocked_keywords = load_json(
        getattr(task, "blocked_keywords", None) or getattr(task, "keywords", None),
        [],
    )
    template_keywords = get_filter_keywords(
        getattr(task, "selected_filter_template_group_id", None)
    )
    blocked_keywords = [
        *(
            blocked_keywords
            if isinstance(blocked_keywords, list)
            else []
        ),
        *template_keywords,
    ]
    replace_words, delete_lines = parse_replace_config(getattr(task, "replace_words", "{}"))
    # Legacy footer is kept in database/API for compatibility, but no longer
    # participates in sending. Use content_templates footer instead.
    # legacy_footer = getattr(task, "footer", "") or ""

    matched_keyword = find_blocked_keyword(text, blocked_keywords)
    if matched_keyword:
        return blocked_keyword_result(text, matched_keyword, "before_cleanup")

    remove_contact_content = bool(getattr(task, "remove_contact_lines", True))
    if remove_contact_content:
        before_contact_cleanup = text
        contact_rule_config = get_contact_rule_config(
            getattr(task, "selected_contact_template_group_id", None)
        )
        text = remove_contact_lines(text, contact_rule_config)
        contact_cleanup_changed = text != before_contact_cleanup
    else:
        contact_cleanup_changed = False

    if remove_contact_content:
        before_url_cleanup = text
        text = remove_standalone_url_lines(text)
        url_cleanup_changed = text != before_url_cleanup
    else:
        url_cleanup_changed = False

    matched_keyword = find_blocked_keyword(text, blocked_keywords)
    if matched_keyword:
        return blocked_keyword_result(text, matched_keyword, "after_cleanup")

    before_delete_lines = text
    text = remove_lines_by_keywords(text, delete_lines)
    delete_lines_changed = text != before_delete_lines

    before_replace = text
    text = apply_replace_words(text, replace_words)
    replace_changed = text != before_replace
    text = compact_blank_lines(text)

    if not text.strip():
        cleanup_reasons = []
        if contact_cleanup_changed:
            cleanup_reasons.append("联系方式/链接清理")
        if url_cleanup_changed:
            cleanup_reasons.append("独立链接清理")
        if delete_lines_changed:
            cleanup_reasons.append("删除行规则")
        if replace_changed:
            cleanup_reasons.append("替换规则")

        return {
            "blocked": True,
            "text": "",
            "reason": "empty_after_process",
            "filter_detail": (
                f"{'、'.join(cleanup_reasons)}后无可发送文本"
                if cleanup_reasons
                else "内容处理后无可发送文本"
            ),
        }

    if not apply_templates:
        return {"blocked": False, "text": text}

    template_result = apply_content_templates_with_format(text, task)
    text = template_result.get("text") or ""
    # Old footer function is intentionally disabled.
    # text = append_footer(text, legacy_footer)
    if not template_result.get("parse_mode"):
        text = trim_to_telegram_limit(text)

    result = {
        "blocked": False,
        "text": text,
    }

    for key in (
        "plain_text",
        "parse_mode",
        "html_text",
        "format_level",
        "content_html",
        "template_head_html",
        "template_body_html",
        "template_footer_html",
        "footer_leading_blank_line",
    ):
        if key in template_result and (
            key == "footer_leading_blank_line" or template_result.get(key)
        ):
            result[key] = template_result.get(key)

    return result


async def process_content_async(raw_text: str, task):
    """固定执行顺序：基础内容处理 -> Head/Body/Footer 模板规则 -> AI 改写。"""
    # 第一阶段只做过滤、联系方式、链接和替换词等基础处理。
    result = process_content(raw_text, task, apply_templates=False)
    if result.get("blocked"):
        return result

    from bot.grok_rewriter import is_rewrite_enabled, rewrite_text

    # 第二阶段先追加模板，让 AI 能对完整的最终文案结构进行改写。
    template_result = apply_content_templates_with_format(
        result.get("text") or "",
        task,
    )
    templated_text = template_result.get("text") or ""
    result["text"] = templated_text
    for key in (
        "plain_text",
        "parse_mode",
        "html_text",
        "format_level",
        "content_html",
        "template_head_html",
        "template_body_html",
        "template_footer_html",
        "footer_leading_blank_line",
    ):
        if key in template_result and (
            key == "footer_leading_blank_line" or template_result.get(key)
        ):
            result[key] = template_result.get(key)

    # 第三阶段让 AI 接收已经追加模板的完整内容。AI 成功后，模板不再重复追加。
    if not is_rewrite_enabled(task):
        if not template_result.get("parse_mode"):
            result["text"] = trim_to_telegram_limit(templated_text)
        return result

    if not has_meaningful_rewrite_input(strip_html_tags(templated_text)):
        return {
            "blocked": True,
            "text": "",
            "reason": "empty_after_process",
            "filter_detail": "内容仅包含数字、符号或表情，已跳过 AI 改写",
        }

    rewritten, error = await rewrite_text(task, templated_text)
    if error:
        if getattr(task, "ai_rewrite_failure_mode", "fallback") == "skip":
            return {
                "blocked": True,
                "text": templated_text,
                "reason": "ai_rewrite_failed",
                "filter_detail": error,
            }
        result["ai_rewrite_error"] = error
        if not template_result.get("parse_mode"):
            result["text"] = trim_to_telegram_limit(templated_text)
        return result

    if not rewritten.strip():
        return {
            "blocked": True,
            "text": "",
            "reason": "empty_after_process",
            "filter_detail": "AI 判定没有可发布内容，已跳过",
            "ai_rewritten": True,
        }

    final_html = trim_to_telegram_limit(sanitize_template_html(rewritten))
    return {
        "blocked": False,
        "text": final_html,
        "plain_text": strip_html_tags(final_html),
        "parse_mode": "HTML",
        "html_text": final_html,
        "format_level": "ai_html",
        "ai_rewritten": True,
    }
