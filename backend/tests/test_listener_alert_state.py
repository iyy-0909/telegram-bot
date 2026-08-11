import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import listener_events


def make_event():
    return {
        "task_id": 46,
        "task_name": "西安频道 实时监听",
        "event_type": "filtered",
        "status": "filtered",
        "source_channel": "@source",
        "target": "@target",
        "source_message_id": 100,
        "message": "监听消息被过滤",
    }


class ListenerAlertStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_stopped_listener_does_not_create_event_alert(self):
        task = SimpleNamespace(id=46, enabled=False, status="stopped")
        with (
            patch.object(listener_events, "get_listener_task", return_value=task),
            patch.object(listener_events, "send_control_alert", new=AsyncMock()) as send_alert,
        ):
            result = await listener_events.notify_listener_event(make_event())

        self.assertFalse(result)
        send_alert.assert_not_awaited()

    async def test_non_running_status_does_not_create_event_alert(self):
        task = SimpleNamespace(id=46, enabled=True, status="waiting_clone")
        with (
            patch.object(listener_events, "get_listener_task", return_value=task),
            patch.object(listener_events, "send_control_alert", new=AsyncMock()) as send_alert,
        ):
            result = await listener_events.notify_listener_event(make_event())

        self.assertFalse(result)
        send_alert.assert_not_awaited()

    async def test_running_listener_still_creates_event_alert(self):
        task = SimpleNamespace(id=46, enabled=True, status="running")
        with (
            patch.object(listener_events, "get_listener_task", return_value=task),
            patch.object(
                listener_events,
                "send_control_alert",
                new=AsyncMock(return_value={"id": 1}),
            ) as send_alert,
        ):
            result = await listener_events.notify_listener_event(make_event())

        self.assertEqual(result, {"id": 1})
        send_alert.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
