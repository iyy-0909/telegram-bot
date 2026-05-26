from telethon import TelegramClient

from config import API_ID, API_HASH, SESSION_PATH, PROXY
from utils.proxy_utils import normalize_proxy_for_runtime


client = TelegramClient(
    SESSION_PATH,
    API_ID,
    API_HASH,
    proxy=normalize_proxy_for_runtime(PROXY)
)
