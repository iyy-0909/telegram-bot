"""Discover managed broadcast channels with existing, owner-scoped live clients."""
import asyncio

from telethon import types, utils
from telethon.errors import FloodWaitError

from auth.runtime_access import get_owner_runtime_access
from db.crud_managed_channels import _owned_account, require_owner, save_scan
from db.database import SessionLocal
from utils.redaction import redact_sensitive_text


RIGHTS = ("post_messages", "edit_messages", "delete_messages", "add_admins", "change_info",
          "invite_users", "ban_users", "pin_messages", "manage_call", "post_stories",
          "edit_stories", "delete_stories", "manage_direct_messages")
_scan_locks = {}


async def sync_account(account_id, account_manager):
    owner = require_owner()
    with SessionLocal() as db:
        account = _owned_account(db, owner, account_id)
        enabled = bool(account.enabled)
        access = get_owner_runtime_access(owner, "channels", db=db)
        if not access.allowed:
            raise PermissionError(access.message)
    lock = _scan_locks.setdefault((owner, account_id), asyncio.Lock())
    if lock.locked():
        raise ValueError("此账号正在同步，请稍后刷新")
    async with lock:
        try:
            if not enabled:
                raise ValueError("账号已停用，请在账号管理中启用后重试")
            client = account_manager.get_client(account_id)
            if client is None or not client.is_connected():
                raise ValueError("账号未连接，请在账号管理中重新登录后重试")

            async def collect():
                me = await client.get_me()
                if not me:
                    raise ValueError("账号登录已失效，请重新登录")
                found = []
                async for dialog in client.iter_dialogs(limit=None):
                    entity = dialog.entity
                    if not isinstance(entity, types.Channel) or not entity.broadcast or entity.left:
                        continue
                    creator = bool(entity.creator)
                    rights = entity.admin_rights
                    if not creator and rights is None:
                        continue
                    found.append({
                        "chat_id": str(utils.get_peer_id(entity)), "title": entity.title or "",
                        "username": "@" + entity.username if entity.username else "",
                        "telegram_user_id": str(me.id), "role": "creator" if creator else "administrator",
                        "rights": {key: creator or bool(getattr(rights, key, False)) for key in RIGHTS},
                    })
                return found

            rows = await asyncio.wait_for(collect(), timeout=45)
            save_scan(account_id, rows=rows)
            return {"ok": True, "count": len(rows), "account_id": account_id}
        except Exception as exc:
            if isinstance(exc, asyncio.TimeoutError):
                message = "同步超时，已保留上次结果，请稍后重试"
            elif isinstance(exc, FloodWaitError):
                message = f"Telegram 请求过于频繁，请在 {exc.seconds} 秒后重试"
            else:
                message = redact_sensitive_text(exc)[:500]
            save_scan(account_id, error=message)
            return {"ok": False, "account_id": account_id, "message": message}
