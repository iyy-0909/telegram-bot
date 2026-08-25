import asyncio
from collections import deque
from difflib import SequenceMatcher
import hashlib
import html
import os
import re
import threading

import aiohttp

from bot.logger import logger


DEFAULT_PROMPT = """你是 Telegram 内容编辑。请在保留原文事实、数字、时间、地点、价格、联系方式和相关标签的前提下，对内容进行明显重写和排版优化。不得编造信息，不得照搬固定模板，只输出可直接发送的 Telegram HTML 正文。总长度不得超过 {{max_chars}} 个字符。

待处理文本：
{{content}}"""

PROVIDERS = {
    "grok": {
        "api_key_env": "XAI_API_KEY",
        "base_url_env": "XAI_BASE_URL",
        "default_url": "https://api.x.ai/v1/chat/completions",
        "model_env": "XAI_MODEL",
        "default_model": "grok-4.6",
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "default_url": "https://api.deepseek.com/chat/completions",
        "model_env": "DEEPSEEK_MODEL",
        "default_model": "deepseek-v4-flash",
    },
}


AI_HTML_TAG_NAMES = (
    "b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler|blockquote|a"
)
AI_SKIP_SENTINEL = "[[SKIP]]"
AI_OUTPUT_PROTOCOL = f"""【强制输出协议】
有可发布内容时，只输出最终 Telegram HTML 正文，不得解释处理过程。
换行必须使用真实换行符；禁止使用 <br>、<br/>、</br> 或 <p> 代替换行。
输入中原本以明文出现的 URL 必须保持其整行内容和明文形式完全不变：禁止修改前后文字、禁止改名、禁止包装成 <a> 或 Markdown 链接。
只有输入中原本已经是 <a href="...">可点击文字</a> 的链接才允许改写可点击文字；必须逐字保留 href，并继续输出完整的 <a href="...">...</a>，禁止删除、转义、降级为纯文字或改成 Markdown 链接。
手机号、微信号以及联系类 <a href="...">...</a> 必须分别单独占一行，禁止塞进正文句子中；“驻场联系：”“点击咨询：”等简短标签可以和对应链接保留在同一行。
没有可发布内容时，只输出 {AI_SKIP_SENTINEL}，不得说明原因，不得输出“空”“输出结果”或其他文字。"""

AI_LAYOUT_VARIANTS = (
    {
        "key": "minimal",
        "name": "极简短文",
        "instruction": """使用一个简短加粗主标题和 2～3 个自然段完成全文。不要设置小标题，不要使用项目符号；把联系方式和标签放在末尾。""",
    },
    {
        "key": "info_card",
        "name": "信息卡片",
        "instruction": """采用紧凑信息卡结构：加粗主标题后，按原文实际信息组织为 2～3 个短区块。价格、时间、地点等事实可以逐行展示；小标题必须根据内容临时命名。""",
    },
    {
        "key": "scene",
        "name": "场景叙述",
        "instruction": """从一个自然场景或读者需求切入，用连贯短段落介绍核心内容，最后再集中放置事实信息、联系方式和标签。除主标题外最多使用一个小标题。""",
    },
    {
        "key": "checklist",
        "name": "重点清单",
        "instruction": """先用一段简短导语概括主题，再用项目符号整理原文明示的卖点或信息，最后紧凑呈现联系方式和标签。条目数量由原文事实决定，信息不足时可以少于三条，禁止为了凑数添加新场景或新卖点；禁止再添加“适合场景”段落。""",
    },
    {
        "key": "qa",
        "name": "问答引导",
        "instruction": """标题或开场使用一个与原文直接相关的自然问题，正文以回答该问题的方式展开；信息较多时只使用一个事实清单，不要套用广告卡片的固定小标题。""",
    },
    {
        "key": "editorial",
        "name": "编辑短评",
        "instruction": """采用编辑推荐式短文：加粗主题标题、简短判断或概括、两段重新组织的正文，末尾列出必要事实和联系方式。不要使用 Emoji 小标题。""",
    },
)

