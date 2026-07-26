import json

from db.crud_templates import create_template_rule, get_template_rules


DEMO_PREFIX = "UI演示"
TYPE_LABELS = {
    "contact": "联系方式",
    "filter": "关键词过滤",
    "head": "头部模板",
    "body": "正文模板",
    "footer": "底部模板",
    "link": "链接配置",
}


def demo_content(rule_type: str, index: int) -> str:
    if rule_type == "contact":
        return json.dumps(
            {
                "remove_phone": index % 2 == 0,
                "remove_links": True,
                "remove_usernames": index % 3 != 0,
                "remove_keywords": True,
                "keywords": [f"演示词{index}", "广告", "联系"],
            },
            ensure_ascii=False,
        )
    if rule_type == "filter":
        return f"演示过滤词{index}\n测试广告{index}\n无效内容{index}"
    if rule_type == "link":
        return json.dumps(
            {
                "source_message_link": "target_link",
                "target_channel_link": "keep",
                "external_channel_link": "downgrade",
                "username_link": "delete",
                "bot_link": "keep",
                "external_url": "keep",
                "invite_link": "delete",
                "other_link": "downgrade",
            },
            ensure_ascii=False,
        )
    if rule_type == "head":
        return f"<b>演示头部 {index}</b>\n今日频道内容"
    if rule_type == "body":
        return f"<b>演示正文 {index}</b>\n这是用于检查表格布局的正文内容。"
    return f"<b>演示底部 {index}</b>\n联系频道管理员获取更多信息。"


def seed_type(rule_type: str, count: int = 20) -> int:
    prefix = f"{DEMO_PREFIX}·{TYPE_LABELS[rule_type]}·"
    groups = [
        row.get("group")
        for row in get_template_rules()
        if row.get("group") is not None
    ]
    existing_names = {
        str(group.name or "")
        for group in groups
        if group.type == rule_type
        and str(group.name or "").startswith(prefix)
    }
    created = 0

    for index in range(1, count + 1):
        name = f"{prefix}{index:02d}"
        if name in existing_names:
            continue
        create_template_rule(
            {
                "type": rule_type,
                "name": name,
                "enabled": index % 5 != 0,
                "items": [
                    {
                        "name": f"演示内容 {index:02d}",
                        "content": demo_content(rule_type, index),
                        "enabled": True,
                        "weight": 1,
                    }
                ],
            }
        )
        created += 1
    return created


def main():
    total = 0
    for rule_type in TYPE_LABELS:
        created = seed_type(rule_type)
        total += created
        print(f"{rule_type}: created {created}")
    print(f"ui demo rules complete: created {total}")


if __name__ == "__main__":
    main()
