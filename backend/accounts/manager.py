from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError

from config import API_ID, API_HASH, PROXY
from db.crud import get_all_accounts
from bot.logger import logger
from utils.proxy_utils import normalize_proxy_for_runtime


class AccountManager:

    def __init__(self):
        self.clients = {}

    async def _disconnect_safely(self, client):
        try:
            await client.disconnect()
        except Exception:
            pass

    async def load_accounts(self):
        accounts = get_all_accounts()
        loaded_count = 0

        for account in accounts:
            if not account.enabled:
                continue

            old_client = self.clients.pop(account.id, None)
            if old_client:
                await self._disconnect_safely(old_client)

            configured_proxy = account.proxy or PROXY
            runtime_proxy = normalize_proxy_for_runtime(
                configured_proxy,
                account_id=account.id,
                account_name=account.name,
            )

            client = None

            try:
                client = TelegramClient(
                    account.session_path,
                    API_ID,
                    API_HASH,
                    proxy=runtime_proxy,
                    connection_retries=999,
                    retry_delay=5,
                    auto_reconnect=True,
                    request_retries=5
                )
                await client.start()
            except AuthKeyDuplicatedError as e:
                logger.error(
                    "账号 session 授权已失效，已跳过加载 | "
                    f"account_id={account.id} | account_name={account.name} | "
                    f"session={account.session_path} | error={e}"
                )
                if client:
                    await self._disconnect_safely(client)
                continue
            except Exception as e:
                if e.__class__.__name__ == "AuthKeyDuplicatedError":
                    logger.error(
                        "账号 session 授权已失效，已跳过加载 | "
                        f"account_id={account.id} | account_name={account.name} | "
                        f"session={account.session_path} | error={e}"
                    )
                    if client:
                        await self._disconnect_safely(client)
                    continue

                logger.exception(
                    "账号加载失败，已跳过该账号 | "
                    f"account_id={account.id} | account_name={account.name} | "
                    f"session={account.session_path} | error={e}"
                )
                if client:
                    await self._disconnect_safely(client)
                continue

            self.clients[account.id] = client
            loaded_count += 1

            logger.info(
                f"账号已加载：id={account.id} name={account.name}"
            )

        logger.info(f"账号加载完成 | loaded={loaded_count}")

    def get_client(self, account_id: int):
        return self.clients.get(account_id)

    async def disconnect_all(self):
        for account_id, client in self.clients.items():
            await client.disconnect()
            logger.info(f"账号已断开：id={account_id}")


account_manager = AccountManager()