AI_ANTI_TEMPLATE_PROTOCOL = """【反模板要求】
本次版式由程序指定，优先于配置提示词里的推荐结构、示例结构或惯用结构。
禁止机械使用“核心亮点”“适合场景”“营业信息”“联系与预约”等通用小标题；只有原文语义确实需要且本次版式允许时，才可换成与内容直接相关的自然标题。
禁止反复使用“氛围感拉满”“这里都能接住”“提前预约更省心”“夜已深，就差你”等套话。
不要为了凑齐区块而增加原文没有的信息。段落数量、是否使用列表、开场方式和收尾方式必须服从本次指定版式。"""

AI_RECENT_LAYOUT_COUNT = 2
AI_RECENT_OUTPUT_COUNT = 5
AI_REQUEST_TIMEOUT_SECONDS = 300
AI_MAX_COMPLETION_TOKENS = 100_000
AI_STRUCTURE_SIMILARITY_THRESHOLD = 0.84

_rewrite_state_lock = threading.Lock()
_layout_counters = {}
_recent_layouts = {}
_recent_outputs = {}

AI_HASHTAG_PATTERN = re.compile(r"(?<![\w#])#[0-9a-zA-Z_\u4e00-\u9fff]+")
AI_USERNAME_PATTERN = re.compile(r"(?<![\w@])@[0-9a-zA-Z_]{4,}")
AI_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
AI_PHONE_PATTERN = re.compile(r"(?<![\w])\+?\d{7,15}(?![\w])")
AI_WECHAT_PATTERN = re.compile(
    r"(?:微信(?:号)?|wx|wechat)\s*[:：]\s*([0-9a-zA-Z_-]{4,})",
    re.IGNORECASE,
)
AI_ANCHOR_PATTERN = re.compile(
    r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a\s*>",
    re.IGNORECASE | re.DOTALL,
)
AI_HREF_PATTERN = re.compile(
    r"\bhref\s*=\s*(['\"])(?P<url>.*?)\1",
    re.IGNORECASE | re.DOTALL,
)


def _task_state_key(task):
    task_id = getattr(task, "id", None)
    if task_id is not None:
        return f"task:{task_id}"
    return f"object:{id(task)}"


def _normalized_content_fingerprint(text):
    normalized = re.sub(r"\s+", " ", html.unescape(text or "")).strip().lower()
    return int.from_bytes(
        hashlib.sha256(normalized.encode("utf-8")).digest()[:8],
        "big",
    )


def reset_rewrite_runtime_state():
    """Clear in-memory layout/output history, mainly for tests and clean restarts."""
    with _rewrite_state_lock:
        _layout_counters.clear()
        _recent_layouts.clear()
        _recent_outputs.clear()


def select_layout_variant(task, text, excluded_keys=None):
    """Select a deterministic-but-rotating layout and avoid the latest two."""
    excluded = set(excluded_keys or ())
    task_key = _task_state_key(task)
    variant_count = len(AI_LAYOUT_VARIANTS)
    fingerprint = _normalized_content_fingerprint(text)

    with _rewrite_state_lock:
        counter = _layout_counters.get(task_key, 0)
        recent = _recent_layouts.setdefault(
            task_key,
            deque(maxlen=AI_RECENT_LAYOUT_COUNT),
        )
        recent_keys = set(recent)

        selected = None
        selected_offset = 0
        for offset in range(variant_count):
            candidate = AI_LAYOUT_VARIANTS[
                (fingerprint + counter + offset) % variant_count
            ]
            if candidate["key"] in excluded or candidate["key"] in recent_keys:
                continue
            selected = candidate
            selected_offset = offset
            break

        if selected is None:
            for offset in range(variant_count):
                candidate = AI_LAYOUT_VARIANTS[
                    (fingerprint + counter + offset) % variant_count
                ]
                if candidate["key"] not in excluded:
                    selected = candidate
                    selected_offset = offset
                    break

        selected = selected or AI_LAYOUT_VARIANTS[0]
        _layout_counters[task_key] = counter + selected_offset + 1
        recent.append(selected["key"])
        return selected


