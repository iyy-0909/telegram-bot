from telethon import TelegramClient

from config import API_ID, API_HASH, PROXY
from db.crud import get_all_accounts
from bot.logger import logger


class AccountManager:

    def __init__(self):
        self.clients = {}

    async def load_accounts(self):
        accounts = get_all_accounts()

        for account in accounts:
            if not account.enabled:
                continue

            client = TelegramClient(
                account.session_path,
                API_ID,
                API_HASH,
                proxy=PROXY,
                connection_retries=999,
                retry_delay=5,
                auto_reconnect=True,
                request_retries=5
            )

            await client.start()

            self.clients[account.id] = client

            logger.info(
                f"账号已加载：id={account.id} name={account.name}"
            )

    def get_client(self, account_id: int):
        return self.clients.get(account_id)

    async def disconnect_all(self):
        for account_id, client in self.clients.items():
            await client.disconnect()
            logger.info(f"账号已断开：id={account_id}")


account_manager = AccountManager()