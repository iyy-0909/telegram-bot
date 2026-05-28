from types import SimpleNamespace

import bot.content_processor as content_processor


def make_task(**overrides):
    data = {
        "blocked_keywords": "[]",
        "replace_words": "{}",
        "remove_contact_lines": True,
        "use_random_head": False,
        "use_random_body": False,
        "use_random_footer": True,
        "selected_footer_template_group_id": 1,
        "selected_footer_template_id": None,
        "selected_filter_template_group_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_skip_when_original_text_removed_before_templates():
    original_picker = content_processor.pick_template_content
    content_processor.pick_template_content = lambda *_args, **_kwargs: "FOOTER"

    try:
        result = content_processor.process_content("TG: @demo_user", make_task())
    finally:
        content_processor.pick_template_content = original_picker

    assert result["blocked"] is True
    assert result["reason"] == "empty_after_process"
    assert result["text"] == ""


if __name__ == "__main__":
    test_skip_when_original_text_removed_before_templates()
    print("ok")
