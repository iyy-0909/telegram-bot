"""Owner-scoped channel discovery, import and role display."""
import json
from datetime import datetime, timedelta

from auth.tenant import current_tenant_user_id
from db.database import SessionLocal
from db.models import Account, AccountChannelSync, AccountManagedChannel, MyChannel


def require_owner():
    owner = current_tenant_user_id()
    if not owner:
        raise PermissionError("请先登录")
    return owner


def utc_text(value):
    return value.isoformat() + "Z" if value else ""


def _owned_account(db, owner, account_id):
    account = db.query(Account).filter(Account.id == account_id, Account.owner_user_id == owner).first()
    if not account:
        raise PermissionError("账号不存在或无权访问")
    return account


def save_scan(account_id, rows=None, error=""):
    """Only a completed scan may retire old roles. Failed scans retain snapshots."""
    owner = require_owner()
    now = datetime.utcnow()
    with SessionLocal() as db:
        account = _owned_account(db, owner, account_id)
        state = db.query(AccountChannelSync).filter_by(owner_user_id=owner, account_id=account_id).first()
        if not state:
            state = AccountChannelSync(owner_user_id=owner, account_id=account_id)
            db.add(state)
        state.last_attempt_at = now
        state.last_error = error
        if rows is not None:
            if not account.enabled:
                raise ValueError("账号已停用，请重新同步")
            existing = {row.chat_id: row for row in db.query(AccountManagedChannel).filter_by(
                owner_user_id=owner, account_id=account_id,
            ).all()}
            for row in existing.values():
                row.active = False
            for item in rows:
                row = existing.get(item["chat_id"])
                if row is None:
                    row = AccountManagedChannel(owner_user_id=owner, account_id=account_id, chat_id=item["chat_id"])
                    db.add(row)
                for field in ("title", "username", "role", "telegram_user_id"):
                    setattr(row, field, item[field])
                row.rights_json = json.dumps(item["rights"], ensure_ascii=False)
                row.checked_at = now
                row.active = True
            state.last_success_at = now
            state.last_error = ""
        db.commit()


def _snapshot(db, owner):
    accounts = db.query(Account).filter(Account.owner_user_id == owner).order_by(Account.id).all()
    states = {row.account_id: row for row in db.query(AccountChannelSync).filter_by(owner_user_id=owner).all()}
    rows = db.query(AccountManagedChannel).filter_by(owner_user_id=owner, active=True).order_by(
        AccountManagedChannel.checked_at.desc(), AccountManagedChannel.id,
    ).all()
    return accounts, states, rows


def _status(account, state, account_manager=None):
    if not account.enabled:
        return "disabled"
    if account_manager is not None:
        client = account_manager.get_client(account.id)
        if client is None or not client.is_connected():
            return "offline"
    if not state or not state.last_success_at:
        return "error" if state and state.last_error else "unknown"
    if state.last_error:
        return "error"
    if datetime.utcnow() - state.last_success_at > timedelta(hours=24):
        return "stale"
    return "success"


def discovery_data(account_manager=None):
    owner = require_owner()
    with SessionLocal() as db:
        accounts, states, rows = _snapshot(db, owner)
        by_id = {account.id: account for account in accounts}
        account_items = [{
            "id": account.id, "name": account.name, "username": account.username or "",
            "enabled": bool(account.enabled), "status": _status(account, states.get(account.id), account_manager),
            "last_success_at": utc_text(getattr(states.get(account.id), "last_success_at", None)),
            "last_error": getattr(states.get(account.id), "last_error", "") or "",
        } for account in accounts]
        candidates = {}
        for row in rows:
            account = by_id.get(row.account_id)
            if not account:
                continue
            item = candidates.setdefault(row.chat_id, {
                "chat_id": row.chat_id, "title": row.title, "username": row.username,
                "managed_accounts": [], "existing_id": None,
            })
            item["managed_accounts"].append({
                "account_id": account.id, "account_name": account.name,
                "account_username": account.username or "", "telegram_user_id": row.telegram_user_id,
                "role": row.role, "rights": json.loads(row.rights_json or "{}"),
                "checked_at": utc_text(row.checked_at), "status": _status(account, states.get(account.id), account_manager),
            })
        existing = db.query(MyChannel).filter_by(owner_user_id=owner).all()
        for item in candidates.values():
            item["managed_accounts"].sort(key=lambda member: (
                member["status"] != "success", member["role"] != "creator", member["account_id"],
            ))
        for channel in existing:
            match = match_channel(channel.chat_id, channel.username, candidates)
            if match:
                match["existing_id"] = channel.id
        return {"accounts": account_items, "items": list(candidates.values())}


def match_channel(chat_id, username, candidates):
    # A stored numeric ID is authoritative; never fall back to a reassigned username.
    if chat_id:
        return candidates.get(str(chat_id))
    username = (username or "").lstrip("@").lower()
    if username:
        return next((item for item in candidates.values()
                     if item["username"].lstrip("@").lower() == username), None)
    return None


def enrich_channels(channels, items, account_id=None, role="", account_manager=None):
    data = discovery_data(account_manager)
    candidates = {item["chat_id"]: item for item in data["items"]}
    owner = require_owner()
    all_confirmed = bool(data["accounts"]) and all(account["status"] == "success" for account in data["accounts"])
    result = []
    for channel, item in zip(channels, items):
        match = match_channel(channel.chat_id, channel.username, candidates) if channel.owner_user_id == owner else None
        item["managed_accounts"] = match["managed_accounts"] if match else []
        item["managed_accounts_status"] = "checked" if all_confirmed and channel.owner_user_id == owner else "unknown"
        if (account_id or role) and not any(
            (not account_id or member["account_id"] == account_id)
            and (not role or member["role"] == role)
            for member in item["managed_accounts"]
        ):
            continue
        result.append(item)
    return result


def import_channels(chat_ids, account_manager=None):
    owner = require_owner()
    candidates = {item["chat_id"]: item for item in discovery_data(account_manager)["items"]}
    ids = list(dict.fromkeys(chat_ids))
    if not ids or len(ids) > 200:
        raise ValueError("请选择 1–200 个频道")
    for chat_id in ids:
        candidate = candidates.get(chat_id)
        if not candidate or not any(member["status"] == "success" for member in candidate["managed_accounts"]):
            raise ValueError("所选频道未确认管理身份，请先重新同步对应账号")
    added = 0
    matched = 0
    with SessionLocal() as db:
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        existing = db.query(MyChannel).filter_by(owner_user_id=owner).all()
        for chat_id in ids:
            item = candidates[chat_id]
            channel = next((row for row in existing if str(row.chat_id) == chat_id), None)
            if channel is None and item["username"]:
                channel = next((row for row in existing if not row.chat_id and
                                (row.username or "").lower() == item["username"].lower()), None)
            if channel:
                # Fill identity only; existing business config and Bot permissions remain intact.
                channel.chat_id = chat_id
                if not channel.title:
                    channel.title = item["title"]
                matched += 1
                continue
            if item["username"] and any((row.username or "").lower() == item["username"].lower() for row in existing):
                raise ValueError("频道用户名已绑定其他频道 ID，请先核对已有频道信息")
            channel = MyChannel(owner_user_id=owner, chat_id=chat_id, title=item["title"],
                                username=item["username"], channel_type="channel", group_name="账号同步",
                                status="pending", last_error="尚未绑定或检测 Bot 发帖权限")
            db.add(channel)
            existing.append(channel)
            added += 1
        db.commit()
    return {"ok": True, "added": added, "matched": matched}
