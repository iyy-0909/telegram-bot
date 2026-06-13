from datetime import datetime, timedelta

from db.database import SessionLocal
from db.models import ControlAckAlert


REPEAT_SECONDS = 600


def now():
    return datetime.utcnow()


def alert_to_dict(alert):
    if not alert:
        return None

    return {
        "id": alert.id,
        "alert_key": alert.alert_key or "",
        "module": alert.module or "",
        "title": alert.title or "",
        "detail": alert.detail or "",
        "status": alert.status or "pending",
        "support_bot_id": alert.support_bot_id,
        "customer_id": alert.customer_id,
        "conversation_id": alert.conversation_id,
        "last_message_chat_id": alert.last_message_chat_id or "",
        "last_message_id": alert.last_message_id,
        "repeat_count": alert.repeat_count or 0,
        "first_sent_at": alert.first_sent_at,
        "last_sent_at": alert.last_sent_at,
        "acknowledged_by": alert.acknowledged_by or "",
        "acknowledged_at": alert.acknowledged_at,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


def upsert_ack_alert(alert_key, title, detail="", module="", context=None):
    context = context or {}
    current = now()
    db = SessionLocal()
    try:
        alert = (
            db.query(ControlAckAlert)
            .filter(ControlAckAlert.alert_key == str(alert_key))
            .first()
        )
        is_new = alert is None
        was_acknowledged = bool(alert and alert.status == "acknowledged")

        if not alert:
            alert = ControlAckAlert(
                alert_key=str(alert_key),
                created_at=current,
            )
            db.add(alert)

        alert.module = module or context.get("module") or alert.module or ""
        alert.title = title or alert.title or ""
        alert.detail = str(detail or "")
        alert.status = "pending"
        alert.support_bot_id = context.get("support_bot_id")
        alert.customer_id = context.get("customer_id")
        alert.conversation_id = context.get("conversation_id")
        alert.acknowledged_by = ""
        alert.acknowledged_at = None
        alert.updated_at = current

        db.commit()
        db.refresh(alert)
        return alert_to_dict(alert), (is_new or was_acknowledged)
    finally:
        db.close()


def mark_ack_alert_sent(alert_id, chat_id, message_id):
    current = now()
    db = SessionLocal()
    try:
        alert = db.query(ControlAckAlert).filter(ControlAckAlert.id == int(alert_id)).first()
        if not alert:
            return None

        if not alert.first_sent_at:
            alert.first_sent_at = current
        alert.last_sent_at = current
        alert.last_message_chat_id = str(chat_id or "")
        alert.last_message_id = int(message_id) if message_id else None
        alert.repeat_count = int(alert.repeat_count or 0) + 1
        alert.updated_at = current
        db.commit()
        db.refresh(alert)
        return alert_to_dict(alert)
    finally:
        db.close()


def acknowledge_ack_alert(alert_id, user_id):
    current = now()
    db = SessionLocal()
    try:
        alert = db.query(ControlAckAlert).filter(ControlAckAlert.id == int(alert_id)).first()
        if not alert:
            return None

        alert.status = "acknowledged"
        alert.acknowledged_by = str(user_id or "")
        alert.acknowledged_at = current
        alert.updated_at = current
        db.commit()
        db.refresh(alert)
        return alert_to_dict(alert)
    finally:
        db.close()


def acknowledge_pending_support_alerts(support_bot_id, user_id="system"):
    if not support_bot_id:
        return 0

    current = now()
    db = SessionLocal()
    try:
        rows = (
            db.query(ControlAckAlert)
            .filter(ControlAckAlert.status == "pending")
            .filter(ControlAckAlert.support_bot_id == int(support_bot_id))
            .all()
        )
        for alert in rows:
            alert.status = "acknowledged"
            alert.acknowledged_by = str(user_id or "system")
            alert.acknowledged_at = current
            alert.updated_at = current
        db.commit()
        return len(rows)
    finally:
        db.close()


def get_pending_ack_alerts_due(limit=50):
    threshold = now() - timedelta(seconds=REPEAT_SECONDS)
    db = SessionLocal()
    try:
        rows = (
            db.query(ControlAckAlert)
            .filter(ControlAckAlert.status == "pending")
            .filter(
                (ControlAckAlert.last_sent_at == None)
                | (ControlAckAlert.last_sent_at <= threshold)
            )
            .order_by(ControlAckAlert.last_sent_at.asc())
            .limit(int(limit))
            .all()
        )
        return [alert_to_dict(row) for row in rows]
    finally:
        db.close()
