from datetime import datetime

from sqlalchemy import or_

from db.crud_bot import normalize_target_channel
from db.database import SessionLocal
from db.models import MyChannel


def normalize_username(value):
    text = (value or "").strip()

    if not text:
        return ""

    if text.startswith("@"):
        return f"@{text[1:].strip().lower()}"

    if text.startswith("-100"):
        return ""

    return f"@{text.lower()}"


def normalize_channel_data(data):
    username = normalize_username(data.get("username"))
    chat_id = str(data.get("chat_id") or "").strip()

    if not username and not chat_id:
        raise ValueError("username 和 chat_id 至少填写一个")

    return {
        "title": (data.get("title") or "").strip(),
        "username": username,
        "chat_id": chat_id,
        "channel_type": (data.get("channel_type") or "").strip(),
        "group_name": (data.get("group_name") or "").strip(),
        "tags": data.get("tags") or "[]",
        "bot_id": data.get("bot_id"),
        "status": data.get("status") or "enabled",
        "is_default": bool(data.get("is_default", False)),
        "remark": data.get("remark") or "",
    }


def channel_to_target(channel):
    return channel.username or channel.chat_id or ""


def my_channel_to_dict(channel):
    return {
        "id": channel.id,
        "title": channel.title or "",
        "username": channel.username or "",
        "chat_id": channel.chat_id or "",
        "channel_type": channel.channel_type or "",
        "group_name": channel.group_name or "",
        "tags": channel.tags or "[]",
        "bot_id": channel.bot_id,
        "status": channel.status or "enabled",
        "is_default": bool(channel.is_default),
        "remark": channel.remark or "",
        "bot_is_member": bool(channel.bot_is_member),
        "bot_is_admin": bool(channel.bot_is_admin),
        "can_post_messages": bool(channel.can_post_messages),
        "can_edit_messages": bool(channel.can_edit_messages),
        "can_delete_messages": bool(channel.can_delete_messages),
        "can_manage_topics": bool(channel.can_manage_topics),
        "last_check_at": str(channel.last_check_at) if channel.last_check_at else "",
        "last_error": channel.last_error or "",
        "created_at": str(channel.created_at) if channel.created_at else "",
        "updated_at": str(channel.updated_at) if channel.updated_at else "",
        "target_value": channel_to_target(channel),
    }


def list_my_channels(keyword="", status="", group_name="", bot_id=None):
    db = SessionLocal()

    try:
        query = db.query(MyChannel)

        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    MyChannel.title.like(like),
                    MyChannel.username.like(like),
                    MyChannel.chat_id.like(like),
                    MyChannel.group_name.like(like),
                )
            )

        if status:
            query = query.filter(MyChannel.status == status)

        if group_name:
            query = query.filter(MyChannel.group_name == group_name)

        if bot_id:
            query = query.filter(MyChannel.bot_id == int(bot_id))

        return query.order_by(MyChannel.id.desc()).all()
    finally:
        db.close()


def get_my_channel(channel_id):
    db = SessionLocal()

    try:
        return db.query(MyChannel).filter(MyChannel.id == channel_id).first()
    finally:
        db.close()


def find_duplicate(db, username="", chat_id="", exclude_id=None):
    filters = []

    if username:
        filters.append(MyChannel.username == username)

    if chat_id:
        filters.append(MyChannel.chat_id == chat_id)

    if not filters:
        return None

    query = db.query(MyChannel).filter(or_(*filters))

    if exclude_id:
        query = query.filter(MyChannel.id != exclude_id)

    return query.first()


def create_my_channel(data):
    normalized = normalize_channel_data(data)
    db = SessionLocal()

    try:
        duplicate = find_duplicate(
            db,
            normalized["username"],
            normalized["chat_id"],
        )

        if duplicate:
            raise ValueError("频道 username 或 chat_id 已存在")

        channel = MyChannel(**normalized)
        now = datetime.utcnow()
        channel.created_at = now
        channel.updated_at = now
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return channel
    finally:
        db.close()


def update_my_channel(channel_id, data):
    db = SessionLocal()

    try:
        channel = db.query(MyChannel).filter(MyChannel.id == channel_id).first()

        if not channel:
            return None

        merged = my_channel_to_dict(channel)
        merged.update(data or {})
        normalized = normalize_channel_data(merged)
        duplicate = find_duplicate(
            db,
            normalized["username"],
            normalized["chat_id"],
            exclude_id=channel_id,
        )

        if duplicate:
            raise ValueError("频道 username 或 chat_id 已存在")

        for key, value in normalized.items():
            setattr(channel, key, value)

        channel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(channel)
        return channel
    finally:
        db.close()


def delete_my_channel(channel_id):
    db = SessionLocal()

    try:
        channel = db.query(MyChannel).filter(MyChannel.id == channel_id).first()

        if not channel:
            return False

        db.delete(channel)
        db.commit()
        return True
    finally:
        db.close()


def set_my_channel_check_result(channel_id, data):
    db = SessionLocal()

    try:
        channel = db.query(MyChannel).filter(MyChannel.id == channel_id).first()

        if not channel:
            return None

        for key, value in (data or {}).items():
            if hasattr(channel, key):
                setattr(channel, key, value)

        channel.last_check_at = datetime.utcnow()
        channel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(channel)
        return channel
    finally:
        db.close()


def upsert_my_channel_from_target(target, bot_id=None, group_name="迁移导入"):
    normalized = normalize_target_channel(target)

    if not normalized:
        return None

    username = normalize_username(normalized) if normalized.startswith("@") else ""
    chat_id = normalized if normalized.startswith("-100") else ""
    db = SessionLocal()

    try:
        duplicate = find_duplicate(db, username, chat_id)

        if duplicate:
            return duplicate

        channel = MyChannel(
            title=username or chat_id,
            username=username,
            chat_id=chat_id,
            group_name=group_name,
            bot_id=bot_id,
            status="enabled",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return channel
    finally:
        db.close()
