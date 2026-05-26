from datetime import datetime
import os

from sqlalchemy import or_

from db.database import SessionLocal
from db.models import (
    SupportConversation,
    SupportCustomer,
    SupportCustomerTag,
    SupportMessage,
    SupportQuickReply,
    SupportSetting,
    SupportTag,
)


DEFAULT_SUPPORT_SETTINGS = {
    "support_bot_id": "",
    "support_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "support_polling_enabled": "0",
    "support_group_chat_id": os.getenv("TELEGRAM_SUPPORT_GROUP_CHAT_ID", ""),
    "support_backend_base_url": os.getenv("ADMIN_PUBLIC_URL", "http://127.0.0.1:5173"),
    "welcome_message": "您好，欢迎咨询，请直接发送您的问题，客服会尽快回复您。",
    "off_hours_message": "您好，当前客服不在线，我们会尽快回复您。",
    "business_hours_enabled": "0",
    "business_start_hour": "9",
    "business_end_hour": "22",
}

DEFAULT_TAGS = ["新客户", "意向客户", "已成交", "无效", "黑名单"]


def now():
    return datetime.utcnow()


def as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def set_support_setting(key, value, remark=""):
    db = SessionLocal()
    try:
        setting = db.query(SupportSetting).filter(SupportSetting.key == key).first()
        if not setting:
            setting = SupportSetting(
                key=key,
                value=str(value or ""),
                remark=remark,
                updated_at=now(),
            )
            db.add(setting)
        else:
            setting.value = str(value or "")
            setting.updated_at = now()
            if remark:
                setting.remark = remark
        db.commit()
        db.refresh(setting)
        return setting
    finally:
        db.close()


def get_support_setting(key, default=""):
    db = SessionLocal()
    try:
        setting = db.query(SupportSetting).filter(SupportSetting.key == key).first()
        return setting.value if setting else default
    finally:
        db.close()


def ensure_support_defaults():
    db = SessionLocal()
    try:
        for key, value in DEFAULT_SUPPORT_SETTINGS.items():
            exists = db.query(SupportSetting).filter(SupportSetting.key == key).first()
            if not exists:
                db.add(SupportSetting(key=key, value=str(value), updated_at=now()))

        for tag_name in DEFAULT_TAGS:
            exists = db.query(SupportTag).filter(SupportTag.name == tag_name).first()
            if not exists:
                db.add(SupportTag(name=tag_name, updated_at=now()))

        db.commit()
    finally:
        db.close()


def get_support_settings():
    ensure_support_defaults()
    return {
        key: get_support_setting(key, default)
        for key, default in DEFAULT_SUPPORT_SETTINGS.items()
    }


def update_support_settings(data):
    ensure_support_defaults()
    allowed = set(DEFAULT_SUPPORT_SETTINGS.keys())
    for key, value in (data or {}).items():
        if key in allowed and value is not None:
            set_support_setting(key, value)
    return get_support_settings()


def get_customer_tags(customer_id):
    db = SessionLocal()
    try:
        rows = (
            db.query(SupportTag)
            .join(SupportCustomerTag, SupportCustomerTag.tag_id == SupportTag.id)
            .filter(SupportCustomerTag.customer_id == customer_id)
            .order_by(SupportTag.id.asc())
            .all()
        )
        return [tag_to_dict(tag) for tag in rows]
    finally:
        db.close()


def customer_to_dict(customer):
    return {
        "id": customer.id,
        "telegram_user_id": customer.telegram_user_id,
        "telegram_chat_id": customer.telegram_chat_id,
        "username": customer.username or "",
        "first_name": customer.first_name or "",
        "last_name": customer.last_name or "",
        "language_code": customer.language_code or "",
        "source": customer.source or "",
        "status": customer.status or "",
        "blocked": bool(customer.blocked),
        "created_at": str(customer.created_at) if customer.created_at else "",
        "updated_at": str(customer.updated_at) if customer.updated_at else "",
        "last_message_at": str(customer.last_message_at) if customer.last_message_at else "",
        "tags": get_customer_tags(customer.id),
    }


