import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telethon import types, utils

from auto_reply.service import AccountAutoReplyService, is_outside_business_hours
from db.database import Base
from db.models import Account, AccountAutoReplyState, UserAccount


class AccountAutoReplyTimeTests(unittest.TestCase):
    def test_daytime_business_hours(self):
        account = SimpleNamespace(business_start_time="09:00", business_end_time="18:00")
        self.assertFalse(is_outside_business_hours(account, datetime(2026, 1, 1, 10, 0)))
        self.assertTrue(is_outside_business_hours(account, datetime(2026, 1, 1, 20, 0)))

    def test_overnight_business_hours(self):
        account = SimpleNamespace(business_start_time="20:00", business_end_time="06:00")
        self.assertFalse(is_outside_business_hours(account, datetime(2026, 1, 1, 23, 0)))
        self.assertFalse(is_outside_business_hours(account, datetime(2026, 1, 1, 2, 0)))
        self.assertTrue(is_outside_business_hours(account, datetime(2026, 1, 1, 12, 0)))


class AccountAutoReplyServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add(UserAccount(
            id=7,
            username="auto-reply-owner",
            password_hash="test-hash",
            role="user",
            status="active",
            plan_tier="free",
            feature_keys_json="[]",
            advertisement_text="ad",
            advertisement_send_time="12:00",
        ))
        db.add(Account(
            id=1,
            owner_user_id=7,
            name="测试账号",
            session_path="test",
            enabled=True,
            greeting_enabled=True,
            greeting_message="欢迎",
            away_enabled=True,
            away_message="暂时离线",
            business_start_time="23:00",
            business_end_time="23:30",
            away_repeat_hours=12,
        ))
        db.commit()
        db.close()
        self.service = AccountAutoReplyService()

    def tearDown(self):
        self.engine.dispose()

    async def test_greeting_once_and_away_rate_limit(self):
        event = SimpleNamespace(respond=AsyncMock())
        with patch("auto_reply.service.SessionLocal", self.Session), patch(
            "auto_reply.service.is_outside_business_hours", return_value=True
        ):
            await self.service._reply(1, "10001", event)
            await self.service._reply(1, "10001", event)

        self.assertEqual(event.respond.await_count, 2)
        self.assertEqual(event.respond.await_args_list[0].args[0], "欢迎")
        self.assertEqual(event.respond.await_args_list[0].kwargs, {"parse_mode": "html"})
        self.assertEqual(event.respond.await_args_list[1].args[0], "暂时离线")

    async def test_greeting_html_preserves_formatting_links_and_line_breaks(self):
        greeting = (
            '<b>您好 👋</b>\n<i>欢迎</i> <u>咨询</u> <s>旧价格</s> <code>编号01</code>\n'
            '<a href="https://t.me/example?start=a&amp;b=c">联系客服</a> &amp; &lt;说明&gt;'
        )
        with self.Session() as db:
            account = db.query(Account).filter(Account.id == 1).one()
            account.greeting_message = greeting
            account.away_enabled = False
            db.commit()
        event = SimpleNamespace(respond=AsyncMock())
        with patch("auto_reply.service.SessionLocal", self.Session):
            await self.service._reply(1, "10004", event)
            await self.service._reply(1, "10004", event)

        event.respond.assert_awaited_once_with(greeting, parse_mode="html")
        call = event.respond.await_args
        text, entities = utils.sanitize_parse_mode(call.kwargs["parse_mode"]).parse(call.args[0])
        self.assertEqual(text, "您好 👋\n欢迎 咨询 旧价格 编号01\n联系客服 & <说明>")
        self.assertEqual([type(entity) for entity in entities], [
            types.MessageEntityBold, types.MessageEntityItalic,
            types.MessageEntityUnderline, types.MessageEntityStrike,
            types.MessageEntityCode, types.MessageEntityTextUrl,
        ])
        self.assertEqual(entities[0].length, 5)  # Telegram counts emoji as UTF-16 pairs.
        self.assertEqual(entities[-1].url, "https://t.me/example?start=a&b=c")

    async def test_greeting_plain_text_is_not_parsed_as_markdown(self):
        greeting = "您好，价格 1 < 2，A & B，编号 user_name，**原样显示**"
        with self.Session() as db:
            account = db.query(Account).filter(Account.id == 1).one()
            account.greeting_message = greeting
            account.away_enabled = False
            db.commit()
        event = SimpleNamespace(respond=AsyncMock())
        with patch("auto_reply.service.SessionLocal", self.Session):
            await self.service._reply(1, "10005", event)
        call = event.respond.await_args
        text, entities = utils.sanitize_parse_mode(call.kwargs["parse_mode"]).parse(call.args[0])
        self.assertEqual(text, greeting)
        self.assertEqual(entities, [])

    async def test_failed_greeting_can_be_retried_on_next_message(self):
        event = SimpleNamespace(respond=AsyncMock(side_effect=RuntimeError("send failed")))
        with patch("auto_reply.service.SessionLocal", self.Session), patch(
            "auto_reply.service.is_outside_business_hours", return_value=False
        ):
            with self.assertRaises(RuntimeError):
                await self.service._reply(1, "10006", event)
            with self.Session() as db:
                state = db.query(AccountAutoReplyState).filter(
                    AccountAutoReplyState.telegram_user_id == "10006"
                ).first()
                self.assertTrue(state is None or state.greeting_sent_at is None)
            event.respond.side_effect = None
            await self.service._reply(1, "10006", event)
            await self.service._reply(1, "10006", event)
        self.assertEqual(event.respond.await_count, 2)

    async def test_away_replies_again_after_interval(self):
        db = self.Session()
        db.add(AccountAutoReplyState(
            account_id=1,
            telegram_user_id="10002",
            greeting_sent_at=datetime.now(),
            away_sent_at=datetime.now() - timedelta(hours=13),
        ))
        db.commit()
        db.close()
        event = SimpleNamespace(respond=AsyncMock())

        with patch("auto_reply.service.SessionLocal", self.Session), patch(
            "auto_reply.service.is_outside_business_hours", return_value=True
        ):
            await self.service._reply(1, "10002", event)

        event.respond.assert_awaited_once_with("暂时离线")

    async def test_expired_owner_does_not_receive_auto_reply(self):
        db = self.Session()
        user = db.query(UserAccount).filter(UserAccount.id == 7).one()
        user.access_expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        db.close()
        event = SimpleNamespace(respond=AsyncMock())

        with patch("auto_reply.service.SessionLocal", self.Session):
            await self.service._reply(1, "10003", event)

        event.respond.assert_not_awaited()
