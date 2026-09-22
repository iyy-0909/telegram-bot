import json

from accounts.session_storage import generate_owner_session_path
from auth.tenant import current_tenant_user_id
from bot.channel_utils import is_same_channel_identifier
from db.database import SessionLocal
from utils.redaction import redact_sensitive_text
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
    if is_same_channel_identifier(source, target):
        raise ValueError(f"监听规则的源频道不能同时作为目标频道：{target}")

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

        next_source = data.get("source", rule.source)
        next_target = data.get("target", rule.target)
        if is_same_channel_identifier(next_source, next_target):
            raise ValueError(f"监听规则的源频道不能同时作为目标频道：{next_target}")

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

        targets = [
            target
            for target in parse_target_channels(clone_task.target_channels)
            if not is_same_channel_identifier(clone_task.source_channel, target)
        ]

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
            "message": redact_sensitive_text(e),
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

def ensure_default_account_in_session(db, owner_user_id=None):
    owner_id = owner_user_id or current_tenant_user_id()
    query = db.query(Account)
    if owner_id not in (None, "", 0, "0"):
        query = query.filter(Account.owner_user_id == int(owner_id))

    default_account = query.filter(
        Account.enabled == True,
        Account.is_default == True,
    ).order_by(Account.id.asc()).first()
    if default_account:
        return default_account

    query.update(
        {Account.is_default: False},
        synchronize_session=False,
    )
    default_account = query.filter(
        Account.enabled == True,
    ).order_by(Account.id.asc()).first()
    if default_account:
        default_account.is_default = True
    return default_account


def ensure_default_account():
    db = SessionLocal()
    try:
        account = ensure_default_account_in_session(db)
        db.commit()
        if account:
            db.refresh(account)
        return account
    finally:
        db.close()


def get_all_accounts():
    db = SessionLocal()

    try:
        return db.query(Account).all()

    finally:
        db.close()


def create_account(
    name: str,
    session_path: str = "",
    username: str = "",
    proxy: str = "",
    remark: str = "",
    is_default: bool = False,
    greeting_enabled: bool = False,
    greeting_message: str = "",
    away_enabled: bool = False,
    away_message: str = "",
    business_start_time: str = "09:00",
    business_end_time: str = "18:00",
    away_repeat_hours: int = 12,
    owner_user_id: int | None = None,
):
    owner_id = owner_user_id or current_tenant_user_id()
    if owner_id in (None, "", 0, "0"):
        raise PermissionError("创建 Telegram 账号时缺少归属人")
    owner_id = int(owner_id)
    db = SessionLocal()

    try:
        occupied_paths = [
            item[0]
            for item in db.query(Account.session_path).filter(
                Account.owner_user_id == owner_id
            ).all()
        ]
        generated_session_path = generate_owner_session_path(
            owner_id,
            occupied_paths=occupied_paths,
        )
        account = Account(
            owner_user_id=owner_id,
            name=name,
            username=(username or "").strip().lstrip("@"),
            session_path=generated_session_path,
            proxy=proxy,
            enabled=True,
            is_default=bool(is_default),
            remark=remark,
            greeting_enabled=bool(greeting_enabled),
            greeting_message=greeting_message or "",
            away_enabled=bool(away_enabled),
            away_message=away_message or "",
            business_start_time=business_start_time or "09:00",
            business_end_time=business_end_time or "18:00",
            away_repeat_hours=max(1, int(away_repeat_hours or 12)),
        )

        if account.is_default:
            db.query(Account).filter(Account.owner_user_id == owner_id).update(
                {Account.is_default: False},
                synchronize_session=False,
            )

        db.add(account)
        db.flush()
        ensure_default_account_in_session(db, owner_id)
        db.commit()
        db.refresh(account)

        return account

    finally:
        db.close()


def update_account(account_id: int, data: dict):
    db = SessionLocal()

    try:
        data = dict(data or {})
        clear_proxy = bool(data.pop("clear_proxy", False))
        data.pop("session_path", None)
        for write_only_field in ("proxy",):
            value = data.get(write_only_field)
            if value is None or (isinstance(value, str) and not value.strip()):
                data.pop(write_only_field, None)
        if clear_proxy:
            data["proxy"] = ""

        account = (
            db.query(Account)
            .filter(Account.id == account_id)
            .first()
        )

        if not account:
            return None

        requested_default = data.get("is_default")
        if requested_default is True:
            other_defaults = db.query(Account).filter(
                Account.owner_user_id == account.owner_user_id,
                Account.id != account_id,
                Account.is_default == True,
            ).all()
            for other_account in other_defaults:
                other_account.is_default = False
            account.is_default = True
            account.enabled = True

        for key, value in data.items():
            if key == "is_default":
                if value is False:
                    account.is_default = False
                continue

            if key == "username":
                account.username = (value or "").strip().lstrip("@")
                continue

            if key == "away_repeat_hours":
                account.away_repeat_hours = max(1, min(168, int(value or 12)))
                continue

            if hasattr(account, key):
                setattr(account, key, value)

        if not account.enabled:
            account.is_default = False

        db.flush()
        ensure_default_account_in_session(db, account.owner_user_id)
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
        db.flush()
        ensure_default_account_in_session(db, account.owner_user_id)
        db.commit()

        return True

    finally:
        db.close()
