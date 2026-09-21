import asyncio

from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError
from telethon.errors.common import TypeNotFoundError

from auth.runtime_access import get_owner_runtime_access
from accounts.session_storage import resolve_owner_session_path
from config import API_ID, API_HASH, PROXY
from db.crud import get_all_accounts
from db.database import SessionLocal
from db.models import Account
from bot.logger import logger
from utils.proxy_utils import normalize_proxy_for_runtime
from utils.redaction import redact_sensitive_text


TYPE_NOT_FOUND_RETRY_DELAY_SECONDS = 0.5


class AccountManager:

    def __init__(self):
        self.clients = {}
        self._load_locks = {}

    def _get_load_lock(self, account_id: int):
        account_id = int(account_id)
        lock = self._load_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            self._load_locks[account_id] = lock
        return lock

    @staticmethod
    def _client_is_healthy(client):
        if client is None:
            return False

        is_connected = getattr(client, "is_connected", None)
        if not callable(is_connected):
            return True

        try:
            return bool(is_connected())
        except Exception:
            return False

    async def _disconnect_safely(self, client):
        try:
            await client.disconnect()
        except Exception:
            pass

    async def _disconnect_completely(self, client):
        """Finish closing a Telethon session before its account lock is released."""
        if client is None:
            return

        cleanup_task = asyncio.create_task(self._disconnect_safely(client))
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            # Shield keeps the close running, but the outer await is still cancelled.
            # Wait for the session close before allowing another loader into the lock.
            await cleanup_task
            raise

    async def _remove_cached_client_locked(self, account_id: int):
        client = self.clients.pop(account_id, None)
        if client is not None:
            await self._disconnect_completely(client)

    def _build_client(self, account, runtime_proxy):
        session_path = resolve_owner_session_path(
            account.owner_user_id,
            account.session_path,
        )
        return TelegramClient(
            str(session_path),
            API_ID,
            API_HASH,
            proxy=runtime_proxy,
            connection_retries=999,
            retry_delay=5,
            auto_reconnect=True,
            request_retries=5,
        )

    async def _start_new_client(
        self,
        account,
        runtime_proxy,
        *,
        retry_type_not_found: bool,
    ):
        attempts = 2 if retry_type_not_found else 1

        for attempt in range(attempts):
            client = None
            try:
                client = self._build_client(account, runtime_proxy)
                await client.start()
                return client
            except TypeNotFoundError as exc:
                await self._disconnect_completely(client)
                if attempt + 1 >= attempts:
                    raise
                logger.warning(
                    "temporary Telegram response while loading account; retrying once | "
                    f"account_id={account.id} | error={redact_sensitive_text(exc)}"
                )
                await asyncio.sleep(TYPE_NOT_FOUND_RETRY_DELAY_SECONDS)
            except BaseException:
                await self._disconnect_completely(client)
                raise

        return None

    async def _load_account_locked(
        self,
        account,
        *,
        force_reload: bool,
        retry_type_not_found: bool,
        db=None,
    ):
        account_id = int(account.id)

        if not account.enabled:
            await self._remove_cached_client_locked(account_id)
            logger.warning(
                f"账号未启用，已跳过加载 | account_id={account_id}"
            )
            return False

        access = get_owner_runtime_access(
            getattr(account, "owner_user_id", None),
            "accounts",
            **({"db": db} if db is not None else {}),
        )
        if not access.allowed:
            await self._remove_cached_client_locked(account_id)
            logger.warning(
                "account runtime load blocked by access | "
                f"account_id={account_id} | reason={access.reason}"
            )
            return False

        existing_client = self.clients.get(account_id)
        if not force_reload and self._client_is_healthy(existing_client):
            return True

        await self._remove_cached_client_locked(account_id)

        configured_proxy = account.proxy or PROXY
        runtime_proxy = normalize_proxy_for_runtime(
            configured_proxy,
            account_id=account_id,
            account_name=account.name,
        )

        try:
            client = await self._start_new_client(
                account,
                runtime_proxy,
                retry_type_not_found=retry_type_not_found,
            )
        except AuthKeyDuplicatedError as exc:
            self.clients.pop(account_id, None)
            logger.error(
                "账号 session 授权已失效，已跳过加载 | "
                f"account_id={account_id} | account_name={account.name} | "
                f"error={redact_sensitive_text(exc)}"
            )
            return False
        except asyncio.CancelledError:
            self.clients.pop(account_id, None)
            raise
        except Exception as exc:
            self.clients.pop(account_id, None)
            if exc.__class__.__name__ == "AuthKeyDuplicatedError":
                logger.error(
                    "账号 session 授权已失效，已跳过加载 | "
                    f"account_id={account_id} | account_name={account.name} | "
                    f"error={redact_sensitive_text(exc)}"
                )
                return False

            logger.exception(
                "账号加载失败，已跳过该账号 | "
                f"account_id={account_id} | account_name={account.name} | "
                f"error={redact_sensitive_text(exc)}"
            )
            return False

        self.clients[account_id] = client
        from bot.channel_activity import register_channel_activity
        register_channel_activity(client, getattr(account, "owner_user_id", None))
        logger.info(f"账号已加载：id={account_id} name={account.name}")
        return True

    async def load_accounts(self, *, force_reload: bool = False):
        accounts = get_all_accounts()
        loaded_count = 0

        for account in accounts:
            lock = self._get_load_lock(account.id)
            async with lock:
                loaded = await self._load_account_locked(
                    account,
                    force_reload=force_reload,
                    retry_type_not_found=True,
                )
            if loaded:
                loaded_count += 1

        logger.info(f"账号加载完成 | loaded={loaded_count}")

    async def load_account(self, account_id: int, *, force_reload: bool = False):
        account_id = int(account_id)
        lock = self._get_load_lock(account_id)

        async with lock:
            db = SessionLocal()
            try:
                account = (
                    db.query(Account)
                    .filter(Account.id == account_id)
                    .first()
                )

                if not account:
                    logger.error(
                        f"账号加载失败，账号不存在 | account_id={account_id}"
                    )
                    return False

                return await self._load_account_locked(
                    account,
                    force_reload=force_reload,
                    retry_type_not_found=False,
                    db=db,
                )
            finally:
                db.close()

    def get_client(self, account_id: int):
        return self.clients.get(account_id)

    async def disconnect_all(self):
        account_ids = list(self.clients)
        for account_id in account_ids:
            lock = self._get_load_lock(account_id)
            async with lock:
                client = self.clients.pop(account_id, None)
                if client is None:
                    continue
                await self._disconnect_completely(client)
                logger.info(f"账号已断开：id={account_id}")


account_manager = AccountManager()
