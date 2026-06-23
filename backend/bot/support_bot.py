import asyncio
import ast
from collections import OrderedDict
from datetime import datetime

from bot.bot_sender import BotApiError, bot_get_me, request_post
from bot.logger import logger
from bot.notifier import resolve_support_bot_alerts, send_ack_required_alert
from bot.support_media import is_uploaded_media_ref, resolve_uploaded_media_path
from db.crud_bot import get_bot
from db.crud_support import (
    add_support_message,
    as_bool,
    get_conversation_by_thread_id,
    get_conversation_detail,
    get_message_by_support_group_message_id,
    get_or_create_conversation,
    get_support_bot_config,
    get_support_settings,
    list_support_bots,
    set_customer_blocked,
    update_conversation_topic,
    update_conversation_status,
    update_support_bot_error,
    update_support_message_group_message_id,
    upsert_customer,
)


_polling_task = None
_polling_tasks = {}
_offset = None
_offsets = {}
_deleted_webhook_tokens = set()
_recent_group_chats = OrderedDict()
_group_join_notice_sent = set()
_last_polling_conflict_log_at = 0
TRANSIENT_BOT_API_ERROR_CODES = {500, 502, 503, 504}


class SupportBotConfigError(Exception):
    pass


def parse_bot_api_error(error):
    text = str(error)
    try:
        data = ast.literal_eval(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"description": text}


def is_message_thread_not_found_error(error):
    data = parse_bot_api_error(error)
    description = str(data.get("description") or "").lower()
    return parse_error_code(data) == 400 and "message thread not found" in description


def friendly_media_error(description):
    lower = (description or "").lower()
    if "wrong file identifier" in lower or "file_id" in lower and "wrong" in lower:
        return "媒体 file_id 无效，无法发送。"
    if "file is too big" in lower or "too big" in lower:
        return "媒体文件过大，Bot API 无法发送。"
    if "bot was blocked by the user" in lower:
        return "客户已拉黑 Bot，无法继续回复。"
    return f"回复客户失败：{description}"


def get_support_token_and_settings():
    settings = get_support_settings()
    bot_id = (settings.get("support_bot_id") or "").strip()
    raw_token = (settings.get("support_bot_token") or "").strip()

    if bot_id:
        try:
            bot = get_bot(int(bot_id))
        except Exception:
            bot = None
        if bot and bot.enabled and bot.token:
            return bot.token, settings

    if raw_token:
        return raw_token, settings

    return None, settings


def get_token_for_support_bot(config):
    bot_id = config.get("bot_id")
    raw_token = (config.get("bot_token") or "").strip()

    if bot_id:
        try:
            bot = get_bot(int(bot_id))
        except Exception:
            bot = None
        if bot and bot.enabled and bot.token:
            return bot.token

    return raw_token or None


def support_bot_settings(config):
    return {
        "support_bot_id": str(config.get("bot_id") or ""),
        "support_bot_token": config.get("bot_token") or "",
        "support_polling_enabled": "1" if config.get("polling_enabled") else "0",
        "support_group_chat_id": config.get("support_group_chat_id") or "",
        "support_backend_base_url": config.get("backend_base_url") or "",
        "welcome_message": config.get("welcome_message") or "",
        "welcome_text_type": config.get("welcome_text_type") or "plain",
        "welcome_media_type": config.get("welcome_media_type") or "text",
        "welcome_media_file_id": config.get("welcome_media_file_id") or "",
        "off_hours_message": config.get("off_hours_message") or "",
        "business_hours_enabled": "1" if config.get("business_hours_enabled") else "0",
        "business_start_hour": str(config.get("business_start_hour") or 9),
        "business_end_hour": str(config.get("business_end_hour") or 22),
        "_support_bot_id": config.get("id"),
    }


def normalize_welcome_text_type(value):
    return "html" if str(value or "").strip().lower() == "html" else "plain"


async def notify_support_warning(title, detail="", context=None):
    context = context or {}
    support_bot_id = context.get("support_bot_id") or "global"
    method = context.get("method") or ""
    alert_key = context.get("alert_key") or f"support:{support_bot_id}:{title}:{method}"
    bot_name = context.get("bot_name") or support_bot_display_name(support_bot_id)
    display_title = f"{bot_name}：{title}" if bot_name else title
    display_detail = detail
    if bot_name and f"客服机器人：{bot_name}" not in str(detail or ""):
        display_detail = f"客服机器人：{bot_name}\n{detail or ''}".strip()
    return await send_ack_required_alert(
        alert_key=alert_key,
        title=display_title,
        detail=display_detail,
        module="客服机器人",
        context={
            **context,
            "module": "客服机器人",
        },
    )


def support_bot_display_name(support_bot_id):
    if not support_bot_id or support_bot_id == "global":
        return ""

    try:
        config = get_support_bot_config(support_bot_id, include_secret=False)
    except Exception:
        config = None

    if not config:
        return f"ID {support_bot_id}"

    return config.get("name") or config.get("bot_username") or f"ID {support_bot_id}"


def parse_error_code(error_data):
    try:
        return int(error_data.get("error_code") or 0)
    except (TypeError, ValueError):
        return 0


def rewind_request_files(files):
    for file_item in (files or {}).values():
        try:
            file_item[1].seek(0)
        except Exception:
            pass


