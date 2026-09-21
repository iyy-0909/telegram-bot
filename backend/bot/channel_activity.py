"""Observe new channel posts and read recent content with an owner's loaded account."""
import asyncio

from telethon import events

from auth.tenant import tenant_scope
from bot.logger import logger
from db.channel_activity import record_channel_content
from db.database import SessionLocal
from db.models import Account
from utils.redaction import redact_sensitive_text


def register_channel_activity(client, owner_user_id):
    if not owner_user_id:
        return

    async def on_post(event):
        if not event.is_channel or getattr(event.message, "action", None):
            return
        try:
            chat = event.chat
            with tenant_scope(owner_user_id):
                record_channel_content(
                    owner_user_id, chat_id=event.chat_id,
                    username=getattr(chat, "username", None), date=event.message.date,
                )
        except Exception as exc:
            logger.warning(f"频道新内容时间记录失败：{redact_sensitive_text(exc)}")

    client.add_event_handler(on_post, events.NewMessage())


async def refresh_channel_activity(channel, account_manager):
    owner_id = getattr(channel, "owner_user_id", None)
    if not owner_id:
        return
    with SessionLocal() as db:
        account_ids = [row[0] for row in db.query(Account.id).filter(
            Account.owner_user_id == owner_id, Account.enabled.is_(True),
        ).all()]
    target = channel.username or channel.chat_id
    if not target:
        return
    if str(target).lstrip("-").isdigit():
        target = int(target)
    for account_id in account_ids:
        client = account_manager.get_client(account_id)
        if client is None:
            continue
        try:
            # Service messages (pin/title changes) do not count as new content.
            messages = await asyncio.wait_for(client.get_messages(target, limit=100), timeout=10)
            latest = next((message for message in messages
                           if getattr(message, "date", None)
                           and not getattr(message, "action", None)
                           and (getattr(message, "message", None) or getattr(message, "media", None))), None)
            if latest:
                record_channel_content(owner_id, chat_id=channel.chat_id,
                                       username=channel.username, date=latest.date)
            return
        except Exception as exc:
            logger.debug(f"频道内容时间读取失败 | channel_id={channel.id} | {redact_sensitive_text(exc)}")
