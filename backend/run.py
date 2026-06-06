import asyncio
import os
import uvicorn

from bot.queue import send_worker
from accounts.manager import account_manager
from bot.handlers import register_handlers
from bot.logger import logger
from bot.support_bot import start_support_polling
from bot.control_bot import start_control_polling
from bot.notifier import start_ack_alert_repeat_worker
from init_db import init_db
from utils.proxy_utils import cleanup_local_proxy_env_vars


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
    cleanup_local_proxy_env_vars()
    init_db()

    await start_bot()

    asyncio.create_task(send_worker())
    start_support_polling()
    start_control_polling()
    start_ack_alert_repeat_worker()

    await start_api()


if __name__ == "__main__":
    asyncio.run(main())
