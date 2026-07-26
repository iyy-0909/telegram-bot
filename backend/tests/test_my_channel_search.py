import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import crud_my_channels
from db.models import MyChannel


class MyChannelSearchTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        MyChannel.__table__.create(self.engine)
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


if __name__ == "__main__":
    unittest.main()
