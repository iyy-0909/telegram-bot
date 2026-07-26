import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from time import monotonic

from telethon import events

from bot.logger import logger
from db.crud_notification import get_notification_setting
from notification.config import NotificationConfig
from notification.formatter import (
    entity_display_name,
    entity_username,
    format_notification_body,
    message_summary,
    notification_priority,
)
from notification.membership import is_chat_member
from notification.mute import is_chat_muted
from notification.ntfy_client import NtfyClient


class NotificationService:
    def __init__(self, config=None, ntfy_client=None, setting_loader=None):
        self.config = config or NotificationConfig.from_env()
        self.ntfy_client = ntfy_client
        self.setting_loader = setting_loader or get_notification_setting
        self.account_manager = None
        self.registrations = {}
        self.sync_task = None
        self.account_clients = {}
        self.account_titles = {}
        self.membership_cache = {}
        self.membership_cache_seconds = 300

    def start(self, account_manager):
        self.account_manager = account_manager
        if not self.config.enabled:
            logger.info("ntfy 通知模块未启用")
            return
        if self.sync_task and not self.sync_task.done():
            return

        self.sync_task = asyncio.create_task(self._sync_loop())
        logger.info(
            "ntfy 通知模块已启动 | "
            f"server={self.config.server} | topic={self.config.topic} | "
            f"only_unmuted={self.config.only_unmuted}"
        )

    async def resolve_ntfy_client(self, account_id: int):
        setting = await asyncio.to_thread(self.setting_loader, account_id)
        if setting and setting["has_setting"]:
            if not setting["enabled"]:
                return None, "account_notification_disabled"
            if not setting["account_enabled"]:
                return None, "account_disabled"
            if not setting["configured"]:
                return None, "ntfy_address_not_configured"

            topic = setting["ntfy_url"]
            cache_key = (self.config.server, topic)
            client = self.account_clients.get(cache_key)
            if not client:
                client = NtfyClient.from_topic(
                    self.config.server,
                    topic,
                    self.config.request_timeout,
                )
                self.account_clients[cache_key] = client
            return client, ""

        return None, "ntfy_address_not_configured"

    async def stop(self):
        if self.sync_task:
            self.sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.sync_task
            self.sync_task = None
        self._clear_registrations()

    async def _sync_loop(self):
        while True:
            try:
                self.sync_clients()
            except Exception as exc:
                logger.exception(f"ntfy 账号监听同步失败 | error={exc}")
            await asyncio.sleep(self.config.sync_interval)

    def sync_clients(self):
        clients = dict(getattr(self.account_manager, "clients", {}) or {})

        for account_id, (old_client, handler, builder) in list(self.registrations.items()):
            if clients.get(account_id) is old_client:
                continue
            with suppress(Exception):
                old_client.remove_event_handler(handler, builder)
            self.registrations.pop(account_id, None)

        for account_id, client in clients.items():
            registration = self.registrations.get(account_id)
            if registration and registration[0] is client:
                continue

            builder = events.NewMessage(incoming=True)

            async def handler(event, current_account_id=account_id):
                await self.handle_event(current_account_id, event)

            client.add_event_handler(handler, builder)
            self.registrations[account_id] = (client, handler, builder)
            logger.info(f"ntfy Telegram 消息监听已注册 | account_id={account_id}")

    def _clear_registrations(self):
        for client, handler, builder in self.registrations.values():
            with suppress(Exception):
                client.remove_event_handler(handler, builder)
        self.registrations.clear()
        self.account_titles.clear()
        self.membership_cache.clear()

    async def _notification_title(self, account_id: int, client) -> str:
        cached = self.account_titles.get(account_id)
        if cached:
            return cached

        try:
            me = await client.get_me()
            username = str(getattr(me, "username", "") or "").strip().lstrip("@")
        except Exception as exc:
            logger.warning(
                "ntfy 获取账号用户名失败 | "
                f"account_id={account_id} | error={exc}"
            )
            username = ""

        title = f"@{username}" if username else f"Telegram账号 {account_id}"
        self.account_titles[account_id] = title
        return title

    async def _is_joined_chat(self, account_id: int, event, chat) -> bool:
        if getattr(event, "is_private", False):
            return True

        if not (
            getattr(event, "is_group", False)
            or getattr(event, "is_channel", False)
        ):
            return True

        if getattr(chat, "left", False) or getattr(chat, "deactivated", False):
            return False

        chat_id = getattr(event, "chat_id", None)
        cache_key = (account_id, chat_id)
        cached = self.membership_cache.get(cache_key)
        now = monotonic()
        if cached and cached[0] > now:
            return cached[1]

        joined = await is_chat_member(event.client, chat)
        self.membership_cache[cache_key] = (
            now + self.membership_cache_seconds,
            joined,
        )
        return joined

    async def handle_event(self, account_id: int, event):
        message = event.message
        chat_id = getattr(event, "chat_id", None)
        message_id = getattr(message, "id", None)
        source = (
            "private" if getattr(event, "is_private", False)
            else "group" if getattr(event, "is_group", False)
            else "channel" if getattr(event, "is_channel", False)
            else "unknown"
        )

        try:
            chat = await event.get_chat()
            sender = await event.get_sender()
            chat_title = entity_display_name(chat, fallback=str(chat_id or "-"))
            username = entity_username(sender)
            if username == "-":
                username = entity_username(chat)

            ntfy_client, skip_reason = await self.resolve_ntfy_client(account_id)
            if not ntfy_client:
                logger.info(
                    "ntfy 通知未发送 | "
                    f"reason={skip_reason} | account_id={account_id} | source={source} | "
                    f"chat={chat_title} | chat_id={chat_id} | message_id={message_id}"
                )
                return

            try:
                joined = await self._is_joined_chat(account_id, event, chat)
            except Exception as exc:
                logger.warning(
                    "ntfy 通知未发送 | reason=membership_check_error | "
                    f"account_id={account_id} | source={source} | chat_id={chat_id} | "
                    f"message_id={message_id} | error={exc}"
                )
                return
            if not joined:
                logger.info(
                    "ntfy 通知未发送 | reason=not_participant | "
                    f"account_id={account_id} | source={source} | "
                    f"chat={chat_title} | chat_id={chat_id} | message_id={message_id}"
                )
                return

            if self.config.only_unmuted:
                try:
                    muted = await is_chat_muted(event.client, chat)
                except Exception as exc:
                    logger.warning(
                        "ntfy 通知未发送 | reason=notify_settings_error | "
                        f"account_id={account_id} | source={source} | chat_id={chat_id} | "
                        f"message_id={message_id} | error={exc}"
                    )
                    return
                if muted:
                    logger.info(
                        "ntfy 通知未发送 | reason=mute | "
                        f"account_id={account_id} | source={source} | "
                        f"chat={chat_title} | chat_id={chat_id} | message_id={message_id}"
                    )
                    return

            sent_at = getattr(message, "date", None) or datetime.now(timezone.utc)
            body = format_notification_body(
                chat_title=chat_title,
                username=username,
                text=message_summary(message),
                sent_at=sent_at,
            )
            priority = notification_priority(event)
            title = await self._notification_title(account_id, event.client)
            status = await ntfy_client.publish(
                title=title,
                message=body,
                priority=priority,
            )
            logger.info(
                "ntfy 通知已发送 | "
                f"account_id={account_id} | source={source} | chat={chat_title} | "
                f"chat_id={chat_id} | message_id={message_id} | "
                f"priority={priority} | ntfy_status={status}"
            )
        except Exception as exc:
            ntfy_status = getattr(exc, "status_code", "-")
            logger.exception(
                "ntfy 通知发送失败 | "
                f"account_id={account_id} | source={source} | chat_id={chat_id} | "
                f"message_id={message_id} | ntfy_status={ntfy_status} | error={exc}"
            )


notification_service = NotificationService()


def start_notification_service(account_manager):
    notification_service.start(account_manager)
    return notification_service