def conversation_to_dict(conversation, customer=None):
    if customer is None:
        customer = get_customer(conversation.customer_id)
    return {
        "id": conversation.id,
        "customer_id": conversation.customer_id,
        "status": conversation.status or "",
        "assigned_admin_id": conversation.assigned_admin_id,
        "support_thread_id": getattr(conversation, "support_thread_id", None),
        "support_topic_name": getattr(conversation, "support_topic_name", "") or "",
        "support_topic_created_at": str(getattr(conversation, "support_topic_created_at", "") or ""),
        "last_message": conversation.last_message or "",
        "last_message_at": str(conversation.last_message_at) if conversation.last_message_at else "",
        "unread_count": conversation.unread_count or 0,
        "created_at": str(conversation.created_at) if conversation.created_at else "",
        "updated_at": str(conversation.updated_at) if conversation.updated_at else "",
        "customer": customer_to_dict(customer) if customer else None,
    }


def message_to_dict(message):
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "customer_id": message.customer_id,
        "sender_type": message.sender_type,
        "sender_id": message.sender_id or "",
        "message_type": message.message_type or "",
        "text": message.text or "",
        "caption": getattr(message, "caption", "") or "",
        "file_id": message.file_id or "",
        "file_unique_id": getattr(message, "file_unique_id", "") or "",
        "file_name": getattr(message, "file_name", "") or "",
        "mime_type": getattr(message, "mime_type", "") or "",
        "file_size": getattr(message, "file_size", None),
        "width": getattr(message, "width", None),
        "height": getattr(message, "height", None),
        "duration": getattr(message, "duration", None),
        "telegram_message_id": message.telegram_message_id,
        "support_group_message_id": getattr(message, "support_group_message_id", None),
        "reply_to_support_group_message_id": getattr(message, "reply_to_support_group_message_id", None),
        "send_status": getattr(message, "send_status", None) or message.status or "",
        "error_message": getattr(message, "error_message", None) or message.error or "",
        "status": message.status or "",
        "error": message.error or "",
        "created_at": str(message.created_at) if message.created_at else "",
    }


def get_customer(customer_id):
    db = SessionLocal()
    try:
        return db.query(SupportCustomer).filter(SupportCustomer.id == customer_id).first()
    finally:
        db.close()


def get_customer_detail(customer_id):
    customer = get_customer(customer_id)
    return customer_to_dict(customer) if customer else None


def get_customer_by_telegram_user_id(telegram_user_id):
    db = SessionLocal()
    try:
        return (
            db.query(SupportCustomer)
            .filter(SupportCustomer.telegram_user_id == str(telegram_user_id))
            .first()
        )
    finally:
        db.close()


def upsert_customer(user, chat_id, source=""):
    db = SessionLocal()
    try:
        telegram_user_id = str(user.get("id") or "")
        customer = (
            db.query(SupportCustomer)
            .filter(SupportCustomer.telegram_user_id == telegram_user_id)
            .first()
        )
        created = False
        if not customer:
            customer = SupportCustomer(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=str(chat_id),
                created_at=now(),
                status="active",
                blocked=False,
            )
            db.add(customer)
            created = True

        customer.telegram_chat_id = str(chat_id)
        customer.username = user.get("username") or ""
        customer.first_name = user.get("first_name") or ""
        customer.last_name = user.get("last_name") or ""
        customer.language_code = user.get("language_code") or ""
        if source:
            customer.source = source
        customer.last_message_at = now()
        customer.updated_at = now()
        db.commit()
        db.refresh(customer)
        return customer, created
    finally:
        db.close()


