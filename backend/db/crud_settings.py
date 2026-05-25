from datetime import datetime

from db.database import SessionLocal
from db.models import SystemSetting


DEFAULT_SEND_SETTINGS = {
    "global_send_delay": 3,
    "send_retry_count": 2,
    "send_retry_delay": 5,
}


SETTING_REMARKS = {
    "global_send_delay": "任意两次 Bot API 发送之间的全局最小间隔秒数",
    "send_retry_count": "发送异常时的重试次数，只重试抛异常的发送，不重试业务失败",
    "send_retry_delay": "发送异常重试前等待秒数",
}


def to_non_negative_int(value, fallback):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback

    if number < 0:
        return fallback

    return number


def get_setting(key, default=""):
    db = SessionLocal()

    try:
        setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == key)
            .first()
        )

        if not setting:
            return default

        return setting.value

    finally:
        db.close()


def set_setting(key, value, remark=None):
    db = SessionLocal()

    try:
        setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == key)
            .first()
        )

        if not setting:
            setting = SystemSetting(
                key=key,
                value=str(value),
                remark=remark or SETTING_REMARKS.get(key, ""),
                updated_at=datetime.utcnow(),
            )
            db.add(setting)
        else:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()

            if remark is not None:
                setting.remark = remark

        db.commit()
        db.refresh(setting)
        return setting

    finally:
        db.close()


def ensure_default_settings():
    for key, value in DEFAULT_SEND_SETTINGS.items():
        if get_setting(key, None) is None:
            set_setting(
                key,
                value,
                remark=SETTING_REMARKS.get(key, ""),
            )


def get_send_settings():
    return {
        key: to_non_negative_int(
            get_setting(key, default),
            default,
        )
        for key, default in DEFAULT_SEND_SETTINGS.items()
    }


def update_send_settings(data):
    normalized = {}

    for key, default in DEFAULT_SEND_SETTINGS.items():
        if key in data and data[key] is not None:
            normalized[key] = to_non_negative_int(data[key], default)

    for key, value in normalized.items():
        set_setting(
            key,
            value,
            remark=SETTING_REMARKS.get(key, ""),
        )

    return get_send_settings()
