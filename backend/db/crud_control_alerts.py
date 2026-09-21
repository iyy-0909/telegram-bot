import json
from datetime import datetime, timedelta

from sqlalchemy import case, func, inspect

from auth.tenant import current_tenant_user_id
from db.database import SessionLocal
from db.models import Account, BotAccount, CloneTask, ControlAckAlert, ListenerTask, SupportBot
from utils.redaction import redact_sensitive_data, redact_sensitive_text


REPEAT_SECONDS = 600


def now():
    return datetime.utcnow()


def resolve_alert_owner(db, context):
    context = context or {}
    current_owner = current_tenant_user_id()
    if current_owner is not None:
        return current_owner
    lookups = (
        (SupportBot, context.get("support_bot_id")),
        (ListenerTask, context.get("listener_task_id")),
        (CloneTask, context.get("clone_task_id")),
        (BotAccount, context.get("bot_id")),
        (Account, context.get("account_id")),
    )
    database_inspector = inspect(db.get_bind())
    for model, resource_id in lookups:
        if resource_id in (None, "", 0, "0"):
            continue
        if not database_inspector.has_table(model.__tablename__):
            continue
        owner_user_id = db.query(model.owner_user_id).filter(
            model.id == int(resource_id)
        ).scalar()
        if owner_user_id is not None:
            return owner_user_id
    task_id = context.get("task_id")
    task_type = str(context.get("task_type") or context.get("module") or "").lower()
    task_model = None
    if "listener" in task_type:
        task_model = ListenerTask
    elif "clone" in task_type:
        task_model = CloneTask
    if (
        task_model is not None
        and task_id not in (None, "", 0, "0")
        and database_inspector.has_table(task_model.__tablename__)
    ):
        owner_user_id = db.query(task_model.owner_user_id).filter(
            task_model.id == int(task_id)
        ).scalar()
        if owner_user_id is not None:
            return owner_user_id
    return None


def _parse_context(value):
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def alert_to_dict(alert):
    if not alert:
        return None

    return {
        "id": alert.id,
        "alert_key": alert.alert_key or "",
        "level": alert.level or "warning",
        "module": alert.module or "",
        "title": alert.title or "",
        "detail": redact_sensitive_text(alert.detail),
        "task_id": alert.task_id,
        "channel": alert.channel or "",
        "target": alert.target or "",
        "bot_name": alert.bot_name or "",
        "context": redact_sensitive_data(_parse_context(alert.context_json)),
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


def upsert_ack_alert(alert_key, title, detail="", module="", context=None, level="warning"):
    context = redact_sensitive_data(context or {})
    current = now()
    db = SessionLocal()
    try:
        owner_user_id = resolve_alert_owner(db, context)
        if owner_user_id is None:
            raise RuntimeError("系统告警缺少可验证的归属人")
        alert = (
            db.query(ControlAckAlert)
            .filter(
                ControlAckAlert.alert_key == str(alert_key),
                ControlAckAlert.owner_user_id == owner_user_id,
            )
            .first()
        )
        is_new = alert is None
        was_acknowledged = bool(alert and alert.status == "acknowledged")

        if not alert:
            alert = ControlAckAlert(
                owner_user_id=owner_user_id,
                alert_key=str(alert_key),
                created_at=current,
            )
            db.add(alert)

        alert.level = str(level or context.get("level") or "warning").lower()
        alert.module = module or context.get("module") or alert.module or ""
        alert.title = title or alert.title or ""
        alert.detail = redact_sensitive_text(detail)
        alert.task_id = context.get("task_id")
        alert.channel = str(context.get("channel") or "")
        alert.target = str(context.get("target") or "")
        alert.bot_name = str(context.get("bot_name") or "")
        alert.context_json = json.dumps(context, ensure_ascii=False, default=str)
        alert.status = "pending"
        alert.support_bot_id = context.get("support_bot_id")
        alert.customer_id = context.get("customer_id")
        alert.conversation_id = context.get("conversation_id")
        alert.acknowledged_by = ""
        alert.acknowledged_at = None
        alert.repeat_count = int(alert.repeat_count or 0) + 1
        if not alert.first_sent_at:
            alert.first_sent_at = current
        alert.last_sent_at = current
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


def list_control_alerts(status="all", level="all", module="", q="", limit=100, offset=0):
    db = SessionLocal()
    try:
        query = db.query(ControlAckAlert)
        if status and status != "all":
            query = query.filter(ControlAckAlert.status == status)
        if level and level != "all":
            query = query.filter(ControlAckAlert.level == level)
        if module:
            query = query.filter(ControlAckAlert.module == module)
        keyword = str(q or "").strip()
        ordered_query = query.order_by(
            case((ControlAckAlert.status == "pending", 0), else_=1),
            ControlAckAlert.updated_at.desc(),
            ControlAckAlert.id.desc(),
        )
        if keyword:
            normalized_keyword = keyword.casefold()
            matched_rows = []
            for row in ordered_query.all():
                item = alert_to_dict(row)
                searchable = " ".join([
                    str(item.get("title") or ""),
                    str(item.get("detail") or ""),
                    str(item.get("module") or ""),
                    str(item.get("channel") or ""),
                    str(item.get("target") or ""),
                    str(item.get("bot_name") or ""),
                    json.dumps(item.get("context") or {}, ensure_ascii=False),
                ]).casefold()
                if normalized_keyword in searchable:
                    matched_rows.append(row)
            total = len(matched_rows)
            start = max(int(offset or 0), 0)
            page_size = min(max(int(limit or 100), 1), 500)
            rows = matched_rows[start:start + page_size]
        else:
            total = query.count()
            rows = (
                ordered_query
                .offset(max(int(offset or 0), 0))
                .limit(min(max(int(limit or 100), 1), 500))
                .all()
            )
        return {"items": [alert_to_dict(row) for row in rows], "total": total}
    finally:
        db.close()


def get_control_alert_stats():
    db = SessionLocal()
    try:
        rows = db.query(
            ControlAckAlert.status,
            ControlAckAlert.level,
            func.count(ControlAckAlert.id),
        ).group_by(ControlAckAlert.status, ControlAckAlert.level).all()
        stats = {
            "total": 0,
            "pending": 0,
            "acknowledged": 0,
            "error": 0,
            "warning": 0,
            "info": 0,
        }
        for status, level, count in rows:
            count = int(count or 0)
            stats["total"] += count
            stats[status or "pending"] = stats.get(status or "pending", 0) + count
            stats[level or "warning"] = stats.get(level or "warning", 0) + count
        return stats
    finally:
        db.close()


def acknowledge_all_control_alerts(user_id="web_admin"):
    current = now()
    db = SessionLocal()
    try:
        rows = db.query(ControlAckAlert).filter(ControlAckAlert.status == "pending").all()
        for alert in rows:
            alert.status = "acknowledged"
            alert.acknowledged_by = str(user_id or "web_admin")
            alert.acknowledged_at = current
            alert.updated_at = current
        db.commit()
        return len(rows)
    finally:
        db.close()
