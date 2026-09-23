import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.tenant import tenant_scope
from db import channel_overview, crud_my_channels
from db.models import (
    Account,
    Base,
    BotAccount,
    CloneTask,
    ListenerTask,
    MyChannel,
    SearchBot,
    SearchBotChannelSubmission,
    SentMessage,
    TaskChannelLink,
)
from migrate_task_channel_links import migrate


class ChannelOverviewTests(unittest.TestCase):
    def setUp(self):
        self.database_dir = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{(Path(self.database_dir.name) / 'overview.db').as_posix()}")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        self.patches = [
            patch.object(channel_overview, "SessionLocal", self.factory),
            patch.object(crud_my_channels, "SessionLocal", self.factory),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.engine.dispose()
        self.database_dir.cleanup()

    def test_links_survive_rename_and_overview_stays_with_owner(self):
        with self.factory() as db:
            channel = MyChannel(owner_user_id=1, title="资讯", username="@news_old", chat_id="-100123")
            other_channel = MyChannel(owner_user_id=2, title="他人", username="@news_old", chat_id="-100999")
            bot = BotAccount(owner_user_id=1, name="发布 Bot", username="@publisher", token="test-only")
            account = Account(owner_user_id=1, name="采集账号", session_path="test-one.session")
            other_account = Account(owner_user_id=2, name="他人账号", session_path="test-two.session")
            db.add_all([account, other_account])
            db.flush()
            search_bot = SearchBot(owner_user_id=1, name="搜索 Bot", username="@searcher")
            task = CloneTask(
                owner_user_id=1, name="克隆资讯", source_channel="@source",
                target_channels=json.dumps(["https://t.me/news_old"]), bot_id=None,
                status="running", last_message_id=42, account_id=account.id,
            )
            other_task = CloneTask(
                owner_user_id=2, name="他人任务", source_channel="@source",
                target_channels=json.dumps(["@news_old"]), account_id=other_account.id,
            )
            db.add_all([channel, other_channel, bot, search_bot, task, other_task])
            db.flush()
            task.bot_id = bot.id
            channel.bot_id = bot.id
            channel_id, task_id = channel.id, task.id
            channel_overview.reconcile_task_links(db, "clone", task)
            channel_overview.reconcile_task_links(db, "clone", other_task)
            db.add(SentMessage(owner_user_id=1, task_id=task.id, source_message_id=40))
            db.add_all([
                SearchBotChannelSubmission(
                    owner_user_id=1, my_channel_id=channel.id, search_bot_id=search_bot.id,
                    collection_status="collected", is_current=False,
                ),
                SearchBotChannelSubmission(
                    owner_user_id=1, my_channel_id=channel.id, search_bot_id=search_bot.id,
                    review_status="reviewing", collection_status="not_collected", is_current=False,
                ),
            ])
            db.commit()

            channel.username = "@news_new"
            channel_overview.reconcile_task_links(db, "clone", task)
            db.commit()
            links = db.query(TaskChannelLink).filter(TaskChannelLink.task_id == task_id).all()
            self.assertEqual([(link.my_channel_id, link.role) for link in links], [(channel_id, "target")])

        overview = channel_overview.get_channel_overview(channel_id)
        self.assertEqual(overview["collection_status"], "审核中")
        self.assertEqual([task["name"] for task in overview["tasks"]], ["克隆资讯"])
        self.assertEqual(overview["tasks"][0]["sent_count"], 1)
        self.assertEqual(overview["tasks"][0]["last_message_id"], 42)
        self.assertEqual([bot["name"] for bot in overview["bots"]], ["发布 Bot"])
        self.assertEqual(crud_my_channels.get_channel_collection_status_map([channel_id])[channel_id], "审核中")
        hidden = channel_overview.get_channel_overview(channel_id, include_clone=False)
        self.assertEqual(hidden["tasks"], [])
        self.assertFalse(hidden["permissions"]["clone_tasks"])

        with tenant_scope(2):
            self.assertIsNone(channel_overview.get_channel_overview(channel_id))

    def test_migration_backs_up_existing_database_and_backfills(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "channels.db"
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            for table in (MyChannel.__table__, CloneTask.__table__, ListenerTask.__table__):
                table.create(engine)
            factory = sessionmaker(bind=engine)
            with factory() as db:
                db.add(MyChannel(owner_user_id=7, username="@channel"))
                db.add(CloneTask(owner_user_id=7, name="旧任务", source_channel="@source", target_channels='["@channel"]'))
                db.commit()

            backup = migrate(engine)
            self.assertTrue(backup and backup.exists())
            with factory() as db:
                links = db.query(TaskChannelLink).all()
                self.assertEqual([(row.owner_user_id, row.role) for row in links], [(7, "target")])
                db.query(TaskChannelLink).delete()
                db.commit()
            self.assertIsNone(migrate(engine))
            with factory() as db:
                self.assertEqual(db.query(TaskChannelLink).count(), 1)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
