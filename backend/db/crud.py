import json

from db.database import SessionLocal
from db.models import ChannelRule, Account


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================
# 频道规则 CRUD
# =========================

def get_all_rules():
    db = SessionLocal()

    try:
        return db.query(ChannelRule).all()
    finally:
        db.close()


def get_enabled_rules():
    db = SessionLocal()

    try:
        return (
            db.query(ChannelRule)
            .filter(ChannelRule.enabled == True)
            .all()
        )
    finally:
        db.close()


def create_rule(
    source: str,
    target: str,
    account_id: int = 1,
    enabled: bool = True,
    blocked_keywords: str = "[]",
    replace_words: str = "{}",
    footer: str = "",
    remove_contact_lines: bool = True,
    clone_task_id=None,
    last_message_id: int = 0,
):
    """
    创建频道监听规则。

    注意：
    前端/接口里可以继续叫 blocked_keywords，
    但 channel_rules 表和 ChannelRule 模型里实际字段叫 keywords。
    """
    db = SessionLocal()

    try:
        rule = ChannelRule(
            source=source,
            target=target,
            account_id=account_id,
            enabled=enabled,
            keywords=blocked_keywords or "[]",
            replace_words=replace_words or "{}",
            footer=footer or "",
            remove_contact_lines=remove_contact_lines,
            clone_task_id=clone_task_id,
            last_message_id=last_message_id or 0,
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        return rule

    finally:
        db.close()


def update_rule(rule_id: int, data: dict):
    """
    更新频道规则。

    兼容：
    data["blocked_keywords"] -> rule.keywords
    """
    db = SessionLocal()

    try:
        rule = (
            db.query(ChannelRule)
            .filter(ChannelRule.id == rule_id)
            .first()
        )

        if not rule:
            return None

        for key, value in data.items():
            if key == "blocked_keywords":
                rule.keywords = value or "[]"
                continue

            if hasattr(rule, key):
                setattr(rule, key, value)

        db.commit()
        db.refresh(rule)

        return rule

    finally:
        db.close()


def delete_rule(rule_id: int):
    db = SessionLocal()

    try:
        rule = (
            db.query(ChannelRule)
            .filter(ChannelRule.id == rule_id)
            .first()
        )

        if not rule:
            return False

        db.delete(rule)
        db.commit()

        return True

    finally:
        db.close()


def update_last_message_id(rule_id: int, message_id: int):
    db = SessionLocal()

    try:
        rule = (
            db.query(ChannelRule)
            .filter(ChannelRule.id == rule_id)
            .first()
        )

        if not rule:
            return False

        rule.last_message_id = message_id
        db.commit()

        return True

    finally:
        db.close()


# =========================
# 克隆任务同步监听规则
# =========================

def parse_target_channels(value):
    """
    解析 clone_task.target_channels。

    支持：
    '["@A", "@B"]'
    ["@A", "@B"]
    """
    if not value:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    try:
        parsed = json.loads(value)

        if isinstance(parsed, list):
            return [
                str(item).strip()
                for item in parsed
                if str(item).strip()
            ]

        return []

    except Exception:
        return []


def sync_clone_task_to_channel_rules(clone_task):
    """
    把一条克隆任务同步成多条实时监听规则。

    enable_listener=True：
    - 每个目标频道生成一条 channel_rule

    enable_listener=False：
    - 删除这条 clone_task 关联的监听规则
    """
    db = SessionLocal()

    try:
        # 先删除旧的关联监听规则，避免目标频道修改后残留
        db.query(ChannelRule).filter(
            ChannelRule.clone_task_id == clone_task.id
        ).delete()

        if not getattr(clone_task, "enable_listener", False):
            db.commit()

            return {
                "ok": True,
                "message": "listener disabled, old rules removed",
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

        created = 0

        for target in targets:
            rule = ChannelRule(
                source=clone_task.source_channel,
                target=target,
                account_id=clone_task.account_id,
                enabled=True,

                # ChannelRule 字段名是 keywords
                keywords=clone_task.blocked_keywords or "[]",

                replace_words=clone_task.replace_words or "{}",
                footer=clone_task.footer or "",
                remove_contact_lines=getattr(
                    clone_task,
                    "remove_contact_lines",
                    True,
                ),

                clone_task_id=clone_task.id,
                last_message_id=clone_task.last_message_id or 0,
            )

            db.add(rule)
            created += 1

        db.commit()

        return {
            "ok": True,
            "message": "listener rules synced",
            "created": created,
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


def delete_channel_rules_by_clone_task_id(clone_task_id: int):
    """
    删除某条克隆任务同步生成的监听规则。
    删除 clone task 时调用。
    """
    db = SessionLocal()

    try:
        count = (
            db.query(ChannelRule)
            .filter(ChannelRule.clone_task_id == clone_task_id)
            .delete()
        )

        db.commit()

        return count

    finally:
        db.close()


# =========================
# 账号 CRUD
# =========================

def get_all_accounts():
    db = SessionLocal()

    try:
        return db.query(Account).all()

    finally:
        db.close()


def create_account(
    name: str,
    session_path: str,
    proxy: str = "",
    remark: str = "",
):
    db = SessionLocal()

    try:
        account = Account(
            name=name,
            session_path=session_path,
            proxy=proxy,
            enabled=True,
            remark=remark,
        )

        db.add(account)
        db.commit()
        db.refresh(account)

        return account

    finally:
        db.close()


def update_account(account_id: int, data: dict):
    db = SessionLocal()

    try:
        account = (
            db.query(Account)
            .filter(Account.id == account_id)
            .first()
        )

        if not account:
            return None

        for key, value in data.items():
            if hasattr(account, key):
                setattr(account, key, value)

        db.commit()
        db.refresh(account)

        return account

    finally:
        db.close()


def delete_account(account_id: int):
    db = SessionLocal()

    try:
        account = (
            db.query(Account)
            .filter(Account.id == account_id)
            .first()
        )

        if not account:
            return False

        db.delete(account)
        db.commit()

        return True

    finally:
        db.close()