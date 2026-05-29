import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError, SessionPasswordNeededError
from telethon.network import ConnectionTcpFull

from bot.logger import logger
from config import API_HASH, API_ID
from db.database import SessionLocal
from db.models import Account
from utils.proxy_utils import normalize_proxy_for_runtime


LOGIN_TTL_MINUTES = 10


def normalize_session_path(value):
    return str(value or "").strip().replace("\\", "/").removesuffix(".session")


def session_file_path(session_path):
    path = Path(session_path)
    if path.suffix != ".session":
        path = path.with_suffix(".session")
    return path


def account_to_payload(account):
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
    created_at: datetime
    needs_password: bool = False

    @property
    def expired(self):
        return datetime.utcnow() - self.created_at > timedelta(minutes=LOGIN_TTL_MINUTES)


class AccountLoginManager:
    def __init__(self):
        self.sessions: dict[str, PendingAccountLogin] = {}
        self.lock = asyncio.Lock()

    async def _cleanup_expired(self):
        expired_ids = [
            login_id
            for login_id, session in self.sessions.items()
            if session.expired
        ]

        for login_id in expired_ids:
            await self.cancel(login_id)

    async def cancel(self, login_id):
        session = self.sessions.pop(login_id, None)
        if not session:
            return

        try:
            await session.client.disconnect()
        except Exception:
            pass

    def get_account(self, account_id):
        db = SessionLocal()
        try:
            return db.query(Account).filter(Account.id == account_id).first()
        finally:
            db.close()

    def find_account_by_session_path(self, session_path):
        normalized = normalize_session_path(session_path)
        db = SessionLocal()
        try:
            for account in db.query(Account).order_by(Account.id.asc()).all():
                if normalize_session_path(account.session_path) == normalized:
                    return account_to_payload(account)
            return None
        finally:
            db.close()

    def find_account_by_identity(self, username, phone):
        username = str(username or "").strip().lstrip("@").lower()
        phone = str(phone or "").strip()
        db = SessionLocal()
        try:
            for account in db.query(Account).order_by(Account.id.asc()).all():
                account_username = str(account.username or "").strip().lstrip("@").lower()
                account_phone = str(account.phone or "").strip()

                if username and account_username == username:
                    return account
                if phone and account_phone == phone:
                    return account

            return None
        finally:
            db.close()

    async def start_login(
        self,
        *,
        phone,
        name="",
        session_path="",
        proxy="",
        remark="",
        account_id=None,
        update_existing=False,
    ):
        async with self.lock:
            await self._cleanup_expired()

        phone = str(phone or "").strip()
        name = str(name or "").strip()
        session_path = normalize_session_path(session_path)
        proxy = str(proxy or "").strip()
        remark = str(remark or "").strip()

        if not phone:
            return {
                "ok": False,
                "code": "phone_required",
                "message": "手机号不能为空",
            }

        account = None
        if account_id:
            account = self.get_account(account_id)
            if not account:
                return {
                    "ok": False,
                    "code": "account_not_found",
                    "message": "账号不存在",
                }

            name = name or account.name or f"账号{account.id}"
            session_path = session_path or normalize_session_path(account.session_path)
            proxy = proxy if proxy != "" else (account.proxy or "")
            remark = remark if remark != "" else (account.remark or "")

        if not name:
            name = "采集账号"

        if not session_path:
            return {
                "ok": False,
                "code": "session_path_required",
                "message": "Session 路径不能为空",
            }

        existing = self.find_account_by_session_path(session_path)
        if existing and (not account_id or int(existing["id"]) != int(account_id)):
            if not update_existing:
                return {
                    "ok": False,
                    "code": "session_path_exists",
                    "message": "该 Session 路径已存在，是否更新已有账号？",
                    "existing_account": existing,
                }
            account_id = existing["id"]
            name = existing["name"] or name
            proxy = proxy if proxy != "" else (existing.get("proxy") or "")
            remark = remark if remark != "" else (existing.get("remark") or "")

        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        runtime_proxy = normalize_proxy_for_runtime(
            proxy or None,
            account_id=account_id,
            account_name=name,
        )

        client = TelegramClient(
            session_path,
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
                )
                return {
                    "ok": True,
                    "already_authorized": True,
                    "account": account_to_payload(saved),
                    "message": "账号已授权，已保存账号信息",
                }

            await client.send_code_request(phone)
        except AuthKeyDuplicatedError:
            await client.disconnect()
            return {
                "ok": False,
                "code": "auth_key_duplicated",
                "message": "旧 session 已失效，请更换或删除旧 session 文件后重新登录",
            }
        except Exception as e:
            await client.disconnect()
            logger.exception(f"后台账号登录发送验证码失败 | account_id={account_id} | phone={phone} | {e}")
            return {
                "ok": False,
                "code": "send_code_failed",
                "message": f"发送验证码失败：{e}",
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
            created_at=datetime.utcnow(),
        )

        return {
            "ok": True,
            "login_id": login_id,
            "expires_in": LOGIN_TTL_MINUTES * 60,
            "message": "验证码已发送，请在 10 分钟内输入验证码",
        }

    async def verify_code(self, *, login_id, code, password=""):
        session = self.sessions.get(login_id)
        if not session:
            return {
                "ok": False,
                "code": "login_not_found",
                "message": "登录会话不存在或已过期，请重新发送验证码",
            }

        if session.expired:
            await self.cancel(login_id)
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
            )

            await self.cancel(login_id)
            return {
                "ok": True,
                "account": account_to_payload(saved),
                "updated_existing": bool(session.account_id),
                "message": "登录成功",
            }

        except Exception as e:
            logger.exception(
                f"后台账号登录验证失败 | account_id={session.account_id} | "
                f"session={session.session_path} | {e}"
            )
            return {
                "ok": False,
                "code": "verify_failed",
                "message": f"登录验证失败：{e}",
            }

    def save_account(self, *, account_id, name, session_path, proxy, remark, me):
        username = getattr(me, "username", "") or ""
        phone = getattr(me, "phone", "") or ""

        db = SessionLocal()
        try:
            account = None

            if account_id:
                account = db.query(Account).filter(Account.id == account_id).first()

            identity_account = None
            for item in db.query(Account).order_by(Account.id.asc()).all():
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

            if account:
                account.name = name or account.name or username or phone or f"账号{account.id}"
                account.username = username
                account.phone = phone
                account.session_path = normalize_session_path(session_path)
                account.proxy = proxy or account.proxy or ""
                account.enabled = True
                account.remark = remark if remark != "" else (account.remark or "")
            else:
                account = Account(
                    name=name or username or phone or "采集账号",
                    username=username,
                    phone=phone,
                    session_path=normalize_session_path(session_path),
                    proxy=proxy or "",
                    enabled=True,
                    remark=remark or "",
                )
                db.add(account)

            if hasattr(account, "updated_at"):
                account.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(account)
            return account
        finally:
            db.close()


account_login_manager = AccountLoginManager()