def get_or_create_conversation(customer_id):
    db = SessionLocal()
    try:
        conversation = (
            db.query(SupportConversation)
            .filter(SupportConversation.customer_id == customer_id)
            .filter(SupportConversation.status == "open")
            .order_by(SupportConversation.id.desc())
            .first()
        )
        if not conversation:
            conversation = SupportConversation(
                customer_id=customer_id,
                status="open",
                created_at=now(),
                updated_at=now(),
                last_message_at=now(),
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        return conversation
    finally:
        db.close()


def add_support_message(
    *,
    conversation_id,
    customer_id,
    sender_type,
    sender_id="",
    message_type="text",
    text="",
    caption="",
    file_id="",
    file_unique_id="",
    file_name="",
    mime_type="",
    file_size=None,
    width=None,
    height=None,
    duration=None,
    telegram_message_id=None,
    support_group_message_id=None,
    reply_to_support_group_message_id=None,
    send_status="success",
    error_message="",
    status="sent",
    error="",
    increment_unread=False,
):
    db = SessionLocal()
    try:
        message = SupportMessage(
            conversation_id=conversation_id,
            customer_id=customer_id,
            sender_type=sender_type,
            sender_id=str(sender_id or ""),
            message_type=message_type or "text",
            text=text or "",
            caption=caption or "",
            file_id=file_id or "",
            file_unique_id=file_unique_id or "",
            file_name=file_name or "",
            mime_type=mime_type or "",
            file_size=file_size,
            width=width,
            height=height,
            duration=duration,
            telegram_message_id=telegram_message_id,
            support_group_message_id=support_group_message_id,
            reply_to_support_group_message_id=reply_to_support_group_message_id,
            send_status=send_status or ("failed" if status == "failed" else "success"),
            error_message=error_message or error or "",
            status=status,
            error=error or "",
            created_at=now(),
        )
        db.add(message)

        conversation = db.query(SupportConversation).filter(
            SupportConversation.id == conversation_id
        ).first()
        if conversation:
            conversation.last_message = text or caption or file_id or f"[{message_type}]"
            conversation.last_message_at = now()
            conversation.updated_at = now()
            if conversation.status == "closed" and sender_type == "customer":
                conversation.status = "open"
            if increment_unread:
                conversation.unread_count = int(conversation.unread_count or 0) + 1

        customer = db.query(SupportCustomer).filter(SupportCustomer.id == customer_id).first()
        if customer:
            customer.last_message_at = now()
            customer.updated_at = now()

        db.commit()
        db.refresh(message)
        return message
    finally:
        db.close()


def update_support_message_group_message_id(message_id, support_group_message_id):
    db = SessionLocal()
    try:
        message = db.query(SupportMessage).filter(SupportMessage.id == message_id).first()
        if not message:
            return None
        message.support_group_message_id = support_group_message_id
        db.commit()
        db.refresh(message)
        return message_to_dict(message)
    finally:
        db.close()


def update_conversation_topic(conversation_id, support_thread_id, support_topic_name):
    db = SessionLocal()
    try:
        conversation = db.query(SupportConversation).filter(
            SupportConversation.id == int(conversation_id)
        ).first()
        if not conversation:
            return None
        conversation.support_thread_id = int(support_thread_id)
        conversation.support_topic_name = support_topic_name or ""
        conversation.support_topic_created_at = now()
        conversation.updated_at = now()
        db.commit()
        db.refresh(conversation)
        return conversation
    finally:
        db.close()


def get_conversation_by_thread_id(thread_id):
    db = SessionLocal()
    try:
        conversation = (
            db.query(SupportConversation)
            .filter(SupportConversation.support_thread_id == int(thread_id))
            .order_by(SupportConversation.id.desc())
            .first()
        )
        if not conversation:
            return None
        customer = db.query(SupportCustomer).filter(
            SupportCustomer.id == conversation.customer_id
        ).first()
        return conversation_to_dict(conversation, customer)
    finally:
        db.close()


def get_message_by_support_group_message_id(group_message_id):
    db = SessionLocal()
    try:
        message = (
            db.query(SupportMessage)
            .filter(SupportMessage.support_group_message_id == int(group_message_id))
            .first()
        )
        return message_to_dict(message) if message else None
    finally:
        db.close()


def list_customers(q="", limit=100):
    db = SessionLocal()
    try:
        query = db.query(SupportCustomer)
        q = str(q or "").strip()
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    SupportCustomer.telegram_user_id.like(like),
                    SupportCustomer.username.like(like),
                    SupportCustomer.first_name.like(like),
                    SupportCustomer.last_name.like(like),
                    SupportCustomer.source.like(like),
                )
            )
        rows = (
            query.order_by(SupportCustomer.last_message_at.desc())
            .limit(max(min(int(limit or 100), 300), 1))
            .all()
        )
        return [customer_to_dict(customer) for customer in rows]
    finally:
        db.close()


