import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from telethon import types

from auth.tenant import tenant_scope
from bot import managed_channels as scanner
from db import crud_managed_channels as store
from db.database import Base
from db.models import Account, AccountChannelSync, AccountManagedChannel, MyChannel
from migrate_managed_channels import migrate


def result(chat_id="-100100", role="creator", username="@sample"):
    return dict(chat_id=chat_id, title="测试频道", username=username, role=role,
                telegram_user_id="9001", rights={"post_messages": True, "add_admins": role == "creator"})


class ManagedChannelsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "test.db"
        self.engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        with self.Session() as db:
            db.add_all([
                Account(id=1, owner_user_id=10, name="主账号", session_path="one", enabled=True),
                Account(id=2, owner_user_id=10, name="备用账号", session_path="two", enabled=True),
                Account(id=3, owner_user_id=20, name="其他用户", session_path="three", enabled=True),
            ])
            db.commit()
        self.patch_store = patch.object(store, "SessionLocal", self.Session)
        self.patch_scan = patch.object(scanner, "SessionLocal", self.Session)
        self.patch_access = patch.object(scanner, "get_owner_runtime_access", return_value=SimpleNamespace(allowed=True))
        self.patch_store.start(); self.patch_scan.start(); self.patch_access.start()
        self.tenant = tenant_scope(10)
        self.tenant.__enter__()

    def tearDown(self):
        self.tenant.__exit__(None, None, None)
        self.patch_store.stop(); self.patch_scan.stop(); self.patch_access.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def test_discovery_is_owner_scoped_even_for_admin(self):
        store.save_scan(1, [result()])
        with tenant_scope(20):
            store.save_scan(3, [result("-100200")])
        with tenant_scope(10, is_admin=True):
            data = store.discovery_data()
            self.assertEqual([item["chat_id"] for item in data["items"]], ["-100100"])
            self.assertEqual([item["id"] for item in data["accounts"]], [1, 2])
            with self.assertRaises(PermissionError):
                store.save_scan(3, [result()])
            with self.assertRaises(ValueError):
                store.import_channels(["-100200"])
        with tenant_scope(None):
            with self.assertRaises(PermissionError):
                store.discovery_data()

    def test_multiple_accounts_merge_and_import_is_idempotent(self):
        store.save_scan(1, [result()])
        store.save_scan(2, [result(role="administrator")])
        data = store.discovery_data()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(len(data["items"][0]["managed_accounts"]), 2)
        self.assertEqual(store.import_channels(["-100100", "-100100"])["added"], 1)
        self.assertEqual(store.import_channels(["-100100"])["matched"], 1)
        with self.Session() as db:
            channel = db.query(MyChannel).one()
            self.assertEqual(channel.owner_user_id, 10)
            self.assertEqual(channel.status, "pending")
            self.assertIsNone(channel.bot_id)
            self.assertFalse(channel.bot_is_admin)

    def test_existing_channel_settings_are_preserved(self):
        with self.Session() as db:
            db.add(MyChannel(owner_user_id=10, title="我的名称", username="@sample", chat_id="",
                             status="disabled", group_name="原分组", remark="备注"))
            db.commit()
        store.save_scan(1, [result()])
        self.assertEqual(store.import_channels(["-100100"])["matched"], 1)
        with self.Session() as db:
            channel = db.query(MyChannel).one()
            self.assertEqual((channel.title, channel.status, channel.group_name, channel.remark),
                             ("我的名称", "disabled", "原分组", "备注"))
            self.assertEqual(channel.chat_id, "-100100")

    def test_failed_scan_retains_roles_and_blocks_import(self):
        store.save_scan(1, [result()])
        store.save_scan(1, error="网络断开")
        item = store.discovery_data()["items"][0]
        self.assertEqual(item["managed_accounts"][0]["role"], "creator")
        self.assertEqual(item["managed_accounts"][0]["status"], "error")
        with self.assertRaises(ValueError):
            store.import_channels(["-100100"])

    def test_full_empty_scan_retires_roles_without_deleting_channel(self):
        store.save_scan(1, [result()])
        store.import_channels(["-100100"])
        store.save_scan(1, [])
        self.assertEqual(store.discovery_data()["items"], [])
        with self.Session() as db:
            self.assertEqual(db.query(MyChannel).count(), 1)
            self.assertFalse(db.query(AccountManagedChannel).one().active)

    def test_filters_match_same_account_and_do_not_cross_owners(self):
        store.save_scan(1, [result()])
        store.save_scan(2, [result(role="administrator")])
        channel = SimpleNamespace(owner_user_id=10, chat_id="-100100", username="@sample")
        self.assertEqual(store.enrich_channels([channel], [{}], account_id=2, role="creator"), [])
        self.assertEqual(len(store.enrich_channels([channel], [{}], account_id=2, role="administrator")), 1)
        channel.owner_user_id = 20
        self.assertEqual(store.enrich_channels([channel], [{}])[0]["managed_accounts"], [])

    def test_known_chat_id_does_not_match_reassigned_username(self):
        store.save_scan(1, [result()])
        channel = SimpleNamespace(owner_user_id=10, chat_id="-100999", username="@sample")
        self.assertEqual(store.enrich_channels([channel], [{}])[0]["managed_accounts"], [])

    def test_import_rejects_reassigned_username_without_changing_existing(self):
        store.save_scan(1, [result()])
        with self.Session() as db:
            db.add(MyChannel(owner_user_id=10, chat_id="-100999", username="@sample", title="原频道"))
            db.commit()
        with self.assertRaises(ValueError):
            store.import_channels(["-100100"])
        with self.Session() as db:
            self.assertEqual(db.query(MyChannel).one().chat_id, "-100999")

    async def test_http_routes_require_auth_and_reject_foreign_accounts(self):
        from api import server
        from db import crud_my_channels
        async def request(method, url, body=None, authenticated=True):
            path, _, query = url.partition("?")
            payload = json.dumps(body).encode() if body is not None else b""
            headers = [(b"content-type", b"application/json")]
            if authenticated:
                headers.append((b"authorization", b"Bearer synthetic-unit-test"))
            messages = []
            received = False
            completed = asyncio.Event()
            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": payload, "more_body": False}
                await completed.wait()
                return {"type": "http.disconnect"}
            async def send(message):
                messages.append(message)
                if message["type"] == "http.response.body" and not message.get("more_body"):
                    completed.set()
            await server.app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                              "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
                              "query_string": query.encode(), "root_path": "", "headers": headers,
                              "client": ("127.0.0.1", 1234), "server": ("testserver", 80)}, receive, send)
            status = next(message["status"] for message in messages if message["type"] == "http.response.start")
            data = json.loads(b"".join(message.get("body", b"") for message in messages))
            return SimpleNamespace(status_code=status, json=lambda: data)
        store.save_scan(1, [result()])
        with patch.object(server, "get_user_by_session_token", return_value=({"id": 10, "role": "admin"}, 1)), \
             patch.object(server, "account_manager", SimpleNamespace(get_client=lambda _: SimpleNamespace(is_connected=lambda: True))), \
             patch.object(crud_my_channels, "SessionLocal", self.Session):
            self.assertEqual((await request("GET", "/api/my-channels/managed/discovery", authenticated=False)).status_code, 401)
            response = await request("GET", "/api/my-channels/managed/discovery")
            self.assertEqual(response.status_code, 200)
            self.assertEqual([account["id"] for account in response.json()["accounts"]], [1, 2])
            response = await request("POST", "/api/my-channels/managed/sync/3")
            self.assertEqual(response.status_code, 404)
            response = await request("POST", "/api/my-channels/managed/import", {"chat_ids": ["-100100"]})
            self.assertEqual(response.status_code, 200)
            response = await request("GET", "/api/my-channels?managed_account_id=1&managed_role=creator")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["items"]), 1)
            response = await request("POST", "/api/my-channels/managed/import", {"chat_ids": []})
            self.assertEqual(response.status_code, 422)

    def test_stale_disabled_and_offline_are_unconfirmed(self):
        store.save_scan(1, [result()])
        manager = SimpleNamespace(get_client=lambda _: None)
        self.assertEqual(store.discovery_data(manager)["items"][0]["managed_accounts"][0]["status"], "offline")
        with self.assertRaises(ValueError):
            store.import_channels(["-100100"], manager)
        with self.Session() as db:
            db.query(AccountChannelSync).one().last_success_at = datetime.utcnow() - timedelta(days=2)
            db.commit()
        self.assertEqual(store.discovery_data()["items"][0]["managed_accounts"][0]["status"], "stale")
        with self.Session() as db:
            db.query(Account).filter_by(id=1).one().enabled = False
            db.commit()
        self.assertEqual(store.discovery_data()["items"][0]["managed_accounts"][0]["status"], "disabled")

    async def test_live_scan_filters_channels_and_maps_actual_rights(self):
        def channel(id, **kwargs):
            return types.Channel(id=id, title=f"频道{id}", photo=types.ChatPhotoEmpty(),
                                 date=datetime.now(), broadcast=True, **kwargs)
        entities = [channel(100, creator=True), channel(200, admin_rights=types.ChatAdminRights(post_messages=True)),
                    channel(300), channel(400, left=True, creator=True),
                    types.Channel(id=500, title="群组", photo=types.ChatPhotoEmpty(), date=datetime.now(),
                                  megagroup=True, creator=True)]
        class Client:
            def is_connected(self): return True
            async def get_me(self): return SimpleNamespace(id=9001)
            async def iter_dialogs(self, limit=None):
                for entity in entities: yield SimpleNamespace(entity=entity)
        response = await scanner.sync_account(1, SimpleNamespace(get_client=lambda _: Client()))
        self.assertTrue(response["ok"])
        self.assertEqual(response["count"], 2)
        items = {item["chat_id"]: item for item in store.discovery_data()["items"]}
        self.assertEqual(items["-1000000000100"]["managed_accounts"][0]["role"], "creator")
        admin = items["-1000000000200"]["managed_accounts"][0]
        self.assertEqual(admin["role"], "administrator")
        self.assertTrue(admin["rights"]["post_messages"])
        self.assertFalse(admin["rights"]["add_admins"])

    async def test_partial_scan_failure_does_not_replace_old_snapshot(self):
        store.save_scan(1, [result()])
        class Client:
            def is_connected(self): return True
            async def get_me(self): return SimpleNamespace(id=9001)
            async def iter_dialogs(self, limit=None):
                yield SimpleNamespace(entity=types.Channel(id=200, title="新频道", creator=True,
                    broadcast=True, photo=types.ChatPhotoEmpty(), date=datetime.now()))
                raise RuntimeError("网络断开")
        response = await scanner.sync_account(1, SimpleNamespace(get_client=lambda _: Client()))
        self.assertFalse(response["ok"])
        self.assertEqual([item["chat_id"] for item in store.discovery_data()["items"]], ["-100100"])

    async def test_foreign_account_never_accesses_runtime_client(self):
        with tenant_scope(10, is_admin=True):
            manager = SimpleNamespace(get_client=lambda _: self.fail("cross-owner client used"))
            with self.assertRaises(PermissionError):
                await scanner.sync_account(3, manager)

    async def test_offline_account_records_failure(self):
        response = await scanner.sync_account(1, SimpleNamespace(get_client=lambda _: None))
        self.assertFalse(response["ok"])
        self.assertIn("未连接", response["message"])


class ManagedChannelMigrationTest(unittest.TestCase):
    def test_backup_precedes_schema_change_and_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.db"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE sentinel (value TEXT)")
                db.execute("INSERT INTO sentinel VALUES ('preserved')")
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            try:
                backup = migrate(engine)
                self.assertTrue(backup.exists())
                with closing(sqlite3.connect(backup)) as db:
                    self.assertEqual(db.execute("SELECT value FROM sentinel").fetchone()[0], "preserved")
                    self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='account_managed_channels'").fetchone())
                self.assertTrue(inspect(engine).has_table("account_managed_channels"))
                self.assertIsNone(migrate(engine))
            finally:
                engine.dispose()
