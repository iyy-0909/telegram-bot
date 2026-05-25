import json
from datetime import datetime

from db.database import SessionLocal
from db.models import ListenerTask, ListenerSentMessage
from db.crud_bot import normalize_target_channel


DEFAULT_TASK_VALUES = {
    "name": "",
    "source_channel": "",
    "target_channels": "[]",
    "account_id": 1,
    "bot_id": None,
    "enabled": True,
    "status": "stopped",
    "blocked_keywords": "[]",
    "replace_words": "{}",
    "footer": "",
    "remove_contact_lines": True,
    "use_random_head": False,
    "use_random_body": False,
    "use_random_footer": False,
    "selected_head_template_group_id": None,
    "selected_body_template_group_id": None,
    "selected_footer_template_group_id": None,
    "selected_head_template_id": None,
    "selected_body_template_id": None,
    "selected_footer_template_id": None,
    "album_wait_seconds": 3,
    "last_error": "",
    "clone_task_id": None,
}


def parse_target_channels(value):
    if not value:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    try:
        parsed = json.loads(value)
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    return [str(item).strip() for item in parsed if str(item).strip()]


def normalize_task_data(data):
    normalized = {}

    for key, default in DEFAULT_TASK_VALUES.items():
        value = data.get(key, default)

        if key in ("name", "source_channel", "footer", "last_error"):
            value = str(value or "").strip()

        if key in ("target_channels", "blocked_keywords", "replace_words"):
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            value = value or default

        if key in ("account_id", "album_wait_seconds"):
            try:
                value = int(value or default)
            except (TypeError, ValueError):
                value = default
            value = max(value, 1)

        if key == "bot_id":
            if value in ("", 0):
                value = None
            elif value is not None:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = None
                value = value if value and value > 0 else None

        if key == "clone_task_id" and value in ("", 0):
            value = None

        if key.startswith("selected_") and key.endswith("_template_id"):
            if value in ("", 0):
                value = None
            elif value is not None:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = None

        normalized[key] = value

    return normalized


def get_all_listener_tasks():
    db = SessionLocal()

    try:
        return db.query(ListenerTask).order_by(ListenerTask.id.desc()).all()
    finally:
        db.close()


def get_enabled_listener_tasks():
    db = SessionLocal()

    try:
        return (
            db.query(ListenerTask)
            .filter(ListenerTask.enabled == True)
            .all()
        )
    finally:
        db.close()


def get_listener_task(task_id: int):
    db = SessionLocal()

    try:
        return (
            db.query(ListenerTask)
            .filter(ListenerTask.id == task_id)
            .first()
        )
    finally:
        db.close()


def create_listener_task(data: dict):
    db = SessionLocal()

    try:
        task = ListenerTask(**normalize_task_data(data))
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def update_listener_task(task_id: int, data: dict):
    db = SessionLocal()

    try:
        task = (
            db.query(ListenerTask)
            .filter(ListenerTask.id == task_id)
            .first()
        )

        if not task:
            return None

        normalized = normalize_task_data({
            **{key: getattr(task, key) for key in DEFAULT_TASK_VALUES},
            **data,
        })

        for key, value in normalized.items():
            setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def delete_listener_task(task_id: int):
    db = SessionLocal()

    try:
        task = (
            db.query(ListenerTask)
            .filter(ListenerTask.id == task_id)
            .first()
        )

        if not task:
            return False

        db.query(ListenerSentMessage).filter(
            ListenerSentMessage.listener_task_id == task_id
        ).delete()
        db.delete(task)
        db.commit()
        return True
    finally:
        db.close()


def delete_listener_tasks_by_clone_task_id(clone_task_id: int):
    db = SessionLocal()

    try:
        task_ids = [
            row.id
            for row in db.query(ListenerTask.id)
            .filter(ListenerTask.clone_task_id == clone_task_id)
            .all()
        ]

        if task_ids:
            db.query(ListenerSentMessage).filter(
                ListenerSentMessage.listener_task_id.in_(task_ids)
            ).delete(synchronize_session=False)

        count = (
            db.query(ListenerTask)
            .filter(ListenerTask.clone_task_id == clone_task_id)
            .delete(synchronize_session=False)
        )

        db.commit()
        return count
    finally:
        db.close()


