import unittest

from bot.runtime_queue import RuntimeQueueState


class RuntimeQueueStateTest(unittest.TestCase):
    def test_waiting_item_becomes_current_and_recent_success(self):
        state = RuntimeQueueState(max_recent=5)

        item_id = state.add_waiting({
            "source_type": "clone",
            "task_id": 16,
            "task_name": "奶昔频道历史克隆",
            "source_channel": "@csmmc6",
            "target_channel": "@CCSWKTV",
            "source_message_id": 1125,
            "message_type": "text",
        })

        waiting_snapshot = state.snapshot()
        self.assertEqual(waiting_snapshot["stats"]["waiting_count"], 1)
        self.assertEqual(waiting_snapshot["waiting"][0]["status"], "waiting")

        state.mark_current(item_id, reason="全局发送间隔")
        current_snapshot = state.snapshot()
        self.assertEqual(current_snapshot["current"]["id"], item_id)
        self.assertEqual(current_snapshot["current"]["status"], "rate_limited")
        self.assertEqual(current_snapshot["current"]["reason"], "全局发送间隔")
        self.assertEqual(current_snapshot["stats"]["waiting_count"], 0)

        state.mark_sending(item_id)
        sending_snapshot = state.snapshot()
        self.assertEqual(sending_snapshot["current"]["status"], "sending")

        state.finish(item_id, success=True)
        final_snapshot = state.snapshot()
        self.assertIsNone(final_snapshot["current"])
        self.assertEqual(final_snapshot["stats"]["recent_count"], 1)
        self.assertEqual(final_snapshot["recent"][0]["status"], "success")

    def test_current_item_can_be_cancelled_as_stale_safety_net(self):
        state = RuntimeQueueState(max_recent=5)
        item_id = state.add_waiting({
            "source_type": "clone",
            "task_id": 60,
            "target_channel": "@target",
        })

        state.mark_current(item_id, reason="全局发送间隔")
        state.mark_sending(item_id)
        state.cancel(item_id, "发送任务已退出，运行态兜底清理")

        snapshot = state.snapshot()
        self.assertIsNone(snapshot["current"])
        self.assertEqual(snapshot["recent"][0]["status"], "cancelled")
        self.assertEqual(snapshot["recent"][0]["reason"], "发送任务已退出，运行态兜底清理")

    def test_waiting_item_can_show_estimated_send_time_and_be_removed(self):
        state = RuntimeQueueState(max_recent=5)
        item_id = state.add_waiting({
            "source_type": "clone",
            "task_id": 61,
            "task_name": "上海源频道历史克隆",
            "source_channel": "@source_sh",
            "target_channel": "@target_sh",
            "source_message_id": 1200,
            "message_type": "single",
            "reason": "克隆任务限流等待中",
            "estimated_send_remaining_seconds": 30,
        })

        snapshot = state.snapshot()
        waiting_item = snapshot["waiting"][0]
        self.assertEqual(waiting_item["id"], item_id)
        self.assertEqual(waiting_item["reason"], "克隆任务限流等待中")
        self.assertTrue(waiting_item["estimated_send_at"])
        self.assertLessEqual(
            waiting_item["estimated_send_remaining_seconds"],
            30,
        )
        self.assertGreaterEqual(
            waiting_item["estimated_send_remaining_seconds"],
            0,
        )

        removed = state.remove_waiting(item_id)
        self.assertEqual(removed["id"], item_id)

        final_snapshot = state.snapshot()
        self.assertEqual(final_snapshot["stats"]["waiting_count"], 0)
        self.assertEqual(final_snapshot["stats"]["recent_count"], 0)

    def test_waiting_items_are_sorted_by_estimated_send_time(self):
        state = RuntimeQueueState(max_recent=5)
        later_id = state.add_waiting({
            "task_id": 1,
            "reason": "等待全局发送队列",
            "estimated_send_remaining_seconds": 60,
        })
        earlier_id = state.add_waiting({
            "task_id": 2,
            "reason": "克隆任务限流等待中",
            "estimated_send_remaining_seconds": 10,
        })
        no_estimate_id = state.add_waiting({
            "task_id": 3,
            "reason": "等待全局发送队列",
        })

        snapshot = state.snapshot()
        waiting_ids = [item["id"] for item in snapshot["waiting"]]

        self.assertEqual(waiting_ids, [earlier_id, later_id, no_estimate_id])


if __name__ == "__main__":
    unittest.main()
