import asyncio
from typing import Dict

from bot.cloner import clone_task
from bot.logger import logger
from db.crud_clone import (
    get_all_clone_tasks,
    get_clone_task,
    update_clone_task,
)


class CloneWorkerManager:
    """
    克隆任务 Worker 管理器

    重点：
    stop 使用软停止，不直接 cancel worker。
    避免在“发送成功但未写 sent_messages / 未更新 last_message_id”时被打断。
    """

    def __init__(self):
        self.workers: Dict[int, asyncio.Task] = {}
        self.stop_events: Dict[int, asyncio.Event] = {}

    def is_running(self, task_id: int) -> bool:
        worker = self.workers.get(task_id)
        return bool(worker and not worker.done())

    async def start(self, task_id: int):
        task = get_clone_task(task_id)

        if not task:
            return {
                "ok": False,
                "message": "clone task not found",
                "task_id": task_id,
            }

        if self.is_running(task_id):
            return {
                "ok": False,
                "message": "clone task already running",
                "task_id": task_id,
            }

        stop_event = asyncio.Event()
        self.stop_events[task_id] = stop_event

        task = update_clone_task(task_id, {"status": "running"})

        if task:
            from bot.handlers import reload_handlers
            from db.crud_listener import sync_clone_task_to_listener_tasks

            listener_sync = sync_clone_task_to_listener_tasks(task)
            if listener_sync.get("suspended"):
                reload_handlers()
                logger.info(
                    "克隆启动，关联监听已暂停 | "
                    f"task_id={task_id} | listener_sync={listener_sync}"
                )

        worker = asyncio.create_task(
            self._run(task_id, stop_event)
        )

        self.workers[task_id] = worker

        logger.info(f"clone worker started | task_id={task_id}")

        return {
            "ok": True,
            "message": "clone started",
            "task_id": task_id,
        }

    async def restore_running_tasks(self):
        """Restore clone workers that were running before the service stopped."""
        tasks = get_all_clone_tasks()
        running_tasks = [
            task
            for task in tasks
            if task.status == "running" and task.enabled is not False
        ]
        disabled_running_ids = [
            task.id
            for task in tasks
            if task.status == "running" and task.enabled is False
        ]
        restored_task_ids = []
        failed = []

        for task in running_tasks:
            try:
                result = await self.start(task.id)
            except Exception as exc:
                logger.exception(
                    "clone worker restore failed | "
                    f"task_id={task.id} | error={exc}"
                )
                failed.append({
                    "task_id": task.id,
                    "message": str(exc),
                })
                continue

            if result.get("ok"):
                restored_task_ids.append(task.id)
                continue

            failed.append({
                "task_id": task.id,
                "message": result.get("message") or "restore failed",
            })

        summary = {
            "found": len(running_tasks),
            "restored": len(restored_task_ids),
            "restored_task_ids": restored_task_ids,
            "disabled_running_task_ids": disabled_running_ids,
            "failed": failed,
        }
        logger.info(f"clone worker startup restore completed | {summary}")
        return summary

    async def _run(self, task_id: int, stop_event: asyncio.Event):
        try:
            task = get_clone_task(task_id)

            if not task:
                logger.error(f"clone worker task not found | task_id={task_id}")
                return

            await clone_task(task, stop_event=stop_event)

        except asyncio.CancelledError:
            # 服务正常退出时 asyncio 会取消未完成的 worker。此时保留
            # running 状态，下一次启动才能从 last_message_id 自动续传。
            # 用户主动停止会先设置 stop_event，并已将状态保存为 stopped。
            logger.warning(
                "clone worker interrupted by service shutdown | "
                f"task_id={task_id} | preserve_running={not stop_event.is_set()}"
            )
            raise

        except Exception as e:
            logger.exception(f"clone worker error | task_id={task_id} | {e}")
            update_clone_task(task_id, {"status": "error"})

        finally:
            if stop_event.is_set():
                update_clone_task(task_id, {"status": "stopped"})

            self.workers.pop(task_id, None)
            self.stop_events.pop(task_id, None)

            logger.info(f"clone worker cleared | task_id={task_id}")

    def pause(self, task_id: int):
        """
        暂停任务。

        pause 也是软暂停：
        只改数据库状态，cloner.py 在安全检查点退出。
        """
        task = update_clone_task(task_id, {"status": "paused"})

        if not task:
            return {
                "ok": False,
                "message": "clone task not found",
                "task_id": task_id,
            }

        return {
            "ok": True,
            "message": "clone paused",
            "task_id": task_id,
        }

    async def resume(self, task_id: int):
        task = get_clone_task(task_id)

        if not task:
            return {
                "ok": False,
                "message": "clone task not found",
                "task_id": task_id,
            }

        if self.is_running(task_id):
            update_clone_task(task_id, {"status": "running"})

            return {
                "ok": True,
                "message": "clone already running",
                "task_id": task_id,
            }

        return await self.start(task_id)

    async def stop(self, task_id: int):
        """
        停止任务。

        这里不要 worker.cancel()。
        只设置 stop_event，让 cloner.py 当前消息完整处理完后退出。
        """
        stop_event = self.stop_events.get(task_id)

        if stop_event:
            stop_event.set()

        update_clone_task(task_id, {"status": "stopped"})

        logger.warning(
            f"clone worker soft stop requested | task_id={task_id}"
        )

        return {
            "ok": True,
            "message": "clone stop requested",
            "task_id": task_id,
        }

    def snapshot(self):
        running_task_ids = [
            task_id
            for task_id, worker in self.workers.items()
            if not worker.done()
        ]

        return {
            "running_task_ids": running_task_ids,
            "total_running": len(running_task_ids),
        }


clone_manager = CloneWorkerManager()
