from datetime import datetime


def _media_label(message) -> str:
    if getattr(message, "photo", None):
        return "[图片]"
    if getattr(message, "video", None) or getattr(message, "video_note", None):
        return "[视频]"
    if getattr(message, "voice", None):
        return "[语音]"
    if getattr(message, "audio", None):
        return "[音频]"
    if getattr(message, "sticker", None):
        return "[贴纸]"
    if getattr(message, "gif", None):
        return "[动图]"
    if getattr(message, "contact", None):
        return "[联系人]"
    if getattr(message, "geo", None):
        return "[位置]"
    if getattr(message, "poll", None):
        return "[投票]"
    if getattr(message, "document", None):
        file_name = getattr(getattr(message, "file", None), "name", None)
        return f"[文件] {file_name}" if file_name else "[文件]"
    if getattr(message, "action", None):
        return "[服务消息]"
    return ""


def message_summary(message) -> str:
    text = (getattr(message, "message", None) or "").strip()
    media = _media_label(message)
    if media and text:
        return f"{media}\n{text}"
    return media or text or "[不支持预览的消息]"


def entity_display_name(entity, fallback: str = "-") -> str:
    title = (getattr(entity, "title", None) or "").strip()
    if title:
        return title

    full_name = " ".join(
        part.strip()
        for part in (
            getattr(entity, "first_name", None) or "",
            getattr(entity, "last_name", None) or "",
        )
        if part and part.strip()
    )
    return full_name or fallback


def entity_username(entity) -> str:
    username = (getattr(entity, "username", None) or "").strip().lstrip("@")
    return f"@{username}" if username else "-"


def notification_priority(event) -> str:
    message = getattr(event, "message", None)
    if getattr(event, "is_private", False) or getattr(message, "mentioned", False):
        return "high"
    return "default"


def format_notification_body(chat_title: str, username: str, text: str, sent_at: datetime) -> str:
    local_time = sent_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"聊天名称:\n{chat_title}\n\n"
        f"用户名:\n{username}\n\n"
        f"消息:\n{text}\n\n"
        f"时间:\n{local_time}"
    )
