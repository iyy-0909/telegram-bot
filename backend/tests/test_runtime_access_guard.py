import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from accounts.manager import AccountManager, account_manager
from auth.runtime_access import evaluate_user_runtime_access
from bot import handlers, runtime_access_guard, support_bot
from bot.clone_manager import CloneWorkerManager
from db.models import Account, CloneTask, ListenerTask, SupportBot, UserAccount


class RuntimeAccessDecisionTests(unittest.TestCase):
    def user(self, **overrides):
        values = {
            "id": 1,
            "role": "user",
            "status": "active",
            "plan_tier": "free",
            "feature_keys_json": "[]",
            "access_expires_at": None,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_free_plan_keeps_listener_and_clone_runtime_access(self):
        user = self.user(plan_tier="free")

        self.assertTrue(
            evaluate_user_runtime_access(user, "listener_tasks").allowed
        )
        self.assertTrue(
            evaluate_user_runtime_access(user, "clone_tasks").allowed
        )
        support = evaluate_user_runtime_access(user, "support")
        self.assertFalse(support.allowed)
        self.assertEqual(support.reason, "feature_revoked")

    def test_disabled_expired_and_missing_feature_fail_closed(self):
        disabled = evaluate_user_runtime_access(
            self.user(status="disabled"),
            "clone_tasks",
        )
        expired = evaluate_user_runtime_access(
            self.user(access_expires_at=datetime.utcnow() - timedelta(seconds=1)),
            "listener_tasks",
        )
        paid_without_support = evaluate_user_runtime_access(
            self.user(plan_tier="paid"),
            "support",
        )

        self.assertEqual(disabled.reason, "disabled")
        self.assertEqual(expired.reason, "expired")
        self.assertEqual(paid_without_support.reason, "feature_revoked")

    def test_active_admin_can_run_support(self):
        decision = evaluate_user_runtime_access(
            self.user(role="admin", plan_tier="paid"),
            "support",
        )
        self.assertTrue(decision.allowed)


class RuntimeAccessPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "runtime-access.db"
        self.engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        for table in (
            UserAccount.__table__,
            Account.__table__,
            CloneTask.__table__,
            ListenerTask.__table__,
            SupportBot.__table__,
        ):
            table.create(bind=self.engine)
        self.session_patch = patch.object(
            runtime_access_guard,
            "SessionLocal",
            self.session_local,
        )
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def add_user(self, username, *, status="active", role="user", plan="free", expires=None):
        db = self.session_local()
        try:
            user = UserAccount(
                username=username,
                password_hash="test-hash",
                role=role,
                status=status,
                plan_tier=plan,
                feature_keys_json="[]",
                access_expires_at=expires,
                advertisement_text="ad",
                advertisement_send_time="12:00",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        finally:
            db.close()

    def seed_runtime(self):
        now = datetime.utcnow()
        free_id = self.add_user("free")
        expired_id = self.add_user(
            "expired",
            expires=now - timedelta(minutes=1),
        )
        disabled_id = self.add_user("disabled", status="disabled")
        admin_id = self.add_user("admin", role="admin", plan="paid")
        paid_id = self.add_user("paid", plan="paid")

        db = self.session_local()
        try:
            db.add_all([
                Account(
                    id=101,
                    owner_user_id=free_id,
                    name="free-account",
                    session_path="free.session",
                    enabled=True,
                ),
                Account(
                    id=102,
                    owner_user_id=expired_id,
                    name="expired-account",
                    session_path="expired.session",
                    enabled=True,
                ),
                Account(
                    id=103,
                    owner_user_id=disabled_id,
                    name="disabled-account",
                    session_path="disabled.session",
                    enabled=True,
                ),
            ])
            db.commit()
            rows = [
                CloneTask(
                    owner_user_id=free_id,
                    name="free-clone",
                    source_channel="@source",
                    account_id=101,
                    status="running",
                ),
                CloneTask(
                    owner_user_id=expired_id,
                    name="expired-clone",
                    source_channel="@source",
                    account_id=102,
                    status="running",
                ),
                CloneTask(
                    owner_user_id=disabled_id,
                    name="disabled-clone",
                    source_channel="@source",
                    account_id=103,
                    status="running",
                ),
                ListenerTask(
                    owner_user_id=free_id,
                    name="free-listener",
                    source_channel="@source",
                    account_id=101,
                    enabled=True,
                    status="running",
                ),
                ListenerTask(
                    owner_user_id=expired_id,
                    name="expired-listener",
                    source_channel="@source",
                    account_id=102,
                    enabled=True,
                    status="running",
                ),
                SupportBot(
                    owner_user_id=admin_id,
                    name="admin-support",
                    polling_enabled=True,
                ),
                SupportBot(
                    owner_user_id=paid_id,
                    name="paid-support",
                    polling_enabled=True,
                ),
            ]
            db.add_all(rows)
            db.commit()
            return free_id, expired_id, disabled_id, admin_id, paid_id
        finally:
            db.close()

    def test_guard_persists_stopped_state_and_keeps_free_clone_listener(self):
        self.seed_runtime()

        result = runtime_access_guard.enforce_runtime_access_state()

        db = self.session_local()
        try:
            clones = {row.name: row for row in db.query(CloneTask).all()}
            listeners = {row.name: row for row in db.query(ListenerTask).all()}
            support = {row.name: row for row in db.query(SupportBot).all()}

            self.assertEqual(clones["free-clone"].status, "running")
            self.assertEqual(clones["expired-clone"].status, "stopped")
            self.assertEqual(clones["disabled-clone"].status, "stopped")
            self.assertTrue(listeners["free-listener"].enabled)
            self.assertFalse(listeners["expired-listener"].enabled)
            self.assertEqual(listeners["expired-listener"].status, "stopped")
            self.assertTrue(support["admin-support"].polling_enabled)
            self.assertFalse(support["paid-support"].polling_enabled)
        finally:
            db.close()

        self.assertEqual(len(result["stopped_clone_task_ids"]), 2)
        self.assertEqual(len(result["stopped_listener_task_ids"]), 1)
        self.assertEqual(len(result["stopped_support_bot_ids"]), 1)

        db = self.session_local()
        try:
            account_ids = {
                row.name: row.id
                for row in db.query(Account).all()
            }
        finally:
            db.close()
        denied_accounts = runtime_access_guard.find_unauthorized_account_clients(
            list(account_ids.values())
        )
        self.assertNotIn(account_ids["free-account"], denied_accounts)
        self.assertEqual(
            denied_accounts[account_ids["expired-account"]],
            "expired",
        )


class CloneRuntimeAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_clone_start_denied_persists_stopped_and_creates_no_worker(self):
        manager = CloneWorkerManager()
        task = SimpleNamespace(id=9, owner_user_id=22)
        denied = SimpleNamespace(
            allowed=False,
            reason="expired",
            message="expired",
        )
        update = Mock(return_value=task)

        with (
            patch("bot.clone_manager.get_clone_task", return_value=task),
            patch("bot.clone_manager.get_owner_runtime_access", return_value=denied),
            patch("bot.clone_manager.update_clone_task", update),
        ):
            result = await manager.start(task.id)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "expired")
        update.assert_called_once_with(task.id, {"status": "stopped"})
        self.assertFalse(manager.is_running(task.id))

    async def test_clone_resume_cannot_revive_running_worker_after_expiry(self):
        manager = CloneWorkerManager()
        task = SimpleNamespace(id=10, owner_user_id=23)
        stop_event = asyncio.Event()
        manager.stop_events[task.id] = stop_event
        manager.workers[task.id] = SimpleNamespace(done=lambda: False)
        denied = SimpleNamespace(
            allowed=False,
            reason="expired",
            message="expired",
        )

        with (
            patch("bot.clone_manager.get_clone_task", return_value=task),
            patch("bot.clone_manager.get_owner_runtime_access", return_value=denied),
            patch("bot.clone_manager.update_clone_task") as update,
        ):
            result = await manager.resume(task.id)

        self.assertFalse(result["ok"])
        self.assertTrue(stop_event.is_set())
        update.assert_called_once_with(task.id, {"status": "stopped"})

    async def test_reconcile_signals_running_clone_and_reloads_listeners(self):
        clone_stop_event = asyncio.Event()
        fake_manager = SimpleNamespace(stop_events={31: clone_stop_event})
        result = {
            "stopped_clone_task_ids": [31],
            "stopped_listener_task_ids": [41],
            "stopped_support_bot_ids": [],
            "reasons": {},
        }

        with (
            patch.object(runtime_access_guard, "enforce_runtime_access_state", return_value=result),
            patch.object(runtime_access_guard, "find_unauthorized_account_clients", return_value={}),
            patch("bot.clone_manager.clone_manager", fake_manager),
            patch("bot.handlers.reload_handlers") as reload_handlers,
        ):
            observed = await runtime_access_guard.reconcile_runtime_access_once()

        self.assertIs(observed, result)
        self.assertTrue(clone_stop_event.is_set())
        reload_handlers.assert_called_once_with()

    async def test_reconcile_disconnects_and_removes_unauthorized_account(self):
        client = object()
        result = {
            "stopped_clone_task_ids": [],
            "stopped_listener_task_ids": [],
            "stopped_support_bot_ids": [],
            "disconnected_account_ids": [],
            "reasons": {},
        }

        with (
            patch.object(runtime_access_guard, "enforce_runtime_access_state", return_value=result),
            patch.object(runtime_access_guard, "find_unauthorized_account_clients", return_value={71: "expired"}),
            patch.object(account_manager, "clients", {71: client}),
            patch.object(account_manager, "_disconnect_safely", AsyncMock()) as disconnect,
        ):
            observed = await runtime_access_guard.reconcile_runtime_access_once()
            self.assertNotIn(71, account_manager.clients)

        disconnect.assert_awaited_once_with(client)
        self.assertEqual(observed["disconnected_account_ids"], [71])
        self.assertEqual(observed["reasons"]["account:71"], "expired")

    async def test_support_worker_disables_polling_before_network_when_revoked(self):
        config = {
            "id": 51,
            "_owner_user_id": 77,
            "bot_token": "",
            "polling_enabled": True,
            "status": "enabled",
        }
        denied = SimpleNamespace(
            allowed=False,
            reason="feature_revoked",
            message="revoked",
        )

        with (
            patch.object(support_bot, "get_support_bot_config", return_value=config),
            patch.object(support_bot, "get_owner_runtime_access", return_value=denied),
            patch.object(support_bot, "update_support_bot") as update_support_bot,
            patch.object(support_bot, "ensure_polling_mode", AsyncMock()) as ensure_polling,
        ):
            await support_bot.support_polling_worker(config)

        update_support_bot.assert_called_once_with(
            51,
            {
                "polling_enabled": False,
                "last_error": "revoked",
            },
        )
        ensure_polling.assert_not_awaited()


class ListenerRuntimeAccessTests(unittest.TestCase):
    def test_revoked_listener_is_persistently_disabled_before_registration(self):
        task = SimpleNamespace(id=61, owner_user_id=88)
        denied = SimpleNamespace(
            allowed=False,
            reason="expired",
            message="expired",
        )

        with (
            patch.object(handlers, "get_owner_runtime_access", return_value=denied),
            patch.object(handlers, "update_listener_status") as update_status,
        ):
            allowed = handlers.filter_runtime_allowed_listener_tasks([task])

        self.assertEqual(allowed, [])
        update_status.assert_called_once_with(
            61,
            enabled=False,
            status="stopped",
            last_error="expired",
        )


class AccountManagerRuntimeAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_bulk_load_skips_revoked_owner_and_disconnects_existing_client(self):
        manager = AccountManager()
        allowed_account = SimpleNamespace(
            id=81,
            owner_user_id=1,
            enabled=True,
            proxy="",
            name="allowed",
            session_path="allowed.session",
        )
        denied_account = SimpleNamespace(
            id=82,
            owner_user_id=2,
            enabled=True,
            proxy="",
            name="denied",
            session_path="denied.session",
        )
        allowed_client = SimpleNamespace(
            start=AsyncMock(),
            disconnect=AsyncMock(),
            add_event_handler=Mock(),
        )
        denied_old_client = SimpleNamespace(disconnect=AsyncMock())
        manager.clients[denied_account.id] = denied_old_client

        def access_for_owner(owner_user_id, _feature_key):
            return SimpleNamespace(
                allowed=owner_user_id == 1,
                reason="allowed" if owner_user_id == 1 else "expired",
            )

        with (
            patch("accounts.manager.get_all_accounts", return_value=[allowed_account, denied_account]),
            patch("accounts.manager.get_owner_runtime_access", side_effect=access_for_owner),
            patch("accounts.manager.resolve_owner_session_path", return_value=Path("runtime.session")),
            patch("accounts.manager.TelegramClient", return_value=allowed_client) as telegram_client,
        ):
            await manager.load_accounts()

        self.assertIs(manager.clients[allowed_account.id], allowed_client)
        allowed_client.add_event_handler.assert_called_once()
        self.assertNotIn(denied_account.id, manager.clients)
        denied_old_client.disconnect.assert_awaited_once_with()
        telegram_client.assert_called_once()


if __name__ == "__main__":
    unittest.main()
