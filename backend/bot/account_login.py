import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError, SessionPasswordNeededError
from telethon.network import ConnectionTcpFull

from bot.logger import logger
from accounts.session_storage import (
    SessionPathError,
    generate_owner_session_path,
    normalize_session_path,
    resolve_owner_session_path,
    session_path_key,
    stored_owner_session_path,
)
from auth.tenant import current_tenant_user_id
from config import API_HASH, API_ID
from db.database import SessionLocal
from db.models import Account
from db.crud import ensure_default_account_in_session
from utils.proxy_utils import normalize_proxy_for_runtime
from utils.redaction import mask_phone, redact_sensitive_text


LOGIN_TTL_MINUTES = 10


def _required_owner_id(owner_user_id=None):
    owner_id = owner_user_id or current_tenant_user_id()
    if owner_id in (None, "", 0, "0"):
        raise PermissionError("Telegram 账号操作缺少归属人")
    return int(owner_id)


def account_to_payload(account):
    if not account:
        return None

    phone = account.phone or ""
    session_path = account.session_path or ""
    proxy = account.proxy or ""
    return {
        "id": account.id,
        "name": account.name or "",
        "username": account.username or "",
        "phone": "",
        "phone_masked": mask_phone(phone),
        "has_phone": bool(phone),
        "session_path": "",
        "has_session_path": bool(session_path),
        "proxy": "",
        "has_proxy": bool(proxy),
        "enabled": bool(account.enabled),
        "remark": account.remark or "",
    }


def _account_to_internal_payload(account):
    if not account:
        return None

    return {
        "id": account.id,
        "name": account.name or "",
        "username": account.username or "",
        "phone": account.phone or "",
        "session_path": account.session_path or "",
        "proxy": account.proxy or "",
        "enabled": bool(account.enabled),
        "remark": account.remark or "",
    }


def _internal_account_to_public_payload(account):
    if not account:
        return None
    phone = account.get("phone") or ""
    session_path = account.get("session_path") or ""
    proxy = account.get("proxy") or ""
    return {
        "id": account.get("id"),
        "name": account.get("name") or "",
        "username": account.get("username") or "",
        "phone": "",
        "phone_masked": mask_phone(phone),
        "has_phone": bool(phone),
        "session_path": "",
        "has_session_path": bool(session_path),
        "proxy": "",
        "has_proxy": bool(proxy),
        "enabled": bool(account.get("enabled")),
        "remark": account.get("remark") or "",
    }


@dataclass
class PendingAccountLogin:
    login_id: str
    client: TelegramClient
    phone: str
    name: str
    session_path: str
    proxy: str
    remark: str
    account_id: int | None
    owner_user_id: int
    created_at: datetime
    needs_password: bool = False

    @property
    def expired(self):
        return datetime.utcnow() - self.created_at > timedelta(minutes=LOGIN_TTL_MINUTES)