def list_conversations(status=None, q="", limit=100):
    db = SessionLocal()
    try:
        query = db.query(SupportConversation, SupportCustomer).join(
            SupportCustomer,
            SupportConversation.customer_id == SupportCustomer.id,
        )

        if status and status != "all":
            mapped = {
                "unhandled": "open",
                "processing": "open",
                "closed": "closed",
                "blocked": "blocked",
            }.get(status, status)
            query = query.filter(SupportConversation.status == mapped)

        q = str(q or "").strip()
        if q:
            like = f"%{q}%"
            message_customer_ids = (
                db.query(SupportMessage.customer_id)
                .filter(SupportMessage.text.like(like))
                .subquery()
            )
            query = query.filter(
                or_(
                    SupportCustomer.telegram_user_id.like(like),
                    SupportCustomer.username.like(like),
                    SupportCustomer.first_name.like(like),
                    SupportCustomer.last_name.like(like),
                    SupportConversation.last_message.like(like),
                    SupportCustomer.id.in_(message_customer_ids),
                )
            )

        rows = (
            query.order_by(SupportConversation.last_message_at.desc())
            .limit(max(min(int(limit or 100), 200), 1))
            .all()
        )
        return [conversation_to_dict(conversation, customer) for conversation, customer in rows]
    finally:
        db.close()


def get_conversation_detail(conversation_id):
    db = SessionLocal()
    try:
        conversation = (
            db.query(SupportConversation)
            .filter(SupportConversation.id == conversation_id)
            .first()
        )
        if not conversation:
            return None

        customer = db.query(SupportCustomer).filter(
            SupportCustomer.id == conversation.customer_id
        ).first()
        messages = (
            db.query(SupportMessage)
            .filter(SupportMessage.conversation_id == conversation_id)
            .order_by(SupportMessage.id.asc())
            .all()
        )
        return {
            "conversation": conversation_to_dict(conversation, customer),
            "messages": [message_to_dict(message) for message in messages],
        }
    finally:
        db.close()


def list_messages(conversation_id=None, customer_id=None, limit=200):
    db = SessionLocal()
    try:
        query = db.query(SupportMessage)
        if conversation_id is not None:
            query = query.filter(SupportMessage.conversation_id == int(conversation_id))
        if customer_id is not None:
            query = query.filter(SupportMessage.customer_id == int(customer_id))
        rows = (
            query.order_by(SupportMessage.id.desc())
            .limit(max(min(int(limit or 200), 500), 1))
            .all()
        )
        return [message_to_dict(message) for message in reversed(rows)]
    finally:
        db.close()


def mark_conversation_read(conversation_id):
    db = SessionLocal()
    try:
        conversation = db.query(SupportConversation).filter(
            SupportConversation.id == conversation_id
        ).first()
        if conversation:
            conversation.unread_count = 0
            conversation.updated_at = now()
            db.commit()
        return conversation
    finally:
        db.close()


def update_conversation_status(conversation_id, status):
    db = SessionLocal()
    try:
        conversation = db.query(SupportConversation).filter(
            SupportConversation.id == conversation_id
        ).first()
        if not conversation:
            return None
        conversation.status = status
        conversation.updated_at = now()
        db.commit()
        db.refresh(conversation)
        return conversation
    finally:
        db.close()


