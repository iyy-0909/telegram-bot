import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import server
from auth.access import (
    PLAN_FEATURES,
    apply_plan_task_constraints,
    plan_feature_keys,
)
from bot import free_plan_ads
from db import crud_advertisements, crud_users
from db.models import (
    BotAccount,
    CloneTask,
    DailyAdvertisementDelivery,
    ListenerTask,
    TargetBotBinding,
    UserAccount,
)


class PlanEditionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "plans.db"
        self.engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        for table in (
            UserAccount.__table__,
            BotAccount.__table__,
            TargetBotBinding.__table__,
            ListenerTask.__table__,
            CloneTask.__table__,
            DailyAdvertisementDelivery.__table__,
        ):
            table.create(bind=self.engine)
        self.patches = [
            patch.object(crud_users, "SessionLocal", self.session_local),
            patch.object(crud_advertisements, "SessionLocal", self.session_local),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def add_user(self, username, plan_tier="free", role="user"):
        db = self.session_local()
        try:
            user = UserAccount(
                username=username,
                password_hash="test-hash",
                role=role,
                status="active",
                plan_tier=plan_tier,
                feature_keys_json="[]",
                advertisement_text=f"{username} 的广告",
                advertisement_send_time="09:00",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        finally:
            db.close()

    def test_fixed_plan_features_match_product_rules(self):
        self.assertEqual(
            plan_feature_keys("free"),
            ["dashboard", "listener_tasks", "clone_tasks", "bots", "accounts"],
        )
        self.assertNotIn("bulk_replace", PLAN_FEATURES["paid"])
        self.assertNotIn("support", PLAN_FEATURES["paid"])
        self.assertNotIn("notifications", PLAN_FEATURES["paid"])
        self.assertNotIn("alerts", PLAN_FEATURES["paid"])
        self.assertIn("ai_settings", PLAN_FEATURES["paid"])
        self.assertIn("system_settings", PLAN_FEATURES["paid"])

    def test_free_task_payload_is_forced_to_original_content(self):
        constrained = apply_plan_task_constraints(
            {
                "blocked_keywords": '["推广"]',
                "replace_words": '{"旧":"新"}',
                "footer": "尾注",
                "remove_contact_lines": True,
                "filter_qr_code": True,
                "ai_rewrite_enabled": True,
                "use_random_head": True,
            },
            "free",
        )
        self.assertEqual(constrained["blocked_keywords"], "[]")
        self.assertEqual(constrained["replace_words"], "{}")
        self.assertEqual(constrained["footer"], "")
        self.assertFalse(constrained["remove_contact_lines"])
        self.assertFalse(constrained["filter_qr_code"])
        self.assertFalse(constrained["ai_rewrite_enabled"])
        self.assertFalse(constrained["use_random_head"])

    def test_downgrade_sanitizes_owned_tasks_only(self):
        free_user_id = self.add_user("downgrade", plan_tier="paid")
        other_user_id = self.add_user("other", plan_tier="paid")
        db = self.session_local()
        try:
            db.add_all([
                ListenerTask(
                    owner_user_id=free_user_id,
                    name="listener",
                    source_channel="@source",
                    target_channels='["@target"]',
                    blocked_keywords='["block"]',
                    replace_words='{"a":"b"}',
                    footer="footer",
                    remove_contact_lines=True,
                    filter_qr_code=True,
                    ai_rewrite_enabled=True,
                ),
                CloneTask(
                    owner_user_id=free_user_id,
                    name="clone",
                    source_channel="@source",
                    target_channels='["@target"]',
                    account_id=1,
                    blocked_keywords='["block"]',
                    replace_words='{"a":"b"}',
                    footer="footer",
                    remove_contact_lines=True,
                    filter_qr_code=True,
                    ai_rewrite_enabled=True,
                ),
                ListenerTask(
                    owner_user_id=other_user_id,
                    name="other",
                    source_channel="@source",
                    target_channels='["@target"]',
                    blocked_keywords='["keep"]',
                ),
            ])
            db.commit()
        finally:
            db.close()

        updated = crud_users.update_user_access(free_user_id, plan_tier="free")
        self.assertEqual(updated["plan_tier"], "free")
        db = self.session_local()
        try:
            listener = db.query(ListenerTask).filter(ListenerTask.owner_user_id == free_user_id).one()
            clone = db.query(CloneTask).filter(CloneTask.owner_user_id == free_user_id).one()
            other = db.query(ListenerTask).filter(ListenerTask.owner_user_id == other_user_id).one()
            for task in (listener, clone):
                self.assertEqual(task.blocked_keywords, "[]")
                self.assertEqual(task.replace_words, "{}")
                self.assertEqual(task.footer, "")
                self.assertFalse(task.remove_contact_lines)
                self.assertFalse(task.filter_qr_code)
                self.assertFalse(task.ai_rewrite_enabled)
            self.assertEqual(other.blocked_keywords, '["keep"]')
        finally:
            db.close()

    def test_daily_ads_include_only_due_free_users_and_deduplicate_targets(self):
        free_user_id = self.add_user("free")
        paid_user_id = self.add_user("paid", plan_tier="paid")
        db = self.session_local()
        try:
            free_bot = BotAccount(
                owner_user_id=free_user_id,
                name="free-sender",
                token="123456:FREE",
                enabled=True,
            )
            paid_bot = BotAccount(
                owner_user_id=paid_user_id,
                name="paid-sender",
                token="123456:PAID",
                enabled=True,
            )
            db.add_all([free_bot, paid_bot])
            db.flush()
            db.add_all([
                ListenerTask(owner_user_id=free_user_id, name="listener", source_channel="@source", target_channels='["@target"]', bot_id=free_bot.id, enabled=True),
                CloneTask(owner_user_id=free_user_id, name="clone", source_channel="@source", target_channels='["@target"]', account_id=1, bot_id=free_bot.id, enabled=True),
                ListenerTask(owner_user_id=paid_user_id, name="paid", source_channel="@source", target_channels='["@paid"]', bot_id=paid_bot.id, enabled=True),
            ])
            db.commit()
        finally:
            db.close()

        now = datetime(2026, 8, 27, 12, 0)
        due = crud_advertisements.list_due_advertisement_targets(now=now)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["user_id"], free_user_id)
        self.assertEqual(due[0]["target_channel"], "@target")

        delivery_id = crud_advertisements.reserve_advertisement_delivery(due[0])
        self.assertTrue(delivery_id)
        crud_advertisements.finish_advertisement_delivery(delivery_id, sent=True)
        self.assertEqual(crud_advertisements.list_due_advertisement_targets(now=now), [])

    def test_daily_ads_resolve_null_bot_only_inside_task_owner(self):
        free_user_id = self.add_user("free-null-bot")
        other_user_id = self.add_user("other-null-bot", plan_tier="paid")
        db = self.session_local()
        try:
            other_bot = BotAccount(
                owner_user_id=other_user_id,
                name="other-first",
                token="123456:OTHER",
                enabled=True,
            )
            owned_bot = BotAccount(
                owner_user_id=free_user_id,
                name="owned",
                token="123456:OWNED",
                enabled=True,
            )
            db.add_all([other_bot, owned_bot])
            db.flush()
            db.add_all([
                TargetBotBinding(
                    owner_user_id=free_user_id,
                    target_channel="@bound",
                    bot_id=owned_bot.id,
                    enabled=True,
                ),
                ListenerTask(
                    owner_user_id=free_user_id,
                    name="null-bot-listener",
                    source_channel="@source",
                    target_channels='["@bound", "@fallback"]',
                    bot_id=None,
                    enabled=True,
                ),
            ])
            db.commit()
            owned_bot_id = int(owned_bot.id)
        finally:
            db.close()

        due = crud_advertisements.list_due_advertisement_targets(
            now=datetime(2026, 8, 27, 12, 0)
        )
        self.assertEqual(
            {(item["target_channel"], item["bot_id"], item["bot_token"]) for item in due},
            {
                ("@bound", owned_bot_id, "123456:OWNED"),
                ("@fallback", owned_bot_id, "123456:OWNED"),
            },
        )

    def test_dispatch_records_success_once(self):
        item = {
            "user_id": 1,
            "delivery_date": "2026-08-27",
            "bot_id": 2,
            "bot_token": "123456:TEST",
            "target_channel": "@target",
            "advertisement_text": "广告",
        }
        with (
            patch.object(free_plan_ads, "list_due_advertisement_targets", return_value=[item]),
            patch.object(free_plan_ads, "reserve_advertisement_delivery", return_value=9),
            patch.object(free_plan_ads, "finish_advertisement_delivery") as finish,
            patch.object(free_plan_ads, "bot_send_text", new=AsyncMock(return_value={"ok": True})) as send,
        ):
            result = asyncio.run(free_plan_ads.dispatch_due_free_plan_advertisements())
        self.assertEqual(result, {"sent": 1, "failed": 0})
        send.assert_awaited_once_with("123456:TEST", "@target", "广告")
        finish.assert_called_once_with(9, sent=True)

    def test_free_plan_content_apis_are_blocked(self):
        request = SimpleNamespace(
            state=SimpleNamespace(
                current_user={
                    "id": 10,
                    "role": "user",
                    "status": "active",
                    "plan_tier": "free",
                    "feature_keys": list(PLAN_FEATURES["free"]),
                    "access_state": "active",
                }
            )
        )
        self.assertEqual(server.request_user_plan(request), "free")
        self.assertTrue(server.is_content_processing_api("/api/settings/ai"))
        self.assertTrue(server.is_content_processing_api("/api/content-template-rules/1"))


if __name__ == "__main__":
    unittest.main()