async def request_post_with_retry(
    token,
    method,
    data=None,
    files=None,
    *,
    max_attempts=3,
    context="",
    alert_context=None,
):
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.to_thread(request_post, token, method, data, files)
        except Exception as e:
            error_data = parse_bot_api_error(e)
            error_code = parse_error_code(error_data)
            should_retry = error_code == 429 or error_code in TRANSIENT_BOT_API_ERROR_CODES

            if not should_retry or attempt >= max_attempts:
                raise

            retry_after = 0
            if error_code == 429:
                retry_after = int((error_data.get("parameters") or {}).get("retry_after") or 3)
            else:
                retry_after = min(2 * attempt, 8)

            logger.warning(
                f"Bot API 临时错误，准备重试 | method={method} | "
                f"error_code={error_code} | attempt={attempt}/{max_attempts} | "
                f"sleep={retry_after}s | context={context or '-'}"
            )
            await notify_support_warning(
                "Bot API 临时错误，准备重试",
                (
                    f"error_code={error_code} | attempt={attempt}/{max_attempts} | "
                    f"sleep={retry_after}s | context={context or '-'}"
                ),
                context={
                    **(alert_context or {}),
                    "method": method,
                },
            )
            rewind_request_files(files)
            await asyncio.sleep(max(retry_after, 1))


async def ensure_polling_mode(token):
    if not token or token in _deleted_webhook_tokens:
        return

    await request_post_with_retry(
        token,
        "deleteWebhook",
        {"drop_pending_updates": False},
        None,
        context="support_delete_webhook",
    )
    _deleted_webhook_tokens.add(token)
    logger.info("客服 Bot 已切换到 polling 模式：deleteWebhook ok")


