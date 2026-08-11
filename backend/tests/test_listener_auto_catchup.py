import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import listener_auto_catchup
from bot.listener_auto_catchup import catchup_latest_listener_message


def content_item(message_id):
    message = SimpleNamespace(id=message_id, message=f"消息 {message_id}")
    return {
        "source_message_id": message_id,
        "grouped_id": None,
        "targets": ["@target"],
        "_messages": [message],
        "_grouped_id": None,
    }


class ListenerAutoCatchupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        workers = list(listener_auto_catchup._active_catchup_tasks.values())
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        listener_auto_catchup._active_catchup_tasks.clear()

    async def test_background_worker_is_retained_and_duplicate_start_is_rejected(self):
        task = SimpleNamespace(id=46)
        release = asyncio.Event()

        async def wait_for_release(*_args, **_kwargs):
            await release.wait()
            return {"ok": True}

        with patch(
            "bot.listener_auto_catchup.run_listener_catchup_background",
            side_effect=wait_for_release,
        ):
            worker = listener_auto_catchup.start_listener_catchup_background(
                task,
                force=False,
                limit=8,
                queue_item_id="queue-46",
            )
            duplicate = listener_auto_catchup.start_listener_catchup_background(
                task,
                force=False,
                limit=8,
                queue_item_id="queue-duplicate",
            )

            self.assertIs(
                listener_auto_catchup._active_catchup_tasks[46],
                worker,
            )
            self.assertIsNone(duplicate)

            release.set()
            await worker
            await asyncio.sleep(0)

        self.assertFalse(listener_auto_catchup.is_listener_catchup_running(46))

    async def test_filtered_middle_item_does_not_stop_later_items(self):
        task = SimpleNamespace(
            id=44,
            name="测试监听",
            target_channels='["@target"]',
        )
        plan = {
            "ok": True,
            "targets": [{"target": "@target"}],
            "_pending_items": [
                content_item(101),
                content_item(102),
                content_item(103),
            ],
        }
        prepared = {
            "ok": True,
            "files": [],
            "text": "",
        }

        with (
            patch(
                "bot.listener_auto_catchup.build_listener_catchup_plan",
                AsyncMock(return_value=plan),
            ),
            patch(
                "bot.listener_auto_catchup.prepare_single_message",
                AsyncMock(return_value=prepared),
            ),
            patch(
                "bot.handlers.send_prepared_to_tasks",
                AsyncMock(side_effect=[True, False, True]),
            ) as send,
        ):
            result = await catchup_latest_listener_message(task, limit=3)

        self.assertEqual(send.await_count, 3)
        self.assertEqual(result["processed"], 3)
        self.assertEqual(result["sent_count"], 2)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["failed_count"], 0)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