class AccountLoginManager:
    def __init__(self):
        self.sessions: dict[str, PendingAccountLogin] = {}
        self.reserved_session_paths: set[str] = set()
        self.lock = asyncio.Lock()

    async def _cleanup_expired(self):
        expired_ids = [
            login_id
            for login_id, session in self.sessions.items()
            if session.expired
        ]

        for login_id in expired_ids:
            await self._discard_session(login_id)

    async def _discard_session(self, login_id):
        session = self.sessions.pop(login_id, None)
        if not session:
            return False

        self.reserved_session_paths.discard(
            session_path_key(session.session_path)
        )
        try:
            await session.client.disconnect()
        except Exception:
            pass
        return True

    async def cancel(self, login_id, *, owner_user_id=None):
        owner_id = _required_owner_id(owner_user_id)
        session = self.sessions.get(login_id)
        if not session or int(session.owner_user_id) != owner_id:
            return False
        return await self._discard_session(login_id)

    def get_account(self, account_id, owner_user_id):
        db = SessionLocal()
        try:
            return db.query(Account).filter(
                Account.id == account_id,
                Account.owner_user_id == int(owner_user_id),
            ).first()
        finally:
            db.close()

    def find_account_by_session_path(self, owner_user_id, session_path):
        normalized = session_path_key(session_path)
        db = SessionLocal()
        try:
            accounts = db.query(Account).filter(
                Account.owner_user_id == int(owner_user_id)
            ).order_by(Account.id.asc()).all()
            for account in accounts:
                if session_path_key(account.session_path) == normalized:
                    return _account_to_internal_payload(account)
            return None
        finally:
            db.close()

    def find_account_by_identity(self, owner_user_id, username, phone):
        username = str(username or "").strip().lstrip("@").lower()
        phone = str(phone or "").strip()
        db = SessionLocal()
        try:
            accounts = db.query(Account).filter(
                Account.owner_user_id == int(owner_user_id)
            ).order_by(Account.id.asc()).all()
            for account in accounts:
                account_username = str(account.username or "").strip().lstrip("@").lower()
                account_phone = str(account.phone or "").strip()

                if username and account_username == username:
                    return account
                if phone and account_phone == phone:
                    return account

            return None
        finally:
            db.close()

    def next_session_path(self, owner_user_id):
        owner_id = _required_owner_id(owner_user_id)
        used_paths = [
            session.session_path
            for session in self.sessions.values()
            if int(session.owner_user_id) == owner_id
        ]
        db = SessionLocal()
        try:
            used_paths.extend(
                account.session_path
                for account in db.query(Account).filter(
                    Account.owner_user_id == owner_id
                ).all()
            )
        finally:
            db.close()
        used_paths.extend(
            session.session_path
            for session in self.sessions.values()
        )
        used_paths.extend(self.reserved_session_paths)
        return generate_owner_session_path(owner_id, occupied_paths=used_paths)

    async def start_login(
        self,
        *,
        phone,
        name="",
        proxy="",
        remark="",
        account_id=None,
        owner_user_id=None,
    ):
        owner_id = _required_owner_id(owner_user_id)
        async with self.lock:
            await self._cleanup_expired()

        phone = str(phone or "").strip()
        name = str(name or "").strip()
        proxy = str(proxy or "").strip()
        remark = str(remark or "").strip()

        account = None
        if account_id:
            account = self.get_account(account_id, owner_id)
            if not account:
                return {
                    "ok": False,
                    "code": "account_not_found",
                    "message": "账号不存在",
                }

            name = name or account.name or f"账号{account.id}"
            phone = phone or account.phone or ""
            session_path = (
                normalize_session_path(account.session_path)
                or self.next_session_path(owner_id)
            )
            proxy = proxy if proxy != "" else (account.proxy or "")
            remark = remark if remark != "" else (account.remark or "")
            async with self.lock:
                reservation_key = session_path_key(session_path)
                if reservation_key in self.reserved_session_paths:
                    return {
                        "ok": False,
                        "code": "login_in_progress",
                        "message": "该账号已有登录验证正在进行",
                    }
                self.reserved_session_paths.add(reservation_key)
        else:
            async with self.lock:
                session_path = self.next_session_path(owner_id)
                self.reserved_session_paths.add(session_path_key(session_path))

        if not phone:
            self.reserved_session_paths.discard(session_path_key(session_path))
            return {
                "ok": False,
                "code": "phone_required",
                "message": "手机号不能为空",
            }

        if not name:
            name = "采集账号"

        try:
            resolved_session_path = resolve_owner_session_path(
                owner_id,
                session_path,
                create_parent=True,
            )
        except SessionPathError:
            self.reserved_session_paths.discard(session_path_key(session_path))
            return {
                "ok": False,
                "code": "session_path_invalid",
                "message": "账号 Session 路径未完成归属迁移，请联系管理员",
            }

        existing = self.find_account_by_session_path(owner_id, session_path)
        if existing and (not account_id or int(existing["id"]) != int(account_id)):
            self.reserved_session_paths.discard(session_path_key(session_path))
            return {
                "ok": False,
                "code": "session_path_exists",
                "message": "账号 Session 路径冲突，请联系管理员",
                "existing_account": _internal_account_to_public_payload(existing),
            }

        runtime_proxy = normalize_proxy_for_runtime(
            proxy or None,
            account_id=account_id,
            account_name=name,
        )

        client = TelegramClient(
            str(resolved_session_path),
            API_ID,
            API_HASH,
            connection=ConnectionTcpFull,
            proxy=runtime_proxy,
            connection_retries=10,
            retry_delay=3,
            timeout=30,
            auto_reconnect=True,
        )

        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                await client.disconnect()
                saved = self.save_account(
                    account_id=account_id,
                    name=name,
                    session_path=session_path,
                    proxy=proxy,
                    remark=remark,
                    me=me,
                    owner_user_id=owner_id,
                )
                self.reserved_session_paths.discard(session_path_key(session_path))
                return {
                    "ok": True,
                    "already_authorized": True,
                    "account": account_to_payload(saved),
                    "message": "账号已授权，已保存账号信息",
                }

            await client.send_code_request(phone)
        except AuthKeyDuplicatedError:
            await client.disconnect()
            self.reserved_session_paths.discard(session_path_key(session_path))
            return {
                "ok": False,
                "code": "auth_key_duplicated",
                "message": "旧 session 已失效，请更换或删除旧 session 文件后重新登录",
            }
        except Exception as e:
            await client.disconnect()
            self.reserved_session_paths.discard(session_path_key(session_path))
            safe_error = redact_sensitive_text(e)
            logger.exception(
                "后台账号登录发送验证码失败 | account_id=%s | error=%s",
                account_id,
                safe_error,
            )
            return {
                "ok": False,
                "code": "send_code_failed",
                "message": f"发送验证码失败：{safe_error}",
            }

        login_id = uuid.uuid4().hex
        self.sessions[login_id] = PendingAccountLogin(
            login_id=login_id,
            client=client,
            phone=phone,
            name=name,
            session_path=session_path,
            proxy=proxy,
            remark=remark,
            account_id=account_id,
            owner_user_id=owner_id,
            created_at=datetime.utcnow(),
        )

        return {
            "ok": True,
            "login_id": login_id,
            "expires_in": LOGIN_TTL_MINUTES * 60,
            "message": "验证码已发送，请在 10 分钟内输入验证码",
        }

    async def verify_code(
        self,
        *,
        login_id,
        code,
        password="",
        owner_user_id=None,
    ):
        owner_id = _required_owner_id(owner_user_id)
        session = self.sessions.get(login_id)
        if not session or int(session.owner_user_id) != owner_id:
            return {
                "ok": False,
                "code": "login_not_found",
                "message": "登录会话不存在或已过期，请重新发送验证码",
            }

        if session.expired:
            await self._discard_session(login_id)
            return {
                "ok": False,
                "code": "login_expired",
                "message": "登录会话已过期，请重新发送验证码",
            }

        code = str(code or "").strip()
        password = str(password or "").strip()

        if not code:
            return {
                "ok": False,
                "code": "code_required",
                "message": "验证码不能为空",
            }

        try:
            if session.needs_password:
                if not password:
                    return {
                        "ok": False,
                        "need_password": True,
                        "message": "该账号开启了二步验证，请输入二步验证密码",
                    }
                await session.client.sign_in(password=password)
            else:
                try:
                    await session.client.sign_in(session.phone, code)
                except SessionPasswordNeededError:
                    session.needs_password = True
                    if not password:
                        return {
                            "ok": False,
                            "need_password": True,
                            "message": "该账号开启了二步验证，请输入二步验证密码",
                        }
                    await session.client.sign_in(password=password)

            me = await session.client.get_me()
            saved = self.save_account(
                account_id=session.account_id,
                name=session.name,
                session_path=session.session_path,
                proxy=session.proxy,
                remark=session.remark,
                me=me,
                owner_user_id=owner_id,
            )

            await self._discard_session(login_id)
            return {
                "ok": True,
                "account": account_to_payload(saved),
                "updated_existing": bool(session.account_id),
                "message": "登录成功",
            }

        except Exception as e:
            safe_error = redact_sensitive_text(e)
            logger.exception(
                "后台账号登录验证失败 | account_id=%s | error=%s",
                session.account_id,
                safe_error,
            )
            return {
                "ok": False,
                "code": "verify_failed",
                "message": f"登录验证失败：{safe_error}",
            }

    def save_account(
        self,
        *,
        account_id,
        name,
        session_path,
        proxy,
        remark,
        me,
        owner_user_id=None,
    ):
        owner_id = _required_owner_id(owner_user_id)
        resolved_session_path = resolve_owner_session_path(
            owner_id,
            session_path,
            create_parent=True,
        )
        stored_session_path = stored_owner_session_path(
            owner_id,
            resolved_session_path,
        )
        username = getattr(me, "username", "") or ""
        phone = getattr(me, "phone", "") or ""

        db = SessionLocal()
        try:
            account = None

            if account_id:
                account = db.query(Account).filter(
                    Account.id == account_id,
                    Account.owner_user_id == owner_id,
                ).first()
                if account is None:
                    raise PermissionError("Telegram 账号不存在或不属于当前用户")

            identity_account = None
            accounts = db.query(Account).filter(
                Account.owner_user_id == owner_id
            ).order_by(Account.id.asc()).all()
            for item in accounts:
                if account and item.id == account.id:
                    continue

                if username and (item.username or "").strip().lstrip("@").lower() == username.lower():
                    identity_account = item
                    break

                if phone and (item.phone or "").strip() == phone:
                    identity_account = item
                    break

            if identity_account:
                account = identity_account

            for item in accounts:
                if account and item.id == account.id:
                    continue
                try:
                    item_path = resolve_owner_session_path(
                        owner_id,
                        item.session_path,
                    )
                except SessionPathError:
                    continue
                if item_path == resolved_session_path:
                    raise SessionPathError("Telegram Session 路径已被其他账号使用")

            if account:
                account.name = name or account.name or username or phone or f"账号{account.id}"
                account.username = username
                account.phone = phone
                account.session_path = stored_session_path
                account.proxy = proxy or account.proxy or ""
                account.enabled = True
                account.remark = remark if remark != "" else (account.remark or "")
            else:
                account = Account(
                    name=name or username or phone or "采集账号",
                    username=username,
                    phone=phone,
                    session_path=stored_session_path,
                    proxy=proxy or "",
                    enabled=True,
                    remark=remark or "",
                    owner_user_id=owner_id,
                )
                db.add(account)

            if hasattr(account, "updated_at"):
                account.updated_at = datetime.utcnow()

            db.flush()
            ensure_default_account_in_session(db, owner_id)
            db.commit()
            db.refresh(account)
            return account
        finally:
            db.close()


account_login_manager = AccountLoginManager()
