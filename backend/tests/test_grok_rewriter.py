import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import grok_rewriter


def rewrite_task(task_id=30):
    return SimpleNamespace(
        id=task_id,
        ai_rewrite_enabled=True,
        ai_rewrite_provider="deepseek",
        ai_rewrite_model="deepseek-chat",
        ai_rewrite_prompt="",
        ai_prompt_template_id=None,
        ai_rewrite_max_chars=800,
        ai_rewrite_ratio=70,
        ai_rewrite_failure_mode="fallback",
    )


class RewriteLayoutTests(unittest.TestCase):
    def setUp(self):
        grok_rewriter.reset_rewrite_runtime_state()

    def tearDown(self):
        grok_rewriter.reset_rewrite_runtime_state()

    def test_repeated_input_rotates_and_avoids_recent_layouts(self):
        task = rewrite_task()
        layouts = [
            grok_rewriter.select_layout_variant(task, "完全相同的测试内容")["key"]
            for _ in range(6)
        ]

        self.assertEqual(len(set(layouts[:3])), 3)
        self.assertTrue(
            all(current != previous for previous, current in zip(layouts, layouts[1:]))
        )

    def test_prompt_contains_forced_layout_without_fixed_template(self):
        task = rewrite_task()
        layout = grok_rewriter.AI_LAYOUT_VARIANTS[0]

        with patch(
            "db.crud_ai_prompts.get_prompt_content_for_task",
            return_value="保留事实并重写。\n\n待处理文本：\n{{content}}",
        ):
            prompt, max_chars = grok_rewriter.build_prompt(
                task,
                "上海门店，营业时间 20:00—06:00",
                layout=layout,
            )

        self.assertEqual(max_chars, 800)
        self.assertIn("【本次指定版式：极简短文】", prompt)
        self.assertIn("较长内容可用贴合内容的表情引导区块", prompt)
        self.assertIn("禁止机械使用“核心亮点”", prompt)
        self.assertIn("禁止使用 <br>", prompt)
        self.assertIn("明文出现的 URL 必须保持其整行内容", prompt)
        self.assertIn("上海门店，营业时间 20:00—06:00", prompt)

    def test_prompt_marks_plain_url_line_as_immutable(self):
        task = rewrite_task()
        source = "频道：https://t.me/cdyuleysh"

        with patch(
            "db.crud_ai_prompts.get_prompt_content_for_task",
            return_value="保留事实并重写。\n\n待处理文本：\n{{content}}",
        ):
            prompt, _max_chars = grok_rewriter.build_prompt(task, source)

        self.assertIn("【本次禁止改写的明文链接行】", prompt)
        self.assertIn(source, prompt)
        self.assertIn("禁止包装成 <a>", prompt)

    def test_prompt_contains_configured_rewrite_ratio(self):
        task = rewrite_task()
        task.ai_rewrite_ratio = 35
        task.ai_rewrite_prompt = "按 {{rewrite_ratio}}% 改写，最多 {{max_chars}} 字。\n{{content}}"

        prompt, _max_chars = grok_rewriter.build_prompt(
            task,
            "成都门店营业时间 20:00—06:00",
            layout=grok_rewriter.AI_LAYOUT_VARIANTS[0],
        )

        self.assertIn("按 35% 改写", prompt)
        self.assertIn("【改写比例：35%｜最高优先级】", prompt)
        self.assertIn("不代表文字替换比例", prompt)
        self.assertNotIn("约保留 65%", prompt)
        self.assertIn("最终输出不得超过 800 字符", prompt)

    def test_all_ratios_preserve_content_and_only_adjust_presentation(self):
        for ratio in (0, 15, 35, 70, 100):
            with self.subTest(ratio=ratio):
                directive = grok_rewriter.build_rewrite_ratio_directive(ratio)
                self.assertIn("保留原文的大致内容、原意和信息", directive)
                self.assertIn("不得大幅改写", directive)
                self.assertIn("评分、数量、状态或条件类表情", directive)
                self.assertNotIn("约保留", directive)
                self.assertNotIn("全面重组", directive)
                if ratio == 0:
                    self.assertIn("保持原文措辞", directive)
                    self.assertIn("Telegram HTML 排版和装饰性表情", directive)
                    self.assertIn("不得改写原句或新增栏目文字", directive)

    def test_layouts_do_not_require_new_scenes_questions_or_editorial_opinions(self):
        for layout in grok_rewriter.AI_LAYOUT_VARIANTS:
            with self.subTest(layout=layout["key"]):
                directive = grok_rewriter.build_layout_directive(layout)
                self.assertIn("保留原文内容、整理排版和表情为主", directive)
                self.assertIn("不得新增开场、收尾、场景、问答、观点", directive)
                self.assertNotIn("从一个自然场景或读者需求切入", directive)
                self.assertNotIn("正文以回答该问题的方式展开", directive)
                self.assertNotIn("采用编辑推荐式短文", directive)
                self.assertIn("标题和栏目名适度加粗", directive)
                self.assertIn("先理解整篇", directive)
                self.assertNotIn("全文最多三个", directive)
                self.assertNotIn("保持原有信息顺序", directive)

    def test_rewrite_ratio_is_clamped_to_supported_range(self):
        task = rewrite_task()
        task.ai_rewrite_ratio = 180
        self.assertEqual(grok_rewriter.normalize_rewrite_ratio(task), 100)

        task.ai_rewrite_ratio = -10
        self.assertEqual(grok_rewriter.normalize_rewrite_ratio(task), 0)

    def test_ai_request_timeout_is_five_minutes(self):
        self.assertEqual(grok_rewriter.AI_REQUEST_TIMEOUT_SECONDS, 300)

    def test_completion_token_limit_is_capped_at_one_hundred_thousand(self):
        self.assertEqual(grok_rewriter.build_completion_token_limit(800), 1600)
        self.assertEqual(
            grok_rewriter.build_completion_token_limit(50_000),
            100_000,
        )
        self.assertEqual(
            grok_rewriter.build_completion_token_limit(100_000),
            100_000,
        )

    def test_normalize_ai_output_converts_br_tags_to_real_newlines(self):
        output = (
            "<b>长沙夜生活</b><br/>"
            "快乐其实可以很简单<br></br>"
            "环境舒适&lt;br&gt;24小时在线"
        )

        normalized = grok_rewriter.normalize_ai_output(output)

        self.assertEqual(
            normalized,
            "<b>长沙夜生活</b>\n"
            "快乐其实可以很简单\n"
            "环境舒适\n24小时在线",
        )
        self.assertNotRegex(normalized, r"(?i)</?br")

    def test_protected_html_link_accepts_changed_label(self):
        source = (
            '联系点击➡️：<a href="https://t.me/nanjingktvyule_bot">'
            "南京最靠谱职业经理人</a>"
        )
        rewritten = (
            '咨询入口：<a href="https://t.me/nanjingktvyule_bot">'
            "南京专业对接经理</a>"
        )

        ensured = grok_rewriter.ensure_preserved_html_links(source, rewritten)

        self.assertEqual(ensured, rewritten)

    def test_plain_url_line_replaces_model_created_contact_anchor(self):
        source = "频道：https://t.me/cdyuleysh"
        rewritten = (
            "<b>成都夜生活</b>\n\n"
            '驻场联系：<a href="https://t.me/cdyuleysh">点击咨询</a>'
        )

        ensured = grok_rewriter.ensure_preserved_plain_url_lines(
            source,
            rewritten,
        )

        self.assertIn(source, ensured)
        self.assertNotIn("驻场联系", ensured)
        self.assertNotIn("点击咨询", ensured)
        self.assertNotIn('<a href="https://t.me/cdyuleysh">', ensured)

    def test_plain_url_protection_does_not_lock_existing_anchor_label(self):
        source = (
            '联系点击➡️：<a href="https://t.me/cdyuleysh">'
            "行行行</a>"
        )
        rewritten = (
            '联系点击➡️：<a href="https://t.me/cdyuleysh">'
            "新的点击文字</a>"
        )

        self.assertEqual(
            grok_rewriter.extract_plain_url_lines(source),
            [],
        )
        self.assertEqual(
            grok_rewriter.ensure_preserved_plain_url_lines(source, rewritten),
            rewritten,
        )

    def test_protected_html_link_is_restored_when_model_downgrades_it(self):
        source = (
            '联系点击➡️：<a href="https://t.me/nanjingktvyule_bot">'
            "南京最靠谱职业经理人</a>"
        )
        rewritten = "联系点击➡️：南京最靠谱职业经理人"

        ensured = grok_rewriter.ensure_preserved_html_links(source, rewritten)

        self.assertIn(
            '<a href="https://t.me/nanjingktvyule_bot">'
            "南京最靠谱职业经理人</a>",
            ensured,
        )
        self.assertNotIn("联系点击➡️：南京最靠谱职业经理人", ensured)

    def test_structure_similarity_detects_repeated_template(self):
        previous = """<b>成都夜生活</b>

<i>今晚换个地方放松。</i>

<b>✨ 核心亮点</b>
• 环境舒适
• 时间充足

<b>🥂 适合场景</b>
朋友聚会或商务安排。

<b>🕒 营业信息</b>
营业时间：20:00—06:00"""
        repeated = """<b>成都夜间新选择</b>

<i>下班后给自己一点空间。</i>

<b>✨ 核心亮点</b>
• 交通方便
• 安排灵活

<b>🥂 适合场景</b>
适合朋友小聚。

<b>🕒 营业信息</b>
营业时间：20:00—06:00"""
        different = """<b>下班以后，去哪里坐坐？</b>

想简单唱几首歌、和朋友聊聊天，可以把晚上的节奏放慢一点。

营业时间：20:00—06:00
TG: @example

#成都夜生活"""

        repeated_score = grok_rewriter.output_structure_similarity(
            previous,
            repeated,
        )
        different_score = grok_rewriter.output_structure_similarity(
            previous,
            different,
        )

        self.assertGreaterEqual(
            repeated_score,
            grok_rewriter.AI_STRUCTURE_SIMILARITY_THRESHOLD,
        )
        self.assertLess(different_score, repeated_score)

    def test_contacts_and_source_hashtags_have_deterministic_fallback(self):
        source = (
            "上海门店，营业时间 20:00—06:00。"
            "TG: @example_contact，电话 18573530930。"
            "#上海商K #上海夜生活"
        )
        model_output = """<b>夜间聚会新选择</b>

可以和朋友在下班后来坐坐。

#KTV #聚会"""

        ensured = grok_rewriter.ensure_preserved_metadata(
            source,
            model_output,
        )

        self.assertIn("@example_contact", ensured)
        self.assertIn("18573530930", ensured)
        self.assertIn("#上海商K", ensured)
        self.assertIn("#上海夜生活", ensured)
        self.assertEqual(
            len(
                [
                    tag
                    for tag in grok_rewriter.extract_source_hashtags(ensured)
                    if tag not in {"#上海商K", "#上海夜生活"}
                ]
            ),
            0,
        )


class RewriteRetryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        grok_rewriter.reset_rewrite_runtime_state()

    def tearDown(self):
        grok_rewriter.reset_rewrite_runtime_state()

    async def test_layout_and_emoji_only_changes_are_accepted_at_any_ratio(self):
        source = "门店介绍\n✅环境舒适，营业时间 20:00—06:00\n电话：18573530930\nTG: @example"
        candidate = "<b>门店介绍</b>\n\n• 环境舒适，营业时间 20:00—06:00\n\n电话：18573530930\nTG: @example"
        for ratio in (0, 70, 100):
            with self.subTest(ratio=ratio):
                task = rewrite_task(task_id=100 + ratio)
                task.ai_rewrite_ratio = ratio
                request = AsyncMock(return_value=(candidate, None))
                with (
                    patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "test-key", "model": "deepseek-chat"}),
                    patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="整理排版：{{content}}"),
                    patch("bot.grok_rewriter._request_completion", request),
                ):
                    rewritten, error = await grok_rewriter.rewrite_text(task, source)
                self.assertIsNone(error)
                self.assertEqual(rewritten, candidate)
                self.assertEqual(request.await_count, 1)

    async def test_fixed_mode_rejects_changed_prices(self):
        source = "包厢价格 1290 元，营业时间 20:00—06:00"
        candidate = "<b>包厢价格 1390 元</b>\n营业时间 20:00—06:00"
        with (
            patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "test-key", "model": "deepseek-chat"}),
            patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="整理排版：{{content}}"),
            patch("bot.grok_rewriter._request_completion", AsyncMock(return_value=(candidate, None))),
        ):
            rewritten, error = await grok_rewriter.rewrite_text(rewrite_task(), source)
        self.assertEqual(rewritten, source)
        self.assertIn("改变了原文数字", error)

    async def test_zero_ratio_rejects_changed_wording(self):
        task = rewrite_task()
        task.ai_rewrite_ratio = 0
        source = "✅环境舒适，营业时间 20:00—06:00"
        candidate = "<b>环境宽敞，营业时间 20:00—06:00</b>"
        request = AsyncMock(return_value=(candidate, None))
        with (
            patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "test-key", "model": "deepseek-chat"}),
            patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="整理排版：{{content}}"),
            patch("bot.grok_rewriter._request_completion", request),
        ):
            rewritten, error = await grok_rewriter.rewrite_text(task, source)
        self.assertEqual(rewritten, source)
        self.assertIn("不得改变原文措辞", error)
        self.assertEqual(request.await_count, 1)

    async def test_zero_ratio_rejects_changed_wording_during_layout_retry(self):
        task = rewrite_task()
        task.ai_rewrite_ratio = 0
        source = "✅环境舒适，营业时间 20:00—06:00"
        first_response = "<b>环境舒适</b>\n营业时间 20:00—06:00"
        retry_response = "<b>环境宽敞</b>\n\n营业时间 20:00—06:00"
        grok_rewriter.remember_rewrite_output(task, first_response)
        request = AsyncMock(side_effect=[(first_response, None), (retry_response, None)])
        with (
            patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "test-key", "model": "deepseek-chat"}),
            patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="整理排版：{{content}}"),
            patch("bot.grok_rewriter._request_completion", request),
        ):
            rewritten, error = await grok_rewriter.rewrite_text(task, source)
        self.assertIsNone(error)
        self.assertEqual(rewritten, first_response)
        self.assertEqual(request.await_count, 2)

    async def test_invalid_retry_keeps_first_valid_layout(self):
        task = rewrite_task()
        source = "门店介绍\n包厢价格 1290 元，营业时间 20:00—06:00"
        first_response = "<b>门店介绍</b>\n\n包厢价格 1290 元，营业时间 20:00—06:00"
        retry_response = "<b>门店介绍</b>\n\n包厢价格 1390 元\n营业时间 20:00—06:00"
        grok_rewriter.remember_rewrite_output(task, first_response)
        request = AsyncMock(side_effect=[(first_response, None), (retry_response, None)])
        with (
            patch("db.crud_settings.get_ai_provider_config", return_value={"api_key": "test-key", "model": "deepseek-chat"}),
            patch("db.crud_ai_prompts.get_prompt_content_for_task", return_value="整理排版：{{content}}"),
            patch("bot.grok_rewriter._request_completion", request),
        ):
            rewritten, error = await grok_rewriter.rewrite_text(task, source)
        self.assertIsNone(error)
        self.assertEqual(rewritten, first_response)
        self.assertEqual(request.await_count, 2)

    async def test_high_similarity_retries_once_with_another_layout(self):
        task = rewrite_task()
        previous = """<b>上海夜生活</b>

<i>今晚给自己一点放松。</i>

<b>✨ 核心亮点</b>
• 环境舒适
• 安排灵活

<b>🥂 适合场景</b>
朋友聚会或商务安排。

<b>🕒 营业信息</b>
营业时间：20:00—06:00"""
        first_response = """<b>上海夜间新选择</b>

<i>下班后换一种节奏。</i>

<b>✨ 核心亮点</b>
• 位置方便
• 营业到凌晨

<b>🥂 适合场景</b>
适合朋友小聚。

<b>🕒 营业信息</b>
营业时间：20:00—06:00"""
        retry_response = """<b>下班以后，去哪里坐坐？</b>

想简单唱几首歌、和朋友聊聊天，可以把晚上的节奏放慢一点。

营业时间：20:00—06:00
TG: @example

#上海夜生活"""
        grok_rewriter.remember_rewrite_output(task, previous)

        request = AsyncMock(
            side_effect=[
                (first_response, None),
                (retry_response, None),
            ]
        )
        with (
            patch(
                "db.crud_settings.get_ai_provider_config",
                return_value={"api_key": "test-key", "model": "deepseek-chat"},
            ),
            patch(
                "db.crud_ai_prompts.get_prompt_content_for_task",
                return_value="保留事实并重写。\n\n待处理文本：\n{{content}}",
            ),
            patch("bot.grok_rewriter._request_completion", request),
        ):
            rewritten, error = await grok_rewriter.rewrite_text(
                task,
                "上海门店，营业时间 20:00—06:00，TG: @example",
            )

        self.assertIsNone(error)
        self.assertEqual(rewritten, retry_response.removesuffix("\n\n#上海夜生活"))
        self.assertEqual(request.await_count, 2)
        first_payload = request.await_args_list[0].args[2]
        retry_payload = request.await_args_list[1].args[2]
        self.assertEqual(first_payload["temperature"], 0.68)
        self.assertNotEqual(
            first_payload["messages"][0]["content"],
            retry_payload["messages"][0]["content"],
        )


if __name__ == "__main__":
    unittest.main()
