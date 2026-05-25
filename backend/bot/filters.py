def should_block(text: str, keywords: list[str]) -> bool:

    if not text:
        return False

    return any(keyword in text for keyword in keywords)