def build_layout_directive(layout):
    return f"""{AI_ANTI_TEMPLATE_PROTOCOL}

【本次指定版式：{layout['name']}】
{layout['instruction']}
本次不得改用其他版式，不得补回固定的“标题＋亮点＋场景＋营业信息＋联系”结构。"""


def _plain_output_text(text):
    normalized = html.unescape(text or "")
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _output_structure_signature(text):
    lines = [
        line.strip()
        for line in html.unescape(text or "").splitlines()
        if line.strip()
    ]
    shape = []
    headings = []
    for line in lines:
        plain_line = re.sub(r"<[^>]+>", "", line).strip()
        if re.fullmatch(r"<(?:b|strong)>.+?</(?:b|strong)>", line, re.IGNORECASE):
            shape.append("H")
            heading = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", plain_line).lower()
            if heading:
                headings.append(heading)
        elif re.fullmatch(r"<(?:i|em)>.+?</(?:i|em)>", line, re.IGNORECASE):
            shape.append("I")
        elif re.match(r"^[•·▪◦*-]\s*", plain_line):
            shape.append("B")
        elif re.match(r"^(?:#[^\s#]+\s*)+$", plain_line):
            shape.append("T")
        elif re.search(
            r"(?:@\w+|https?://|t\.me/|(?:电话|手机|微信|wx|tg|联系|预订|预约)\s*[:：])",
            plain_line,
            re.IGNORECASE,
        ):
            shape.append("C")
        elif re.search(r"<(?:b|strong)>", line, re.IGNORECASE):
            shape.append("K")
        else:
            shape.append("P")
    return tuple(shape), set(headings)


def output_structure_similarity(first, second):
    first_shape, first_headings = _output_structure_signature(first)
    second_shape, second_headings = _output_structure_signature(second)
    shape_similarity = SequenceMatcher(
        None,
        first_shape,
        second_shape,
    ).ratio()

    if first_headings or second_headings:
        heading_similarity = len(first_headings & second_headings) / max(
            len(first_headings | second_headings),
            1,
        )
    else:
        heading_similarity = 0.0

    text_similarity = SequenceMatcher(
        None,
        _plain_output_text(first)[:1200],
        _plain_output_text(second)[:1200],
    ).ratio()
    return max(
        text_similarity,
        shape_similarity * 0.75 + heading_similarity * 0.25,
    )


def max_recent_output_similarity(task, candidate):
    task_key = _task_state_key(task)
    with _rewrite_state_lock:
        recent = list(_recent_outputs.get(task_key, ()))
    if not recent:
        return 0.0
    return max(output_structure_similarity(candidate, previous) for previous in recent)


def remember_rewrite_output(task, text):
    task_key = _task_state_key(task)
    with _rewrite_state_lock:
        recent = _recent_outputs.setdefault(
            task_key,
            deque(maxlen=AI_RECENT_OUTPUT_COUNT),
        )
        recent.append(text)


def _unique_preserving_order(values):
    unique = []
    seen = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def extract_source_hashtags(text):
    return _unique_preserving_order(AI_HASHTAG_PATTERN.findall(text or ""))


def extract_source_contact_tokens(text):
    source = html.unescape(text or "")
    urls = [
        value.rstrip(".,，。；;!?！？)")
        for value in AI_URL_PATTERN.findall(source)
    ]
    usernames = AI_USERNAME_PATTERN.findall(source)
    phones = AI_PHONE_PATTERN.findall(source)
    wechat_ids = AI_WECHAT_PATTERN.findall(source)
    return _unique_preserving_order(urls + usernames + phones + wechat_ids)


