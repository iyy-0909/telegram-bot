from datetime import datetime

from sqlalchemy import or_

from db.database import SessionLocal
from db.models import CloneChannel


def normalize_clone_channel_data(data):
    channel_link = (data.get("channel_link") or "").strip()

    if not channel_link:
        raise ValueError("频道链接不能为空")

    return {
        "title": (data.get("title") or "").strip(),
        "channel_link": channel_link,
        "group_name": (data.get("group_name") or "").strip(),
        "channel_type": (data.get("channel_type") or "").strip(),
        "remark": (data.get("remark") or "").strip(),
    }


def clone_channel_to_dict(channel):
    return {
        "id": channel.id,
        "title": channel.title or "",
        "channel_link": channel.channel_link or "",
        "group_name": channel.group_name or "",
        "channel_type": channel.channel_type or "",
        "remark": channel.remark or "",
        "created_at": str(channel.created_at) if channel.created_at else "",
        "updated_at": str(channel.updated_at) if channel.updated_at else "",
    }


def list_clone_channels(keyword="", group_name="", channel_type=""):
    db = SessionLocal()

    try:
        query = db.query(CloneChannel)

        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    CloneChannel.title.like(like),
                    CloneChannel.channel_link.like(like),
                    CloneChannel.group_name.like(like),
                    CloneChannel.channel_type.like(like),
                    CloneChannel.remark.like(like),
                )
            )

        if group_name:
            query = query.filter(CloneChannel.group_name == group_name)

        if channel_type:
            query = query.filter(CloneChannel.channel_type == channel_type)

        return query.order_by(CloneChannel.id.desc()).all()
    finally:
        db.close()


def get_clone_channel(channel_id):
    db = SessionLocal()

    try:
        return db.query(CloneChannel).filter(CloneChannel.id == channel_id).first()
    finally:
        db.close()


def find_duplicate(db, channel_link="", exclude_id=None):
    if not channel_link:
        return None

    query = db.query(CloneChannel).filter(CloneChannel.channel_link == channel_link)

    if exclude_id:
        query = query.filter(CloneChannel.id != exclude_id)

    return query.first()


def create_clone_channel(data):
    normalized = normalize_clone_channel_data(data)
    db = SessionLocal()

    try:
        duplicate = find_duplicate(db, normalized["channel_link"])

        if duplicate:
            raise ValueError("频道链接已存在")

        channel = CloneChannel(**normalized)
        now = datetime.utcnow()
        channel.created_at = now
        channel.updated_at = now
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return channel
    finally:
        db.close()


def update_clone_channel(channel_id, data):
    db = SessionLocal()

    try:
        channel = db.query(CloneChannel).filter(CloneChannel.id == channel_id).first()

        if not channel:
            return None

        merged = clone_channel_to_dict(channel)
        merged.update(data or {})
        normalized = normalize_clone_channel_data(merged)
        duplicate = find_duplicate(
            db,
            normalized["channel_link"],
            exclude_id=channel_id,
        )

        if duplicate:
            raise ValueError("频道链接已存在")

        for key, value in normalized.items():
            setattr(channel, key, value)

        channel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(channel)
        return channel
    finally:
        db.close()


def delete_clone_channel(channel_id):
    db = SessionLocal()

    try:
        channel = db.query(CloneChannel).filter(CloneChannel.id == channel_id).first()

        if not channel:
            return False

        db.delete(channel)
        db.commit()
        return True
    finally:
        db.close()
