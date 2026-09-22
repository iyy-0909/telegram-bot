import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import crud_listener
from db.models import ListenerSentMessage, ListenerTask


def make_clone_task(**overrides):
    values = {
        "id": 28,
        "owner_user_id": 1,
        "name": "测试克隆任务",
        "source_channel": "@source",
        "target_channels": '["@target"]',
        "account_id": 3,
        "bot_id": 1,
        "enable_listener": True,
        "status": "idle",
        "blocked_keywords": "[]",
        "replace_words": "{}",
        "footer": "",
        "remove_contact_lines": True,
        "filter_qr_code": True,
        "use_random_head": False,
        "use_random_body": False,
        "use_random_footer": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class CloneListenerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ListenerTask.__table__.create(self.engine)
        ListenerSentMessage.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def sync(self, task):
        with patch.object(crud_listener, "SessionLocal", self.session_factory):
            return crud_listener.sync_clone_task_to_listener_tasks(task)

    def get_listener(self):
        db = self.session_factory()
        try:
            return (
                db.query(ListenerTask)
                .filter(ListenerTask.clone_task_id == 28)
                .first()
            )
        finally:
            db.close()

    def create_listener(self, **overrides):
        values = {
            "owner_user_id": 1,
            "name": "direct listener",
            "source_channel": "@source",
            "target_channels": '["@target"]',
            "account_id": 3,
            "enabled": True,
            "status": "running",
        }
        values.update(overrides)
        with patch.object(crud_listener, "SessionLocal", self.session_factory):
            return crud_listener.create_listener_task(values)

    def test_listener_is_not_created_before_clone_finishes(self):
        result = self.sync(make_clone_task(status="running"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["created"], 0)
        self.assertIsNone(self.get_listener())

    def test_listener_is_created_after_clone_finishes(self):
        result = self.sync(make_clone_task(status="done"))
        listener = self.get_listener()

        self.assertEqual(result["created"], 1)
        self.assertIsNotNone(listener)
        self.assertTrue(listener.enabled)
        self.assertEqual(listener.status, "running")

    def test_same_channel_clone_finishes_without_creating_listener(self):
        result = self.sync(make_clone_task(
            status="done",
            source_channel="@source",
            target_channels='["https://t.me/SOURCE"]',
        ))

        self.assertFalse(result["ok"])
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["skipped_same_channel_targets"], ["https://t.me/SOURCE"])
        self.assertIsNone(self.get_listener())

    def test_same_channel_target_is_skipped_when_other_targets_exist(self):
        result = self.sync(make_clone_task(
            status="done",
            source_channel="@source",
            target_channels='["@source", "@target"]',
        ))
        listener = self.get_listener()

        self.assertTrue(result["ok"])
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped_same_channel_targets"], ["@source"])
        self.assertEqual(json.loads(listener.target_channels), ["@target"])

    def test_direct_listener_rejects_same_channel_in_different_formats(self):
        with self.assertRaisesRegex(ValueError, "源频道不能同时作为目标频道"):
            self.create_listener(
                source_channel="@Source",
                target_channels='["https://t.me/source"]',
            )

    def test_listener_update_rejects_same_channel(self):
        task = self.create_listener()

        with patch.object(crud_listener, "SessionLocal", self.session_factory):
            with self.assertRaisesRegex(ValueError, "源频道不能同时作为目标频道"):
                crud_listener.update_listener_task(
                    task.id,
                    {"target_channels": '["t.me/source"]'},
                )

    def test_restarted_clone_suspends_existing_listener_without_deleting_it(self):
        self.sync(make_clone_task(status="done"))
        existing = self.get_listener()
        existing_id = existing.id

        result = self.sync(make_clone_task(status="running"))
        listener = self.get_listener()

        self.assertEqual(result["suspended"], 1)
        self.assertEqual(listener.id, existing_id)
        self.assertFalse(listener.enabled)
        self.assertEqual(listener.status, "waiting_clone")


if __name__ == "__main__":
    unittest.main()
