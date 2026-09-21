import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bot import notifier
from auth.tenant import tenant_scope
from db import crud_control_alerts
from db.models import CloneTask, ControlAckAlert, ListenerTask


class ControlAlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ListenerTask.__table__.create(self.engine)
        CloneTask.__table__.create(self.engine)
        ControlAckAlert.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session_patch = patch.object(
            crud_control_alerts,
            "SessionLocal",
            self.session_factory,
        )
        self.session_patch.start()
        db = self.session_factory()
        try:
            db.add_all([
                ListenerTask(
                    id=39,
                    owner_user_id=202,
                    name="listener collision",
                    source_channel="@listener",
                    target_channels='["@target"]',
                ),
                CloneTask(
                    id=39,
                    owner_user_id=101,
                    name="clone collision",
                    source_channel="@clone",
                    target_channels='["@target"]',
                ),
            ])
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    async def test_control_alert_is_stored_without_telegram_send(self):
        with patch.object(notifier, "notify_text") as telegram_notify:
            alert = await notifier.send_control_alert(
                "监听任务疑似漏发",
                "没有找到成功发送记录",
                level="error",
                context={
                    "alert_key": "listener:39:missing",
                    "module": "listener_health",
                    "task_id": 39,
                    "channel": "@source",
                    "target": "@target",
                },
            )

        telegram_notify.assert_not_called()
        self.assertEqual(alert["level"], "error")
        self.assertEqual(alert["task_id"], 39)
        self.assertEqual(alert["status"], "pending")

    async def test_repeated_alert_updates_occurrence_and_can_be_acknowledged(self):
        with tenant_scope(303, is_admin=False):
            for _ in range(2):
                await notifier.send_control_alert(
                    "客服连接失败",
                    "Gateway Timeout",
                    level="warning",
                    context={
                        "alert_key": "support:8:timeout",
                        "module": "客服机器人",
                        "support_bot_id": 8,
                    },
                )

            result = crud_control_alerts.list_control_alerts(
                status="pending",
                q="Gateway",
            )
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["items"][0]["repeat_count"], 2)

            count = crud_control_alerts.acknowledge_all_control_alerts("tester")
            self.assertEqual(count, 1)
            stats = crud_control_alerts.get_control_alert_stats()
            self.assertEqual(stats["pending"], 0)
            self.assertEqual(stats["acknowledged"], 1)

    async def test_alert_storage_and_search_do_not_expose_secret_errors(self):
        raw_error = "proxy=http://alice:secret@example.test:8080"
        with tenant_scope(404, is_admin=False):
            crud_control_alerts.upsert_ack_alert(
                "secure:new",
                "network error",
                raw_error,
                context={"error": raw_error},
            )

        db = self.session_factory()
        try:
            stored = db.query(ControlAckAlert).filter(
                ControlAckAlert.alert_key == "secure:new"
            ).one()
            self.assertNotIn("alice", stored.detail)
            self.assertNotIn("secret", stored.context_json)

            historical = ControlAckAlert(
                owner_user_id=404,
                alert_key="secure:historical",
                title="historical network error",
                detail=raw_error,
                context_json='{"error":"proxy=http://alice:secret@example.test:8080"}',
                status="pending",
            )
            db.add(historical)
            db.commit()
        finally:
            db.close()

        with tenant_scope(404, is_admin=False):
            result = crud_control_alerts.list_control_alerts(q="secret")
            self.assertEqual(result["total"], 0)
            all_alerts = crud_control_alerts.list_control_alerts()
        serialized = str(all_alerts)
        self.assertNotIn("alice", serialized)
        self.assertNotIn("secret", serialized)

    async def test_task_type_prevents_clone_listener_id_collision(self):
        clone_alert = await notifier.send_control_alert(
            "clone failed",
            "detail",
            context={
                "alert_key": "clone:39:failed",
                "module": "clone",
                "task_type": "clone",
                "task_id": 39,
                "clone_task_id": 39,
            },
        )
        listener_alert = await notifier.send_control_alert(
            "listener failed",
            "detail",
            context={
                "alert_key": "listener:39:failed",
                "module": "listener",
                "task_type": "listener",
                "task_id": 39,
                "listener_task_id": 39,
            },
        )

        self.assertEqual(clone_alert["id"] > 0, True)
        self.assertEqual(listener_alert["id"] > 0, True)
        db = self.session_factory()
        try:
            owners = {
                row.alert_key: row.owner_user_id
                for row in db.query(ControlAckAlert).filter(
                    ControlAckAlert.alert_key.in_([
                        "clone:39:failed",
                        "listener:39:failed",
                    ])
                )
            }
        finally:
            db.close()
        self.assertEqual(owners["clone:39:failed"], 101)
        self.assertEqual(owners["listener:39:failed"], 202)


if __name__ == "__main__":
    unittest.main()
