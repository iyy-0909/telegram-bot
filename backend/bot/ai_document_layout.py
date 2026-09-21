"""Assemble layouts without losing source provenance or topic boundaries."""
import html
import re


def assemble_document(parts, source, analysis, candidates, layout, ratio):
    if layout is None:
        result = list(parts)
        for segment in source:
            result[segment["id"] - 1] = candidates[segment["id"]]
        return "".join(result)
    if not isinstance(layout, dict):
        raise ValueError("全文排版方案格式无效")
    order, separators = layout.get("order"), layout.get("separators")
    expected = [item["id"] for item in source]
    if (not isinstance(order, list) or any(type(ident) is not int for ident in order)
            or len(order) != len(expected) or set(order) != set(expected)):
        raise ValueError("全文排版必须恰好包含所有原段落，不能遗漏或重复")
    if (not isinstance(separators, list) or len(separators) != len(order) - 1
            or any(value not in ("\n", "\n\n") for value in separators)):
        raise ValueError("全文排版分隔必须与段落一一对应，只能使用一个或两个换行")
    items = {item["id"]: item for item in analysis["segments"]}
    group = {ident: items[ident].get("layout_group", ident) for ident in expected}
    if [group[ident] for ident in order] != [group[ident] for ident in expected]:
        raise ValueError("不能跨不同对象或主题移动段落、费用和联系方式")
    for group_id in set(group.values()):
        original_order = [ident for ident in expected if group[ident] == group_id]
        new_order = [ident for ident in order if group[ident] == group_id]
        sequential = any(items[ident]["content_type"] in ("tutorial", "story") for ident in original_order)
        if (ratio == 0 or sequential) and original_order != new_order:
            raise ValueError("仅排版模式、教程步骤及故事叙述必须保持原有顺序")
    return "".join(candidates[ident] + (separators[index] if index < len(separators) else "")
                   for index, ident in enumerate(order))


def layout_quality_issue(source, output, ratio):
    """Check observable presentation for long promotional posts, not word novelty."""
    source_plain = html.unescape(re.sub(r"<[^>]+>", "", source))
    source_lines = [line for line in source_plain.splitlines() if line.strip()]
    if ratio < 35 or len(source_plain) < 120 or len(source_lines) < 6 or len(re.split(r"\n\s*\n", source_plain)) < 3:
        return None
    bold = re.findall(r"<(?:b|strong)>(.*?)</(?:b|strong)>", output, flags=re.I | re.S)
    headings = [html.unescape(re.sub(r"<[^>]+>", "", value)).strip() for value in bold]
    headings = [value for value in headings if "\n" not in value and 1 <= len(value) <= 48]
    plain = html.unescape(re.sub(r"<[^>]+>", "", output))
    section_icons = "🎤💰📍📅📌🎁🏠🏢🏪🎉📣📢📝📋💡🔎📖🎯🛎☎📞📱📩📨🕒⏰💬🎬🎵🎶🍷🍸🏷🧾🗓📊⚠"
    icon_lines = [line for line in plain.splitlines() if line.strip()
                  and any(char in section_icons for char in line[:6])]
    missing = []
    if len(headings) < 2:
        missing.append("为主标题和信息栏目合理加粗，至少两处短标题，不能整段全加粗")
    if len(icon_lines) < 2:
        missing.append("用符合内容的表情区分至少两个信息区块，例如介绍、费用、地址；评分和列表符号不算区块表情")
    if len(re.split(r"\n\s*\n", plain.strip())) < 3:
        missing.append("主标题、介绍、费用、地址等独立区块之间空一行，区块内部的条目紧凑排列；请相应设置 layout.separators")
    return "全文排版尚未完成：" + "；".join(missing) if missing else None
