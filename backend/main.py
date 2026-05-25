import asyncio

from bot.client import client
from bot.handlers import register_handlers
from bot.history import clone_missing_history
from bot.logger import logger


async def main():

    await client.start()

    logger.info("机器人已登录")

    await clone_missing_history(limit=20)

    register_handlers()

    logger.info("实时监听已启动")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())