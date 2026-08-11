import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bot import notifier
from db import crud_control_alerts
from db.models import ControlAckAlert


class ControlAlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ControlAckAlert.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session_patch = patch.object(
            crud_control_alerts,
            "SessionLocal",
            self.session_factory,
        )
        self.session_patch.start()

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


if __name__ == "__main__":
    unittest.main()