def set_customer_blocked(customer_id, blocked=True):
    db = SessionLocal()
    try:
        customer = db.query(SupportCustomer).filter(SupportCustomer.id == customer_id).first()
        if not customer:
            return None
        customer.blocked = bool(blocked)
        customer.status = "blocked" if blocked else "active"
        customer.updated_at = now()
        conversations = db.query(SupportConversation).filter(
            SupportConversation.customer_id == customer.id
        ).all()
        for conversation in conversations:
            conversation.status = "blocked" if blocked else "open"
            conversation.updated_at = now()
        db.commit()
        db.refresh(customer)
        return customer
    finally:
        db.close()


def quick_reply_to_dict(reply):
    return {
        "id": reply.id,
        "title": reply.title,
        "content": reply.content or "",
        "sort": reply.sort or 0,
        "enabled": bool(reply.enabled),
        "created_at": str(reply.created_at) if reply.created_at else "",
        "updated_at": str(reply.updated_at) if reply.updated_at else "",
    }


def list_quick_replies(include_disabled=True):
    db = SessionLocal()
    try:
        query = db.query(SupportQuickReply)
        if not include_disabled:
            query = query.filter(SupportQuickReply.enabled == True)
        return [
            quick_reply_to_dict(reply)
            for reply in query.order_by(SupportQuickReply.sort.asc(), SupportQuickReply.id.desc()).all()
        ]
    finally:
        db.close()


def create_quick_reply(data):
    db = SessionLocal()
    try:
        reply = SupportQuickReply(
            title=str(data.get("title") or "").strip(),
            content=str(data.get("content") or ""),
            sort=int(data.get("sort") or 0),
            enabled=bool(data.get("enabled", True)),
            created_at=now(),
            updated_at=now(),
        )
        db.add(reply)
        db.commit()
        db.refresh(reply)
        return quick_reply_to_dict(reply)
    finally:
        db.close()


def update_quick_reply(reply_id, data):
    db = SessionLocal()
    try:
        reply = db.query(SupportQuickReply).filter(SupportQuickReply.id == reply_id).first()
        if not reply:
            return None
        for key in ["title", "content"]:
            if key in data and data[key] is not None:
                setattr(reply, key, str(data[key]))
        if "sort" in data and data["sort"] is not None:
            reply.sort = int(data["sort"] or 0)
        if "enabled" in data and data["enabled"] is not None:
            reply.enabled = bool(data["enabled"])
        reply.updated_at = now()
        db.commit()
        db.refresh(reply)
        return quick_reply_to_dict(reply)
    finally:
        db.close()


def delete_quick_reply(reply_id):
    db = SessionLocal()
    try:
        reply = db.query(SupportQuickReply).filter(SupportQuickReply.id == reply_id).first()
        if not reply:
            return False
        db.delete(reply)
        db.commit()
        return True
    finally:
        db.close()


def tag_to_dict(tag):
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color or "",
    }


def list_tags():
    ensure_support_defaults()
    db = SessionLocal()
    try:
        return [tag_to_dict(tag) for tag in db.query(SupportTag).order_by(SupportTag.id.asc()).all()]
    finally:
        db.close()


def create_tag(data):
    db = SessionLocal()
    try:
        tag = SupportTag(
            name=str(data.get("name") or "").strip(),
            color=str(data.get("color") or ""),
            updated_at=now(),
        )
        db.add(tag)
        db.commit()
        db.refresh(tag)
        return tag_to_dict(tag)
    finally:
        db.close()


def set_customer_tags(customer_id, tag_ids):
    db = SessionLocal()
    try:
        db.query(SupportCustomerTag).filter(
            SupportCustomerTag.customer_id == customer_id
        ).delete(synchronize_session=False)
        for tag_id in tag_ids or []:
            db.add(SupportCustomerTag(customer_id=customer_id, tag_id=int(tag_id)))
        db.commit()
        return get_customer_tags(customer_id)
    finally:
        db.close()
