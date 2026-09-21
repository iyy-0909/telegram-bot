import unittest
from unittest.mock import AsyncMock, patch

from bot.runtime_queue import RuntimeQueueState
from bot.send_queue import SendQueue


class QrSendQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_cancels_queue_without_failure_retry_or_send_timestamp(self):
        queue = SendQueue()
        state = RuntimeQueueState()
        filtered = {"filtered": True, "message": "二维码过滤：只有二维码，已过滤整条消息"}
        sender = AsyncMock(return_value=filtered)
        with patch("bot.send_queue.runtime_queue_state", state), patch(
            "bot.send_queue.get_send_settings",
            return_value={"global_send_delay": 0, "send_retry_count": 2, "send_retry_delay": 0},
        ):
            result = await queue.send(sender, task_id=9, target="@test")
        self.assertEqual(result, filtered)
        sender.assert_awaited_once()
        self.assertEqual(queue.last_sent_at, 0)
        snapshot = state.snapshot()
        self.assertEqual(snapshot["recent"][0]["status"], "cancelled")
        self.assertEqual(snapshot["recent"][0]["reason"], filtered["message"])
        self.assertEqual(snapshot["stats"]["failed_count"], 0)
        self.assertIsNone(snapshot["current"])

    async def test_ordinary_send_failure_and_success_keep_existing_statuses(self):
        for value, expected in ((False, "failed"), ({"target_message_ids": [77]}, "success")):
            with self.subTest(expected=expected):
                queue = SendQueue()
                state = RuntimeQueueState()
                with patch("bot.send_queue.runtime_queue_state", state), patch(
                    "bot.send_queue.get_send_settings",
                    return_value={"global_send_delay": 0, "send_retry_count": 0, "send_retry_delay": 0},
                ):
                    await queue.send(AsyncMock(return_value=value), task_id=9, target="@test")
                self.assertEqual(state.snapshot()["recent"][0]["status"], expected)
                self.assertGreater(queue.last_sent_at, 0)


if __name__ == "__main__":
    unittest.main()