def sync_clone_task_to_listener_tasks(clone_task):
    db = SessionLocal()

    try:
        old_task_ids = [
            row.id
            for row in db.query(ListenerTask.id)
            .filter(ListenerTask.clone_task_id == clone_task.id)
            .all()
        ]

        if old_task_ids:
            db.query(ListenerSentMessage).filter(
                ListenerSentMessage.listener_task_id.in_(old_task_ids)
            ).delete(synchronize_session=False)

        db.query(ListenerTask).filter(
            ListenerTask.clone_task_id == clone_task.id
        ).delete(synchronize_session=False)

        if not getattr(clone_task, "enable_listener", False):
            db.commit()
            return {
                "ok": True,
                "message": "listener disabled, old listener tasks removed",
                "created": 0,
            }

        targets = parse_target_channels(clone_task.target_channels)

        if not targets:
            db.commit()
            return {
                "ok": False,
                "message": "target_channels empty",
                "created": 0,
            }

        task = ListenerTask(
            name=f"{clone_task.name} 实时监听",
            source_channel=clone_task.source_channel,
            target_channels=json.dumps(targets, ensure_ascii=False),
            account_id=clone_task.account_id,
            bot_id=getattr(clone_task, "bot_id", None),
            enabled=True,
            status="running",
            blocked_keywords=clone_task.blocked_keywords or "[]",
            replace_words=clone_task.replace_words or "{}",
            footer=clone_task.footer or "",
            remove_contact_lines=getattr(clone_task, "remove_contact_lines", True),
            use_random_head=getattr(clone_task, "use_random_head", False),
            use_random_body=getattr(clone_task, "use_random_body", False),
            use_random_footer=getattr(clone_task, "use_random_footer", False),
            selected_head_template_group_id=getattr(clone_task, "selected_head_template_group_id", None),
            selected_body_template_group_id=getattr(clone_task, "selected_body_template_group_id", None),
            selected_footer_template_group_id=getattr(clone_task, "selected_footer_template_group_id", None),
            selected_head_template_id=getattr(clone_task, "selected_head_template_id", None),
            selected_body_template_id=getattr(clone_task, "selected_body_template_id", None),
            selected_footer_template_id=getattr(clone_task, "selected_footer_template_id", None),
            album_wait_seconds=3,
            last_error="",
            clone_task_id=clone_task.id,
        )
        db.add(task)
        db.commit()

        return {
            "ok": True,
            "message": "listener task synced",
            "created": 1,
        }

    except Exception as e:
        db.rollback()
        return {
            "ok": False,
            "message": str(e),
            "created": 0,
        }

    finally:
        db.close()


def update_listener_status(task_id: int, enabled=None, status=None, last_error=None):
    db = SessionLocal()

    try:
        task = (
            db.query(ListenerTask)
            .filter(ListenerTask.id == task_id)
            .first()
        )

        if not task:
            return None

        if enabled is not None:
            task.enabled = bool(enabled)

        if status is not None:
            task.status = status

        if last_error is not None:
            task.last_error = last_error

        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def is_listener_message_sent(task_id: int, target_channel: str, source_message_id: int):
    db = SessionLocal()

    try:
        target = normalize_target_channel(target_channel)
        exists = (
            db.query(ListenerSentMessage)
            .filter(
                ListenerSentMessage.listener_task_id == task_id,
                ListenerSentMessage.target_channel == target,
                ListenerSentMessage.source_message_id == source_message_id,
                ListenerSentMessage.grouped_id.is_(None),
            )
            .first()
        )
        return exists is not None
    finally:
        db.close()


def is_listener_album_sent(task_id: int, target_channel: str, grouped_id):
    db = SessionLocal()

    try:
        target = normalize_target_channel(target_channel)
        exists = (
            db.query(ListenerSentMessage)
            .filter(
                ListenerSentMessage.listener_task_id == task_id,
                ListenerSentMessage.target_channel == target,
                ListenerSentMessage.grouped_id == str(grouped_id),
            )
            .first()
        )
        return exists is not None
    finally:
        db.close()


def mark_listener_message_sent(
    task_id: int,
    target_channel: str,
    source_message_id: int,
    grouped_id=None,
):
    db = SessionLocal()

    try:
        target = normalize_target_channel(target_channel)
        record = ListenerSentMessage(
            listener_task_id=task_id,
            target_channel=target,
            source_message_id=source_message_id,
            grouped_id=str(grouped_id) if grouped_id else None,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()
