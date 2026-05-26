import asyncio
import os
import uvicorn

from bot.queue import send_worker
from accounts.manager import account_manager
from bot.handlers import register_handlers
from bot.logger import logger
from bot.support_bot import start_support_polling


async def start_bot():
    await account_manager.load_accounts()

    logger.info("账号池加载完成")

    register_handlers()

    logger.info("实时监听已启动")


async def start_api():
    config = uvicorn.Config(
        "api.server:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=False,
        access_log=False,
    )

    server = uvicorn.Server(config)

    await server.serve()


async def main():
    await start_bot()

    asyncio.create_task(send_worker())
    start_support_polling()

    await start_api()


if __name__ == "__main__":
    asyncio.run(main())
