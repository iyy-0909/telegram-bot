def rewrite_text(
    text: str,
    replace_words: dict,
    footer: str = ""
) -> str:

    text = text or ""

    for old, new in replace_words.items():
        text = text.replace(old, new)

    text = text.strip()

    if footer:
        text += footer

    return text