import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from auth.tenant import tenant_scope
from bot.ai_prompt_routing import fallback_analysis, split_source, validate_analysis, rewrite_automatically
from bot.content_processor import process_content_async
from db import crud_ai_prompts
from db.crud_settings import DEFAULT_AI_COMMON_REWRITE_RULES
from db.database import Base
from db.models import AiPromptTemplate
from migrate_ai_prompt_routing import migrate


def task(**kwargs):
    return SimpleNamespace(**{"id": 1, "owner_user_id": 1, "ai_rewrite_enabled": True,
                             "ai_prompt_mode": "auto", "ai_rewrite_max_chars": 800,
                             "ai_rewrite_ratio": 70, "ai_rewrite_failure_mode": "fallback", **kwargs})


def analysis_for(source, category="product", action="rewrite", facts=None):
    data = fallback_analysis(split_source(source)[1])
    for item in data["segments"]:
        item.update(content_type=category, confidence=0.9, action=action, facts=facts or [])
    return json.dumps(data, ensure_ascii=False)


def output_for(*values):
    return json.dumps({"segments": [{"id": ident, "text": value} for ident, value in values]}, ensure_ascii=False)


class AutoRewriteTests(unittest.IsolatedAsyncioTestCase):
    async def run_rewrite(self, source, responses, rules=None, **kwargs):
        request = AsyncMock(side_effect=responses)
        report = {}
        with patch.object(crud_ai_prompts, "get_routing_prompts", return_value=rules or {}), patch(
            "db.crud_settings.get_ai_common_rewrite_rules",
            return_value=DEFAULT_AI_COMMON_REWRITE_RULES,
        ):
            result = await rewrite_automatically(task(**kwargs), source, "test-model", request, report)
        return result, request, report

    async def test_classification_selects_category_prompt_and_exposes_exact_request(self):
        source = "商品价格100元"
        rules = {"product": {"id": 8, "name": "商品专用", "content": "突出规格 {{rewrite_ratio}} {{analysis}}"}}
        (output, error), request, report = await self.run_rewrite(source, [
            (analysis_for(source, facts=["100元"]), None),
            (output_for((1, "商品售价100元")), None)], rules)
        self.assertIsNone(error)
        self.assertEqual(output, "商品售价100元")
        self.assertEqual(request.await_count, 2)
        self.assertEqual(report["matches"][0]["prompt_id"], 8)
        self.assertEqual(report["rewrite_status"], "changed")
        payload = request.await_args_list[1].args[0]
        self.assertIn("突出规格 70", payload["messages"][1]["content"])
        # Check the fixed-mode instruction block, not a shared-rule mention of layout.
        self.assertNotIn("【本次指定版式：", report["rewrite_prompt"])

    async def test_mixed_content_preserves_order_and_immutable_segments(self):
        source = "活动99元\n\nhttps://example.com/a\n\n明天营业"
        analysis = json.loads(analysis_for(source))
        analysis["segments"][0]["content_type"] = "promotion"
        analysis["segments"][1]["action"] = "preserve"
        analysis["segments"][2]["content_type"] = "notice"
        (output, error), _, report = await self.run_rewrite(source, [
            (json.dumps(analysis), None), (output_for((5, "明天正常营业"), (1, "活动价99元")), None)])
        self.assertIsNone(error)
        self.assertEqual(output, "活动价99元\n\nhttps://example.com/a\n\n明天正常营业")
        self.assertEqual([item["content_type"] for item in report["matches"]], ["promotion", "product", "notice"])

    async def test_bad_analysis_falls_back_to_general(self):
        for first in [("bad json", None), ("", "HTTP 503"), TimeoutError()]:
            with self.subTest(first=first):
                (_, error), _, report = await self.run_rewrite("明天营业", [first, (output_for((1, "明天正常营业")), None)])
                self.assertIsNone(error)
                self.assertTrue(report["analysis_fallback"])
                self.assertEqual(report["matches"][0]["content_type"], "general")

    async def test_invalid_rewrite_never_silently_drops_changes_or_truncates(self):
        cases = [("价格100元", output_for((1, "价格200元"))),
                 ("价格100元", output_for((2, "价格100元"))),
                 ("原文正文", output_for((1, ""))),
                 ("原文正文", output_for((1, "<b>原文正文"))),
                 ("原文正文", output_for((1, "<div>原文正文</div>"))),
                 ("原文正文", output_for((1, "新文" * 1000))),
                 ('<a href="https://example.com">联系</a>', output_for((1, "联系"))),
                 ("链接 https://example.com", output_for((1, "其他 https://example.com")))]
        for source, rewritten in cases:
            with self.subTest(source=source, output=rewritten[:50]):
                (output, error), request, report = await self.run_rewrite(source, [(analysis_for(source), None), (rewritten, None), (rewritten, None)])
                self.assertTrue(error)
                self.assertEqual(output, source)
                self.assertEqual(request.await_count, 3)
                self.assertEqual(report["rewrite_status"], "failed")
                self.assertEqual(report["rewrite_error"], error)

    async def test_preserve_only_does_not_call_rewrite(self):
        for options in [{"ai_rewrite_ratio": 0}, {}]:
            (output, error), request, report = await self.run_rewrite("原文正文", [(analysis_for("原文正文", action="preserve"), None)], **options)
            self.assertIsNone(error)
            self.assertEqual(output, "原文正文")
            self.assertEqual(request.await_count, 1)
            self.assertEqual(report["rewrite_status"], "preserved")
            self.assertTrue(report["rewrite_reason"])
            self.assertEqual(report["rewrite_attempts"], 0)
            self.assertIn("固定信息", report["rewrite_reason"])

    async def test_unchanged_or_invisible_changes_retry_once(self):
        source = "环境舒适，活动100元！"
        for value in (source, " \n" + source + " \u200b", "环境舒适，活动１００元！"):
            with self.subTest(value=value):
                (output, error), request, report = await self.run_rewrite(source, [
                    (analysis_for(source), None), (output_for((1, value)), None), (output_for((1, value)), None)])
                self.assertEqual(output, source)
                self.assertTrue(error)
                self.assertEqual(request.await_count, 3)
                # Fullwidth numbers must still fail the stricter numeric protection.
                self.assertEqual(report["rewrite_status"], "failed" if "１００" in value else "unchanged")
                self.assertEqual(report["rewrite_attempts"], 2)
                self.assertTrue(report["rewrite_retried"])

    async def test_formatting_and_emoji_only_changes_succeed_at_every_ratio(self):
        source = "环境舒适，活动100元！"
        for ratio in (0, 15, 70, 100):
            for value in ("<b>环境舒适</b>，活动100元！", "环境舒适，\n活动100元！", "✨环境舒适，活动100元！"):
                with self.subTest(ratio=ratio, value=value):
                    (output, error), request, report = await self.run_rewrite(source, [
                        (analysis_for(source, facts=["100元"]), None),
                        (output_for((1, value)), None)], ai_rewrite_ratio=ratio)
                    self.assertIsNone(error)
                    self.assertEqual(output, value)
                    self.assertEqual(request.await_count, 2)
                    self.assertEqual(report["rewrite_status"], "changed")

    async def test_zero_ratio_rejects_wording_changes_then_accepts_formatting(self):
        source = "环境舒适，活动100元！"
        formatted = "<b>环境舒适</b>，活动100元！"
        (output, error), request, report = await self.run_rewrite(source, [
            (analysis_for(source), None),
            (output_for((1, "环境很好，活动100元！")), None),
            (output_for((1, formatted)), None)], ai_rewrite_ratio=0)
        self.assertIsNone(error)
        self.assertEqual(output, formatted)
        self.assertEqual(request.await_count, 3)
        self.assertIn("不得修改正文措辞", report["rewrite_prompt"])

    async def test_equivalent_html_tags_are_not_a_visible_change(self):
        source = "<b>活动100元</b>"
        value = "<strong>活动100元</strong>"
        (_, error), _, report = await self.run_rewrite(source, [
            (analysis_for(source), None), (output_for((1, value)), None), (output_for((1, value)), None)])
        self.assertTrue(error)
        self.assertEqual(report["rewrite_status"], "unchanged")

    async def test_unchanged_retry_changes_expression_without_altering_protected_values(self):
        source = "活动100元\n联系 @example\n#活动\n详情 https://example.com"
        rewritten = source.replace("活动100元", "<b>活动100元</b>")
        (output, error), request, report = await self.run_rewrite(source, [
            (analysis_for(source, facts=["100元"]), None), (output_for((1, source)), None), (output_for((1, rewritten)), None)])
        self.assertIsNone(error)
        self.assertEqual(output, rewritten)
        self.assertEqual(report["rewrite_status"], "changed")
        self.assertIsNone(report["rewrite_error"])
        retry_system = request.await_args_list[2].args[0]["messages"][0]["content"]
        self.assertIn("未产生可见变化", retry_system)
        self.assertIn(retry_system, report["rewrite_prompt"])

    async def test_failed_fact_validation_retries_with_specific_segment_reason(self):
        source = "门店A活动100元\n\n周末营业"
        analysis = json.loads(analysis_for(source))
        analysis["segments"][0]["facts"] = ["门店A", "100元"]
        analysis["segments"][1]["action"] = "preserve"
        (output, error), request, report = await self.run_rewrite(source, [
            (json.dumps(analysis), None),
            (output_for((1, "门店B活动100元")), None),
            (output_for((1, "门店A活动价格100元")), None)])
        self.assertIsNone(error)
        self.assertEqual(output, "门店A活动价格100元\n\n周末营业")
        self.assertTrue(report["rewrite_retried"])
        self.assertIn("段落 1：改写未保留原文事实", request.await_args_list[2].args[0]["messages"][0]["content"])

    async def test_retry_never_relaxes_protected_numbers_contacts_or_links(self):
        cases = [
            ("活动100元", "优惠活动200元", "数字"),
            ("联系 @example", "预约请联系工作人员", "联系方式"),
            ("活动介绍\nhttps://example.com", "优惠活动介绍\n详情 https://example.com", "链接"),
        ]
        for source, rewritten, reason in cases:
            with self.subTest(reason=reason):
                (output, error), request, report = await self.run_rewrite(source, [
                    (analysis_for(source), None), (output_for((1, source)), None), (output_for((1, rewritten)), None)])
                self.assertEqual(output, source)
                self.assertIn(reason, error)
                self.assertIn("段落 1", report["rewrite_error"])
                self.assertEqual(report["rewrite_status"], "failed")
                self.assertEqual(request.await_count, 3)

    async def test_analysis_failure_explains_validation_without_exposing_model_output(self):
        source = "活动100元"
        bad = json.loads(analysis_for(source))
        bad["segments"][0]["facts"] = ["secret-from-model"]
        (output, error), _, report = await self.run_rewrite(source, [
            (json.dumps(bad), None), (output_for((1, "活动价格100元")), None)])
        self.assertIsNone(error)
        self.assertTrue(report["analysis_fallback"])
        self.assertIn("段落 1", report["analysis_error"])
        self.assertIn("事实片段不在原文", report["analysis_error"])
        self.assertNotIn("secret-from-model", str(report))

    async def test_request_failure_details_never_expose_raw_error(self):
        source = "原文内容"
        (_, error), _, report = await self.run_rewrite(source, [
            ValueError("secret-key-value"), (output_for((1, "改写内容")), None)])
        self.assertIsNone(error)
        self.assertEqual(report["analysis_error"], "分析请求失败")
        for response in (RuntimeError("secret-key-value"), ("", "secret-key-value")):
            (_, error), request, report = await self.run_rewrite(source, [
                (analysis_for(source), None), response])
            self.assertIn("请求失败", error)
            self.assertNotIn("secret-key-value", str(report))
            self.assertEqual(report["rewrite_status"], "failed")
            self.assertEqual(request.await_count, 2)

    async def test_minimal_facts_allow_expression_changes_around_immutable_conditions(self):
        source = "环境舒适，活动价100元，仅限周末"
        (output, error), request, report = await self.run_rewrite(source, [
            (analysis_for(source, facts=["100元", "仅限周末"]), None),
            (output_for((1, "舒适的环境，活动价格100元，仅限周末")), None)])
        self.assertIsNone(error)
        self.assertNotEqual(output, source)
        self.assertEqual(report["rewrite_status"], "changed")
        self.assertIn("宣传形容、主观评价", request.await_args_list[0].args[0]["messages"][0]["content"])

    async def test_rewrite_keeps_plain_and_html_links_in_same_segment(self):
        for link in ["详情 https://example.com?a=1&b=2", "详情 t.me/example", '<a href="https://example.com?a=1&b=2">联系</a>']:
            source = "商品介绍\n" + link
            (output, error), _, _ = await self.run_rewrite(source, [(analysis_for(source), None), (output_for((1, "产品信息\n" + link)), None)])
            self.assertIsNone(error)
            self.assertIn(link, output)

    async def test_analysis_input_is_bounded(self):
        for source in ["文" * 16001, "\n\n".join(["段落"] * 101)]:
            (output, error), request, _ = await self.run_rewrite(source, [])
            self.assertEqual(output, source)
            self.assertTrue(error)
            request.assert_not_awaited()

    async def test_auto_pipeline_analyzes_body_before_templates(self):
        with patch("bot.content_processor.process_content", return_value={"blocked": False, "text": "源正文"}), \
             patch("bot.grok_rewriter.rewrite_text", new=AsyncMock(return_value=("改写正文", None))) as rewrite, \
             patch("bot.content_processor.get_template_part", side_effect=lambda t, kind: "广告尾部" if kind == "footer" else ""):
            result = await process_content_async("原文", task())
        self.assertEqual(rewrite.await_args.args[1], "源正文")
        self.assertEqual(result["text"], "改写正文\n\n广告尾部")
        self.assertTrue(result["ai_rewritten"])

    async def test_pipeline_failure_modes(self):
        for mode in ("skip", "fallback"):
            with self.subTest(mode=mode), \
                 patch("bot.content_processor.process_content", return_value={"blocked": False, "text": "源正文"}), \
                 patch("bot.grok_rewriter.rewrite_text", new=AsyncMock(return_value=("源正文", "校验失败"))), \
                 patch("bot.content_processor.get_template_part", return_value=""):
                result = await process_content_async("原文", task(ai_rewrite_failure_mode=mode))
                self.assertEqual(result["blocked"], mode == "skip")
                self.assertEqual(result["text"], "源正文")

    async def test_unchanged_after_retry_uses_existing_pipeline_failure_policy(self):
        source = "有可改写的原文正文"
        for mode in ("skip", "fallback"):
            report = {}
            request = AsyncMock(side_effect=[(analysis_for(source), None),
                                             (output_for((1, source)), None), (output_for((1, source)), None)])

            async def rewrite(current_task, text):
                return await rewrite_automatically(current_task, text, "test-model", request, report)

            with self.subTest(mode=mode), \
                 patch("bot.content_processor.process_content", return_value={"blocked": False, "text": source}), \
                 patch("bot.grok_rewriter.rewrite_text", new=rewrite), \
                 patch.object(crud_ai_prompts, "get_routing_prompts", return_value={}), \
                 patch("bot.content_processor.get_template_part", return_value=""):
                result = await process_content_async(source, task(ai_rewrite_failure_mode=mode))
            self.assertEqual(result["blocked"], mode == "skip")
            self.assertEqual(result["text"], source)
            self.assertFalse(result.get("ai_rewritten", False))
            self.assertEqual(report["rewrite_status"], "unchanged")
            self.assertEqual(request.await_count, 3)

    async def test_templates_do_not_silently_truncate_successful_rewrite(self):
        with patch("bot.content_processor.process_content", return_value={"blocked": False, "text": "源正文"}), \
             patch("bot.grok_rewriter.rewrite_text", new=AsyncMock(return_value=("新正文" * 400, None))), \
             patch("bot.content_processor.get_template_part", return_value=""):
            result = await process_content_async("原文", task(ai_rewrite_failure_mode="skip"))
        self.assertTrue(result["blocked"])
        self.assertIn("未截断", result["filter_detail"])

    async def test_full_document_layout_reorders_same_venue_and_restores_contact_segment(self):
        source = "门店A\n\n地址：某路\n\n价格100元\n\n联系 @example"
        analysis = json.loads(analysis_for(source))
        for item in analysis["segments"]:
            item["layout_group"] = 1
        analysis["segments"][-1]["action"] = "preserve"
        response = {"segments": [{"id": 1, "text": "<b>门店A</b>"}, {"id": 3, "text": "📍地址：某路"},
                                  {"id": 5, "text": "💰价格100元"}, {"id": 7, "text": "模型错误改动联系人"}],
                    "layout": {"order": [1, 5, 3, 7], "separators": ["\n", "\n\n", "\n\n"]}}
        (output, error), request, report = await self.run_rewrite(source, [(json.dumps(analysis), None), (json.dumps(response), None)])
        self.assertIsNone(error)
        self.assertEqual(output, "<b>门店A</b>\n💰价格100元\n\n📍地址：某路\n\n联系 @example")
        self.assertEqual(report["layout"]["order"], [1, 5, 3, 7])
        context = json.loads(request.await_args_list[1].args[0]["messages"][1]["content"])
        self.assertEqual(context[-1]["original_text"], "联系 @example")
        self.assertEqual(context[-1]["action"], "preserve")
        self.assertEqual(context[-1]["protected_tokens"], ["@example"])

    async def test_rating_symbols_remain_immutable_without_ai_extracted_facts(self):
        source = "推荐指数:✨✨✨✨"
        invalid = "<b>推荐指数:✨✨✨</b>"
        (output, error), _, _ = await self.run_rewrite(source, [(analysis_for(source), None),
            (output_for((1, invalid)), None), (output_for((1, invalid)), None)])
        self.assertEqual(output, source)
        self.assertIn("评分", error)

    async def test_document_layout_rejects_moving_prices_across_venues(self):
        source = "门店A\n\n费用100元\n\n门店B\n\n费用200元"
        analysis = json.loads(analysis_for(source))
        for item, group in zip(analysis["segments"], [1, 1, 5, 5]):
            item["layout_group"] = group
        response = {"segments": [{"id": item["id"], "text": "<b>" + item["text"] + "</b>"}
                                  for item in split_source(source)[1]],
                    "layout": {"order": [1, 7, 5, 3], "separators": ["\n"] * 3}}
        (output, error), request, _ = await self.run_rewrite(source, [(json.dumps(analysis), None)] + [(json.dumps(response), None)] * 2)
        self.assertEqual(output, source)
        self.assertIn("跨不同对象", error)
        self.assertEqual(request.await_count, 3)

    async def test_long_product_requires_section_icons_and_emphasis_then_retries(self):
        source = "店铺介绍\n\n" + ("已有服务内容说明，环境与服务按原文描述。" * 4) + "\n还有其他原有内容。\n\n消费明细\n费用100元\n费用200元\n\n地址：原有完整地址，附近地点与条件沿用原文。"
        analysis = json.loads(analysis_for(source))
        analysis["content_type"] = "product"
        original = split_source(source)[1]
        first = {"segments": [{"id": item["id"], "text": "<b>" + item["text"] + "</b>" if index == 0 else item["text"]}
                              for index, item in enumerate(original)]}
        second = {"segments": [{"id": item["id"], "text": ("🎤 <b>" + item["text"] + "</b>" if index == 0 else
                                item["text"].replace("消费明细", "💰 <b>消费明细</b>") if index == 2 else item["text"])}
                               for index, item in enumerate(original)]}
        (output, error), request, report = await self.run_rewrite(source, [(json.dumps(analysis), None),
            (json.dumps(first), None), (json.dumps(second), None)])
        self.assertIsNone(error)
        self.assertIn("💰", output)
        self.assertEqual(request.await_count, 3)
        self.assertIn("全文排版尚未完成", report["rewrite_prompt"])

    async def test_fee_relationships_cannot_swap_even_when_numbers_match(self):
        source = "女演员 (500/600)小时\n抵消 (2000)\n包厢➕管家 (1290)"
        invalid = "女演员 (500/600)小时\n抵消 (1290)\n包厢➕管家 (2000)"
        (output, error), _, _ = await self.run_rewrite(source, [
            (analysis_for(source, facts=source.splitlines()), None),
            (output_for((1, invalid)), None), (output_for((1, invalid)), None)])
        self.assertEqual(output, source)
        self.assertIn("未保留原文事实", error)