def remember_group_chat(chat):
    chat_type = chat.get("type")
    if chat_type not in {"group", "supergroup"}:
        return

    chat_id = str(chat.get("id") or "")
    if not chat_id:
        return

    _recent_group_chats[chat_id] = {
        "chat_id": chat_id,
        "title": chat.get("title") or "",
        "type": chat_type,
        "username": chat.get("username") or "",
        "last_seen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    while len(_recent_group_chats) > 20:
        _recent_group_chats.popitem(last=False)


def get_recent_group_chats():
    return list(reversed(list(_recent_group_chats.values())))


async def maybe_send_group_chat_id_notice(token, message):
    chat = message.get("chat") or {}
    chat_type = chat.get("type")

    if chat_type not in {"group", "supergroup"}:
        return

    new_members = message.get("new_chat_members") or []
    if not new_members:
        return

    bot = await get_bot_identity(token)
    bot_id = str(bot.get("id") or "")

    if not bot_id:
        return

    joined_self = any(str(member.get("id") or "") == bot_id for member in new_members)

    if not joined_self:
        return

    chat_id = str(chat.get("id") or "")
    if not chat_id:
        return

    dedupe_key = f"{bot_id}:{chat_id}"
    if dedupe_key in _group_join_notice_sent:
        return

    _group_join_notice_sent.add(dedupe_key)
    title = chat.get("title") or "-"
    text = (
        "客服 Bot 已加入当前群。\n\n"
        f"群名称：{title}\n"
        f"群类型：{chat_type}\n"
        f"客服群 chat_id：{chat_id}\n\n"
        "请把上面的 chat_id 填到后台「客服机器人」里的客服群 chat_id。"
    )
    await send_text_to_chat(token, chat_id, text)


async def test_support_bot_config():
    token, settings = get_support_token_and_settings()
    if not token:
        return {
            "ok": False,
            "message": "客服 Bot 未配置",
        }

    try:
        await ensure_polling_mode(token)
        result = await bot_get_me(token)
        group_chat_id = (settings.get("support_group_chat_id") or "").strip()
        permission = (
            await check_group_topic_permission(token, group_chat_id)
            if group_chat_id
            else None
        )
        return {
            "ok": True,
            "mode": "polling",
            "bot": result.get("result") or {},
            "group_permission": permission,
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": "polling",
            "message": str(e),
        }


def extract_group_chats_from_updates(updates):
    groups = OrderedDict()
    for update in updates or []:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") not in {"group", "supergroup"}:
            continue

        remember_group_chat(chat)
        chat_id = str(chat.get("id") or "")
        groups[chat_id] = {
            "chat_id": chat_id,
            "title": chat.get("title") or "",
            "type": chat.get("type") or "",
            "username": chat.get("username") or "",
            "last_update_id": update.get("update_id"),
            "message_id": message.get("message_id"),
            "last_seen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return list(groups.values())


async def get_bot_identity(token):
    result = await bot_get_me(token)
    return result.get("result") or {}


async def check_group_topic_permission(token, chat_id):
    try:
        bot = await get_bot_identity(token)
        bot_id = bot.get("id")
        if not bot_id:
            return {
                "ok": False,
                "message": "无法获取 Bot ID",
            }
        result = await asyncio.to_thread(
            request_post,
            token,
            "getChatMember",
            {
                "chat_id": chat_id,
                "user_id": bot_id,
            },
            None,
        )
        member = result.get("result") or {}
        status = member.get("status")
        can_manage_topics = bool(member.get("can_manage_topics"))
        return {
            "ok": status == "administrator" and can_manage_topics,
            "status": status,
            "can_manage_topics": can_manage_topics,
            "message": "" if can_manage_topics else "Bot 缺少管理话题权限，无法自动创建客户话题",
        }
    except Exception as e:
        return {
            "ok": False,
            "message": str(e),
        }


async def get_recent_support_updates(limit=30):
    token, settings = get_support_token_and_settings()
    if not token:
        return {
            "ok": False,
            "message": "客服 Bot 未配置",
            "groups": get_recent_group_chats(),
        }

    try:
        await ensure_polling_mode(token)
        result = await asyncio.to_thread(
            request_post,
            token,
            "getUpdates",
            {
                "timeout": 0,
                "limit": max(min(int(limit or 30), 100), 1),
                "allowed_updates": '["message"]',
            },
            None,
        )
        updates = result.get("result") or []
        groups = extract_group_chats_from_updates(updates)
        for group in groups:
            group["permission"] = await check_group_topic_permission(token, group["chat_id"])
        return {
            "ok": True,
            "mode": "polling",
            "groups": groups or get_recent_group_chats(),
            "updates_count": len(updates),
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": "polling",
            "message": str(e),
            "groups": get_recent_group_chats(),
        }


def media_payload(media, field_name, caption=""):
    media = media or {}
    return {
        "text": caption or "",
        "caption": caption or "",
        "file_id": media.get("file_id") or "",
        "file_unique_id": media.get("file_unique_id") or "",
        "file_name": media.get("file_name") or "",
        "mime_type": media.get("mime_type") or "",
        "file_size": media.get("file_size"),
        "width": media.get("width"),
        "height": media.get("height"),
        "duration": media.get("duration"),
        "api_field": field_name,
    }


def extract_message_payload(message):
    if message.get("text") is not None:
        return {
            "message_type": "text",
            "text": message.get("text") or "",
            "caption": "",
            "file_id": "",
            "api_field": "text",
        }

    caption = message.get("caption") or ""
    if message.get("photo"):
        photos = message.get("photo") or []
        photo = photos[-1] if photos else {}
        return {
            "message_type": "photo",
            **media_payload(photo, "photo", caption),
        }
    if message.get("video"):
        return {
            "message_type": "video",
            **media_payload(message.get("video"), "video", caption),
        }
    if message.get("document"):
        return {
            "message_type": "document",
            **media_payload(message.get("document"), "document", caption),
        }
    if message.get("voice"):
        return {
            "message_type": "voice",
            **media_payload(message.get("voice"), "voice", caption),
        }
    if message.get("sticker"):
        sticker = message.get("sticker") or {}
        payload = media_payload(sticker, "sticker", sticker.get("emoji") or "")
        payload["text"] = sticker.get("emoji") or ""
        payload["caption"] = ""
        return {
            "message_type": "sticker",
            **payload,
        }
    if message.get("animation"):
        return {
            "message_type": "animation",
            **media_payload(message.get("animation"), "animation", caption),
        }
    if message.get("audio"):
        return {
            "message_type": "audio",
            **media_payload(message.get("audio"), "audio", caption),
        }
    if message.get("video_note"):
        return {
            "message_type": "video_note",
            **media_payload(message.get("video_note"), "video_note", ""),
        }

    return {
        "message_type": "other",
        "text": "",
        "caption": "",
        "file_id": "",
        "api_field": "text",
    }


def detect_message_type(message):
    payload = extract_message_payload(message)
    return payload["message_type"], payload.get("text") or "", payload.get("file_id") or ""


def parse_start_source(text):
    text = (text or "").strip()
    if not text.startswith("/start"):
        return ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def is_configured_support_group(chat_id, settings):
    configured = str(settings.get("support_group_chat_id") or "").strip()
    return bool(configured) and str(chat_id) == configured


def is_outside_business_hours(settings):
    if not as_bool(settings.get("business_hours_enabled")):
        return False
    try:
        start_hour = int(settings.get("business_start_hour") or 9)
        end_hour = int(settings.get("business_end_hour") or 22)
    except (TypeError, ValueError):
        return False
    hour = datetime.now().hour
    if start_hour <= end_hour:
        return not (start_hour <= hour < end_hour)
    return not (hour >= start_hour or hour < end_hour)


def support_group_message_text(customer, conversation, text, message_type):
    username = f"@{customer.username}" if customer.username else "-"
    customer_name = customer_display_name(customer)
    preview = text or message_type_label(message_type)
    return (
        "【新客户消息】\n\n"
        f"客户：{customer_name}\n"
        f"用户名：{username}\n"
        f"用户ID：{customer.telegram_user_id}\n\n"
        "内容：\n"
        f"{preview[:1500]}\n\n"
        "客服在当前话题内直接发送消息，即可回复该客户。"
    )


def support_group_caption(customer, conversation, payload):
    message_type = payload.get("message_type") or "other"
    content = payload.get("caption") or payload.get("text") or message_type_label(message_type)
    return support_group_message_text(
        customer,
        conversation,
        content,
        message_type,
    )


def build_topic_name(customer, conversation):
    return f"客户 {customer_display_name(customer)}"


def customer_display_name(customer):
    name = " ".join([
        item
        for item in [customer.first_name or "", customer.last_name or ""]
        if item
    ]).strip()

    if name:
        return name

    if customer.username:
        return f"@{customer.username}"

    return str(customer.telegram_user_id or "-")


def message_type_label(message_type):
    labels = {
        "text": "[文本]",
        "photo": "[图片]",
        "video": "[视频]",
        "document": "[文件]",
        "voice": "[语音]",
        "sticker": "[贴纸]",
        "animation": "[动图]",
        "audio": "[音频]",
        "video_note": "[视频消息]",
        "other": "[其他消息]",
    }
    return labels.get(message_type or "other", f"[{message_type}]")


def support_user_label(user):
    if not user:
        return ""
    username = user.get("username") or ""
    user_id = user.get("id") or ""
    return f"@{username}" if username else str(user_id)


async def send_text_with_retry(token, chat_id, text, *, retry_429=True):
    return await send_text_to_chat(
        token,
        chat_id,
        text,
        retry_429=retry_429,
    )


async def send_text_to_chat(token, chat_id, text, message_thread_id=None, *, retry_429=True):
    data = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if message_thread_id:
        data["message_thread_id"] = int(message_thread_id)
    return await request_post_with_retry(
        token,
        "sendMessage",
        data,
        None,
        max_attempts=3 if retry_429 else 1,
        context=f"send_text chat_id={chat_id}",
    )


SEND_METHOD_BY_TYPE = {
    "text": ("sendMessage", "text"),
    "photo": ("sendPhoto", "photo"),
    "video": ("sendVideo", "video"),
    "document": ("sendDocument", "document"),
    "voice": ("sendVoice", "voice"),
    "sticker": ("sendSticker", "sticker"),
    "animation": ("sendAnimation", "animation"),
    "audio": ("sendAudio", "audio"),
    "video_note": ("sendVideoNote", "video_note"),
}


CAPTION_TYPES = {"photo", "video", "document", "voice", "animation", "audio"}


async def send_telegram_by_type(
    token,
    chat_id,
    message_type,
    payload,
    *,
    message_thread_id=None,
    reply_to_message_id=None,
    retry_429=True,
):
    method, field_name = SEND_METHOD_BY_TYPE.get(message_type, ("sendMessage", "text"))
    data = {"chat_id": chat_id}
    if message_thread_id:
        data["message_thread_id"] = int(message_thread_id)
    if reply_to_message_id:
        data["reply_to_message_id"] = int(reply_to_message_id)

    if message_type == "text":
        data["text"] = payload.get("text") or payload.get("caption") or ""
        data["disable_web_page_preview"] = True
        parse_mode = payload.get("parse_mode") or ""
        if parse_mode:
            data["parse_mode"] = parse_mode
    else:
        file_id = payload.get("file_id") or ""
        if not file_id:
            raise BotApiError(f"{message_type} missing file_id")
        files = None
        if is_uploaded_media_ref(file_id):
            media_path = resolve_uploaded_media_path(file_id)
            if not media_path or not media_path.exists():
                raise BotApiError(f"{message_type} uploaded media missing")
            upload_file = media_path.open("rb")
            files = {
                field_name: (media_path.name, upload_file),
            }
        else:
            data[field_name] = file_id
        caption = payload.get("caption") or ""
        if caption and message_type in CAPTION_TYPES:
            data["caption"] = caption[:1024]
            parse_mode = payload.get("parse_mode") or ""
            if parse_mode:
                data["parse_mode"] = parse_mode

    try:
        return await request_post_with_retry(
            token,
            method,
            data,
            files if message_type != "text" else None,
            max_attempts=3 if retry_429 else 1,
            context=f"send_{message_type} chat_id={chat_id}",
        )
    finally:
        if message_type != "text" and files:
            for file_item in files.values():
                file_item[1].close()


async def create_forum_topic(token, chat_id, name):
    result = await request_post_with_retry(
        token,
        "createForumTopic",
        {
            "chat_id": chat_id,
            "name": name[:128],
        },
        None,
        context=f"create_forum_topic chat_id={chat_id}",
    )
    topic = result.get("result") or {}
    return topic.get("message_thread_id")


async def ensure_conversation_topic(token, group_chat_id, customer, conversation, *, force_recreate=False):
    thread_id = getattr(conversation, "support_thread_id", None)
    if thread_id and not force_recreate:
        return int(thread_id)

    topic_name = build_topic_name(customer, conversation)
    thread_id = await create_forum_topic(token, group_chat_id, topic_name)
    if not thread_id:
        raise BotApiError("createForumTopic did not return message_thread_id")

    update_conversation_topic(conversation.id, thread_id, topic_name)
    conversation.support_thread_id = thread_id
    conversation.support_topic_name = topic_name
    return int(thread_id)


async def recreate_conversation_topic(token, group_chat_id, customer, conversation, settings, reason=""):
    old_thread_id = getattr(conversation, "support_thread_id", None)
    thread_id = await ensure_conversation_topic(
        token,
        group_chat_id,
        customer,
        conversation,
        force_recreate=True,
    )
    detail = (
        "客服话题已丢失，系统已自动重建话题 | "
        f"conversation_id={conversation.id} | customer_id={customer.id} | "
        f"old_thread_id={old_thread_id or '-'} | new_thread_id={thread_id} | "
        f"reason={reason or '-'}"
    )
    logger.warning(detail)
    await notify_support_warning(
        "客服话题已自动重建",
        detail,
        context={
            "support_bot_id": settings.get("_support_bot_id"),
            "customer_id": customer.id,
            "conversation_id": conversation.id,
            "group_chat_id": group_chat_id,
            "thread_id": thread_id,
        },
    )
    return thread_id


async def send_support_message(chat_id, text, token=None):
    if not token:
        token, _settings = get_support_token_and_settings()
    if not token:
        raise BotApiError("客服 Bot 未配置或未启用")
    return await send_text_to_chat(token, chat_id, text)


async def send_group_notice(text, token=None, settings=None, message_thread_id=None):
    if not token or not settings:
        token, settings = get_support_token_and_settings()
    group_chat_id = (settings.get("support_group_chat_id") or "").strip()
    if not token or not group_chat_id:
        return None
    try:
        return await send_text_to_chat(
            token,
            group_chat_id,
            text,
            message_thread_id=message_thread_id,
        )
    except Exception as e:
        detail = f"客服群提示发送失败 | {e}"
        logger.warning(detail)
        await notify_support_warning(
            "客服群提示发送失败",
            detail,
            context={
                "support_bot_id": settings.get("_support_bot_id"),
                "group_chat_id": group_chat_id,
                "thread_id": message_thread_id,
            },
        )
        return None


async def forward_customer_message_to_group(customer, conversation, message, payload, support_message, token, settings):
    group_chat_id = (settings.get("support_group_chat_id") or "").strip()
    if not token or not group_chat_id:
        detail = "客服群未配置，客户消息只入库不转发"
        logger.warning(detail)
        await notify_support_warning(
            "客服群未配置",
            detail,
            context={
                "support_bot_id": settings.get("_support_bot_id"),
                "customer_id": getattr(customer, "id", None),
                "conversation_id": getattr(conversation, "id", None),
            },
        )
        return None

    message_type = payload.get("message_type") or "text"
    notice = support_group_caption(customer, conversation, payload)
    thread_id = None
    try:
        thread_id = await ensure_conversation_topic(token, group_chat_id, customer, conversation)
    except Exception as e:
        detail = (
            f"创建客户话题失败，降级发送到 General | "
            f"conversation_id={conversation.id} | customer_id={customer.id} | {e}"
        )
        logger.warning(detail)
        await notify_support_warning(
            "创建客户话题失败",
            detail,
            context={
                "support_bot_id": settings.get("_support_bot_id"),
                "customer_id": customer.id,
                "conversation_id": conversation.id,
                "group_chat_id": group_chat_id,
            },
        )
        await send_text_to_chat(
            token,
            group_chat_id,
            "创建客户话题失败，请检查 Bot 是否有 Manage Topics 权限。",
        )

    async def send_once(current_thread_id):
        send_payload = dict(payload)
        if message_type == "text":
            send_payload["text"] = notice
        elif message_type in CAPTION_TYPES:
            send_payload["caption"] = notice
        else:
            await send_text_to_chat(
                token,
                group_chat_id,
                notice,
                message_thread_id=current_thread_id,
            )

        return await send_telegram_by_type(
            token,
            group_chat_id,
            message_type,
            send_payload,
            message_thread_id=current_thread_id,
        )

    try:
        result = await send_once(thread_id)
    except Exception as e:
        if not thread_id or not is_message_thread_not_found_error(e):
            raise
        thread_id = await recreate_conversation_topic(
            token,
            group_chat_id,
            customer,
            conversation,
            settings,
            reason=str(e),
        )
        result = await send_once(thread_id)

    group_message_id = (result.get("result") or {}).get("message_id")
    if group_message_id:
        update_support_message_group_message_id(support_message.id, group_message_id)
    else:
        detail = (
            "客服群消息发送成功但未返回 message_id，无法建立会话映射 | "
            f"conversation_id={conversation.id} | customer_id={customer.id} | "
            f"support_message_id={support_message.id}"
        )
        logger.warning(detail)
        await notify_support_warning(
            "客服群消息未返回 message_id",
            detail,
            context={
                "support_bot_id": settings.get("_support_bot_id"),
                "customer_id": customer.id,
                "conversation_id": conversation.id,
                "group_chat_id": group_chat_id,
            },
        )
    return group_message_id


async def maybe_send_auto_message(customer, conversation, text, token, settings, text_type="plain"):
    media_type = settings.get("welcome_media_type") or "text"
    media_file_id = settings.get("welcome_media_file_id") or ""
    parse_mode = "HTML" if normalize_welcome_text_type(text_type) == "html" else ""

    if not (text.strip() or media_file_id) or customer.blocked:
        return
    try:
        if media_file_id:
            payload = {
                "file_id": media_file_id,
                "caption": text,
                "text": text,
            }
            if parse_mode and text:
                payload["parse_mode"] = parse_mode
            result = await send_telegram_by_type(
                token,
                customer.telegram_chat_id,
                media_type,
                payload,
            )
            message_type = media_type
        else:
            payload = {"text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            result = await send_telegram_by_type(
                token,
                customer.telegram_chat_id,
                "text",
                payload,
            )
            message_type = "text"
        telegram_message_id = (result.get("result") or {}).get("message_id")
        add_support_message(
            support_bot_id=settings.get("_support_bot_id"),
            conversation_id=conversation.id,
            customer_id=customer.id,
            sender_type="bot",
            sender_id="support_bot",
            message_type=message_type,
            text=text,
            caption=text if media_file_id else "",
            file_id=media_file_id,
            telegram_message_id=telegram_message_id,
            send_status="success",
        )
    except Exception as e:
        detail = f"客服自动回复失败，已忽略 | customer_id={customer.id} | {e}"
        logger.warning(detail)
        await notify_support_warning(
            "客服自动回复失败",
            detail,
            context={
                "support_bot_id": settings.get("_support_bot_id"),
                "customer_id": customer.id,
                "conversation_id": conversation.id,
            },
        )


async def handle_private_customer_message(message, settings, token):
    user = message.get("from") or {}
    if user.get("is_bot"):
        return

    payload = extract_message_payload(message)
    message_type = payload.get("message_type") or "other"
    text = payload.get("text") or ""
    is_start = message_type == "text" and (text or "").strip().startswith("/start")
    source = parse_start_source(text) if message_type == "text" else ""
    support_bot_id = settings.get("_support_bot_id")
    customer, created = upsert_customer(
        user,
        message.get("chat", {}).get("id"),
        source=source,
        support_bot_id=support_bot_id,
    )
    conversation = get_or_create_conversation(customer.id, support_bot_id=support_bot_id)

    if is_start and customer.blocked:
        set_customer_blocked(customer.id, False)
        customer.blocked = False
        update_conversation_status(conversation.id, "open")
        logger.info(f"客户重新 /start，已恢复 blocked 状态 | customer_id={customer.id}")

    support_message = add_support_message(
        support_bot_id=support_bot_id,
        conversation_id=conversation.id,
        customer_id=customer.id,
        sender_type="customer",
        sender_id=customer.telegram_user_id,
        message_type=message_type,
        text=text,
        caption=payload.get("caption") or "",
        file_id=payload.get("file_id") or "",
        file_unique_id=payload.get("file_unique_id") or "",
        file_name=payload.get("file_name") or "",
        mime_type=payload.get("mime_type") or "",
        file_size=payload.get("file_size"),
        width=payload.get("width"),
        height=payload.get("height"),
        duration=payload.get("duration"),
        telegram_message_id=message.get("message_id"),
        send_status="success",
        increment_unread=True,
    )

    if customer.blocked:
        update_conversation_status(conversation.id, "blocked")
        logger.info(f"黑名单客户消息已入库但不转发 | customer_id={customer.id}")
        return

    try:
        await forward_customer_message_to_group(
            customer,
            conversation,
            message,
            payload,
            support_message,
            token,
            settings,
        )
    except Exception as e:
        detail = f"客户消息转发客服群失败 | customer_id={customer.id} | {e}"
        logger.warning(detail)
        await notify_support_warning(
            "客户消息转发客服群失败",
            detail,
            context={
                "support_bot_id": support_bot_id,
                "customer_id": customer.id,
                "conversation_id": conversation.id,
            },
        )

    if is_start:
        await maybe_send_auto_message(
            customer,
            conversation,
            settings.get("welcome_message") or "",
            token,
            settings,
            text_type=settings.get("welcome_text_type") or "plain",
        )
        return

    if is_outside_business_hours(settings):
        await maybe_send_auto_message(customer, conversation, settings.get("off_hours_message") or "", token, settings)


def get_replied_customer_context(reply_to_message, support_bot_id=None):
    if not reply_to_message:
        return None
    group_message_id = reply_to_message.get("message_id")
    if not group_message_id:
        return None
    source_message = get_message_by_support_group_message_id(group_message_id, support_bot_id=support_bot_id)
    if not source_message:
        return None
    if source_message.get("sender_type") != "customer":
        return None
    detail = get_conversation_detail(source_message["conversation_id"])
    if not detail:
        return None
    return source_message, detail


def get_thread_customer_context(message, support_bot_id=None):
    thread_id = message.get("message_thread_id")
    if not thread_id:
        return None
    conversation = get_conversation_by_thread_id(thread_id, support_bot_id=support_bot_id)
    if not conversation:
        return None
    detail = get_conversation_detail(conversation["id"])
    if not detail:
        return None
    return None, detail


async def handle_support_group_command(command, context, token, settings):
    source_message, detail = context
    conversation = detail["conversation"]
    customer = conversation.get("customer") or {}
    customer_id = customer.get("id")
    conversation_id = conversation.get("id")
    thread_id = conversation.get("support_thread_id")

    if command == "/close":
        update_conversation_status(conversation_id, "closed")
        await send_group_notice(
            f"会话已关闭：conversation_id={conversation_id}",
            token=token,
            settings=settings,
            message_thread_id=thread_id,
        )
        return

    if command == "/block":
        set_customer_blocked(customer_id, True)
        await send_group_notice(
            f"客户已拉黑：{customer.get('telegram_user_id')}",
            token=token,
            settings=settings,
            message_thread_id=thread_id,
        )
        return

    if command == "/unblock":
        set_customer_blocked(customer_id, False)
        await send_group_notice(
            f"客户已取消拉黑：{customer.get('telegram_user_id')}",
            token=token,
            settings=settings,
            message_thread_id=thread_id,
        )
        return

    if command == "/info":
        await send_group_notice(
            "客户信息\n"
            f"客户ID：{customer_id}\n"
            f"Telegram ID：{customer.get('telegram_user_id')}\n"
            f"用户名：@{customer.get('username') or '-'}\n"
            f"昵称：{customer.get('first_name') or ''} {customer.get('last_name') or ''}\n"
            f"来源：{customer.get('source') or '-'}\n"
            f"状态：{conversation.get('status')}\n"
            f"拉黑：{'是' if customer.get('blocked') else '否'}",
            token=token,
            settings=settings,
            message_thread_id=thread_id,
        )


async def reply_group_message_to_customer(message, context, token, settings):
    source_message, detail = context
    conversation = detail["conversation"]
    customer = conversation.get("customer") or {}
    thread_id = conversation.get("support_thread_id")
    payload = extract_message_payload(message)
    message_type = payload.get("message_type") or "other"
    text = payload.get("text") or ""
    if message_type == "other":
        return

    if customer.get("blocked"):
        await send_group_notice(
            "该客户已被拉黑，不能回复。可回复客户消息发送 /unblock 取消拉黑。",
            token=token,
            settings=settings,
            message_thread_id=thread_id,
        )
        return

    sender = message.get("from") or {}
    sender_label = support_user_label(sender)
    try:
        if not token:
            raise BotApiError("客服 Bot 未配置或未启用")
        result = await send_telegram_by_type(
            token,
            customer.get("telegram_chat_id"),
            message_type,
            payload,
        )
        telegram_message_id = (result.get("result") or {}).get("message_id")
        add_support_message(
            support_bot_id=settings.get("_support_bot_id"),
            conversation_id=conversation["id"],
            customer_id=customer["id"],
            sender_type="support",
            sender_id=sender_label,
            message_type=message_type,
            text=text,
            caption=payload.get("caption") or "",
            file_id=payload.get("file_id") or "",
            file_unique_id=payload.get("file_unique_id") or "",
            file_name=payload.get("file_name") or "",
            mime_type=payload.get("mime_type") or "",
            file_size=payload.get("file_size"),
            width=payload.get("width"),
            height=payload.get("height"),
            duration=payload.get("duration"),
            telegram_message_id=telegram_message_id,
            support_group_message_id=message.get("message_id"),
            reply_to_support_group_message_id=(
                source_message.get("support_group_message_id")
                if source_message
                else None
            ),
            send_status="success",
        )
        update_conversation_status(conversation["id"], "open")
        logger.info(
            f"客服群回复已转发客户 | conversation_id={conversation['id']} | customer_id={customer['id']}"
        )
    except Exception as e:
        data = parse_bot_api_error(e)
        description = str(data.get("description") or e)
        error_code = data.get("error_code")
        if error_code == 403 or "bot was blocked by the user" in description.lower():
            set_customer_blocked(customer["id"], True)
            await send_group_notice(
                "该客户已拉黑 Bot，无法继续回复。",
                token=token,
                settings=settings,
                message_thread_id=thread_id,
            )
        else:
            await send_group_notice(
                friendly_media_error(description),
                token=token,
                settings=settings,
                message_thread_id=thread_id,
            )
        add_support_message(
            support_bot_id=settings.get("_support_bot_id"),
            conversation_id=conversation["id"],
            customer_id=customer["id"],
            sender_type="support",
            sender_id=sender_label,
            message_type=message_type,
            text=text,
            caption=payload.get("caption") or "",
            file_id=payload.get("file_id") or "",
            file_unique_id=payload.get("file_unique_id") or "",
            file_name=payload.get("file_name") or "",
            mime_type=payload.get("mime_type") or "",
            file_size=payload.get("file_size"),
            width=payload.get("width"),
            height=payload.get("height"),
            duration=payload.get("duration"),
            support_group_message_id=message.get("message_id"),
            reply_to_support_group_message_id=(
                source_message.get("support_group_message_id")
                if source_message
                else None
            ),
            send_status="failed",
            status="failed",
            error=description,
            error_message=description,
        )


async def handle_support_group_message(message, settings, token):
    text = (message.get("text") or "").strip()
    reply_to_message = message.get("reply_to_message")
    current_thread_id = message.get("message_thread_id")
    support_bot_id = settings.get("_support_bot_id")
    context = get_thread_customer_context(message, support_bot_id=support_bot_id)
    if not context:
        context = get_replied_customer_context(reply_to_message, support_bot_id=support_bot_id)

    if text in {"/close", "/block", "/info", "/unblock"}:
        if not context:
            await send_group_notice(
                "请回复某条客户消息后再使用该命令。",
                token=token,
                settings=settings,
                message_thread_id=current_thread_id,
            )
            return
        await handle_support_group_command(text, context, token, settings)
        return

    if not context:
        if reply_to_message:
            await send_group_notice(
                "未找到对应客户会话，可能是历史消息或数据已失效。",
                token=token,
                settings=settings,
                message_thread_id=current_thread_id,
            )
        elif text:
            await send_group_notice(
                "请在客户话题内发送消息，或回复某条客户消息后再发送内容。",
                token=token,
                settings=settings,
                message_thread_id=current_thread_id,
            )
        return

    await reply_group_message_to_customer(message, context, token, settings)


async def handle_support_update(update, token=None, settings=None):
    message = update.get("message")
    if not message:
        return

    chat = message.get("chat") or {}
    if settings is None:
        settings = get_support_settings()
    remember_group_chat(chat)

    if chat.get("type") in {"group", "supergroup"} and token:
        try:
            await maybe_send_group_chat_id_notice(token, message)
        except Exception as e:
            detail = f"客服群 chat_id 自动提示发送失败 | {e}"
            logger.warning(detail)
            await notify_support_warning(
                "客服群 chat_id 自动提示发送失败",
                detail,
                context={"support_bot_id": settings.get("_support_bot_id")},
            )

    if chat.get("type") == "private":
        await handle_private_customer_message(message, settings, token)
        return

    if is_configured_support_group(chat.get("id"), settings):
        await handle_support_group_message(message, settings, token)


async def support_polling_worker(config):
    global _last_polling_conflict_log_at
    support_bot_id = config.get("id")
    settings = support_bot_settings(config)
    token = get_token_for_support_bot(config)
    logger.info(f"Support Bot polling worker started | support_bot_id={support_bot_id}")

    while True:
        try:
            latest_config = get_support_bot_config(support_bot_id)
            if not latest_config:
                detail = f"Support Bot config removed, worker exit | support_bot_id={support_bot_id}"
                logger.warning(detail)
                await notify_support_warning(
                    "Support Bot 配置已删除，worker 退出",
                    detail,
                    context={"support_bot_id": support_bot_id},
                )
                return

            settings = support_bot_settings(latest_config)
            token = get_token_for_support_bot(latest_config)
            if (
                not token
                or not latest_config.get("polling_enabled")
                or latest_config.get("status") == "disabled"
            ):
                await asyncio.sleep(5)
                continue

            await ensure_polling_mode(token)

            data = {
                "timeout": 30,
                "allowed_updates": '["message"]',
            }
            if _offsets.get(support_bot_id) is not None:
                data["offset"] = _offsets[support_bot_id]

            result = await request_post_with_retry(
                token,
                "getUpdates",
                data,
                None,
                context=f"support_get_updates support_bot_id={support_bot_id}",
                alert_context={
                    "support_bot_id": support_bot_id,
                    "bot_name": latest_config.get("name") or "",
                },
            )
            updates = result.get("result") or []
            for update in updates:
                _offsets[support_bot_id] = int(update.get("update_id", 0)) + 1
                try:
                    await handle_support_update(update, token=token, settings=settings)
                except Exception as e:
                    logger.exception(
                        f"Support Bot update handling failed | "
                        f"support_bot_id={support_bot_id} | {e}"
                    )
                    await notify_support_warning(
                        "Support Bot update 处理失败",
                        f"support_bot_id={support_bot_id} | {e}",
                        context={"support_bot_id": support_bot_id},
                    )

            update_support_bot_error(support_bot_id, "")
            await resolve_support_bot_alerts(
                support_bot_id,
                latest_config.get("name") or "",
            )

        except Exception as e:
            error_data = parse_bot_api_error(e)
            description = str(error_data.get("description") or e)

            if error_data.get("error_code") == 409:
                now_ts = datetime.now().timestamp()
                if now_ts - _last_polling_conflict_log_at >= 60:
                    _last_polling_conflict_log_at = now_ts
                    logger.warning(
                        "Support Bot polling conflict: another getUpdates instance is "
                        "running with the same Bot token. Stop duplicate backend "
                        "containers/local processes, or disable support polling in one "
                        f"instance | support_bot_id={support_bot_id} | {description}"
                    )
                    await notify_support_warning(
                        "Support Bot polling 冲突",
                        (
                            "another getUpdates instance is running with the same Bot token | "
                            f"support_bot_id={support_bot_id} | {description}"
                        ),
                        context={"support_bot_id": support_bot_id},
                    )
                update_support_bot_error(support_bot_id, description)
                await asyncio.sleep(60)
                continue

            update_support_bot_error(support_bot_id, str(e)[:1000])
            detail = (
                f"Support Bot polling error, retry later | "
                f"support_bot_id={support_bot_id} | {e}"
            )
            logger.warning(detail)
            await notify_support_warning(
                "Support Bot polling 异常",
                detail,
                context={"support_bot_id": support_bot_id},
            )
            await asyncio.sleep(5)


async def support_polling_manager():
    logger.info("Support Bot polling manager started")
    while True:
        try:
            configs = list_support_bots(include_disabled=False, include_secret=True)
            active_ids = {config["id"] for config in configs}

            for support_bot_id, task in list(_polling_tasks.items()):
                if support_bot_id not in active_ids and not task.done():
                    task.cancel()
                    _polling_tasks.pop(support_bot_id, None)

            for config in configs:
                support_bot_id = config["id"]
                task = _polling_tasks.get(support_bot_id)
                if task and not task.done():
                    continue
                _polling_tasks[support_bot_id] = asyncio.create_task(
                    support_polling_worker(config)
                )

        except Exception as e:
            detail = f"Support Bot polling manager error | {e}"
            logger.warning(detail)
            await notify_support_warning("Support Bot polling manager 异常", detail)

        await asyncio.sleep(10)


def start_support_polling():
    global _polling_task
    if _polling_task and not _polling_task.done():
        return _polling_task
    _polling_task = asyncio.create_task(support_polling_manager())
    return _polling_task
