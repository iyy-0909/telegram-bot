import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth.tenant import current_tenant_user_id
from bot import support_bot
from db import crud_control_alerts, crud_users
from db.models import ControlAckAlert, UserAccount


class SupportPollingManagerAlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        UserAccount.__table__.create(self.engine)
        ControlAckAlert.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session_patches = [
            patch.object(crud_users, "SessionLocal", self.session_factory),
            patch.object(
                crud_control_alerts,
                "SessionLocal",
                self.session_factory,
            ),
        ]
        for session_patch in self.session_patches:
            session_patch.start()

    def tearDown(self):
        for session_patch in reversed(self.session_patches):
            session_patch.stop()
        self.engine.dispose()

    def add_admin(self, user_id, username, *, status="active"):
        db = self.session_factory()
        try:
            db.add(
                UserAccount(
                    id=user_id,
                    username=username,
                    password_hash="test-hash",
                    role="admin",
                    status=status,
                    plan_tier="paid",
                    feature_keys_json="[]",
                )
            )
            db.commit()
        finally:
            db.close()

    async def test_global_warning_is_owned_by_the_only_active_admin(self):
        self.add_admin(41, "only-admin")

        alert = await support_bot.notify_support_warning(
            "Support Bot polling manager 异常",
            "database unavailable",
            context={"alert_key": "support:global:manager-test"},
        )

        self.assertIsNotNone(alert)
        self.assertIsNone(current_tenant_user_id())
        db = self.session_factory()
        try:
            stored = (
                db.query(ControlAckAlert)
                .filter(ControlAckAlert.alert_key == "support:global:manager-test")
                .one()
            )
            self.assertEqual(stored.owner_user_id, 41)
        finally:
            db.close()

    async def test_global_warning_fails_closed_without_unique_active_admin(self):
        send_alert = AsyncMock()
        warning_log = MagicMock()
        with (
            patch.object(support_bot, "send_ack_required_alert", send_alert),
            patch.object(support_bot.logger, "warning", warning_log),
        ):
            no_admin_result = await support_bot.notify_support_warning(
                "Support Bot polling manager 异常",
                "database unavailable",
            )
            self.add_admin(51, "first-admin")
            self.add_admin(52, "second-admin")
            multiple_admin_result = await support_bot.notify_support_warning(
                "Support Bot polling manager 异常",
                "database unavailable",
            )

        self.assertIsNone(no_admin_result)
        self.assertIsNone(multiple_admin_result)
        send_alert.assert_not_awaited()
        warning_text = " ".join(str(call) for call in warning_log.call_args_list)
        self.assertIn("exactly one active admin", warning_text)
        self.assertNotIn("first-admin", warning_text)
        self.assertNotIn("second-admin", warning_text)

    async def test_alert_failure_does_not_terminate_polling_manager(self):
        manager_secret = "manager-secret-value"
        alert_secret = "alert-secret-value"
        list_configs = MagicMock(
            side_effect=[
                RuntimeError(f"password={manager_secret}"),
                asyncio.CancelledError(),
            ]
        )
        warning_alert = AsyncMock(
            side_effect=RuntimeError(f"token={alert_secret}")
        )
        warning_log = MagicMock()

        with (
            patch.object(support_bot, "list_support_bots", list_configs),
            patch.object(support_bot, "notify_support_warning", warning_alert),
            patch.object(support_bot.asyncio, "sleep", AsyncMock()),
            patch.object(support_bot.logger, "warning", warning_log),
            patch.dict(support_bot._polling_tasks, {}, clear=True),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await support_bot.support_polling_manager()

        self.assertEqual(list_configs.call_count, 2)
        warning_alert.assert_awaited_once()
        warning_text = " ".join(str(call) for call in warning_log.call_args_list)
        self.assertIn("background worker continues", warning_text)
        self.assertNotIn(manager_secret, warning_text)
        self.assertNotIn(alert_secret, warning_text)


if __name__ == "__main__":
    unittest.main()
