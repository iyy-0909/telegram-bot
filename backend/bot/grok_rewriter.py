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
from db.crud_settings import DEFAULT_AI_REWRITE_PROMPT


DEFAULT_PROMPT = DEFAULT_AI_REWRITE_PROMPT

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
        "instruction": """保留原文内容，用简短自然段形成清楚的阅读层次。标题适当加粗，较长内容可用贴合内容的表情引导区块；同一主题中可调整信息位置，关联条件须放在一起。无需把每句话都列成清单，不补写导语或收尾；联系方式完整独立成行。""",
    },
    {
        "key": "info_card",
        "name": "信息卡片",
        "instruction": """根据整篇已有信息形成紧凑信息卡：标题加粗，同一对象的介绍、费用、地址等分别成组，区块之间留一行空白。栏目名适度加粗并配一个相关表情，费用项目用 ▫️ 或 • 逐行紧凑排列。可以提炼已有内容的中性栏目名，不能为凑卡片补出不存在的信息。""",
    },
    {
        "key": "scene",
        "name": "自然分段",
        "instruction": """按完整文案的语义分组，把同一主题的相关内容放在一起，用自然段与空行区分层次。标题和少量栏目适当加粗，表情用于提示区块。保留原句意思和宣传力度，只按本次比例少量润色，不补写场景、读者需求、开场或收尾。""",
    },
    {
        "key": "checklist",
        "name": "重点清单",
        "instruction": """原文存在并列内容时，用 ▫️ 或 • 整理原有条目，并把同一主题的条目归到对应栏目。栏目可用一个相关表情和加粗名称引导，清单内部保持紧凑。保留每条原意，不新增导语、总结或信息条目，不把连续叙述强拆为清单，不新增数字编号。""",
    },
    {
        "key": "qa",
        "name": "信息分组",
        "instruction": """重新梳理同一主题中的介绍、费用、地点、通知等已有信息，归入清楚的区块。可使用贴合已有内容的中性栏目名、相关表情和适度加粗；不混合不同对象，不拆散费用与条件，不新增问答、情境或解释。联系方式与链接的受保护行完整保留。""",
    },
    {
        "key": "editorial",
        "name": "重点加粗",
        "instruction": """保留原文内容，重点突出标题、栏目名及少量关键字段，用适量区块表情和空行帮助扫读。同一主题可以重新分组，但不添加编辑评价、推荐理由、总结或新的宣传措辞；不要把整段全部加粗。""",
    },
)

AI_ANTI_TEMPLATE_PROTOCOL = """【反模板要求】
本次任务以保留原文内容、整理排版和表情为主，不进行独立创作或大幅重写。该要求优先于配置提示词中的场景开头、问答、短评和创作要求。
本次版式由程序指定，只适用于原文已有内容；先理解整篇，再对同一主题分组和安排区块，不必沿用原来的段落位置。原文不适合某种排版时保持自然结构，不得为套用版式添加或删除信息。
栏目名称可以从已有内容中提炼，例如已有介绍、费用、地址时可用“场所介绍”“消费明细”“地址”。禁止机械使用“核心亮点”“适合场景”等与内容不符的小标题，不强迫每段都有栏目；0% 时不新增栏目文字。
禁止反复使用“氛围感拉满”“这里都能接住”“提前预约更省心”“夜已深，就差你”等套话。
装饰性表情用于引导区块，按长度通常选用 2—5 个，短文可更少；评分符号与 ▫️ 等小型列表符号不计入该建议。标题和栏目名适度加粗，不整段加粗、不在每句堆表情；表示评分、数量、状态或条件的表情不得改变含义与数量。
不得新增开场、收尾、场景、问答、观点、卖点或承诺，不得跨主题重组、改变宣传力度或删除原有有效信息。"""

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
按本次版式和原文内容安排区块，不为凑齐“标题＋亮点＋场景＋营业信息＋联系”结构新增信息。"""


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

    if output_tags:
        output = AI_HASHTAG_PATTERN.sub("", output)
        output = "\n".join(line.rstrip() for line in output.splitlines())
        output = re.sub(r"[ \t]{2,}", " ", output)
        output = re.sub(r"\n{3,}", "\n\n", output).strip()

    if missing_contacts:
        output = f"{output.rstrip()}\n\n" + "\n".join(missing_contacts)

    if source_tags:
        output = f"{output.rstrip()}\n\n" + " ".join(source_tags)
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
    if ratio == 0:
        guidance = "保持原文措辞，不得改写原句或新增栏目文字；只整理换行、空行、Telegram HTML 排版和装饰性表情，不增删原有内容。"
    elif ratio <= 25:
        guidance = "轻度整理：以换行、留白和少量装饰性表情调整为主，保持原句，仅在不改变原意时轻微润色。"
    elif ratio <= 50:
        guidance = "适度整理：将同一主题的相关内容归为区块，以标题、栏目加粗和相关表情区分层次，最多对不通顺的少量措辞轻微润色。"
    elif ratio <= 75:
        guidance = "明显整理：按整篇已有内容重新安排同主题区块，用相关表情引导栏目、标题和栏目适度加粗；并列信息用紧凑列表展示，只允许少量轻微润色。"
    else:
        guidance = "充分整理：围绕完整文案安排同主题信息，明显优化区块顺序、段间留白、紧凑列表、标题加粗和栏目表情；保持主要内容、表达意思和宣传力度，只允许少量轻微润色。"

    return f"""【改写比例：{ratio}%｜最高优先级】
