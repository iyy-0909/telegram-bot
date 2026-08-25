import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import crud_my_channels
from db.models import MyChannel, SearchBotChannelSubmission


class MyChannelSearchTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        MyChannel.__table__.create(self.engine)
        SearchBotChannelSubmission.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        db = self.session_factory()
        try:
            db.add_all(
                [
                    MyChannel(
                        title="上海频道 A",
                        username="@shanghaiktval",
                        chat_id="-100000001",
                    ),
                    MyChannel(
                        title="上海频道 B",
                        username="@shanghaiktvyl",
                        chat_id="-100000002",
                        clone_status="克隆完成--源频道 @shanghaiktval",
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.engine.dispose()

    def test_hidden_status_does_not_match_keyword(self):
        with patch.object(
            crud_my_channels,
            "SessionLocal",
            self.session_factory,
        ):
            rows = crud_my_channels.list_my_channels(keyword="shanghaiktval")

        self.assertEqual([row.username for row in rows], ["@shanghaiktval"])

    def test_telegram_link_matches_username(self):
        with patch.object(
            crud_my_channels,
            "SessionLocal",
            self.session_factory,
        ):
            rows = crud_my_channels.list_my_channels(
                keyword="https://t.me/shanghaiktval"
            )

        self.assertEqual([row.username for row in rows], ["@shanghaiktval"])

    def test_telegram_link_is_normalized_to_username(self):
        self.assertEqual(
            crud_my_channels.normalize_username("https://t.me/xianktv1"),
            "@xianktv1",
        )

    def test_collection_status_shows_reviewing_when_any_submission_is_reviewing(self):
        db = self.session_factory()
        try:
            db.add(SearchBotChannelSubmission(
                search_bot_id=1,
                my_channel_id=1,
                review_status="reviewing",
                collection_status="unknown",
            ))
            db.commit()
        finally:
            db.close()

        with patch.object(crud_my_channels, "SessionLocal", self.session_factory):
            statuses = crud_my_channels.get_channel_collection_status_map([1, 2])

        self.assertEqual(statuses[1], "审核中")
        self.assertEqual(statuses[2], "未收录")

    def test_collected_status_has_priority_over_reviewing(self):
        db = self.session_factory()
        try:
            db.add_all([
                SearchBotChannelSubmission(
                    search_bot_id=1,
                    my_channel_id=1,
                    review_status="reviewing",
                    collection_status="unknown",
                ),
                SearchBotChannelSubmission(
                    search_bot_id=2,
                    my_channel_id=1,
                    review_status="approved",
                    collection_status="collected",
                ),
            ])
            db.commit()
        finally:
            db.close()

        with patch.object(crud_my_channels, "SessionLocal", self.session_factory):
            statuses = crud_my_channels.get_channel_collection_status_map([1])

        self.assertEqual(statuses[1], "已收录")

    def test_auto_check_only_fills_empty_identity_fields(self):
        with patch.object(crud_my_channels, "SessionLocal", self.session_factory):
            updated = crud_my_channels.set_my_channel_check_result(
                1,
                {
                    "title": "Telegram 返回的频道名",
                    "username": "@detected_name",
                    "chat_id": "-100999999",
                    "channel_type": "channel",
                    "member_count": 321,
                },
                fill_empty_only_fields={"title", "username", "chat_id", "channel_type"},
            )

        self.assertEqual(updated.title, "上海频道 A")
        self.assertEqual(updated.username, "@shanghaiktval")
        self.assertEqual(updated.chat_id, "-100000001")
        self.assertEqual(updated.channel_type, "channel")
        self.assertEqual(updated.member_count, 321)

    def test_auto_check_preserves_disabled_status(self):
        db = self.session_factory()
        try:
            channel = db.query(MyChannel).filter(MyChannel.id == 1).first()
            channel.status = "disabled"
            db.commit()
        finally:
            db.close()

        with patch.object(crud_my_channels, "SessionLocal", self.session_factory):
            updated = crud_my_channels.set_my_channel_check_result(
                1,
                {"status": "enabled", "last_error": ""},
                preserve_disabled_status=True,
            )

        self.assertEqual(updated.status, "disabled")


if __name__ == "__main__":
    unittest.main()
