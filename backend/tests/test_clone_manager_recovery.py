import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import run
from bot.clone_manager import CloneWorkerManager


class CloneWorkerRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_backend_startup_restores_clone_workers(self):
        restore = AsyncMock(return_value={"restored": 0})

        with (
            patch.object(run, "cleanup_local_proxy_env_vars"),
            patch.object(run, "init_db"),
            patch.object(run, "start_bot", AsyncMock()),
            patch.object(run, "send_worker", AsyncMock()),
            patch.object(run.clone_manager, "restore_running_tasks", restore),
            patch.object(run, "start_support_polling"),
            patch.object(run, "start_control_polling"),
            patch.object(run, "start_listener_health_worker"),
            patch.object(run, "start_api", AsyncMock()),
        ):
            await run.main()
            await asyncio.sleep(0)

        restore.assert_awaited_once_with()

    async def test_restore_starts_only_enabled_running_tasks(self):
        manager = CloneWorkerManager()
        tasks = [
            SimpleNamespace(id=7, status="running", enabled=True),
            SimpleNamespace(id=8, status="paused", enabled=True),
            SimpleNamespace(id=9, status="running", enabled=False),
            SimpleNamespace(id=10, status="done", enabled=True),
        ]
        manager.start = AsyncMock(return_value={
            "ok": True,
            "message": "clone started",
        })

        with patch(
            "bot.clone_manager.get_all_clone_tasks",
            return_value=tasks,
        ):
            result = await manager.restore_running_tasks()

        manager.start.assert_awaited_once_with(7)
        self.assertEqual(result["found"], 1)
        self.assertEqual(result["restored"], 1)
        self.assertEqual(result["restored_task_ids"], [7])
        self.assertEqual(result["disabled_running_task_ids"], [9])
        self.assertEqual(result["failed"], [])

    async def test_service_shutdown_preserves_running_status(self):
        manager = CloneWorkerManager()
        stop_event = asyncio.Event()
        task = SimpleNamespace(id=7)
        update = Mock()

        with (
            patch("bot.clone_manager.get_clone_task", return_value=task),
            patch(
                "bot.clone_manager.clone_task",
                AsyncMock(side_effect=asyncio.CancelledError),
            ),
            patch("bot.clone_manager.update_clone_task", update),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await manager._run(task.id, stop_event)

        update.assert_not_called()
        self.assertNotIn(task.id, manager.workers)
        self.assertNotIn(task.id, manager.stop_events)

    async def test_user_stop_still_persists_stopped_during_cancellation(self):
        manager = CloneWorkerManager()
        stop_event = asyncio.Event()
        stop_event.set()
        task = SimpleNamespace(id=7)
        update = Mock()

        with (
            patch("bot.clone_manager.get_clone_task", return_value=task),
            patch(
                "bot.clone_manager.clone_task",
                AsyncMock(side_effect=asyncio.CancelledError),
            ),
            patch("bot.clone_manager.update_clone_task", update),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await manager._run(task.id, stop_event)

        update.assert_called_once_with(task.id, {"status": "stopped"})


if __name__ == "__main__":
    unittest.main()
