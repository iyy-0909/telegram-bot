import unittest

from bot.ai_document_layout import assemble_document, layout_quality_issue


def document_fixture(texts, groups=None, content_types=None, separator="\n\n"):
    parts = []
    source = []
    segments = []
    for index, text in enumerate(texts):
        if index:
            parts.append(separator)
        ident = len(parts) + 1
        parts.append(text)
        source.append({"id": ident, "text": text})
        item = {"id": ident, "content_type": (content_types or {}).get(ident, "product")}
        if groups is not None:
            item["layout_group"] = groups[index]
        segments.append(item)
    return parts, source, {"segments": segments}, {item["id"]: item["text"] for item in source}


LONG_SOURCE = """#普陀区 鑫悦汇 PARTY K

地址：长寿路城市社交中心·THE CITY CENR0

推荐指数:✨✨✨✨

✅普陀新开小时场，活动多多性价比拉满，每天出勤150~！
✅活动选择丰富，可以根据到店人数和实际需求提前安排。
✅环境舒适，场所介绍、消费项目和预约方式都在下方。

消费明细💰

✅女演员 (500/600)小时
✅抵消 (2000)
✅包厢➕管家 (1290)

预订: 18573530930
TG:@shanghai_xiaozhang
#上海商k #上海KTV #上海妹妹"""


class DocumentAssemblyTests(unittest.TestCase):
    def test_group_can_reorder_sections_and_join_heading_to_prices(self):
        fixture = document_fixture(
            ["<b>场所名称</b>", "📍 地址：长寿路", "🎤 场所介绍", "💰 <b>消费明细</b>",
             "▫️500/600\n▫️2000\n▫️1290", "预订: 18573530930\nTG:@example"],
            groups=[1] * 6,
        )
        output = assemble_document(*fixture, {
            "order": [1, 5, 7, 9, 3, 11],
            "separators": ["\n\n", "\n\n", "\n", "\n\n", "\n\n"],
        }, 70)
        self.assertEqual(output, "<b>场所名称</b>\n\n🎤 场所介绍\n\n💰 <b>消费明细</b>\n"
                         "▫️500/600\n▫️2000\n▫️1290\n\n📍 地址：长寿路\n\n"
                         "预订: 18573530930\nTG:@example")

    def test_multiple_groups_may_each_reorder_without_crossing_boundaries(self):
        fixture = document_fixture(["A介绍", "A价格", "B介绍", "B价格"], groups=[10, 10, 20, 20])
        output = assemble_document(*fixture, {"order": [3, 1, 7, 5], "separators": ["\n"] * 3}, 70)
        self.assertEqual(output, "A价格\nA介绍\nB价格\nB介绍")

    def test_groups_cannot_interleave_or_exchange_positions(self):
        fixture = document_fixture(["A介绍", "A联系方式", "B介绍", "B联系方式"], groups=[1, 1, 2, 2])
        for order in ([1, 5, 3, 7], [5, 7, 1, 3], [1, 7, 5, 3]):
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, "跨不同对象或主题"):
                assemble_document(*fixture, {"order": order, "separators": ["\n\n"] * 3}, 70)

    def test_unknown_layout_groups_default_to_independent_sections(self):
        fixture = document_fixture(["A介绍", "B联系方式"])
        with self.assertRaisesRegex(ValueError, "跨不同对象或主题"):
            assemble_document(*fixture, {"order": [3, 1], "separators": ["\n"]}, 70)

    def test_missing_duplicate_unknown_non_integer_and_boolean_ids_are_rejected(self):
        fixture = document_fixture(["标题", "正文", "联系"], groups=[1, 1, 1])
        for order in ([1, 3], [1, 3, 3], [1, 3, 7], [True, 3, 5], [1.0, 3, 5],
                      ["1", 3, 5], [None, 3, 5], (1, 3, 5), "135", None):
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, "恰好包含所有原段落"):
                assemble_document(*fixture, {"order": order, "separators": ["\n", "\n"]}, 70)

    def test_separator_type_count_and_content_are_strict(self):
        fixture = document_fixture(["标题", "费用", "联系"], groups=[1, 1, 1])
        for separators in ([], ["\n"], ["\n"] * 3, "\n\n", ("\n", "\n"), None,
                           ["", "\n"], ["\n\n\n", "\n"], ["\r\n", "\n"],
                           ["新增宣传语", "\n"], ["<br>", "\n"], [True, "\n"]):
            with self.subTest(separators=separators), self.assertRaisesRegex(ValueError, "分隔必须"):
                assemble_document(*fixture, {"order": [1, 3, 5], "separators": separators}, 70)

    def test_layout_must_be_an_object(self):
        fixture = document_fixture(["正文"], groups=[1])
        for layout in ([], "layout", True, 0):
            with self.subTest(layout=layout), self.assertRaisesRegex(ValueError, "格式无效"):
                assemble_document(*fixture, layout, 70)

    def test_none_layout_keeps_legacy_original_separators_and_uses_candidate_text(self):
        fixture = document_fixture(["原标题", "原正文", "原联系"], groups=[1, 1, 1], separator="\r\n\r\n")
        fixture[3][3] = "<b>新正文</b>"
        for ratio in (0, 15, 70, 100):
            with self.subTest(ratio=ratio):
                self.assertEqual(assemble_document(*fixture, None, ratio), "原标题\r\n\r\n<b>新正文</b>\r\n\r\n原联系")

    def test_zero_ratio_allows_new_spacing_but_rejects_section_reordering(self):
        fixture = document_fixture(["标题", "正文", "联系"], groups=[1, 1, 1])
        self.assertEqual(assemble_document(*fixture, {"order": [1, 3, 5], "separators": ["\n", "\n"]}, 0),
                         "标题\n正文\n联系")
        with self.assertRaisesRegex(ValueError, "必须保持原有顺序"):
            assemble_document(*fixture, {"order": [1, 5, 3], "separators": ["\n", "\n"]}, 0)

    def test_story_and_tutorial_keep_the_order_of_the_entire_topic_group(self):
        for content_type in ("story", "tutorial"):
            fixture = document_fixture(["标题", "有顺序的正文", "补充说明"], groups=[1, 1, 1],
                                       content_types={3: content_type})
            with self.subTest(content_type=content_type):
                self.assertEqual(assemble_document(*fixture, {"order": [1, 3, 5], "separators": ["\n", "\n\n"]}, 70),
                                 "标题\n有顺序的正文\n\n补充说明")
                with self.assertRaisesRegex(ValueError, "必须保持原有顺序"):
                    assemble_document(*fixture, {"order": [5, 1, 3], "separators": ["\n", "\n"]}, 70)

    def test_sequential_topic_does_not_block_other_independent_topic_reordering(self):
        fixture = document_fixture(["商品介绍", "商品费用", "故事开头", "故事经过"],
                                   groups=[1, 1, 2, 2], content_types={5: "story", 7: "story"})
        self.assertEqual(assemble_document(*fixture, {"order": [3, 1, 5, 7], "separators": ["\n"] * 3}, 70),
                         "商品费用\n商品介绍\n故事开头\n故事经过")


