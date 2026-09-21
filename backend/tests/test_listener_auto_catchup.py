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
            patch("bot.listener_auto_catchup.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await catchup_latest_listener_message(task, limit=3)

        self.assertEqual(send.await_count, 3)
        self.assertEqual(result["processed"], 3)
        self.assertEqual(result["sent_count"], 2)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["failed_count"], 0)
        self.assertTrue(result["ok"])

    async def run_timed_batch(self, items, outcomes, interval=30):
        clock = SimpleNamespace(now=100.0)
        sent_at, waits = [], []
        queue_id = listener_auto_catchup.runtime_queue_state.add_waiting({})

        async def send(**kwargs):
            sent_at.append(clock.now)
            # A send takes two seconds; the interval starts after completion.
            clock.now += 2
            return outcomes[len(sent_at) - 1]

        async def sleep(seconds):
            waits.append(seconds)
            snapshot = listener_auto_catchup.runtime_queue_state.snapshot()
            entry = next(row for row in snapshot["waiting"] if row["id"] == queue_id)
            self.assertEqual(entry["status"], "waiting")
            self.assertIn("内容间隔", entry["reason"])
            self.assertIsNone(snapshot["current"])
            clock.now += seconds

        with (
            patch.object(listener_auto_catchup, "build_listener_catchup_plan", AsyncMock(return_value={"ok": True, "_pending_items": items})),
            patch.object(listener_auto_catchup, "prepare_single_message", AsyncMock(return_value={"ok": True, "files": []})),
            patch.object(listener_auto_catchup, "prepare_album", AsyncMock(return_value={"ok": True, "files": []})) as album,
            patch("bot.handlers.send_prepared_to_tasks", side_effect=send),
            patch.object(listener_auto_catchup.time, "monotonic", side_effect=lambda: clock.now),
            patch.object(listener_auto_catchup.asyncio, "sleep", side_effect=sleep),
        ):
            result = await catchup_latest_listener_message(
                SimpleNamespace(id=44), limit=3, interval_seconds=interval, queue_item_id=queue_id,
            )
        return result, sent_at, waits, album.await_count

    async def test_interval_is_between_completed_contents_without_first_or_final_wait(self):
        result, sent_at, waits, _ = await self.run_timed_batch(
            [content_item(1), content_item(2), content_item(3)], [True, True, True], 45,
        )
        self.assertEqual(sent_at, [100, 147, 194])
        self.assertEqual(waits, [45, 45])
        self.assertEqual(result["interval_seconds"], 45)

    async def test_album_is_one_content_and_filtered_item_does_not_add_interval(self):
        album = content_item(1)
        album["_grouped_id"] = 123
        album["_messages"].append(SimpleNamespace(id=2, message=""))
        result, sent_at, waits, album_count = await self.run_timed_batch(
            [album, content_item(3), content_item(4)], [True, False, True],
        )
        self.assertEqual(sent_at, [100, 132, 134])
        self.assertEqual(waits, [30])
        self.assertEqual(album_count, 1)
        self.assertEqual(result["sent_count"], 2)

    async def test_single_content_does_not_wait(self):
        _, sent_at, waits, _ = await self.run_timed_batch([content_item(1)], [True])
        self.assertEqual(sent_at, [100])
        self.assertEqual(waits, [])

    async def test_background_forwards_interval_and_cancellation_during_wait(self):
        with patch.object(listener_auto_catchup, "catchup_latest_listener_message", AsyncMock(side_effect=asyncio.CancelledError)) as run, patch.object(listener_auto_catchup.runtime_queue_state, "cancel") as cancel:
            worker = listener_auto_catchup.start_listener_catchup_background(
                SimpleNamespace(id=47), force=False, limit=3, queue_item_id="cancel-test", interval_seconds=300,
            )
            with self.assertRaises(asyncio.CancelledError):
                await worker
            self.assertEqual(run.call_args.kwargs["interval_seconds"], 300)
            cancel.assert_called_once_with("cancel-test", "补齐任务被取消")


if __name__ == "__main__":
    unittest.main()
