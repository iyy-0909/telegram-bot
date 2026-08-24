import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot.content_processor import (
    apply_content_templates_with_format,
    compose_content_templates_html,
)
from bot.entity_formatter import restore_source_links_as_html
from bot.link_rules import normalize_link_rules


MessageEntityTextUrl = type("MessageEntityTextUrl", (), {})


def text_link_entity(text, label, url, start_at=0):
    start = text.index(label, start_at)
    entity = MessageEntityTextUrl()
    entity.offset = len(text[:start].encode("utf-16-le")) // 2
    entity.length = len(label.encode("utf-16-le")) // 2
    entity.url = url
    return entity


def source_message(text, links):
    entities = []
    search_start = 0
    for label, url in links:
        entity = text_link_entity(text, label, url, search_start)
        entities.append(entity)
        search_start = text.index(label, search_start) + len(label)
    return SimpleNamespace(message=text, entities=entities)


def listener_task(
    group_id=15,
    *,
    remove_contact_lines=False,
    contact_group_id=None,
):
    return SimpleNamespace(
        id=7,
        source_channel="@source_channel",
        selected_link_template_group_id=group_id,
        remove_contact_lines=remove_contact_lines,
        selected_contact_template_group_id=contact_group_id,
    )


class RestoreSourceLinksTests(unittest.TestCase):
    def test_contact_cleanup_prevents_hidden_contact_link_from_being_restored(self):
        label = "认准杭州第一靠谱"
        source_url = "https://t.me/hzktvbot"
        source = source_message(
            f"联系点击➡️：{label}",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "keep"})
        contact_rules = {
            "remove_phone": True,
            "remove_links": True,
            "remove_usernames": True,
            "remove_keywords": True,
            "keywords": ["联系", "点击"],
            "custom_regex": [],
        }

        with (
            patch("bot.entity_formatter.get_link_rules", return_value=rules),
            patch(
                "bot.entity_formatter.get_contact_rule_config",
                return_value=contact_rules,
            ),
        ):
            restored = restore_source_links_as_html(
                source,
                "<b>互动体验场</b>\n\n正文内容。",
                task=listener_task(remove_contact_lines=True),
                target="@target_channel",
            )

        self.assertNotIn(label, restored)
        self.assertNotIn(source_url, restored)
        self.assertNotIn("<a ", restored)

    def test_contact_cleanup_disabled_still_keeps_clickable_contact_link(self):
        label = "认准杭州第一靠谱"
        source_url = "https://t.me/hzktvbot"
        source = source_message(
            f"联系点击➡️：{label}",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "delete"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                "<b>互动体验场</b>\n\n正文内容。",
                task=listener_task(remove_contact_lines=False),
                target="@target_channel",
            )

        self.assertIn(
            f'<a href="{source_url}">{label}</a>',
            restored,
        )

    def test_contact_cleanup_respects_custom_rule_that_keeps_links_and_keywords(self):
        label = "认准杭州第一靠谱"
        source_url = "https://t.me/hzktvbot"
        source = source_message(
            f"联系点击➡️：{label}",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "delete"})
        contact_rules = {
            "remove_phone": True,
            "remove_links": False,
            "remove_usernames": True,
            "remove_keywords": False,
            "keywords": ["联系", "点击"],
            "custom_regex": [],
        }

        with (
            patch("bot.entity_formatter.get_link_rules", return_value=rules),
            patch(
                "bot.entity_formatter.get_contact_rule_config",
                return_value=contact_rules,
            ),
        ):
            restored = restore_source_links_as_html(
                source,
                "<b>互动体验场</b>\n\n正文内容。",
                task=listener_task(remove_contact_lines=True),
                target="@target_channel",
            )

        self.assertIn(
            f'<a href="{source_url}">{label}</a>',
            restored,
        )

    def test_keep_rule_wraps_visible_label_in_ai_html(self):
        source = source_message(
            "推荐查看 场所A 的详细介绍",
            [("场所A", "https://t.me/OtherChannel/123")],
        )
        rules = normalize_link_rules({"external_channel_link": "keep"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                "<b>今日推荐</b>\n\n场所A 的环境和配置都值得了解。",
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn(
            '<a href="https://t.me/OtherChannel/123">场所A</a>',
            restored,
        )

    def test_ai_omitted_links_are_appended_as_compact_link_list(self):
        source = source_message(
            "场所A 场所B",
            [
                ("场所A", "https://t.me/OtherChannel/123"),
                ("场所B", "https://example.com/detail?id=2&from=tg"),
            ],
        )
        rules = normalize_link_rules({
            "external_channel_link": "keep",
            "external_url": "keep",
        })

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                "<b>两家场所快速参考</b>\n\n可根据位置和预算选择。",
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn("<b>🔗 相关链接</b>", restored)
        self.assertIn(
            '<a href="https://t.me/OtherChannel/123">场所A</a>',
            restored,
        )
        self.assertIn(
            '<a href="https://example.com/detail?id=2&amp;from=tg">场所B</a>',
            restored,
        )

    def test_downgrade_rule_keeps_plain_label_without_anchor(self):
        source = source_message(
            "推荐查看 场所A",
            [("场所A", "https://t.me/OtherChannel/123")],
        )
        rules = normalize_link_rules({"external_channel_link": "downgrade"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                "<b>推荐</b>\n\n场所A",
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn("场所A", restored)
        self.assertNotIn("<a ", restored)

    def test_downgrade_rule_restores_contact_label_omitted_by_ai(self):
        label = "长沙最靠谱职业经理人"
        source = source_message(
            f"驻场联系: {label}\n24小时在线预订",
            [(label, "https://t.me/source_contact")],
        )
        rules = normalize_link_rules({"external_channel_link": "downgrade"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                "<b>长沙夜生活新玩法</b>\n\n• 驻场联系：\n• 24小时在线预订",
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn(
            f'• 驻场联系：<a href="https://t.me/source_contact">{label}</a>',
            restored,
        )

    def test_contact_link_skips_downgrade_and_keeps_ai_edited_label(self):
        source_label = "南京最靠谱职业经理人"
        source_url = "https://t.me/nanjingktvyule_bot"
        source = source_message(
            f"联系点击➡️：{source_label}",
            [(source_label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "downgrade"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                (
                    "联系点击➡️："
                    f'<a href="{source_url}">南京专业对接经理</a>'
                ),
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn(
            f'<a href="{source_url}">南京专业对接经理</a>',
            restored,
        )

    def test_contact_link_skips_explicit_bot_delete_rule(self):
        label = "南京最靠谱职业经理人"
        source_url = "https://t.me/nanjingktvyule_bot"
        source = source_message(
            f"联系点击➡️：{label}",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "delete"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                f'联系点击➡️：<a href="{source_url}">{label}</a>',
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn(
            f'<a href="{source_url}">{label}</a>',
            restored,
        )

    def test_task_7_contact_delete_rule_wraps_ai_edited_plain_label(self):
        source_label = "南京最靠谱职业经理人"
        edited_label = "南京专业对接经理"
        source_url = "https://t.me/nanjingktvyule_bot"
        source = source_message(
            f"联系点击➡️：{source_label}",
            [(source_label, source_url)],
        )
        rules = normalize_link_rules({
            "username_link": "delete",
            "bot_link": "delete",
        })

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                f"联系点击➡️：{edited_label}",
                task=listener_task(),
                target="@target_channel",
            )

        self.assertEqual(
            restored,
            f'联系点击➡️：<a href="{source_url}">{edited_label}</a>',
        )
        self.assertNotIn(source_label, restored)

    def test_contact_link_is_moved_out_of_a_long_prose_line(self):
        label = "认准杭州第一靠谱"
        source_url = "https://t.me/hzktvbot"
        source = source_message(
            f"杭州本地客服在线，咨询不收费，{label}。",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "delete"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                (
                    "聚会、唱歌、喝酒，提前预定更好安排。"
                    "杭州本地客服在线，咨询不收费，"
                    f'<a href="{source_url}">{label}</a>。'
                ),
                task=listener_task(),
                target="@target_channel",
            )

        self.assertIn("杭州本地客服在线，咨询不收费。\n", restored)
        self.assertIn(
            f'\n<a href="{source_url}">{label}</a>。',
            restored,
        )

    def test_short_contact_prefix_stays_with_link_and_suffix_moves_next(self):
        label = "长沙最靠谱职业经理人"
        source_url = "https://t.me/changshaktv1_bot"
        source = source_message(
            f"驻场联系：{label}，24小时在线预订",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "delete"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                (
                    "驻场联系："
                    f'<a href="{source_url}">{label}</a>，24小时在线预订'
                ),
                task=listener_task(),
                target="@target_channel",
            )

        self.assertEqual(
            restored,
            (
                "驻场联系："
                f'<a href="{source_url}">{label}</a>\n'
                "24小时在线预订"
            ),
        )

    def test_non_contact_bot_link_still_obeys_delete_rule(self):
        label = "打开工具机器人"
        source_url = "https://t.me/example_helper_bot"
        source = source_message(
            f"推荐工具：{label}",
            [(label, source_url)],
        )
        rules = normalize_link_rules({"bot_link": "delete"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                f'推荐工具：<a href="{source_url}">{label}</a>',
                task=listener_task(),
                target="@target_channel",
            )

        self.assertNotIn(label, restored)
        self.assertNotIn(source_url, restored)

    def test_downgrade_rule_appends_plain_label_when_context_is_gone(self):
        label = "长沙最靠谱职业经理人"
        source = source_message(
            label,
            [(label, "https://t.me/source_contact")],
        )
        rules = normalize_link_rules({"external_channel_link": "downgrade"})

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored = restore_source_links_as_html(
                source,
                "<b>长沙夜生活新玩法</b>",
                task=listener_task(),
                target="@target_channel",
            )

        self.assertTrue(restored.endswith(label))
        self.assertNotIn("https://t.me/source_contact", restored)
        self.assertNotIn("<a ", restored)

    def test_without_link_template_source_link_is_kept(self):
        source = source_message(
            "查看 场所A",
            [("场所A", "https://example.com/a")],
        )

        with patch("bot.entity_formatter.get_link_rules", return_value=None):
            restored = restore_source_links_as_html(
                source,
                "查看场所A",
                task=listener_task(group_id=None),
                target="@target_channel",
            )

        self.assertIn('<a href="https://example.com/a">场所A</a>', restored)

    def test_contact_source_and_template_links_are_not_downgraded(self):
        label = "驻场联系：长沙最靠谱职业经理人"
        source = source_message(
            label,
            [(label, "https://t.me/source_contact")],
        )
        rules = normalize_link_rules({"external_channel_link": "downgrade"})
        task = listener_task()

        def template_part(_task, template_type):
            if template_type == "footer":
                return f'<a href="https://t.me/template_contact">{label}</a>'
            return ""

        with patch("bot.content_processor.get_template_part", side_effect=template_part):
            formatted = apply_content_templates_with_format(
                "<b>AI 改写正文</b>",
                task,
                text_is_html=True,
            )

        with patch("bot.entity_formatter.get_link_rules", return_value=rules):
            restored_content = restore_source_links_as_html(
                source,
                formatted["content_html"],
                task=task,
                target="@target_channel",
            )

        final_html = compose_content_templates_html(formatted, restored_content)

        self.assertIn("<b>AI 改写正文</b>", final_html)
        self.assertIn(
            f'<a href="https://t.me/template_contact">{label}</a>',
            final_html,
        )
        self.assertIn("https://t.me/source_contact", final_html)


if __name__ == "__main__":
    unittest.main()
