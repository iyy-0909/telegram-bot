import asyncio
from typing import Dict

from bot.cloner import clone_task
from bot.logger import logger
from db.crud_clone import get_clone_task, update_clone_task


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

        update_clone_task(task_id, {"status": "running"})

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

    async def _run(self, task_id: int, stop_event: asyncio.Event):
        try:
            task = get_clone_task(task_id)

            if not task:
                logger.error(f"clone worker task not found | task_id={task_id}")
                return

            await clone_task(task, stop_event=stop_event)

        except asyncio.CancelledError:
            # 理论上软停止后不应该经常进入这里，保留兜底
            logger.warning(f"clone worker cancelled | task_id={task_id}")
            update_clone_task(task_id, {"status": "stopped"})
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
