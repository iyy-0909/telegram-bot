import asyncio

from bot.logger import logger


send_queue = asyncio.Queue()


async def add_send_task(func, *args, **kwargs):
    await send_queue.put((func, args, kwargs))


async def send_worker():
    logger.info("发送队列已启动")

    while True:
        func, args, kwargs = await send_queue.get()

        try:
            await func(*args, **kwargs)

        except Exception as e:
            logger.exception(e)

        finally:
            send_queue.task_done()

        await asyncio.sleep(2)