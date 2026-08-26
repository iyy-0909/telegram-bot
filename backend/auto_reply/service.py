import asyncio
from contextlib import suppress
from datetime import datetime, timedelta

from telethon import events

from bot.logger import logger
from db.database import SessionLocal
from db.models import Account, AccountAutoReplyState


def parse_minutes(value, fallback):
    try:
        hour, minute = str(value or "").split(":", 1)
        hour = int(hour)
        minute = int(minute)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
    except (TypeError, ValueError):
        pass
    return fallback


def is_outside_business_hours(account, now=None):
    now = now or datetime.now()
    start = parse_minutes(account.business_start_time, 9 * 60)
    end = parse_minutes(account.business_end_time, 18 * 60)
    current = now.hour * 60 + now.minute

    if start == end:
        return False
    if start < end:
        return not (start <= current < end)
    return not (current >= start or current < end)


class AccountAutoReplyService:
    def __init__(self, sync_interval=5):
        self.sync_interval = sync_interval
        self.account_manager = None
        self.registrations = {}
        self.sync_task = None
        self.peer_locks = {}

    def start(self, account_manager):
        self.account_manager = account_manager
        if self.sync_task and not self.sync_task.done():
            return
        self.sync_task = asyncio.create_task(self._sync_loop())
        logger.info("账号自动回复模块已启动")

    async def _sync_loop(self):
        while True:
            try:
                self.sync_clients()
            except Exception:
                logger.exception("账号自动回复监听同步失败")
            await asyncio.sleep(self.sync_interval)

    def sync_clients(self):
        clients = dict(getattr(self.account_manager, "clients", {}) or {})

        for account_id, (old_client, handler, builder) in list(self.registrations.items()):
            if clients.get(account_id) is old_client:
                continue
            with suppress(Exception):
                old_client.remove_event_handler(handler, builder)
            self.registrations.pop(account_id, None)

        for account_id, client in clients.items():
            current = self.registrations.get(account_id)
            if current and current[0] is client:
                continue

            builder = events.NewMessage(incoming=True)

            async def handler(event, current_account_id=account_id):
                await self.handle_event(current_account_id, event)

            client.add_event_handler(handler, builder)
            self.registrations[account_id] = (client, handler, builder)

    async def handle_event(self, account_id, event):
        if not getattr(event, "is_private", False):
            return

        try:
            sender = await event.get_sender()
        except Exception:
            logger.exception("自动回复读取发送人失败 | account_id=%s", account_id)
            return

        if not sender or getattr(sender, "bot", False) or getattr(sender, "is_self", False):
            return

        telegram_user_id = str(getattr(sender, "id", "") or "")
        if not telegram_user_id:
            return

        lock_key = (account_id, telegram_user_id)
        lock = self.peer_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            try:
                await self._reply(account_id, telegram_user_id, event)
            except Exception:
                logger.exception(
                    "账号自动回复处理失败 | account_id=%s | telegram_user_id=%s",
                    account_id,
                    telegram_user_id,
                )

    async def _reply(self, account_id, telegram_user_id, event):
        db = SessionLocal()
        try:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account or not account.enabled:
                return

            greeting_text = (account.greeting_message or "").strip()
            away_text = (account.away_message or "").strip()
            if not (
                (account.greeting_enabled and greeting_text)
                or (account.away_enabled and away_text)
            ):
                return

            state = (
                db.query(AccountAutoReplyState)
                .filter(
                    AccountAutoReplyState.account_id == account_id,
                    AccountAutoReplyState.telegram_user_id == telegram_user_id,
                )
                .first()
            )
            if not state:
                state = AccountAutoReplyState(
                    account_id=account_id,
                    telegram_user_id=telegram_user_id,
                )
                db.add(state)

            now = datetime.now()
            if account.greeting_enabled and greeting_text and not state.greeting_sent_at:
                await event.respond(greeting_text)
                state.greeting_sent_at = now
                db.commit()
                logger.info(
                    "已发送账号问候消息 | account_id=%s | telegram_user_id=%s",
                    account_id,
                    telegram_user_id,
                )

            repeat_hours = max(1, int(account.away_repeat_hours or 12))
            away_due = (
                not state.away_sent_at
                or now - state.away_sent_at >= timedelta(hours=repeat_hours)
            )
            if (
                account.away_enabled
                and away_text
                and is_outside_business_hours(account, now)
                and away_due
            ):
                await event.respond(away_text)
                state.away_sent_at = now
                db.commit()
                logger.info(
                    "已发送账号离线消息 | account_id=%s | telegram_user_id=%s",
                    account_id,
                    telegram_user_id,
                )

            state.last_incoming_at = now
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


account_auto_reply_service = AccountAutoReplyService()


def start_account_auto_reply_service(account_manager):
    account_auto_reply_service.start(account_manager)
    return account_auto_reply_service
