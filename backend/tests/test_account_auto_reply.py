import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auto_reply.service import AccountAutoReplyService, is_outside_business_hours
from db.database import Base
from db.models import Account, AccountAutoReplyState


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
        db.add(Account(
            id=1,
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
        self.assertEqual(event.respond.await_args_list[1].args[0], "暂时离线")

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
