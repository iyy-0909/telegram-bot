import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError
from api import server


class CatchupIntervalApiTests(unittest.IsolatedAsyncioTestCase):
    def test_interval_validation_and_default(self):
        self.assertEqual(server.ListenerCatchupRequest().interval_seconds, 60)
        for value in (0, -1, 86401, 1.5, None, True, "30"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                server.ListenerCatchupRequest(interval_seconds=value)
        for value in (1, 30, 300, 86400):
            self.assertEqual(server.ListenerCatchupRequest(interval_seconds=value).interval_seconds, value)

    async def test_interval_reaches_sync_and_background_workers(self):
        task = SimpleNamespace(id=44, name="test", source_channel="@source", target_channels='["@target"]')
        request = Mock()
        for background in (False, True):
            with (
                self.subTest(background=background),
                patch.object(server, "get_listener_task", return_value=task),
                patch.object(server, "require_task_owner") as ownership,
                patch.object(server, "is_listener_catchup_running", return_value=False),
                patch.object(server.runtime_queue_state, "add_waiting", return_value="test-queue") as queue,
                patch.object(server, "start_listener_catchup_background", return_value=Mock()) as start,
                patch.object(server, "catchup_latest_listener_message", AsyncMock(return_value={"ok": True})) as run,
            ):
                result = await server.api_listener_catchup_latest(
                    task.id, request,
                    server.ListenerCatchupRequest(background=background, limit=3, interval_seconds=300),
                )
                self.assertTrue(result["ok"])
                ownership.assert_called_once_with(task, request)
                worker = start if background else run
                self.assertEqual(worker.call_args.kwargs["interval_seconds"], 300)
                if background:
                    self.assertEqual(queue.call_args.args[0]["interval_seconds"], 300)


if __name__ == "__main__":
    unittest.main()
