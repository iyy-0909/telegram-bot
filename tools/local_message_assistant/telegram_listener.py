"""Telethon adapter with exact account verification; no desktop session import."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
import sys
import time

from telethon import TelegramClient, events

from engine import Assistant, CodexExtractor, DEFAULT_DATA, Store, account_key, load_config


class RuntimeLock:
    def __init__(self):
        self.file = None

    def acquire(self):
        DEFAULT_DATA.mkdir(parents=True, exist_ok=True)
        self.file = (DEFAULT_DATA / "telegram.lock").open("a+b")
        self.file.seek(0)
        if not self.file.read(1):
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise RuntimeError("另一个本地 Telegram 助手正在运行，拒绝重复启动") from exc

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


def credentials():
    api_id = os.environ.get("LOCAL_ASSISTANT_TELEGRAM_API_ID")
    api_hash = os.environ.get("LOCAL_ASSISTANT_TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("请配置本地助手专用 TELEGRAM_API_ID/API_HASH 环境变量，见 README")
    return int(api_id), api_hash


def make_client(username, api_id, api_hash):
    directory = DEFAULT_DATA / "telegram_sessions"
    directory.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(directory / username.lower()), api_id, api_hash,
                          catch_up=False, flood_sleep_threshold=0)


async def verify(client, username):
    if not await client.is_user_authorized():
        raise RuntimeError(f"@{username} 尚未登录本地监听器；桌面客户端登录不等于监听器已授权")
    me = await client.get_me()
    if not me or (me.username or "").lower() != username.lower() or me.bot:
        raise RuntimeError(f"登录身份与 @{username} 不符，拒绝监听和发送")
    return me


async def login(username, config):
    allowed = {a["username"].lower() for a in config["accounts"] if a["platform"] == "telegram"}
    if username.lower() not in allowed:
        raise RuntimeError("该用户名不在指定的两个账号中")
    client = make_client(username, *credentials())
    try:
        # This command must be run interactively by the account owner.
        await client.start()
        await verify(client, username)
        print(f"已验证 @{username}；尚未启用自动回复")
    finally:
        await client.disconnect()


async def run(config):
    accounts = [a for a in config["accounts"] if a["platform"] == "telegram" and a["enabled"]]
    if not accounts:
        raise RuntimeError("尚无已启用的 Telegram 账号；不会创建虚假的在线状态")
    api_id, api_hash = credentials()
    store = Store(DEFAULT_DATA)
    assistant = Assistant(store, CodexExtractor(config, DEFAULT_DATA), config)
    clients, workers, wakeups, incoming_times = [], {}, {}, {}
    model_lock = asyncio.Lock()
    started_at = time.time()

    def status(kind, account, **fields):
        # Only operational metadata in console logs; conversations stay in the local DB.
        print(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": kind,
                          "account": account, **fields}, ensure_ascii=False), flush=True)

    async def work(client, key, chat):
        pair = (key, chat)
        wakeup = wakeups[pair]
        while True:
            await wakeup.wait()
            wakeup.clear()
            while True:
                remaining = config.get("debounce_seconds", 5) - (time.monotonic() - incoming_times[pair])
                if remaining <= 0:
                    break
                await asyncio.sleep(remaining)
            async with model_lock:
                # The model process itself is offloaded; SQLite stays on this event-loop thread.
                rows = store.pending(key, chat)
                conversation = store.conversation(key, chat)
                if not rows or conversation["status"] != "active":
                    if rows:
                        with store.db:
                            store.mark(key, chat, rows, "human_required")
                    continue
                try:
                    extracted = await asyncio.to_thread(
                        assistant.extractor.extract, conversation["facts"], conversation["history"],
                        [r["text"] for r in rows],
                    )
                except Exception as exc:
                    # No timer-based retry storm: retained locally for human review.
                    with store.db:
                        store.mark(key, chat, rows, "model_failed")
                        conversation["status"] = "human_required"
                        store.save_conversation(key, chat, conversation)
                    status("model_failed", key, error=type(exc).__name__)
                    continue
                # New incoming messages invalidate the extraction; handle the entire batch next.
                if len(store.pending(key, chat)) != len(rows):
                    wakeup.set()
                    continue
                if store.conversation(key, chat)["status"] != "active":
                    continue
                class Extracted:
                    def extract(self, *_args):
                        return extracted
                prepared = Assistant(store, Extracted(), config).prepare(key, chat)
                if not prepared:
                    status("human_required", key)
                    continue
                # Recheck peer type and fresh outgoing history before sending.
                try:
                    peer = await client.get_entity(int(chat))
                    recent = await client.get_messages(int(chat), limit=1)
                except Exception as exc:
                    assistant.finish_send(prepared, False)
                    status("verification_failed", key, error=type(exc).__name__)
                    continue
                if getattr(peer, "bot", False) or not hasattr(peer, "first_name"):
                    assistant.finish_send(prepared, False)
                    continue
                if not recent or recent[0].out or str(recent[0].id) != str(rows[-1]["message_id"]):
                    assistant.finish_send(prepared, False)
                    status("conversation_changed", key)
                    continue
                assistant.begin_send(prepared)
                try:
                    await client.send_message(peer, prepared["reply"])
                except Exception as exc:
                    # A network timeout does not prove the send failed. Never resend automatically.
                    assistant.finish_send(prepared, False)
                    status("send_uncertain", key, error=type(exc).__name__)
                else:
                    assistant.finish_send(prepared, True)
                    status("sent", key)

    try:
        # All enabled accounts must verify before any handler is attached.
        for account in accounts:
            client = make_client(account["username"], api_id, api_hash)
            clients.append((account, client))
            await client.connect()
            await verify(client, account["username"])
        for account, client in clients:
            key = account_key("telegram", account["username"])

            async def incoming(event, current_client=client, current_key=key):
                if not event.is_private or event.out or event.chat_id == 777000:
                    return
                sender = await event.get_sender()
                if not sender or getattr(sender, "bot", False) or getattr(sender, "is_self", False):
                    return
                chat = str(event.chat_id)
                payload = {"kind": "private", "outgoing": False, "bot": False,
                           "service": bool(event.message.action), "date": event.date.timestamp(),
                           "id": str(event.id), "chat": chat, "text": event.raw_text}
                if store.ingest(current_key, payload, started_at):
                    pair = (current_key, chat)
                    incoming_times[pair] = time.monotonic()
                    if pair not in workers or workers[pair].done():
                        wakeups[pair] = asyncio.Event()
                        workers[pair] = asyncio.create_task(work(current_client, current_key, chat))
                    wakeups[pair].set()
                    status("new_private_message", current_key)

            client.add_event_handler(incoming, events.NewMessage(incoming=True))
            status("listening", key)
        await asyncio.gather(*(client.run_until_disconnected() for _, client in clients))
    finally:
        for worker in workers.values():
            worker.cancel()
        await asyncio.gather(*workers.values(), return_exceptions=True)
        for _, client in clients:
            await client.disconnect()
        store.db.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="仅处理指定 Telegram 账号的新私聊")
    parser.add_argument("--login", metavar="USERNAME")
    args = parser.parse_args()
    runtime_lock = RuntimeLock()
    try:
        runtime_lock.acquire()
        asyncio.run(login(args.login.lstrip("@"), load_config()) if args.login else run(load_config()))
    except (RuntimeError, ValueError) as exc:
        print(str(exc))
        raise SystemExit(1)
    finally:
        runtime_lock.close()
