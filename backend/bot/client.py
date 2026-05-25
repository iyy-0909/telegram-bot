from telethon import TelegramClient

from config import API_ID, API_HASH, SESSION_PATH, PROXY


client = TelegramClient(
    SESSION_PATH,
    API_ID,
    API_HASH,
    proxy=PROXY
)