from datetime import datetime

from db.database import SessionLocal
from db.models import Account, NotificationAccountSetting
from notification.ntfy_client import normalize_ntfy_topic


def _display_topic(value):
    raw_value = (value or "").strip()
    if not raw_value:
        return ""
    try:
        return normalize_ntfy_topic(raw_value)
    except ValueError:
        return raw_value


def notification_setting_to_dict(account, setting):
    return {
        "account_id": account.id,
        "account_name": account.name,
        "account_username": account.username or "",
        "account_enabled": bool(account.enabled),
        "has_setting": setting is not None,
        "configured": setting is not None and bool((setting.ntfy_url or "").strip()),
        "enabled": bool(setting.enabled) if setting else False,
        "ntfy_url": _display_topic(setting.ntfy_url) if setting else "",
        "last_test_status": (setting.last_test_status or "") if setting else "",
        "last_test_message": (setting.last_test_message or "") if setting else "",
        "last_test_at": setting.last_test_at.isoformat() if setting and setting.last_test_at else None,
        "updated_at": setting.updated_at.isoformat() if setting and setting.updated_at else None,
    }


def list_notification_settings():
    db = SessionLocal()
    try:
        rows = (
            db.query(Account, NotificationAccountSetting)
            .outerjoin(
                NotificationAccountSetting,
                NotificationAccountSetting.account_id == Account.id,
            )
            .order_by(Account.id.asc())
            .all()
        )
        return [notification_setting_to_dict(account, setting) for account, setting in rows]
    finally:
        db.close()


def get_notification_setting(account_id: int):
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return None
        setting = (
            db.query(NotificationAccountSetting)
            .filter(NotificationAccountSetting.account_id == account_id)
            .first()
        )
        return notification_setting_to_dict(account, setting)
    finally:
        db.close()


def upsert_notification_setting(account_id: int, ntfy_url: str, enabled: bool):
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return None

        setting = (
            db.query(NotificationAccountSetting)
            .filter(NotificationAccountSetting.account_id == account_id)
            .first()
        )
        if not setting:
            setting = NotificationAccountSetting(account_id=account_id)
            db.add(setting)

        setting.ntfy_url = (ntfy_url or "").strip()
        setting.enabled = bool(enabled)
        setting.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(setting)
        return notification_setting_to_dict(account, setting)
    finally:
        db.close()


def update_notification_test_result(
    account_id: int,
    status: str,
    message: str,
):
    db = SessionLocal()
    try:
        setting = (
            db.query(NotificationAccountSetting)
            .filter(NotificationAccountSetting.account_id == account_id)
            .first()
        )
        if not setting:
            return None

        setting.last_test_status = status
        setting.last_test_message = message
        setting.last_test_at = datetime.utcnow()
        setting.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(setting)
        account = db.query(Account).filter(Account.id == account_id).first()
        return notification_setting_to_dict(account, setting) if account else None
    finally:
        db.close()
