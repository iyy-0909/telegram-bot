import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from accounts.session_storage import (
    SessionPathError,
    generate_owner_session_path,
    resolve_owner_session_path,
)
from bot.account_login import AccountLoginManager, PendingAccountLogin


class FakeClient:
    def __init__(self):
        self.disconnected = False
        self.sign_in_calls = 0

    async def disconnect(self):
        self.disconnected = True

    async def sign_in(self, *_args, **_kwargs):
        self.sign_in_calls += 1


class AccountSessionStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backend_dir = Path(self.temp_dir.name) / "backend"
        self.storage_root = self.backend_dir / "data" / "sessions"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generated_path_is_unguessable_and_owner_scoped(self):
        stored = generate_owner_session_path(
            42,
            backend_dir=self.backend_dir,
            storage_root=self.storage_root,
        )
        self.assertRegex(
            stored,
            re.compile(r"^data/sessions/user_42/[0-9a-f]{32}$"),
        )
        resolved = resolve_owner_session_path(
            42,
            stored,
            backend_dir=self.backend_dir,
            storage_root=self.storage_root,
        )
        self.assertEqual(resolved.parent, (self.storage_root / "user_42").resolve())

    def test_owner_path_resolution_rejects_traversal_and_other_owner(self):
        with self.assertRaises(SessionPathError):
            resolve_owner_session_path(
                42,
                "data/sessions/user_41/not-mine",
                backend_dir=self.backend_dir,
                storage_root=self.storage_root,
            )
        with self.assertRaises(SessionPathError):
            resolve_owner_session_path(
                42,
                "data/sessions/user_42/../user_41/not-mine",
                backend_dir=self.backend_dir,
                storage_root=self.storage_root,
            )


class PendingLoginIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_and_cancel_hide_other_tenants_pending_login(self):
        manager = AccountLoginManager()
        client = FakeClient()
        manager.sessions["private-login"] = PendingAccountLogin(
            login_id="private-login",
            client=client,
            phone="+10000000000",
            name="private",
            session_path="data/sessions/user_7/0123456789abcdef0123456789abcdef",
            proxy="",
            remark="",
            account_id=None,
            owner_user_id=7,
            created_at=datetime.utcnow(),
        )

        result = await manager.verify_code(
            login_id="private-login",
            code="12345",
            owner_user_id=8,
        )
        self.assertEqual(result["code"], "login_not_found")
        self.assertEqual(client.sign_in_calls, 0)
        self.assertIn("private-login", manager.sessions)

        self.assertFalse(
            await manager.cancel("private-login", owner_user_id=8)
        )
        self.assertFalse(client.disconnected)
        self.assertTrue(
            await manager.cancel("private-login", owner_user_id=7)
        )
        self.assertTrue(client.disconnected)
        self.assertNotIn("private-login", manager.sessions)


if __name__ == "__main__":
    unittest.main()
