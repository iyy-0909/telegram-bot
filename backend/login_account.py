import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import socks
from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError, SessionPasswordNeededError
from telethon.network import ConnectionTcpFull

from config import API_ID, API_HASH
from db.database import DATABASE_URL, SessionLocal
from db.models import Account
from init_db import init_db
from utils.proxy_utils import normalize_proxy_for_runtime


PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7897
PROXY = (
    socks.SOCKS5,
    PROXY_HOST,
    PROXY_PORT,
)


def sqlite_db_path():
    if not DATABASE_URL.startswith("sqlite:///"):
        return DATABASE_URL

    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    if db_path in {":memory:", ""}:
        return db_path
    if db_path.startswith("./"):
        db_path = db_path[2:]
    return str(Path(unquote(db_path)).resolve())


def normalize_session_path(value):
    return str(value or "").strip().replace("\\", "/").removesuffix(".session")


def session_file_path(session_path):
    path = Path(session_path)
    if path.suffix != ".session":
        path = path.with_suffix(".session")
    return path


def print_accounts(accounts):
    print("\n已有采集账号：")
    if not accounts:
        print("  暂无账号")
        return

    print("ID | 名称 | username | phone | session_path | enabled")
    for account in accounts:
        print(
            f"{account.id} | "
            f"{account.name or ''} | "
            f"{getattr(account, 'username', '') or ''} | "
            f"{getattr(account, 'phone', '') or ''} | "
            f"{account.session_path or ''} | "
            f"{bool(account.enabled)}"
        )


def load_accounts(db):
    return db.query(Account).order_by(Account.id.asc()).all()


def find_account_by_id(db, account_id):
    return db.query(Account).filter(Account.id == account_id).first()


def find_account_by_session_path(db, session_path):
    normalized = normalize_session_path(session_path)
    for account in load_accounts(db):
        if normalize_session_path(account.session_path) == normalized:
            return account
    return None


def find_account_by_identity(db, username, phone):
    username = str(username or "").strip().lstrip("@").lower()
    phone = str(phone or "").strip()

    for account in load_accounts(db):
        account_username = str(getattr(account, "username", "") or "").strip().lstrip("@").lower()
        account_phone = str(getattr(account, "phone", "") or "").strip()

        if username and account_username == username:
            return account
        if phone and account_phone == phone:
            return account

    return None


def yes_no(prompt, default=False):
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({suffix})：").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "是", "1", "true"}


def next_session_path(accounts):
    existing_ids = [account.id for account in accounts]
    next_number = (max(existing_ids) + 1) if existing_ids else 1
    return f"data/sessions/collector_{next_number}"


def backup_invalid_session(session_path):
    path = session_file_path(session_path)
    if not path.exists():
        return None

    backup_path = path.with_name(
        f"{path.name}.invalid_{datetime.now():%Y%m%d_%H%M%S}"
    )
    path.rename(backup_path)
    return backup_path


def update_account_record(db, account, *, name, session_path, me):
    account.name = name or account.name or f"账号{account.id}"
    account.session_path = normalize_session_path(session_path)
    account.username = me.username or ""
    account.phone = me.phone or ""
    account.enabled = True
    if hasattr(account, "updated_at"):
        account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return account


def create_account_record(db, *, name, session_path, me):
    account = Account(
        name=name or me.username or me.phone or "采集账号",
        username=me.username or "",
        phone=me.phone or "",
        session_path=normalize_session_path(session_path),
        proxy="",
        enabled=True,
        remark="",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


async def login_telegram(session_path):
    Path(session_path).parent.mkdir(parents=True, exist_ok=True)
    runtime_proxy = normalize_proxy_for_runtime(PROXY)

    for attempt in range(2):
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

        if runtime_proxy:
            print(f"正在通过代理连接 Telegram：{PROXY_HOST}:{PROXY_PORT}")
        else:
            print("正在直连 Telegram")

        try:
            await client.connect()
            if not await client.is_user_authorized():
                phone = input("请输入手机号，带国家区号，例如 +86138xxxx：").strip()
                if not phone:
                    raise RuntimeError("手机号不能为空")

                await client.send_code_request(phone)
                code = input("请输入验证码：").strip()

                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input("请输入二步验证密码：").strip()
                    await client.sign_in(password=password)

            me = await client.get_me()
            return me
        except AuthKeyDuplicatedError:
            if attempt > 0:
                raise
            backup_path = backup_invalid_session(session_path)
            print(f"旧 session 授权已失效，已备份：{backup_path}")
            print("将使用相同 session_path 重新登录。")
            continue
        finally:
            await client.disconnect()

    raise RuntimeError("登录失败")


def select_existing_account(db):
    raw_id = input("请输入要重新登录的 account_id：").strip()
    if not raw_id.isdigit():
        print("account_id 必须是数字")
        return None, None, None

    account = find_account_by_id(db, int(raw_id))
    if not account:
        print("未找到该账号")
        return None, None, None

    default_path = normalize_session_path(account.session_path)
    session_path = input(f"Session 路径 [{default_path}]：").strip() or default_path
    name = input(f"账号名称 [{account.name}]：").strip() or account.name
    return account, name, normalize_session_path(session_path)


def input_new_account(db, accounts):
    default_path = next_session_path(accounts)
    name = input("请输入账号名称：").strip() or "采集账号"
    session_path = input(f"请输入 session 路径 [{default_path}]：").strip() or default_path
    session_path = normalize_session_path(session_path)

    existing = find_account_by_session_path(db, session_path)
    if existing:
        print(f"该 session_path 已存在：account_id={existing.id} name={existing.name}")
        if yes_no("是否更新这个已有账号", default=True):
            return existing, existing.name or name, session_path
        return None, None, None

    return None, name, session_path


async def main():
    print("Telegram 用户号登录工具")
    print(f"DATABASE_URL = {DATABASE_URL}")
    print(f"实际数据库 = {sqlite_db_path()}")
    print(f"sessions 目录 = {Path('data/sessions').resolve()}")
    init_db()

    db = SessionLocal()
    try:
        accounts = load_accounts(db)
        print(f"已有账号数量 = {len(accounts)}")
        print_accounts(accounts)

        print("\n请选择操作：")
        print("1. 重新登录已有账号")
        print("2. 新增账号")
        print("3. 退出")
        choice = input("请输入选项 [1/2/3]：").strip()

        if choice == "1":
            account, name, session_path = select_existing_account(db)
            updated_existing = True
        elif choice == "2":
            account, name, session_path = input_new_account(db, accounts)
            updated_existing = bool(account)
        else:
            print("已退出")
            return

        if not session_path:
            print("session 路径不能为空")
            return

        me = await login_telegram(session_path)

        identity_account = find_account_by_identity(db, me.username, me.phone)
        if identity_account and (not account or identity_account.id != account.id):
            print(
                "手机号或 username 已存在："
                f"account_id={identity_account.id} name={identity_account.name}"
            )
            if yes_no("是否更新这个已有账号", default=True):
                account = identity_account
                updated_existing = True
            else:
                print("已取消保存，避免创建重复账号。")
                return

        if account:
            saved = update_account_record(
                db,
                account,
                name=name,
                session_path=session_path,
                me=me,
            )
            updated_existing = True
        else:
            saved = create_account_record(
                db,
                name=name,
                session_path=session_path,
                me=me,
            )
            updated_existing = False

        print("\n登录成功：")
        print("id =", saved.id)
        print("name =", saved.name)
        print("username =", saved.username)
        print("phone =", saved.phone)
        print("session =", saved.session_path)
        print("updated_existing =", str(updated_existing).lower())
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
