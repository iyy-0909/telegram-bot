import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from telethon.errors.common import TypeNotFoundError

from accounts.manager import AccountManager


class FakeQuery:
    def __init__(self, account):
        self.account = account

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.account


class FakeSession:
    def __init__(self, account):
        self.account = account
        self.closed = False

    def query(self, *_args, **_kwargs):
        return FakeQuery(self.account)

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, *, start_error=None, start_gate=None):
        self.start_error = start_error
        self.start_gate = start_gate
        self.start_entered = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.start_calls = 0
        self.disconnect_calls = 0
        self.connected = False
        self.event_handlers = []

    def add_event_handler(self, callback, event):
        self.event_handlers.append((callback, event))

    async def start(self):
        self.start_calls += 1
        self.start_entered.set()
        if self.start_gate is not None:
            await self.start_gate.wait()
        if self.start_error is not None:
            raise self.start_error
        self.connected = True

    async def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False
        self.disconnected.set()

    def is_connected(self):
        return self.connected


class AccountManagerLoadingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.account = SimpleNamespace(
            id=3,
            owner_user_id=1,
            enabled=True,
            proxy="",
            name="collector",
            session_path="data/sessions/user_1/collector",
        )
        self.allowed = SimpleNamespace(allowed=True, reason="allowed")

    def runtime_patches(self, account=None):
        account = account or self.account
        return (
            patch(
                "accounts.manager.SessionLocal",
                side_effect=lambda: FakeSession(account),
            ),
            patch(
                "accounts.manager.get_owner_runtime_access",
                return_value=self.allowed,
            ),
            patch(
                "accounts.manager.normalize_proxy_for_runtime",
                return_value=None,
            ),
        )

    async def test_concurrent_lazy_loads_share_one_started_client(self):
        manager = AccountManager()
        start_gate = asyncio.Event()
        client = FakeClient(start_gate=start_gate)
        build_client = Mock(return_value=client)
        session_patch, access_patch, proxy_patch = self.runtime_patches()

        with (
            session_patch,
            access_patch,
            proxy_patch,
            patch.object(manager, "_build_client", build_client),
        ):
            tasks = [
                asyncio.create_task(manager.load_account(self.account.id))
                for _ in range(5)
            ]
            await asyncio.wait_for(client.start_entered.wait(), timeout=1)
            await asyncio.sleep(0)

            self.assertEqual(build_client.call_count, 1)
            start_gate.set()
            results = await asyncio.gather(*tasks)

        self.assertEqual(results, [True] * 5)
        self.assertEqual(client.start_calls, 1)
        self.assertEqual(client.disconnect_calls, 0)
        self.assertIs(manager.get_client(self.account.id), client)

    async def test_bulk_and_lazy_load_use_the_same_account_lock(self):
        manager = AccountManager()
        start_gate = asyncio.Event()
        client = FakeClient(start_gate=start_gate)
        build_client = Mock(return_value=client)
        session_patch, access_patch, proxy_patch = self.runtime_patches()

        with (
            patch("accounts.manager.get_all_accounts", return_value=[self.account]),
            session_patch,
            access_patch,
            proxy_patch,
            patch.object(manager, "_build_client", build_client),
        ):
            bulk_task = asyncio.create_task(manager.load_accounts())
            await asyncio.wait_for(client.start_entered.wait(), timeout=1)
            lazy_task = asyncio.create_task(manager.load_account(self.account.id))
            await asyncio.sleep(0)

            self.assertEqual(build_client.call_count, 1)
            start_gate.set()
            await bulk_task
            self.assertTrue(await lazy_task)

        self.assertEqual(build_client.call_count, 1)
        self.assertIs(manager.get_client(self.account.id), client)

    async def test_force_reload_replaces_a_healthy_cached_client(self):
        manager = AccountManager()
        old_client = FakeClient()
        old_client.connected = True
        new_client = FakeClient()
        manager.clients[self.account.id] = old_client
        session_patch, access_patch, proxy_patch = self.runtime_patches()

        with (
            session_patch,
            access_patch,
            proxy_patch,
            patch.object(manager, "_build_client", return_value=new_client) as build,
        ):
            loaded = await manager.load_account(
                self.account.id,
                force_reload=True,
            )

        self.assertTrue(loaded)
        self.assertEqual(old_client.disconnect_calls, 1)
        self.assertEqual(new_client.start_calls, 1)
        self.assertEqual(build.call_count, 1)
        self.assertIs(manager.get_client(self.account.id), new_client)

    async def test_failed_start_disconnects_candidate_and_clears_cache(self):
        manager = AccountManager()
        client = FakeClient(start_error=RuntimeError("database is locked"))
        session_patch, access_patch, proxy_patch = self.runtime_patches()

        with (
            session_patch,
            access_patch,
            proxy_patch,
            patch.object(manager, "_build_client", return_value=client),
        ):
            loaded = await manager.load_account(self.account.id)

        self.assertFalse(loaded)
        self.assertEqual(client.disconnect_calls, 1)
        self.assertNotIn(self.account.id, manager.clients)

    async def test_cancelled_start_closes_candidate_before_lock_is_reused(self):
        manager = AccountManager()
        never_release = asyncio.Event()
        cancelled_client = FakeClient(start_gate=never_release)
        replacement_client = FakeClient()
        build_client = Mock(side_effect=[cancelled_client, replacement_client])
        session_patch, access_patch, proxy_patch = self.runtime_patches()

        with (
            session_patch,
            access_patch,
            proxy_patch,
            patch.object(manager, "_build_client", build_client),
        ):
            first_load = asyncio.create_task(manager.load_account(self.account.id))
            await asyncio.wait_for(cancelled_client.start_entered.wait(), timeout=1)
            first_load.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first_load

            self.assertTrue(cancelled_client.disconnected.is_set())
            self.assertTrue(await manager.load_account(self.account.id))

        self.assertEqual(cancelled_client.disconnect_calls, 1)
        self.assertEqual(build_client.call_count, 2)
        self.assertIs(manager.get_client(self.account.id), replacement_client)

    async def test_bulk_load_retries_type_not_found_once_with_fresh_client(self):
        manager = AccountManager()
        first_client = FakeClient(
            start_error=TypeNotFoundError(0x12345678, b""),
        )
        second_client = FakeClient()
        build_client = Mock(side_effect=[first_client, second_client])

        with (
            patch("accounts.manager.get_all_accounts", return_value=[self.account]),
            patch(
                "accounts.manager.get_owner_runtime_access",
                return_value=self.allowed,
            ),
            patch(
                "accounts.manager.normalize_proxy_for_runtime",
                return_value=None,
            ),
            patch.object(manager, "_build_client", build_client),
            patch("accounts.manager.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            await manager.load_accounts()

        self.assertEqual(build_client.call_count, 2)
        self.assertEqual(first_client.disconnect_calls, 1)
        self.assertEqual(second_client.start_calls, 1)
        sleep.assert_awaited_once()
        self.assertIs(manager.get_client(self.account.id), second_client)

    async def test_bulk_type_not_found_retry_is_bounded(self):
        manager = AccountManager()
        first_client = FakeClient(
            start_error=TypeNotFoundError(0x12345678, b""),
        )
        second_client = FakeClient(
            start_error=TypeNotFoundError(0x12345678, b""),
        )
        build_client = Mock(side_effect=[first_client, second_client])

        with (
            patch("accounts.manager.get_all_accounts", return_value=[self.account]),
            patch(
                "accounts.manager.get_owner_runtime_access",
                return_value=self.allowed,
            ),
            patch(
                "accounts.manager.normalize_proxy_for_runtime",
                return_value=None,
            ),
            patch.object(manager, "_build_client", build_client),
            patch("accounts.manager.asyncio.sleep", new_callable=AsyncMock),
        ):
            await manager.load_accounts()

        self.assertEqual(build_client.call_count, 2)
        self.assertEqual(first_client.disconnect_calls, 1)
        self.assertEqual(second_client.disconnect_calls, 1)
        self.assertNotIn(self.account.id, manager.clients)


if __name__ == "__main__":
    unittest.main()