def extract_plain_url_lines(text):
    """Return source lines containing URLs that were not inside HTML anchors."""
    items = []
    seen = set()
    for raw_line in html.unescape(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        without_anchors = AI_ANCHOR_PATTERN.sub("", line)
        visible_text = re.sub(r"<[^>]+>", "", without_anchors)
        urls = [
            value.rstrip(".,，。；;!?！？)")
            for value in AI_URL_PATTERN.findall(visible_text)
        ]
        if not urls:
            continue

        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "line": line,
            "urls": _unique_preserving_order(urls),
        })
    return items


def build_plain_url_directive(text):
    items = extract_plain_url_lines(text)
    if not items:
        return ""

    lines = ["【本次禁止改写的明文链接行】"]
    lines.extend(item["line"] for item in items)
    lines.append("以上各行必须逐字、逐行保留，并继续显示为明文 URL；禁止包装成 <a>。")
    return "\n".join(lines)


def ensure_preserved_plain_url_lines(source_text, rewritten_text):
    """Restore source plaintext-URL lines and undo model-created anchors."""
    items = extract_plain_url_lines(source_text)
    if not items:
        return rewritten_text or ""

    output_lines = (rewritten_text or "").splitlines()
    for item in items:
        source_line = item["line"]
        exact_index = next(
            (
                index
                for index, line in enumerate(output_lines)
                if html.unescape(line).strip() == source_line
            ),
            None,
        )
        matching_indices = [
            index
            for index, line in enumerate(output_lines)
            if any(url in html.unescape(line) for url in item["urls"])
        ]

        if exact_index is not None:
            output_lines[exact_index] = source_line
            for index in reversed(matching_indices):
                if index != exact_index:
                    del output_lines[index]
            continue

        if matching_indices:
            first_index = matching_indices[0]
            output_lines[first_index] = source_line
            for index in reversed(matching_indices[1:]):
                del output_lines[index]
            continue

        if output_lines and any(line.strip() for line in output_lines):
            output_lines.extend(["", source_line])
        else:
            output_lines.append(source_line)

    output = "\n".join(output_lines)
    output = re.sub(r"[ \t]+\n", "\n", output)
    output = re.sub(r"\n{3,}", "\n\n", output)
    return output.strip()


def build_source_metadata_directive(text):
    contacts = extract_source_contact_tokens(text)
    hashtags = extract_source_hashtags(text)
    if not contacts and not hashtags:
        return ""

    lines = ["【本次必须逐字保留的元数据】"]
    if contacts:
        lines.append("联系方式/链接：" + " | ".join(contacts))
    if hashtags:
        lines.append("原始标签：" + " ".join(hashtags))
    lines.append("上述值由程序从清理后的输入中提取，禁止改名、替换或遗漏。")
    return "\n".join(lines)


def ensure_preserved_metadata(source_text, rewritten_text):
    """Deterministically keep cleaned contacts and source tags in final output."""
    output = rewritten_text or ""
    output_plain = html.unescape(output)
    missing_contacts = [
        token
        for token in extract_source_contact_tokens(source_text)
        if token not in output_plain
    ]

    output_tags = extract_source_hashtags(output)
    source_tags = extract_source_hashtags(source_text)
    source_tag_keys = {tag.casefold() for tag in source_tags}
    generated_tags = [
        tag
        for tag in output_tags
        if tag.casefold() not in source_tag_keys
    ][:1]

    if len(source_tags) > 5:
        output_tag_keys = {tag.casefold() for tag in output_tags}
        selected_source_tags = [
            tag for tag in source_tags if tag.casefold() in output_tag_keys
        ][:5]
        if len(selected_source_tags) < 5:
            selected_keys = {tag.casefold() for tag in selected_source_tags}
            selected_source_tags.extend(
                tag
                for tag in source_tags
                if tag.casefold() not in selected_keys
            )
            selected_source_tags = selected_source_tags[:5]
    else:
        selected_source_tags = source_tags

    if output_tags:
        output = AI_HASHTAG_PATTERN.sub("", output)
        output = "\n".join(line.rstrip() for line in output.splitlines())
        output = re.sub(r"[ \t]{2,}", " ", output)
        output = re.sub(r"\n{3,}", "\n\n", output).strip()

    if missing_contacts:
        output = f"{output.rstrip()}\n\n" + "\n".join(missing_contacts)

    final_tags = _unique_preserving_order(selected_source_tags + generated_tags)
    if final_tags:
        output = f"{output.rstrip()}\n\n" + " ".join(final_tags)
    return output.strip()