该比例控制排版与装饰性表情的整理程度，不代表文字替换比例，也不是要求重新创作。{guidance}
任何比例都必须保留原文的大致内容、原意和信息，不得大幅改写、补写场景、观点、导语或结尾。
不得删除事实、添加事实或修改受保护的链接、数字、时间、地点、价格、联系方式和标签。评分、数量、状态或条件类表情必须保留原意与数量。"""


def build_common_rewrite_rules(task, max_chars):
    from db.crud_settings import get_ai_common_rewrite_rules

    content = get_ai_common_rewrite_rules(
        owner_user_id=getattr(task, "owner_user_id", None),
    )
    values = {
        "max_chars": str(max_chars),
        "rewrite_ratio": str(normalize_rewrite_ratio(task)),
    }
    # Source content is provided separately, never interpolated into common rules.
    content = re.sub(r"\{\{(max_chars|rewrite_ratio)\}\}", lambda match: values[match[1]], content)
    return (
        "【所有改写共用规则】\n"
        "以下共同规则适用于全文，优先于分类或固定提示词中冲突的写法；"
        "不得覆盖系统的输出协议、改写比例、事实保护与长度限制。\n"
        + content
    )


def build_prompt(task, text, layout=None):
    max_chars = max(100, min(int(getattr(task, "ai_rewrite_max_chars", 800) or 800), 4000))
    rewrite_ratio = normalize_rewrite_ratio(task)
    from db.crud_ai_prompts import get_prompt_content_for_task

    template = get_prompt_content_for_task(
        getattr(task, "ai_prompt_template_id", None),
        getattr(task, "ai_rewrite_prompt", ""),
        owner_user_id=getattr(task, "owner_user_id", None),
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
        f"{build_common_rewrite_rules(task, max_chars)}\n\n"
        f"{build_layout_directive(layout)}\n\n"
        f"{build_rewrite_ratio_directive(rewrite_ratio)}\n\n"
        f"【长度与完整性】最终输出不得超过 {max_chars} 字符。不得为了缩短篇幅删除原有有效信息、事实或联系方式；空间不足时减少装饰、额外标题和空行。"
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


async def rewrite_text(task, text, *, details=None):
    """Return (rewritten_text, error). Never exposes the API key in errors."""
    if not is_rewrite_enabled(task) or not text.strip():
        return text, None

    configured_provider = (getattr(task, "ai_rewrite_provider", "") or "").strip().lower()
    if configured_provider in PROVIDERS:
        provider_name = configured_provider
    else:
        from db.crud_settings import get_default_ai_provider

        provider_name = get_default_ai_provider(
            owner_user_id=getattr(task, "owner_user_id", None),
        )
    provider = PROVIDERS.get(provider_name)
    if not provider:
        return text, "不支持的 AI 供应商"
    from db.crud_settings import get_ai_provider_config

    saved_config = get_ai_provider_config(
        provider_name,
        owner_user_id=getattr(task, "owner_user_id", None),
    ) or {}
    api_key = saved_config.get("api_key") or os.getenv(provider["api_key_env"], "").strip()
    if not api_key:
        return text, f"未配置 {provider['api_key_env']}"

    model_name = (
        (getattr(task, "ai_rewrite_model", "") or "").strip()
        or saved_config.get("model")
        or os.getenv(provider["model_env"], provider["default_model"])
    )
    if getattr(task, "ai_prompt_mode", "fixed") == "auto":
        from bot.ai_prompt_routing import rewrite_automatically
        api_url = os.getenv(provider["base_url_env"], provider["default_url"])
        async def request(payload):
            return await _request_completion(api_url, api_key, payload)
        try:
            return await rewrite_automatically(task, text, model_name, request, details)
        except Exception:
            return text, f"{provider_name} 自动改写请求失败"

    layout = select_layout_variant(task, text)
    payload, max_chars = _build_request_payload(
        task,
        text,
        model_name,
        layout,
    )
    if details is not None:
        details["rewrite_prompt"] = payload["messages"][0]["content"]
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
            return text, "改写结果超过最大输出字数，已保留原文供失败策略处理"
        from bot.ai_prompt_routing import _expression_fingerprint, validate_rewrite

        try:
            validate_rewrite(text, rewritten, [])
            if normalize_rewrite_ratio(task) == 0 and _expression_fingerprint(text) != _expression_fingerprint(rewritten):
                raise ValueError("改写比例为 0% 时只能整理排版和装饰性表情，不得改变原文措辞")
        except ValueError as exc:
            return text, f"改写校验未通过：{exc}"

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
                    if details is not None:
                        details["rewrite_prompt"] = retry_payload["messages"][0]["content"]
                    return text, "改写结果超过最大输出字数，已保留原文供失败策略处理"
                try:
                    validate_rewrite(text, retry_rewritten, [])
                    if normalize_rewrite_ratio(task) == 0 and _expression_fingerprint(text) != _expression_fingerprint(retry_rewritten):
                        raise ValueError("改写比例为 0% 时只能整理排版和装饰性表情，不得改变原文措辞")
                except ValueError as exc:
                    logger.warning("AI 换版重试未通过事实校验，保留首次结果 | task_id=%s reason=%s", getattr(task, "id", None), exc)
                    retry_rewritten = rewritten
                retry_similarity = max_recent_output_similarity(
                    task,
                    retry_rewritten,
                )
                if retry_similarity < initial_similarity:
                    rewritten = retry_rewritten
                    layout = alternate_layout
                    initial_similarity = retry_similarity
                    if details is not None:
                        details["rewrite_prompt"] = retry_payload["messages"][0]["content"]

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
