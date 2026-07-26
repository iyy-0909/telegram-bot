from db.database import SessionLocal
from db.models import Account, CloneTask


NUMERIC_DEFAULTS = {
    "single_delay": 3,
    "album_delay": 8,
    "target_delay": 2,
}

OPTIONAL_NUMERIC_FIELDS = {
    "account_id",
    "bot_id",
    "selected_head_template_group_id",
    "selected_body_template_group_id",
    "selected_footer_template_group_id",
    "selected_filter_template_group_id",
    "selected_link_template_group_id",
    "selected_contact_template_group_id",
    "selected_head_template_id",
    "selected_body_template_id",
    "selected_footer_template_id",
}


def resolve_clone_account_id(db, account_id=None):
    if account_id not in (None, "", 0):
        try:
            requested_id = int(account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("采集账号格式不正确") from exc

        account = db.query(Account).filter(
            Account.id == requested_id,
            Account.enabled == True,
        ).first()
        if not account:
            raise ValueError("所选采集账号不存在或未启用")
        return account.id

    account = db.query(Account).filter(
        Account.is_default == True,
        Account.enabled == True,
    ).order_by(Account.id.asc()).first()
    if not account:
        raise ValueError("未选择采集账号，且账号管理中没有启用的全局默认账号")
    return account.id


def normalize_numeric_fields(data: dict):
    normalized = dict(data or {})

    for key, default in NUMERIC_DEFAULTS.items():
        if key not in normalized:
            continue

        try:
            value = int(normalized.get(key))
        except (TypeError, ValueError):
            value = default

        if value < 1:
            value = default

        normalized[key] = value

    for key in OPTIONAL_NUMERIC_FIELDS:
        if key not in normalized:
            continue

        value = normalized.get(key)

        if value in ("", 0):
            normalized[key] = None
            continue

        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = None

        normalized[key] = value if value and value > 0 else None

    return normalized


def get_all_clone_tasks():
    """获取所有克隆任务"""
    db = SessionLocal()

    try:
        return db.query(CloneTask).all()
    finally:
        db.close()


def get_clone_task(task_id: int):
    """根据 ID 获取单个克隆任务"""
    db = SessionLocal()

    try:
        return db.query(CloneTask).filter(
            CloneTask.id == task_id
        ).first()
    finally:
        db.close()


def create_clone_task(data: dict):
    """创建克隆任务"""
    db = SessionLocal()

    try:
        data = normalize_numeric_fields(data)
        data["account_id"] = resolve_clone_account_id(
            db,
            data.get("account_id"),
        )
        task = CloneTask(**data)

        db.add(task)
        db.commit()
        db.refresh(task)

        return task
    finally:
        db.close()


def update_clone_task(task_id: int, data: dict):
    """更新克隆任务"""
    db = SessionLocal()

    try:
        task = db.query(CloneTask).filter(
            CloneTask.id == task_id
        ).first()

        if not task:
            return None

        data = normalize_numeric_fields(data)
        if "account_id" in data:
            data["account_id"] = resolve_clone_account_id(
                db,
                data.get("account_id"),
            )

        for key, value in data.items():
            if hasattr(task, key):
                setattr(task, key, value)

        db.commit()
        db.refresh(task)

        return task
    finally:
        db.close()


def update_clone_progress(task_id: int, message_id: int):
    """更新克隆进度"""
    db = SessionLocal()

    try:
        task = db.query(CloneTask).filter(
            CloneTask.id == task_id
        ).first()

        if task:
            task.last_message_id = message_id
            db.commit()

        return task
    finally:
        db.close()


def delete_clone_task(task_id: int):
    """删除克隆任务"""
    db = SessionLocal()

    try:
        task = db.query(CloneTask).filter(
            CloneTask.id == task_id
        ).first()

        if task:
            db.delete(task)
            db.commit()
            return True

        return False
    finally:
        db.close()
