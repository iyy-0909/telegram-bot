import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import crud, crud_clone
from db.models import Account, CloneTask


class DefaultCloneAccountTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Account.__table__.create(self.engine)
        CloneTask.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        db = self.session_factory()
        try:
            db.add_all([
                Account(
                    id=1,
                    name="账号一",
                    session_path="data/sessions/one",
                    enabled=True,
                    is_default=True,
                ),
                Account(
                    id=2,
                    name="账号二",
                    session_path="data/sessions/two",
                    enabled=True,
                    is_default=False,
                ),
            ])
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.engine.dispose()

    def test_clone_task_uses_default_account_when_omitted(self):
        with patch.object(crud_clone, "SessionLocal", self.session_factory):
            task = crud_clone.create_clone_task({
                "name": "默认账号任务",
                "source_channel": "@source",
                "target_channels": '["@target"]',
            })

        self.assertEqual(task.account_id, 1)

    def test_explicit_account_overrides_default(self):
        with patch.object(crud_clone, "SessionLocal", self.session_factory):
            task = crud_clone.create_clone_task({
                "name": "指定账号任务",
                "source_channel": "@source",
                "target_channels": '["@target"]',
                "account_id": 2,
            })

        self.assertEqual(task.account_id, 2)

    def test_setting_default_clears_previous_default(self):
        with patch.object(crud, "SessionLocal", self.session_factory):
            account = crud.update_account(2, {"is_default": True})
            accounts = crud.get_all_accounts()

        self.assertTrue(account.is_default)
        self.assertTrue(account.enabled)
        self.assertEqual(
            [item.id for item in accounts if item.is_default],
            [2],
        )

    def test_missing_default_returns_readable_error(self):
        db = self.session_factory()
        try:
            db.query(Account).update({Account.is_default: False})
            db.commit()
        finally:
            db.close()

        with patch.object(crud_clone, "SessionLocal", self.session_factory):
            with self.assertRaisesRegex(ValueError, "全局默认账号"):
                crud_clone.create_clone_task({
                    "name": "无默认账号任务",
                    "source_channel": "@source",
                    "target_channels": '["@target"]',
                })


if __name__ == "__main__":
    unittest.main()
