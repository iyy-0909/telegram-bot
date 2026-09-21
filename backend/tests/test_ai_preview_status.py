import unittest
from unittest.mock import patch

from api.server import AiRewritePreview, api_ai_rewrite_preview
from auth.tenant import tenant_scope


class AiPreviewStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_or_unchanged_preview_never_labels_original_as_a_result(self):
        for status in ("unchanged", "failed"):
            with self.subTest(status=status):
                async def rewrite(_task, text, *, details):
                    details.update(rewrite_status=status, rewrite_attempts=2,
                                   rewrite_error="第 2 段未保留原文数字")
                    return text, "未生成有效改写，请检查原文数字"

                with patch("bot.grok_rewriter.rewrite_text", side_effect=rewrite), tenant_scope(1):
                    response = await api_ai_rewrite_preview(AiRewritePreview(text="原文100元"))
                self.assertEqual(response["text"], "")
                self.assertTrue(response["error"])
                self.assertEqual(response["rewrite_status"], status)
                self.assertEqual(response["rewrite_attempts"], 2)

    async def test_intentional_preservation_has_explicit_status_and_reason(self):
        async def rewrite(_task, text, *, details):
            details.update(rewrite_status="preserved", rewrite_reason="分析识别为无需整理的固定信息，按规则保留原文")
            return text, None

        with patch("bot.grok_rewriter.rewrite_text", side_effect=rewrite), tenant_scope(1):
            response = await api_ai_rewrite_preview(AiRewritePreview(text="原文100元", rewrite_ratio=0))
        self.assertEqual(response["text"], "原文100元")
        self.assertIsNone(response["error"])
        self.assertEqual(response["rewrite_status"], "preserved")
        self.assertIn("固定信息", response["rewrite_reason"])

    async def test_changed_preview_passes_diagnostics_without_losing_output(self):
        async def rewrite(task, _text, *, details):
            self.assertEqual(task.owner_user_id, 1)
            details.update(rewrite_status="changed", analysis_fallback=True,
                           analysis_error="分析返回的段落编号不匹配")
            return "每份100元，欢迎了解。", None

        with patch("bot.grok_rewriter.rewrite_text", side_effect=rewrite), tenant_scope(1):
            response = await api_ai_rewrite_preview(AiRewritePreview(text="价格100元"))
        self.assertEqual(response["rewrite_status"], "changed")
        self.assertEqual(response["text"], "每份100元，欢迎了解。")
        self.assertTrue(response["analysis_fallback"])
        self.assertIn("段落编号", response["analysis_error"])


if __name__ == "__main__":
    unittest.main()
