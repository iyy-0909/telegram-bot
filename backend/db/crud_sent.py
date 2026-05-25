from sqlalchemy.exc import IntegrityError

from db.database import SessionLocal
from db.models import SentMessage


def is_message_sent(task_id: int, source_message_id: int):
    """普通消息去重：task_id + source_message_id"""
    db = SessionLocal()

    try:
        exists = (
            db.query(SentMessage)
            .filter(
                SentMessage.task_id == task_id,
                SentMessage.source_message_id == source_message_id,
                SentMessage.grouped_id.is_(None),
            )
            .first()
        )

        return exists is not None

    finally:
        db.close()


def is_album_sent(task_id: int, grouped_id):
    """相册去重：task_id + grouped_id"""
    db = SessionLocal()

    try:
        exists = (
            db.query(SentMessage)
            .filter(
                SentMessage.task_id == task_id,
                SentMessage.grouped_id == str(grouped_id),
            )
            .first()
        )

        return exists is not None

    finally:
        db.close()


def mark_message_sent(task_id: int, source_message_id: int, grouped_id=None):
    """记录已发送消息"""
    db = SessionLocal()

    try:
        record = SentMessage(
            task_id=task_id,
            source_message_id=source_message_id,
            grouped_id=str(grouped_id) if grouped_id else None,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    except IntegrityError:
        db.rollback()
        return None

    finally:
        db.close()


def delete_sent_by_task(task_id: int):
    """重置任务时清空该任务去重记录"""
    db = SessionLocal()

    try:
        count = (
            db.query(SentMessage)
            .filter(SentMessage.task_id == task_id)
            .delete()
        )

        db.commit()
        return count

    finally:
        db.close()