import asyncio
import time

from bot.logger import logger
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

    async def send(
        self,
        sender_func,
        *args,
        task_id=None,
        target=None,
        target_delay=0,
        skip_initial_delay=False,
        stop_event=None,
        **kwargs,
    ):
        async with self.lock:
            if stop_event and stop_event.is_set():
                logger.warning(
                    f"全局发送队列收到停止信号，跳过发送 | "
                    f"task_id={task_id} | target={target}"
                )
                return False

            settings = get_send_settings()
            global_delay = settings["global_send_delay"]
            retry_count = settings["send_retry_count"]
            retry_delay = settings["send_retry_delay"]
            send_delay = max(global_delay, int(target_delay or 0))

            logger.info(
                f"进入全局发送队列 | task_id={task_id} | target={target} | "
                f"global_delay={global_delay} | target_delay={target_delay} | "
                f"effective_delay={send_delay} | "
                f"skip_initial_delay={skip_initial_delay}"
            )

            if self.last_sent_at and send_delay > 0 and not skip_initial_delay:
                elapsed = time.monotonic() - self.last_sent_at
                wait_seconds = send_delay - elapsed

                logger.info(
                    f"全局发送间隔检查 | task_id={task_id} | target={target} | "
                    f"elapsed={elapsed:.2f}s | wait={max(wait_seconds, 0):.2f}s"
                )

                if wait_seconds > 0:
                    stopped = await wait_or_stop(wait_seconds, stop_event)

                    if stopped:
                        logger.warning(
                            f"全局发送等待被停止信号打断 | "
                            f"task_id={task_id} | target={target}"
                        )
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
                    return False

                try:
                    result = await sender_func(*args, **kwargs)
                    self.last_sent_at = time.monotonic()

                    logger.info(
                        f"全局发送完成 | task_id={task_id} | target={target} | "
                        f"result={self.summarize_result(result)} | "
                        f"attempt={attempt}/{attempts}"
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
                        return False

                    logger.exception(
                        f"全局发送队列发送异常，准备重试 | "
                        f"task_id={task_id} | target={target} | "
                        f"attempt={attempt}/{attempts} | retry_delay={retry_delay}s | {e}"
                    )

                    if retry_delay > 0:
                        stopped = await wait_or_stop(retry_delay, stop_event)

                        if stopped:
                            logger.warning(
                                f"全局发送重试等待被停止信号打断 | "
                                f"task_id={task_id} | target={target}"
                            )
                            return False

            return False


send_queue = SendQueue()