class DocumentLayoutQualityTests(unittest.TestCase):
    def test_long_post_with_only_one_bold_heading_is_insufficient(self):
        output = LONG_SOURCE.replace("#普陀区 鑫悦汇 PARTY K", "<b>#普陀区 鑫悦汇 PARTY K</b>")
        issue = layout_quality_issue(LONG_SOURCE, output, 70)
        self.assertIn("至少两处短标题", issue)
        self.assertIn("至少两个信息区块", issue)

    def test_whole_paragraph_bold_and_rating_emojis_do_not_count_as_section_layout(self):
        output = "<b>" + LONG_SOURCE + "</b>"
        issue = layout_quality_issue(LONG_SOURCE, output, 70)
        self.assertIn("不能整段全加粗", issue)
        self.assertIn("评分和列表符号不算", issue)

    def test_sample_style_with_short_bold_headings_and_section_emojis_passes(self):
        output = LONG_SOURCE.replace("#普陀区 鑫悦汇 PARTY K", "<b>鑫悦汇 PARTY K</b>\n#普陀区")
        output = output.replace("地址：", "📍 <strong>地址</strong>\n")
        output = output.replace("消费明细💰", "💰 <b>消费明细</b>")
        output = output.replace("✅普陀新开", "🎤 <b>场所介绍</b>\n普陀新开")
        self.assertIsNone(layout_quality_issue(LONG_SOURCE, output, 70))

    def test_each_missing_visual_treatment_has_specific_feedback(self):
        headings_only = LONG_SOURCE.replace("地址：", "<b>地址</b>：").replace("消费明细💰", "<b>消费明细</b>")
        icons_only = LONG_SOURCE.replace("地址：", "📍 地址：").replace("消费明细💰", "💰 消费明细")
        self.assertNotIn("短标题", layout_quality_issue(LONG_SOURCE, headings_only, 70))
        self.assertIn("表情", layout_quality_issue(LONG_SOURCE, headings_only, 70))
        self.assertIn("短标题", layout_quality_issue(LONG_SOURCE, icons_only, 70))
        self.assertNotIn("区块表情", layout_quality_issue(LONG_SOURCE, icons_only, 70))

    def test_short_text_and_low_ratio_do_not_require_multi_section_layout(self):
        for ratio in (0, 15, 34):
            with self.subTest(ratio=ratio):
                self.assertIsNone(layout_quality_issue(LONG_SOURCE, LONG_SOURCE, ratio))
        for source in ("价格100元", "标题\n\n地址\n第一行\n第二行\n\n联系\n标签", "正文" * 100):
            with self.subTest(source=source[:20]):
                self.assertIsNone(layout_quality_issue(source, source, 70))

    def test_long_formatted_post_still_needs_space_between_information_blocks(self):
        output = LONG_SOURCE.replace("地址：", "📍 <b>地址</b>：").replace("消费明细💰", "💰 <b>消费明细</b>")
        self.assertIsNone(layout_quality_issue(LONG_SOURCE, output, 70))
        self.assertIn("独立区块之间空一行", layout_quality_issue(LONG_SOURCE, output.replace("\n\n", "\n"), 70))


if __name__ == "__main__":
    unittest.main()
