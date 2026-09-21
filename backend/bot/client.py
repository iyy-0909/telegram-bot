from telethon import TelegramClient

from accounts.session_storage import resolve_owner_session_path
from config import API_ID, API_HASH, PROXY
from utils.proxy_utils import normalize_proxy_for_runtime


def build_account_client(account):
    """Build a client only after validating the account-owned session path."""
    session_path = resolve_owner_session_path(
        account.owner_user_id,
        account.session_path,
    )
    return TelegramClient(
        str(session_path),
        API_ID,
        API_HASH,
        proxy=normalize_proxy_for_runtime(PROXY),
    )