class AnalysisValidationTests(unittest.TestCase):
    def test_layout_groups_are_contiguous_and_start_with_source_id(self):
        source = split_source("门店A\n\nA费用\n\n门店B")[1]
        for groups in ([1, 1, 5], [1, 3, 5]):
            data = json.loads(analysis_for("门店A\n\nA费用\n\n门店B"))
            for item, group in zip(data["segments"], groups):
                item["layout_group"] = group
            self.assertEqual([item["layout_group"] for item in validate_analysis(json.dumps(data), source)["segments"]], list(groups))
        for groups in ([1, 3, 1], [True, 1, 1], [2, 2, 2]):
            for item, group in zip(data["segments"], groups):
                item["layout_group"] = group
            with self.assertRaisesRegex(ValueError, "分组"):
                validate_analysis(json.dumps(data), source)

    def test_task_api_schema_defaults_and_updates(self):
        from api.server import CloneTaskCreate, CloneTaskUpdate, ListenerTaskCreate, ListenerTaskUpdate
        from pydantic import ValidationError
        for schema in (CloneTaskCreate, ListenerTaskCreate):
            model = schema(name="测试", source_channel="@source", target_channels="[]")
            self.assertEqual(model.ai_prompt_mode, "fixed")
        for schema in (CloneTaskUpdate, ListenerTaskUpdate):
            self.assertNotIn("ai_prompt_mode", schema(name="更新").dict(exclude_unset=True))
            self.assertEqual(schema(ai_prompt_mode="auto").ai_prompt_mode, "auto")
            with self.assertRaises(ValidationError):
                schema(ai_prompt_mode="unsupported")

    def test_untrusted_analysis_cannot_invent_facts_or_ids(self):
        source = split_source("商品100元")[1]
        data = json.loads(analysis_for("商品100元"))
        data["segments"][0]["facts"] = ["虚构地址"]
        with self.assertRaises(ValueError):
            validate_analysis(json.dumps(data), source)
        data["segments"][0]["facts"] = []
        data["segments"].append(data["segments"][0])
        with self.assertRaises(ValueError):
            validate_analysis(json.dumps(data), source)

    def test_low_confidence_uses_general(self):
        data = json.loads(analysis_for("原文"))
        data["segments"][0]["confidence"] = 0.3
        result = validate_analysis(json.dumps(data), split_source("原文")[1])
        self.assertEqual(result["segments"][0]["content_type"], "general")


class PromptPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_routing_uses_only_owner_enabled_latest_category(self):
        now = datetime.utcnow()
        with self.sessions() as db:
            for owner, name, enabled, days, category in [(1, "旧", True, -2, "product"), (1, "新", True, -1, "product"), (1, "停用", False, 0, "product"), (2, "其他租户", True, 0, "product"), (1, "固定", True, 0, "")]:
                db.add(AiPromptTemplate(owner_user_id=owner, name=name, content=name, enabled=enabled, content_type=category, updated_at=now + timedelta(days=days)))
            db.commit()
        with patch.object(crud_ai_prompts, "SessionLocal", self.sessions):
            self.assertEqual(crud_ai_prompts.get_routing_prompts(1)["product"]["name"], "新")
            self.assertEqual(crud_ai_prompts.get_routing_prompts(2)["product"]["name"], "其他租户")
            self.assertEqual(crud_ai_prompts.get_routing_prompts(), {})

    def test_create_update_category_and_reject_invalid_category(self):
        with patch.object(crud_ai_prompts, "SessionLocal", self.sessions), tenant_scope(1):
            created = crud_ai_prompts.create_ai_prompt({"name": "测试", "content": "规则", "content_type": "notice"})
            self.assertEqual(created["content_type"], "notice")
            changed = crud_ai_prompts.update_ai_prompt(created["id"], {"content_type": "product"})
            self.assertEqual(changed["content_type"], "product")
            with self.assertRaises(ValueError):
                crud_ai_prompts.update_ai_prompt(created["id"], {"content_type": "bad"})

    def test_task_modes_roundtrip_without_reset_on_unrelated_update(self):
        from db import crud_clone, crud_listener
        from db.models import Account
        with self.sessions() as db:
            db.add(Account(id=1, owner_user_id=1, name="测试账号", session_path="test.session", enabled=True))
            db.commit()
        with patch.object(crud_clone, "SessionLocal", self.sessions), patch.object(crud_listener, "SessionLocal", self.sessions), tenant_scope(1):
            for crud, create, update in [(crud_clone, crud_clone.create_clone_task, crud_clone.update_clone_task),
                                         (crud_listener, crud_listener.create_listener_task, crud_listener.update_listener_task)]:
                created = create({"name": "自动任务", "source_channel": "@source", "target_channels": "[]", "account_id": 1, "owner_user_id": 1, "ai_prompt_mode": "auto"})
                self.assertEqual(created.ai_prompt_mode, "auto")
                updated = update(created.id, {"name": "更名任务"})
                self.assertEqual(updated.ai_prompt_mode, "auto")
                updated = update(created.id, {"ai_prompt_mode": "fixed"})
                self.assertEqual(updated.ai_prompt_mode, "fixed")

    def test_migration_backs_up_existing_rows_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.db"
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            with engine.begin() as conn:
                for table in ("clone_tasks", "listener_tasks", "ai_prompt_templates"):
                    conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)"))
                    conn.execute(text(f"INSERT INTO {table} (name) VALUES ('existing')"))
            backup = migrate(engine)
            self.assertTrue(backup.exists())
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT ai_prompt_mode FROM clone_tasks")).scalar_one(), "fixed")
                self.assertEqual(conn.execute(text("SELECT name FROM clone_tasks")).scalar_one(), "existing")
            self.assertIsNone(migrate(engine))
            old_engine = create_engine(f"sqlite:///{backup.as_posix()}")
            self.assertNotIn("ai_prompt_mode", {item["name"] for item in inspect(old_engine).get_columns("clone_tasks")})
            old_engine.dispose()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
