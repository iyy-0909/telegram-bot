import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth.tenant import tenant_scope
from bot.channel_activity import refresh_channel_activity, register_channel_activity
from db import channel_activity
from db.models import Account, BotAccount, MyChannel
from migrate_channel_activity import migrate


class ChannelActivityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool,
                                    connect_args={"check_same_thread": False})
        MyChannel.__table__.create(self.engine)
        BotAccount.__table__.create(self.engine)
        Account.__table__.create(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([MyChannel(id=1, owner_user_id=1, username="@demo", chat_id="-1001"),
                        MyChannel(id=2, owner_user_id=2, username="@demo", chat_id="-1001")])
            db.commit()
        self.patcher = patch.object(channel_activity, "SessionLocal", self.factory)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    def test_five_day_boundary_and_unknown(self):
        now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        self.assertEqual(channel_activity.activity_fields(None, now)["update_status"], "unknown")
        boundary = now - timedelta(days=5)
        self.assertEqual(channel_activity.activity_fields(boundary, now)["update_status"], "enabled")
        self.assertEqual(channel_activity.activity_fields(boundary - timedelta(seconds=1), now)["update_status"], "error")
        self.assertEqual(channel_activity.activity_fields(boundary.astimezone(timezone(timedelta(hours=8))), now),
                         channel_activity.activity_fields(boundary.replace(tzinfo=None), now))

    def test_out_of_order_events_and_owner_isolation(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(channel_activity.record_channel_content(1, username="DEMO", date=now), 1)
        self.assertEqual(channel_activity.record_channel_content(1, chat_id="-1001", date=now - timedelta(days=8)), 0)
        self.assertEqual(channel_activity.record_channel_content(None, chat_id="-1001", date=now), 0)
        with self.factory() as db:
            self.assertEqual(db.get(MyChannel, 1).last_content_at, now.replace(tzinfo=None))
            self.assertIsNone(db.get(MyChannel, 2).last_content_at)

    def test_bot_response_tracks_album_for_token_owner_only(self):
        with self.factory() as db:
            db.add(BotAccount(owner_user_id=1, name="test", token="test-token"))
            db.commit()
        channel_activity.record_bot_content("test-token", [
            {"chat": {"id": -1001, "type": "channel"}, "date": 1700000000},
            {"chat": {"id": -1001, "type": "channel"}, "date": 1700000001},
        ])
        with self.factory() as db:
            self.assertEqual(db.get(MyChannel, 1).last_content_at,
                             datetime.fromtimestamp(1700000001, timezone.utc).replace(tzinfo=None))
            self.assertIsNone(db.get(MyChannel, 2).last_content_at)

    def test_tracking_failure_does_not_retry_successful_send(self):
        from bot import bot_sender
        response = {"ok": True, "result": {"chat": {"id": -1001, "type": "channel"}, "date": 1700000000}}
        with patch.object(bot_sender.requests, "Session") as session, patch.object(channel_activity, "record_bot_content", side_effect=RuntimeError("test")):
            session.return_value.post.return_value.json.return_value = response
            self.assertEqual(bot_sender.request_post("test-token", "sendMessage"), response)
            self.assertEqual(session.return_value.post.call_count, 1)

    def test_editing_message_does_not_record_content(self):
        from bot import bot_sender
        with patch.object(bot_sender.requests, "Session") as session, patch.object(channel_activity, "record_bot_content") as record:
            session.return_value.post.return_value.json.return_value = {"ok": True}
            bot_sender.request_post("test-token", "editMessageText")
            record.assert_not_called()

    def test_channel_metadata_cannot_overwrite_content_timestamp(self):
        from db import crud_my_channels
        date = datetime(2026, 9, 1)
        channel_activity.record_channel_content(1, chat_id="-1001", date=date)
        with patch.object(crud_my_channels, "SessionLocal", self.factory), tenant_scope(1):
            updated = crud_my_channels.update_my_channel(1, {
                "title": "new title", "last_content_at": datetime(2026, 9, 21),
                "update_status": "enabled",
            })
            self.assertEqual(updated.last_content_at, date)
            self.assertEqual(crud_my_channels.my_channel_to_dict(updated)["update_status"], "error")


class ActivityObservationTest(unittest.IsolatedAsyncioTestCase):
    async def test_service_event_ignored_and_post_recorded(self):
        client = Mock()
        register_channel_activity(client, 1)
        handler = client.add_event_handler.call_args.args[0]
        event = SimpleNamespace(is_channel=True, chat_id=-1001, chat=SimpleNamespace(username="demo"),
                                message=SimpleNamespace(action="pin", date=datetime.now(timezone.utc)))
        with patch("bot.channel_activity.record_channel_content") as record:
            await handler(event)
            record.assert_not_called()
            event.message.action = None
            await handler(event)
            record.assert_called_once()

    async def test_detection_skips_service_messages_and_other_owners(self):
        engine = create_engine("sqlite://", poolclass=StaticPool)
        Account.__table__.create(engine)
        factory = sessionmaker(bind=engine)
        with factory() as db:
            db.add_all([Account(id=1, owner_user_id=1, name="one", session_path="test-one", enabled=True),
                        Account(id=2, owner_user_id=2, name="two", session_path="test-two", enabled=True)])
            db.commit()
        date = datetime.now(timezone.utc) - timedelta(days=6)
        client = SimpleNamespace(get_messages=AsyncMock(return_value=[
            SimpleNamespace(date=datetime.now(timezone.utc), action="pin"),
            SimpleNamespace(date=date, action=None, message="content"),
        ]))
        manager = SimpleNamespace(get_client=Mock(return_value=client))
        with patch("bot.channel_activity.SessionLocal", factory), patch("bot.channel_activity.record_channel_content") as record:
            await refresh_channel_activity(SimpleNamespace(id=1, owner_user_id=1, username="@demo", chat_id="-1001"), manager)
            manager.get_client.assert_called_once_with(1)
            self.assertEqual(record.call_args.kwargs["date"], date)
        engine.dispose()


class ActivityMigrationTest(unittest.TestCase):
    def test_backup_precedes_migration_and_repeat_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activity.db"
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE my_channels (id INTEGER PRIMARY KEY, title TEXT)"))
                connection.execute(text("INSERT INTO my_channels VALUES (1, 'original')"))
            backup = migrate(engine)
            self.assertTrue(backup.exists())
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("SELECT title FROM my_channels").fetchone()[0], "original")
                self.assertNotIn("last_content_at", [row[1] for row in db.execute("PRAGMA table_info(my_channels)")])
            self.assertIn("last_content_at", {column["name"] for column in inspect(engine).get_columns("my_channels")})
            self.assertIsNone(migrate(engine))
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
