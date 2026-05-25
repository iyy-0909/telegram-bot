import asyncio

from accounts.manager import account_manager
from db.crud import get_enabled_rules
from bot.cloner import clone_rule
from bot.logger import logger


async def main():
    await account_manager.load_accounts()

    rules = get_enabled_rules()

    if not rules:
        logger.warning("没有启用的规则")
        return

    for rule in rules:
        await clone_rule(
            rule,
            limit=50,
            delay=5
        )


if __name__ == "__main__":
    asyncio.run(main())