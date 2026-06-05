import asyncio
import time

from bot.logger import logger
from bot.runtime_queue import runtime_queue_state
from db.crud_settings import get_send_settings


async def wait_or_stop(seconds, stop_event=None):
    seconds = max(float(seconds or 0), 0)

    if seconds <= 0:
        return False

    if not stop_event:
        await asyncio.sleep(seconds)
        return False

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        return True
    except asyncio.TimeoutError:
        return False


class SendQueue:
    """
    全局发送调度器。

    作用：
    - 所有 clone/listener 发送动作共享同一个锁
    - 任意两次 Bot API 发送之间应用全局间隔
    - 同一内容的多目标发送可传入 target_delay，和全局间隔取较大值
    - 抛异常的发送按系统设置重试；业务返回 False 不重试，避免 403 等权限错误刷屏
    """

    def __init__(self):
        self.lock = asyncio.Lock()
        self.started = False
        self.last_sent_at = 0.0

    def summarize_result(self, result):
        if not isinstance(result, dict):
            return result

        summary = {
            "ok": result.get("ok"),
            "target_channel": result.get("target_channel"),
            "target_message_ids": result.get("target_message_ids"),
            "target_message_url": result.get("target_message_url"),
        }

        return {
            key: value
            for key, value in summary.items()
            if value not in (None, "", [])
        }

    async def start(self):
        self.started = True
        logger.info("全局发送调度器已启动")

    def estimate_global_wait_seconds(self, send_delay):
        send_delay = max(float(send_delay or 0), 0)
        base_remaining = 0

        if self.last_sent_at and send_delay > 0:
            base_remaining = max(self.last_sent_at + send_delay - time.monotonic(), 0)

        if self.lock.locked() and send_delay > 0:
            base_remaining += send_delay

        waiting_global_count = len([
            item
            for item in runtime_queue_state.waiting.values()
            if item.get("queue_kind") == "global_send"
        ])

        return base_remaining + waiting_global_count * send_delay

    def build_waiting_meta(self, meta, task_id, target, send_delay, skip_initial_delay):
        payload = dict(meta or {
            "task_id": task_id,
            "target_channel": target,
        })
        payload.setdefault("reason", "等待全局发送队列")
        payload["queue_kind"] = "global_send"

        if not skip_initial_delay:
            payload.setdefault(
                "estimated_send_remaining_seconds",
                self.estimate_global_wait_seconds(send_delay),
            )

        return payload

    async def send(
        self,
        sender_func,
        *args,
        task_id=None,
        target=None,
        target_delay=0,
        skip_initial_delay=False,
        stop_event=None,
        queue_meta=None,
        **kwargs,
    ):
        settings = get_send_settings()
        global_delay = settings["global_send_delay"]
        retry_count = settings["send_retry_count"]
        retry_delay = settings["send_retry_delay"]
        send_delay = max(global_delay, int(target_delay or 0))
        queue_item_id = runtime_queue_state.add_waiting(
            self.build_waiting_meta(
                queue_meta,
                task_id,
                target,
                send_delay,
                skip_initial_delay,
            )
        )

        try:
            async with self.lock:
                if stop_event and stop_event.is_set():
                    logger.warning(
                        f"全局发送队列收到停止信号，跳过发送 | "
                        f"task_id={task_id} | target={target}"
                    )
                    runtime_queue_state.cancel(queue_item_id, "任务已停止")
                    return False

                logger.info(
                    f"进入全局发送队列 | task_id={task_id} | target={target} | "
                    f"global_delay={global_delay} | target_delay={target_delay} | "
                    f"effective_delay={send_delay} | "
                    f"skip_initial_delay={skip_initial_delay}"
                )

                runtime_queue_state.mark_current(
                    queue_item_id,
                    reason="全局发送间隔",
                )

                if self.last_sent_at and send_delay > 0 and not skip_initial_delay:
                    elapsed = time.monotonic() - self.last_sent_at
                    wait_seconds = send_delay - elapsed

                    logger.info(
                        f"全局发送间隔检查 | task_id={task_id} | target={target} | "
                        f"elapsed={elapsed:.2f}s | wait={max(wait_seconds, 0):.2f}s"
                    )

                    if wait_seconds > 0:
                        runtime_queue_state.update_current(
                            reason="等待全局发送间隔",
                            estimated_send_remaining_seconds=wait_seconds,
                        )
                        stopped = await wait_or_stop(wait_seconds, stop_event)

                        if stopped:
                            logger.warning(
                                f"全局发送等待被停止信号打断 | "
                                f"task_id={task_id} | target={target}"
                            )
                            runtime_queue_state.cancel(queue_item_id, "等待期间任务被停止")
                            return False

                elif skip_initial_delay:
                    logger.info(
                        f"跳过首次发送前等待 | task_id={task_id} | target={target}"
                    )

                attempts = retry_count + 1

                for attempt in range(1, attempts + 1):
                    if stop_event and stop_event.is_set():
                        logger.warning(
                            f"全局发送队列收到停止信号，停止重试 | "
                            f"task_id={task_id} | target={target}"
                        )
                        runtime_queue_state.cancel(queue_item_id, "任务已停止")
                        return False

                    try:
                        runtime_queue_state.mark_sending(queue_item_id)
                        result = await sender_func(*args, **kwargs)
                        self.last_sent_at = time.monotonic()

                        logger.info(
                            f"全局发送完成 | task_id={task_id} | target={target} | "
                            f"result={self.summarize_result(result)} | "
                            f"attempt={attempt}/{attempts}"
                        )

                        runtime_queue_state.finish(
                            queue_item_id,
                            success=bool(result),
                            error="" if result else "业务发送返回失败",
                        )
                        return result

                    except Exception as e:
                        self.last_sent_at = time.monotonic()

                        if attempt >= attempts:
                            logger.exception(
                                f"全局发送队列发送异常，已达最大重试次数 | "
                                f"task_id={task_id} | target={target} | "
                                f"attempt={attempt}/{attempts} | {e}"
                            )
                            runtime_queue_state.finish(
                                queue_item_id,
                                success=False,
                                error=str(e),
                            )
                            return False

                        logger.exception(
                            f"全局发送队列发送异常，准备重试 | "
                            f"task_id={task_id} | target={target} | "
                            f"attempt={attempt}/{attempts} | retry_delay={retry_delay}s | {e}"
                        )

                        if retry_delay > 0:
                            runtime_queue_state.update_current(
                                status="retrying",
                                reason=f"发送异常，{retry_delay}s 后重试",
                                error=str(e),
                            )
                            stopped = await wait_or_stop(retry_delay, stop_event)

                            if stopped:
                                logger.warning(
                                    f"全局发送重试等待被停止信号打断 | "
                                    f"task_id={task_id} | target={target}"
                                )
                                runtime_queue_state.cancel(queue_item_id, "重试等待被停止")
                                return False

                runtime_queue_state.finish(
                    queue_item_id,
                    success=False,
                    error="发送未完成",
                )
                return False

        except asyncio.CancelledError:
            runtime_queue_state.cancel(queue_item_id, "发送协程被取消，运行态已清理")
            raise

        except BaseException as e:
            runtime_queue_state.cancel(queue_item_id, f"发送协程异常退出，运行态已清理：{e}")
            raise


send_queue = SendQueue()
