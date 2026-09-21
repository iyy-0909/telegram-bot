import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.tenant import tenant_scope
from db import crud
from db import crud_support
from db.models import (
    Account,
    BotAccount,
    CloneTask,
    SupportBot,
    SupportSetting,
    SupportTag,
    SystemSetting,
    UserAccount,
)


class TenantIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "tenant.db"
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
            BotAccount.__table__,
            CloneTask.__table__,
            SystemSetting.__table__,
            SupportSetting.__table__,
            SupportTag.__table__,
            SupportBot.__table__,
        ):
            table.create(bind=self.engine)

        db = self.session_local()
        try:
            users = [
                UserAccount(username="tenant_one", password_hash="hash"),
                UserAccount(username="tenant_two", password_hash="hash"),
            ]
            db.add_all(users)
            db.flush()
            self.owner_one = users[0].id
            self.owner_two = users[1].id
            accounts = [
                Account(
                    owner_user_id=self.owner_one,
                    name="one",
                    session_path="one.session",
                ),
                Account(
                    owner_user_id=self.owner_two,
                    name="two",
                    session_path="two.session",
                ),
            ]
            db.add_all(accounts)
            db.commit()
            self.account_one = accounts[0].id
            self.account_two = accounts[1].id
        finally:
            db.close()

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_select_update_and_owner_assignment_are_tenant_scoped(self):
        with tenant_scope(self.owner_one):
            db = self.session_local()
            try:
                self.assertEqual(
                    [row.name for row in db.query(Account).order_by(Account.id).all()],
                    ["one"],
                )
                setting = SystemSetting(key="ai_model", value="one-model")
                db.add(setting)
                db.query(Account).update({Account.enabled: False})
                db.commit()
                self.assertEqual(setting.owner_user_id, self.owner_one)
            finally:
                db.close()

        with tenant_scope(self.owner_two):
            db = self.session_local()
            try:
                self.assertEqual(
                    [row.name for row in db.query(Account).order_by(Account.id).all()],
                    ["two"],
                )
                self.assertTrue(db.query(Account).one().enabled)
                self.assertEqual(db.query(SystemSetting).count(), 0)
            finally:
                db.close()

    def test_cross_tenant_task_reference_is_rejected(self):
        with tenant_scope(self.owner_one):
            db = self.session_local()
            try:
                db.add(CloneTask(
                    name="invalid",
                    source_channel="@source",
                    target_channels='["@target"]',
                    account_id=self.account_two,
                ))
                with self.assertRaises(PermissionError):
                    db.commit()
                db.rollback()
            finally:
                db.close()

    def test_admin_can_inspect_all_but_new_rows_keep_admin_owner(self):
        with tenant_scope(self.owner_one, is_admin=True):
            db = self.session_local()
            try:
                self.assertEqual(db.query(Account).count(), 2)
                setting = SystemSetting(key="admin_only", value="1")
                db.add(setting)
                db.commit()
                self.assertEqual(setting.owner_user_id, self.owner_one)
            finally:
                db.close()

    def test_admin_default_account_changes_only_the_resource_owner(self):
        db = self.session_local()
        try:
            db.query(Account).update(
                {Account.is_default: True},
                synchronize_session=False,
            )
            db.commit()
        finally:
            db.close()

        generated = f"data/sessions/user_{self.owner_one}/" + "a" * 32
        with patch.object(crud, "SessionLocal", self.session_local), patch.object(
            crud,
            "generate_owner_session_path",
            return_value=generated,
        ):
            with tenant_scope(self.owner_one, is_admin=True):
                created = crud.create_account(
                    name="one-new-default",
                    is_default=True,
                )
                self.assertEqual(created.owner_user_id, self.owner_one)

                crud.update_account(
                    self.account_one,
                    {
                        "is_default": True,
                        "session_path": "data/sessions/user_2/attacker-choice",
                    },
                )

        db = self.session_local()
        try:
            owner_one_defaults = db.query(Account).filter(
                Account.owner_user_id == self.owner_one,
                Account.is_default.is_(True),
            ).all()
            owner_two_account = db.query(Account).filter(
                Account.id == self.account_two,
            ).one()
            self.assertEqual([row.id for row in owner_one_defaults], [self.account_one])
            self.assertEqual(owner_one_defaults[0].session_path, "one.session")
            self.assertTrue(owner_two_account.is_default)
        finally:
            db.close()

    def test_tenant_support_defaults_do_not_copy_environment_secrets(self):
        with patch.object(crud_support, "SessionLocal", self.session_local), patch.dict(
            crud_support.DEFAULT_SUPPORT_SETTINGS,
            {
                "support_bot_token": "123456:environment-secret",
                "support_group_chat_id": "-100123456",
            },
        ):
            with tenant_scope(self.owner_one):
                crud_support.ensure_support_defaults()
                self.assertEqual(crud_support.get_support_setting("support_bot_token"), "")
                self.assertEqual(crud_support.get_support_setting("support_group_chat_id"), "")

            with tenant_scope(self.owner_two):
                crud_support.ensure_support_defaults()
                crud_support.set_support_setting("welcome_message", "tenant two")
                self.assertEqual(
                    crud_support.get_support_setting("welcome_message"),
                    "tenant two",
                )

            with tenant_scope(self.owner_one):
                self.assertNotEqual(
                    crud_support.get_support_setting("welcome_message"),
                    "tenant two",
                )

            db = self.session_local()
            try:
                self.assertEqual(
                    db.query(SupportSetting)
                    .filter(SupportSetting.owner_user_id.is_(None))
                    .count(),
                    0,
                )
                self.assertEqual(db.query(SupportBot).count(), 2)
            finally:
                db.close()

    def test_global_support_listing_never_creates_ownerless_defaults(self):
        with patch.object(crud_support, "SessionLocal", self.session_local):
            self.assertFalse(crud_support.ensure_support_defaults())
            self.assertEqual(crud_support.list_support_bots(), [])

        db = self.session_local()
        try:
            self.assertEqual(db.query(SupportSetting).count(), 0)
            self.assertEqual(db.query(SupportTag).count(), 0)
            self.assertEqual(db.query(SupportBot).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