def extract_protected_html_links(text):
    """Extract Telegram-compatible anchors that must survive AI rewriting."""
    source = html.unescape(text or "")
    links = []
    seen_urls = set()
    for match in AI_ANCHOR_PATTERN.finditer(source):
        href_match = AI_HREF_PATTERN.search(match.group("attrs") or "")
        if not href_match:
            continue

        url = html.unescape(href_match.group("url") or "").strip()
        if not re.match(
            r"^(?:https?://|tg://|t\.me/|telegram\.me/)",
            url,
            re.IGNORECASE,
        ):
            continue

        url_key = url.casefold()
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)
        label = html.unescape(re.sub(r"<[^>]+>", "", match.group("body") or "")).strip()
        if not label:
            continue
        links.append({
            "url": url,
            "url_key": url_key,
            "label": label,
            "html": f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>',
        })
    return links


def _output_anchor_urls(text):
    return {
        item["url_key"]
        for item in extract_protected_html_links(text)
    }


def _wrap_first_unlinked_label(html_text, label, anchor_html):
    parts = re.split(r"(<[^>]+>)", html_text or "")
    anchor_depth = 0
    escaped_label = html.escape(label)

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
                + anchor_html
                + part[position + len(needle):]
            )
            return "".join(parts), True

    return html_text or "", False


def ensure_preserved_html_links(source_text, rewritten_text):
    """Keep every source anchor clickable, while accepting an AI-edited label."""
    protected_links = extract_protected_html_links(source_text)
    if not protected_links:
        return rewritten_text or ""

    output = rewritten_text or ""
    output_urls = _output_anchor_urls(output)
    missing_anchors = []
    for item in protected_links:
        if item["url_key"] in output_urls:
            continue

        output, wrapped = _wrap_first_unlinked_label(
            output,
            item["label"],
            item["html"],
        )
        if wrapped:
            output_urls.add(item["url_key"])
        else:
            missing_anchors.append(item["html"])

    if missing_anchors:
        output = f"{output.rstrip()}\n\n" + "\n".join(missing_anchors)
    return output.strip()


