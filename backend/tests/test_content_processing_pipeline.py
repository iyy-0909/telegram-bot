import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.content_processor import (
    apply_content_templates,
    apply_content_templates_with_format,
    compose_content_templates_html,
    process_content_async,
)


class FooterTemplateSpacingTests(unittest.TestCase):
    def test_footer_keeps_blank_line_by_default(self):
        task = SimpleNamespace()

        with patch(
            "bot.content_processor.get_template_part",
            side_effect=lambda _task, template_type: (
                "底部内容" if template_type == "footer" else ""
            ),
        ):
            result = apply_content_templates("正文", task)

        self.assertEqual(result, "正文\n\n底部内容")

    def test_footer_can_follow_content_without_blank_line(self):
        task = SimpleNamespace(footer_leading_blank_line=False)

        with patch(
            "bot.content_processor.get_template_part",
            side_effect=lambda _task, template_type: (
                "底部内容" if template_type == "footer" else ""
            ),
        ):
            result = apply_content_templates("正文", task)

        self.assertEqual(result, "正文\n底部内容")

    def test_html_recompose_preserves_footer_spacing_setting(self):
        task = SimpleNamespace(footer_leading_blank_line=False)

        with patch(
            "bot.content_processor.get_template_part",
            side_effect=lambda _task, template_type: (
                '<a href="https://t.me/contact_bot">联系经理人</a>'
                if template_type == "footer"
                else ""
            ),
        ):
            result = apply_content_templates_with_format(
                "<b>正文</b>",
                task,
                text_is_html=True,
            )

        recomposed = compose_content_templates_html(result, "<b>处理后的正文</b>")

        self.assertEqual(
            recomposed,
            '<b>处理后的正文</b>\n'
            '<a href="https://t.me/contact_bot">联系经理人</a>',
        )


class ContentProcessingPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_content_processing_then_templates_then_ai(self):
        task = SimpleNamespace(
            ai_rewrite_enabled=True,
            ai_rewrite_failure_mode="fallback",
        )
        calls = []

        def process_content(raw_text, current_task, apply_templates=True):
            calls.append(("content", raw_text, apply_templates))
            self.assertIs(current_task, task)
            return {"blocked": False, "text": "清洗后的正文"}

        async def rewrite_text(current_task, text):
            calls.append(("ai", text))
            self.assertIs(current_task, task)
            return (
                '<b>AI 改写完整内容</b>\n'
                '<a href="https://t.me/contact_bot">联系经理人</a>',
                None,
            )

        def apply_templates(text, current_task, text_is_html=False):
            calls.append(("templates", text, text_is_html))
            self.assertIs(current_task, task)
            return {
                "text": (
                    f"<b>Head</b>\n{text}\n"
                    '<a href="https://t.me/contact_bot">联系经理人</a>'
                ),
                "plain_text": "Head\n清洗后的正文\n联系经理人",
                "parse_mode": "HTML",
                "html_text": (
                    f"<b>Head</b>\n{text}\n"
                    '<a href="https://t.me/contact_bot">联系经理人</a>'
                ),
                "format_level": "template_html",
            }

        with (
            patch("bot.content_processor.process_content", side_effect=process_content),
            patch("bot.grok_rewriter.is_rewrite_enabled", return_value=True),
            patch("bot.grok_rewriter.rewrite_text", new=AsyncMock(side_effect=rewrite_text)),
            patch(
                "bot.content_processor.apply_content_templates_with_format",
                side_effect=apply_templates,
            ),
        ):
            result = await process_content_async("原始正文", task)

        self.assertEqual(
            calls,
            [
                ("content", "原始正文", False),
                ("templates", "清洗后的正文", False),
                (
                    "ai",
                    "<b>Head</b>\n清洗后的正文\n"
                    '<a href="https://t.me/contact_bot">联系经理人</a>',
                ),
            ],
        )
        self.assertEqual(
            result["text"],
            "<b>AI 改写完整内容</b>\n"
            '<a href="https://t.me/contact_bot">联系经理人</a>',
        )
        self.assertTrue(result["ai_rewritten"])
        self.assertEqual(result["parse_mode"], "HTML")


if __name__ == "__main__":
    unittest.main()
