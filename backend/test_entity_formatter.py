from bot.entity_formatter import (
    format_prepared_text,
    utf16_len,
)


class BaseEntity:
    def __init__(self, offset, length, **kwargs):
        self.offset = offset
        self.length = length
        for key, value in kwargs.items():
            setattr(self, key, value)


class MessageEntityBold(BaseEntity):
    pass


class MessageEntityTextUrl(BaseEntity):
    pass


class MessageEntityBlockquote(BaseEntity):
    pass


class Message:
    def __init__(self, text, entities):
        self.message = text
        self.entities = entities


def assert_entity(result, entity_type, text, final_text=None):
    final_text = final_text or result["plain_text"]
    for entity in result.get("entities", []):
        if entity["type"] != entity_type:
            continue

        start = entity["offset"]
        end = start + entity["length"]
        assert end <= utf16_len(final_text)
        return entity

    raise AssertionError(f"missing entity type={entity_type} for {text}")


def test_unmodified_emoji_bold():
    text = "中文 😀 bold"
    start = text.index("bold")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("bold"))])
    result = format_prepared_text(msg, text)
    assert result["format_level"] == "entities"
    assert_entity(result, "bold", "bold")


def test_insert_head_shifts_offset():
    text = "hello bold"
    start = text.index("bold")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("bold"))])
    result = format_prepared_text(msg, "HEAD\n\nhello bold")
    entity = assert_entity(result, "bold", "bold")
    assert entity["offset"] == utf16_len("HEAD\n\nhello ")


def test_append_footer_keeps_entity():
    text = "hello bold"
    start = text.index("bold")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("bold"))])
    result = format_prepared_text(msg, "hello bold\n\nFOOTER")
    assert_entity(result, "bold", "bold")


def test_replace_before_entity_shifts_offset():
    text = "abc bold"
    start = text.index("bold")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("bold"))])
    result = format_prepared_text(msg, "abcdef bold")
    entity = assert_entity(result, "bold", "bold")
    assert entity["offset"] == utf16_len("abcdef ")


def test_replace_inside_entity_drops_entity():
    text = "hello bold"
    start = text.index("bold")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("bold"))])
    result = format_prepared_text(msg, "hello bXXX")
    assert not result.get("entities")
    assert result["format_level"] == "html"


def test_delete_line_keeps_other_line_entity():
    text = "remove me\nkeep bold"
    start = text.index("bold")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("bold"))])
    result = format_prepared_text(msg, "keep bold")
    entity = assert_entity(result, "bold", "bold")
    assert entity["offset"] == utf16_len("keep ")


def test_delete_contact_drops_related_entity():
    text = "contact @name\nnormal"
    start = text.index("@name")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("@name"))])
    result = format_prepared_text(msg, "normal")
    assert not result.get("entities")


def test_truncate_shrinks_or_drops():
    text = "hello boldtail"
    start = text.index("boldtail")
    msg = Message(text, [MessageEntityBold(utf16_len(text[:start]), utf16_len("boldtail"))])
    result = format_prepared_text(msg, "hello bold")
    entity = assert_entity(result, "bold", "bold")
    assert entity["length"] == utf16_len("bold")


def test_html_escape_fallback():
    text = "<tag> & bold"
    msg = Message(text, [])
    result = format_prepared_text(msg, text)
    assert result["format_level"] == "html"
    assert result["text"] == "&lt;tag&gt; &amp; bold"


def test_text_link_downgrades_and_blockquote_keeps():
    text = "quote\nlink"
    quote = MessageEntityBlockquote(0, utf16_len("quote\n"))
    link_start = text.index("link")
    link = MessageEntityTextUrl(
        utf16_len(text[:link_start]),
        utf16_len("link"),
        url="https://example.com",
    )
    msg = Message(text, [quote, link])
    result = format_prepared_text(msg, text)
    assert_entity(result, "blockquote", "quote")
    assert not any(
        entity.get("type") == "text_link"
        for entity in result.get("entities", [])
    )
    assert "https://example.com" not in result.get("text", "")


def run_all():
    tests = [
        test_unmodified_emoji_bold,
        test_insert_head_shifts_offset,
        test_append_footer_keeps_entity,
        test_replace_before_entity_shifts_offset,
        test_replace_inside_entity_drops_entity,
        test_delete_line_keeps_other_line_entity,
        test_delete_contact_drops_related_entity,
        test_truncate_shrinks_or_drops,
        test_html_escape_fallback,
        test_text_link_downgrades_and_blockquote_keeps,
    ]

    for test in tests:
        test()
        print(f"ok {test.__name__}")


if __name__ == "__main__":
    run_all()