def normalize_ai_output(text: str) -> str:
    """Normalize common model escaping while preserving Telegram HTML tags."""
    text = (text or "").strip()
    if not text:
        return ""

    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = html.unescape(text)
    # Telegram HTML does not support BR. Models sometimes emit BR tags even
    # when asked for plain line breaks, so convert every common variant before
    # the HTML sanitizer can escape it into visible text.
    text = re.sub(
        r"(?:<\s*/?\s*br\s*/?\s*>[ \t]*)+",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        rf"\\+(?=</?(?:{AI_HTML_TAG_NAMES})\b)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_ai_skip_response(text: str) -> bool:
    """Recognize the sentinel and common explanatory no-content responses."""
    normalized = re.sub(r"\s+", "", html.unescape(text or "")).strip()
    if normalized.upper() == AI_SKIP_SENTINEL:
        return True

    exact_empty_markers = {"（空）", "(空)", "空", "输出结果：（空）", "输出结果:(空)"}
    if normalized in exact_empty_markers:
        return True

    no_content_signals = (
        "没有包含任何可提取的有效信息",
        "没有任何可提取的有效信息",
        "无法进行事实性内容的重新创作",
        "原文没有有效文字内容",
    )
    return (
        normalized.startswith("根据您提供的待处理文本")
        and any(signal in normalized for signal in no_content_signals)
    )


def is_rewrite_enabled(task):
    return bool(getattr(task, "ai_rewrite_enabled", False))


def normalize_rewrite_ratio(task):
    try:
        value = int(getattr(task, "ai_rewrite_ratio", 70))
    except (TypeError, ValueError):
        value = 70
    return max(0, min(value, 100))


def build_rewrite_ratio_directive(ratio):
    retained_ratio = 100 - ratio
    if ratio == 0:
        guidance = "不得改写原句，只允许整理换行、空行和 Telegram HTML 排版。"
    elif ratio <= 25:
        guidance = "轻度润色，保留绝大多数原句、用词和信息顺序，只调整少量表达。"
    elif ratio <= 50:
        guidance = "中度改写，保留主要句式和信息顺序，可重写部分表达并优化段落。"
    elif ratio <= 75:
        guidance = "较明显改写，可重新组织多数句子和段落，但仍需保留部分原文表达。"
    else:
        guidance = "高强度改写，可全面重组表达、句式和排版，但不得改变事实或受保护内容。"

    return f"""【改写比例：{ratio}%｜最高优先级】
目标约改写原文 {ratio}% 的表达，约保留 {retained_ratio}% 的原有措辞与结构。{guidance}
该比例控制表达变化强度，不允许据此删除事实、添加事实或修改受保护的链接、数字、时间、地点、价格、联系方式和标签。"""


def build_prompt(task, text, layout=None):
    max_chars = max(100, min(int(getattr(task, "ai_rewrite_max_chars", 800) or 800), 4000))
    rewrite_ratio = normalize_rewrite_ratio(task)
    from db.crud_ai_prompts import get_prompt_content_for_task

    template = get_prompt_content_for_task(
        getattr(task, "ai_prompt_template_id", None),
        getattr(task, "ai_rewrite_prompt", ""),
    ) or DEFAULT_PROMPT
    prompt = (
        template
        .replace("{{max_chars}}", str(max_chars))
        .replace("{{rewrite_ratio}}", str(rewrite_ratio))
        .replace("{{content}}", text)
    )
    if "{{content}}" not in template:
        prompt = f"{prompt}\n\n待处理文本：\n{text}"
    layout = layout or select_layout_variant(task, text)
    metadata_directive = build_source_metadata_directive(text)
    plain_url_directive = build_plain_url_directive(text)
    prompt = (
        f"{AI_OUTPUT_PROTOCOL}\n\n"
        f"{prompt}\n\n"
        f"{build_layout_directive(layout)}\n\n"
        f"{build_rewrite_ratio_directive(rewrite_ratio)}"
    )
    if metadata_directive:
        prompt = f"{prompt}\n\n{metadata_directive}"
    if plain_url_directive:
        prompt = f"{prompt}\n\n{plain_url_directive}"
    return prompt, max_chars


async def _request_completion(api_url, api_key, payload):
    timeout = aiohttp.ClientTimeout(total=AI_REQUEST_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            api_url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                return "", f"HTTP {response.status}"
    content = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        or ""
    )
    return content, None


def _build_request_payload(task, text, model_name, layout):
    prompt, max_chars = build_prompt(task, text, layout=layout)
    return {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.68,
        "max_completion_tokens": build_completion_token_limit(max_chars),
    }, max_chars


def build_completion_token_limit(max_chars):
    return min(
        max(256, int(max_chars or 0) * 2),
        AI_MAX_COMPLETION_TOKENS,
    )


async def rewrite_text(task, text):
    """Return (rewritten_text, error). Never exposes the API key in errors."""
    if not is_rewrite_enabled(task) or not text.strip():
        return text, None

    provider_name = (getattr(task, "ai_rewrite_provider", "grok") or "grok").strip().lower()
    provider = PROVIDERS.get(provider_name)
    if not provider:
        return text, "不支持的 AI 供应商"
    from db.crud_settings import get_ai_provider_config

    saved_config = get_ai_provider_config(provider_name) or {}
    api_key = saved_config.get("api_key") or os.getenv(provider["api_key_env"], "").strip()
    if not api_key:
        return text, f"未配置 {provider['api_key_env']}"

    model_name = (
        (getattr(task, "ai_rewrite_model", "") or "").strip()
        or saved_config.get("model")
        or os.getenv(provider["model_env"], provider["default_model"])
    )
    layout = select_layout_variant(task, text)
    payload, max_chars = _build_request_payload(
        task,
        text,
        model_name,
        layout,
    )
    api_url = os.getenv(provider["base_url_env"], provider["default_url"])
    try:
        logger.info(
            "AI 改写请求 | task_id=%s provider=%s model=%s layout=%s rewrite_ratio=%s input_chars=%s",
            getattr(task, "id", None),
            provider_name,
            model_name,
            layout["key"],
            normalize_rewrite_ratio(task),
            len(text),
        )
        raw_content, request_error = await _request_completion(
            api_url,
            api_key,
            payload,
        )
        if request_error:
            return text, f"{provider_name} 请求失败（{request_error}）"

        rewritten = normalize_ai_output(raw_content)
        if is_ai_skip_response(rewritten):
            logger.info(
                "AI 判定无可发布内容 | task_id=%s provider=%s model=%s",
                getattr(task, "id", None),
                provider_name,
                model_name,
            )
            return "", None
        rewritten = ensure_preserved_html_links(text, rewritten)
        rewritten = ensure_preserved_plain_url_lines(text, rewritten)
        rewritten = ensure_preserved_metadata(text, rewritten)
        if not rewritten:
            return text, f"{provider_name} 未返回可用文本"
        if len(rewritten) > max_chars:
            rewritten = rewritten[:max_chars].rstrip()
            rewritten = ensure_preserved_html_links(text, rewritten)
            rewritten = ensure_preserved_plain_url_lines(text, rewritten)

        initial_similarity = max_recent_output_similarity(task, rewritten)
        if initial_similarity >= AI_STRUCTURE_SIMILARITY_THRESHOLD:
            alternate_layout = select_layout_variant(
                task,
                text,
                excluded_keys={layout["key"]},
            )
            retry_payload, _ = _build_request_payload(
                task,
                text,
                model_name,
                alternate_layout,
            )
            logger.info(
                "AI 排版相似度过高，换版重试 | task_id=%s similarity=%.3f from=%s to=%s",
                getattr(task, "id", None),
                initial_similarity,
                layout["key"],
                alternate_layout["key"],
            )
            retry_raw, retry_error = await _request_completion(
                api_url,
                api_key,
                retry_payload,
            )
            retry_rewritten = normalize_ai_output(retry_raw)
            if (
                not retry_error
                and retry_rewritten
                and not is_ai_skip_response(retry_rewritten)
            ):
                retry_rewritten = ensure_preserved_html_links(
                    text,
                    retry_rewritten,
                )
                retry_rewritten = ensure_preserved_plain_url_lines(
                    text,
                    retry_rewritten,
                )
                retry_rewritten = ensure_preserved_metadata(
                    text,
                    retry_rewritten,
                )
                if len(retry_rewritten) > max_chars:
                    retry_rewritten = retry_rewritten[:max_chars].rstrip()
                    retry_rewritten = ensure_preserved_html_links(
                        text,
                        retry_rewritten,
                    )
                    retry_rewritten = ensure_preserved_plain_url_lines(
                        text,
                        retry_rewritten,
                    )
                retry_similarity = max_recent_output_similarity(
                    task,
                    retry_rewritten,
                )
                if retry_similarity < initial_similarity:
                    rewritten = retry_rewritten
                    layout = alternate_layout
                    initial_similarity = retry_similarity

        remember_rewrite_output(task, rewritten)
        logger.info(
            "AI 改写完成 | task_id=%s provider=%s model=%s layout=%s similarity=%.3f output_chars=%s",
            getattr(task, "id", None),
            provider_name,
            model_name,
            layout["key"],
            initial_similarity,
            len(rewritten),
        )
        return rewritten, None
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.warning(f"{provider_name} 改写失败：{type(exc).__name__}")
        return text, f"{provider_name} 连接超时或不可用"
