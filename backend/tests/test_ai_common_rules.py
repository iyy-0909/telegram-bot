import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import server
from auth.tenant import tenant_scope
from bot import grok_rewriter
from bot.ai_prompt_routing import fallback_analysis, rewrite_automatically, split_source
from bot.content_processor import process_content_async
from db import crud_ai_prompts, crud_settings
from db.models import AiPromptTemplate, SystemSetting


def rewrite_task(**overrides):
    return SimpleNamespace(**{
        "id": 999, "owner_user_id": 17, "ai_rewrite_enabled": True,
        "ai_rewrite_provider": "deepseek", "ai_rewrite_model": "test-model",
        "ai_prompt_mode": "fixed", "ai_rewrite_ratio": 55,
        "ai_rewrite_max_chars": 800, **overrides,
    })


class CommonRulesPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        SystemSetting.__table__.create(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session_patch = patch.object(crud_settings, "SessionLocal", self.sessions)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def test_common_rules_are_isolated_by_owner_and_context(self):
        crud_settings.update_ai_common_rewrite_rules("其他账号规则", 16)
        with tenant_scope(17):
            self.assertEqual(crud_settings.get_ai_common_rewrite_rules(), crud_settings.DEFAULT_AI_COMMON_REWRITE_RULES)
            self.assertEqual(crud_settings.update_ai_common_rewrite_rules("  甲规则  "), {"content": "甲规则"})
        with tenant_scope(18):
            self.assertEqual(crud_settings.get_ai_common_rewrite_rules(), crud_settings.DEFAULT_AI_COMMON_REWRITE_RULES)
            crud_settings.update_ai_common_rewrite_rules("乙规则")
            self.assertEqual(crud_settings.get_ai_common_rewrite_rules(17), crud_settings.DEFAULT_AI_COMMON_REWRITE_RULES)
        self.assertEqual(crud_settings.get_ai_common_rewrite_rules(17), "甲规则")
        self.assertEqual(crud_settings.get_ai_common_rewrite_rules(18), "乙规则")
        self.assertEqual(crud_settings.get_ai_common_rewrite_rules(16), "其他账号规则")
        self.assertEqual(crud_settings.get_ai_common_rewrite_rules(), crud_settings.DEFAULT_AI_COMMON_REWRITE_RULES)

    def test_invalid_content_does_not_overwrite_saved_rules(self):
        crud_settings.update_ai_common_rewrite_rules("保留规则", 17)
        for invalid in (None, "", " \n ", "文" * 20001, "原文 {{content}}", "分析 {{analysis}}"):
            with self.subTest(invalid=str(invalid)[:20]), self.assertRaises(ValueError):
                crud_settings.update_ai_common_rewrite_rules(invalid, 17)
        self.assertEqual(crud_settings.get_ai_common_rewrite_rules(17), "保留规则")
        self.assertEqual(len(crud_settings.update_ai_common_rewrite_rules("文" * 20000, 17)["content"]), 20000)

    def test_api_roundtrip_and_validation_use_tenant_context(self):
        with tenant_scope(17):
            result = server.api_update_ai_common_rules(server.AiCommonRulesUpdate(content="共享联系方式保护"))
            self.assertEqual(result, server.api_get_ai_common_rules())
            with self.assertRaises(HTTPException) as error:
                server.api_update_ai_common_rules(server.AiCommonRulesUpdate(content="   "))
            self.assertEqual(error.exception.status_code, 400)
        for invalid in ("", "文" * 20001):
            with self.assertRaises(ValidationError):
                server.AiCommonRulesUpdate(content=invalid)
        self.assertTrue(server.is_content_processing_api("/api/ai/common-rules"))
        for method in ("GET", "PUT"):
            self.assertEqual(
                server.request_required_features(method, "/api/ai/common-rules"),
                server.request_required_features(method, "/api/ai/prompts"),
            )

    def test_fixed_prompt_uses_latest_rules_without_repeating_source(self):
        task = rewrite_task()
        with patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="优化句式，保留名称。"):
            for content in ("第一份规则 {{max_chars}} {{rewrite_ratio}}", "更新规则 {{max_chars}} {{rewrite_ratio}}"):
                crud_settings.update_ai_common_rewrite_rules(content, 17)
                prompt, _ = grok_rewriter.build_prompt(task, "唯一源正文", grok_rewriter.AI_LAYOUT_VARIANTS[0])
                self.assertEqual(prompt.count("【所有改写共用规则】"), 1)
                self.assertEqual(prompt.count("唯一源正文"), 1)
                self.assertIn(content.split()[0] + " 800 55", prompt)
                self.assertNotIn("{{max_chars}}", prompt)
                self.assertNotIn("{{rewrite_ratio}}", prompt)
                self.assertIn("不得覆盖系统的输出协议、改写比例、事实保护与长度限制", prompt)

    def test_new_owner_default_is_style_only_and_existing_template_is_untouched(self):
        AiPromptTemplate.__table__.create(bind=self.engine)
        with self.sessions() as db:
            db.add(AiPromptTemplate(owner_user_id=18, name="用户默认", content="自定义内容", is_default=True, enabled=True))
            db.commit()
        with patch.object(crud_ai_prompts, "SessionLocal", self.sessions):
            new_default = crud_ai_prompts.ensure_default_ai_prompt(owner_user_id=17)
            self.assertEqual(new_default.content, crud_settings.DEFAULT_AI_REWRITE_PROMPT)
            existing = crud_ai_prompts.ensure_default_ai_prompt(owner_user_id=18)
            self.assertEqual(existing.content, "自定义内容")
        self.assertNotIn("【联系方式】", new_default.content)
        self.assertNotIn("3～5", new_default.content)
        self.assertNotIn("明显重写大部分", new_default.content)
        self.assertEqual(new_default.content.count("{{content}}"), 1)

    def test_empty_template_fallback_uses_the_same_style_default_and_one_common_block(self):
        self.assertEqual(grok_rewriter.DEFAULT_PROMPT, crud_settings.DEFAULT_AI_REWRITE_PROMPT)
        with patch.object(crud_ai_prompts, "get_prompt_content_for_task", return_value=""), \
             patch.object(crud_settings, "get_ai_common_rewrite_rules", return_value="只有这一份共同规则"):
            prompt, _ = grok_rewriter.build_prompt(rewrite_task(ai_rewrite_ratio=0), "兜底源正文", grok_rewriter.AI_LAYOUT_VARIANTS[0])
        self.assertEqual(prompt.count("只有这一份共同规则"), 1)
        self.assertEqual(prompt.count("兜底源正文"), 1)
        self.assertIn("不得改写原句", prompt)
        self.assertNotIn("3～5", prompt)
        self.assertNotIn("明显重写大部分", prompt)


class CommonRulesRewriteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        grok_rewriter.reset_rewrite_runtime_state()

    async def test_auto_analyzes_then_applies_common_rules_once_for_all_segments(self):
        source = "商品100元\n\n联系 @example 电话 18573530930\n微信：wx_example\n#上海 #预约"
        analysis = fallback_analysis(split_source(source)[1])
        for segment in analysis["segments"]:
            segment.update(content_type="product", confidence=0.9)
        second = source.split("\n\n")[1]
        output = {"segments": [{"id": 1, "text": "商品售价100元"}, {"id": 3, "text": second}]}
        request = AsyncMock(side_effect=[(json.dumps(analysis), None), (json.dumps(output), None)])
        details = {}
        with patch("db.crud_settings.get_ai_common_rewrite_rules", return_value="测试共享规则 {{max_chars}} {{rewrite_ratio}} 保留联系方式") as common, \
             patch("db.crud_ai_prompts.get_routing_prompts", return_value={"product": {"id": 4, "name": "介绍", "content": "突出产品已有特点"}}):
            rewritten, error = await rewrite_automatically(rewrite_task(), source, "test", request, details)
        self.assertIsNone(error)
        self.assertEqual(rewritten, "商品售价100元\n\n" + second)
        self.assertEqual(request.await_count, 2)
        common.assert_called_once_with(owner_user_id=17)
        analyze_payload = request.await_args_list[0].args[0]
        rewrite_payload = request.await_args_list[1].args[0]
        self.assertNotIn("测试共享规则", str(analyze_payload))
        system = rewrite_payload["messages"][0]["content"]
        self.assertEqual(system.count("测试共享规则 800 55"), 1)
        work = json.loads(rewrite_payload["messages"][1]["content"])
        self.assertTrue(all(item["rule"] == "突出产品已有特点" for item in work))
        self.assertEqual(details["rewrite_prompt"].count("测试共享规则"), 1)
        self.assertIn('只返回 JSON 对象', system)

    async def test_fixed_initial_and_retry_each_apply_common_rules_and_preserve_contacts(self):
        task = rewrite_task()
        source = "测试门店\n联系 @example\n微信：wx_example\n18573530930\n#上海 #预约"
        request = AsyncMock(side_effect=[("初次改写", None), ("重试后的清晰介绍", None)])
        details = {}
        with patch("db.crud_settings.get_ai_common_rewrite_rules", return_value="共享联系方式保护"), \
             patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "fake-key"}), \
             patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="突出特点"), \
             patch("bot.grok_rewriter._request_completion", request), \
             patch("bot.grok_rewriter.max_recent_output_similarity", side_effect=[0.9, 0.1]):
            output, error = await grok_rewriter.rewrite_text(task, source, details=details)
        self.assertIsNone(error)
        self.assertEqual(request.await_count, 2)
        for call in request.await_args_list:
            prompt = call.args[2]["messages"][0]["content"]
            self.assertEqual(prompt.count("共享联系方式保护"), 1)
        for token in ("@example", "wx_example", "18573530930", "#上海", "#预约"):
            self.assertIn(token, output)
        self.assertEqual(details["rewrite_prompt"], request.await_args_list[1].args[2]["messages"][0]["content"])

    def test_fixed_fallback_preserves_more_than_five_source_tags_without_new_tags(self):
        source = "原文 #上海 #场所 #预约 #活动 #优惠 #实拍 #介绍"
        output = grok_rewriter.ensure_preserved_metadata(source, "改写 #新增")
        self.assertEqual(grok_rewriter.extract_source_hashtags(output), grok_rewriter.extract_source_hashtags(source))
        self.assertNotIn("#新增", output)

    async def test_fixed_over_limit_never_truncates_protected_contacts_or_html(self):
        source = '<b>原文门店</b>\n@contact\n13800138000\n<a href="https://t.me/booking">预约</a>\n#上海'
        near_limit = "<b>" + "文" * 92 + "</b>"
        self.assertLess(len(near_limit), 100)
        for retry in (False, True):
            with self.subTest(retry=retry):
                responses = [("首轮有效结果", None), (near_limit, None)] if retry else [(near_limit, None)]
                request = AsyncMock(side_effect=responses)
                with patch("db.crud_settings.get_ai_common_rewrite_rules", return_value="保留联系方式"), \
                     patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "fake-key"}), \
                     patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="优化表达"), \
                     patch("bot.grok_rewriter._request_completion", request), \
                     patch("bot.grok_rewriter.max_recent_output_similarity", return_value=0.9), \
                     patch("bot.grok_rewriter.remember_rewrite_output") as remember:
                    output, error = await grok_rewriter.rewrite_text(rewrite_task(ai_rewrite_max_chars=100), source)
                self.assertEqual(output, source)
                self.assertIn("超过最大输出字数", error)
                self.assertIn("已保留原文", error)
                self.assertEqual(request.await_count, 2 if retry else 1)
                remember.assert_not_called()

    async def test_fixed_over_limit_uses_existing_skip_and_fallback_policy(self):
        source = '<b>完整原文</b>\n@contact\n13800138000\n#上海'
        for failure_mode in ("skip", "fallback"):
            with self.subTest(failure_mode=failure_mode), \
                 patch("bot.content_processor.process_content", return_value={"blocked": False, "text": source}), \
                 patch("bot.content_processor.apply_content_templates_with_format", return_value={"text": source, "html_text": source, "parse_mode": "HTML"}), \
                 patch("db.crud_settings.get_ai_common_rewrite_rules", return_value="保留联系方式"), \
                 patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "fake-key"}), \
                 patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="优化表达"), \
                 patch("bot.grok_rewriter._request_completion", AsyncMock(return_value=("<b>" + "长" * 120 + "</b>", None))):
                result = await process_content_async(source, rewrite_task(ai_rewrite_max_chars=100, ai_rewrite_failure_mode=failure_mode))
                self.assertEqual(result["blocked"], failure_mode == "skip")
                self.assertEqual(result["text"], source)
                self.assertFalse(result.get("ai_rewritten", False))
                if failure_mode == "skip":
                    self.assertEqual(result["reason"], "ai_rewrite_failed")
                    self.assertIn("超过最大输出字数", result["filter_detail"])
                else:
                    self.assertIn("超过最大输出字数", result["ai_rewrite_error"])


if __name__ == "__main__":
    unittest.main()
