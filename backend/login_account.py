import asyncio
from pathlib import Path

import socks
from telethon import TelegramClient
from telethon.network import ConnectionTcpFull

from config import API_ID, API_HASH
from utils.proxy_utils import normalize_proxy_for_runtime


# ====== 代理配置 ======
# Clash 常见 mixed-port：7890
# v2rayN 常见 socks：10808
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7897

# 如果 7890 不行，试试 10808
# PROXY_PORT = 10808

PROXY = (
    socks.SOCKS5,
    PROXY_HOST,
    PROXY_PORT,
)


async def main():
    session_path = input("请输入 session 路径，例如 data/sessions/collector_2：").strip()

    if not session_path:
        print("session 路径不能为空")
        return

    Path(session_path).parent.mkdir(parents=True, exist_ok=True)

    runtime_proxy = normalize_proxy_for_runtime(PROXY)

    client = TelegramClient(
        session_path,
        API_ID,
        API_HASH,
        connection=ConnectionTcpFull,
        proxy=runtime_proxy,
        connection_retries=10,
        retry_delay=3,
        timeout=30,
        auto_reconnect=True,
    )

    if runtime_proxy:
        print(f"正在通过代理连接 Telegram：{PROXY_HOST}:{PROXY_PORT}")
    else:
        print("正在直连 Telegram")

    await client.connect()

    if not await client.is_user_authorized():
        phone = input("请输入手机号，带国家区号，例如 +86138xxxx：").strip()

        await client.send_code_request(phone)

        code = input("请输入验证码：").strip()

        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "password" in str(e).lower() or "two-step" in str(e).lower():
                password = input("请输入二步验证密码：").strip()
                await client.sign_in(password=password)
            else:
                raise

    me = await client.get_me()

    print("登录成功：")
    print("id =", me.id)
    print("username =", me.username)
    print("phone =", me.phone)
    print("session =", session_path)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
