import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import listener_health


def make_task(*, enabled=True, status="running"):
    return SimpleNamespace(
        id=39,
        enabled=enabled,
        status=status,
        source_channel="@source",
    )


class ListenerHealthStateTests(unittest.IsolatedAsyncioTestCase):
    def test_only_enabled_running_tasks_are_monitored(self):
        self.assertTrue(listener_health.is_running_listener_task(make_task()))
        self.assertFalse(
            listener_health.is_running_listener_task(
                make_task(enabled=False, status="running")
            )
        )
        self.assertFalse(
            listener_health.is_running_listener_task(
                make_task(enabled=True, status="stopped")
            )
        )
        self.assertFalse(listener_health.is_running_listener_task(None))

    async def test_stopped_task_is_rechecked_before_sending_alert(self):
        task = make_task()
        with (
            patch.object(
                listener_health,
                "get_listener_task",
                return_value=make_task(enabled=False, status="stopped"),
            ),
            patch.object(
                listener_health,
                "send_control_alert",
                new=AsyncMock(return_value=True),
            ) as send_alert,
        ):
            sent = await listener_health.send_task_alert(
                task=task,
                title="监听任务疑似漏发",
                level="error",
                message="test",
                alert_key="listener-health:test:stopped",
            )

        self.assertFalse(sent)
        send_alert.assert_not_awaited()

    async def test_running_task_can_send_alert(self):
        task = make_task()
        with (
            patch.object(
                listener_health,
                "get_listener_task",
                return_value=task,
            ),
            patch.object(
                listener_health,
                "should_alert",
                return_value=True,
            ),
            patch.object(
                listener_health,
                "send_control_alert",
                new=AsyncMock(return_value=True),
            ) as send_alert,
        ):
            sent = await listener_health.send_task_alert(
                task=task,
                title="监听任务疑似漏发",
                level="error",
                message="test",
                alert_key="listener-health:test:running",
            )

        self.assertTrue(sent)
        send_alert.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
