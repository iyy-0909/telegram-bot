import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from telethon.tl.functions.channels import EditAdminRequest, InviteToChannelRequest
from telethon.tl.types import ChatAdminRights

from bot.search_bot_submissions import add_search_bot_as_channel_admin
from db import crud_search_bots
from db.models import MyChannel, SearchBot, SearchBotChannelSubmission


class FakeEntity:
    def __init__(self, *, bot=False, broadcast=False, megagroup=False, forum=False):
        self.bot = bot
        self.broadcast = broadcast
        self.megagroup = megagroup
        self.forum = forum


class FakeParticipant:
    def __init__(self, rights):
        self.admin_rights = rights


class FakePermissions:
    def __init__(self, rights=None, is_admin=False):
        self.is_admin = is_admin
        self.is_creator = False
        self.participant = FakeParticipant(rights) if rights else None


class FakeClient:
    def __init__(self, channel):
        self.channel = channel
        self.bot = FakeEntity(bot=True)
        self.requests = []
        self.applied_rights = None

    async def get_entity(self, reference):
        return self.bot if str(reference).startswith("@bot") else self.channel

    async def get_permissions(self, channel, bot):
        if self.applied_rights is None:
            raise ValueError("USER_NOT_PARTICIPANT")
        return FakePermissions(self.applied_rights, is_admin=True)

    async def __call__(self, request):
        self.requests.append(request)
        if isinstance(request, EditAdminRequest):
            specific_rights = [
                field
                for field in (
                    "change_info",
                    "post_messages",
                    "edit_messages",
                    "delete_messages",
                    "ban_users",
                    "invite_users",
                    "pin_messages",
                    "add_admins",
                    "anonymous",
                    "manage_call",
                    "manage_topics",
                    "post_stories",
                    "edit_stories",
                    "delete_stories",
                    "manage_direct_messages",
                    "manage_ranks",
                )
                if getattr(request.admin_rights, field, False)
            ]
            if request.admin_rights.other and specific_rights:
                raise ValueError("wrong rights combination")
            self.applied_rights = request.admin_rights
        return True


class SearchBotSubmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_channel_adds_bot_directly_as_admin(self):
        client = FakeClient(FakeEntity(broadcast=True))

        result = await add_search_bot_as_channel_admin(
            client,
            "@target_channel",
            "@bot_search",
            {
                "post_messages": True,
                "ban_users": True,
                "pin_messages": True,
                "anonymous": True,
                "manage_topics": True,
                "manage_ranks": True,
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["channel_kind"], "broadcast")
        self.assertFalse(any(isinstance(item, InviteToChannelRequest) for item in client.requests))
        self.assertTrue(any(isinstance(item, EditAdminRequest) for item in client.requests))
        self.assertTrue(result["applicable_rights"]["ban_users"])
        self.assertEqual(
            set(result["ignored_rights"]),
            {"pin_messages", "anonymous", "manage_topics", "manage_ranks"},
        )
        edit_request = next(item for item in client.requests if isinstance(item, EditAdminRequest))
        self.assertFalse(edit_request.admin_rights.other)

    async def test_megagroup_keeps_invite_then_promote_flow(self):
        client = FakeClient(FakeEntity(megagroup=True))

        result = await add_search_bot_as_channel_admin(
            client,
            "@target_group",
            "@bot_search",
            {"delete_messages": True},
        )

        self.assertTrue(result["ok"])
        self.assertIsInstance(client.requests[0], InviteToChannelRequest)
        self.assertIsInstance(client.requests[1], EditAdminRequest)

    async def test_forum_allows_topic_and_story_permissions(self):
        client = FakeClient(FakeEntity(megagroup=True, forum=True))

        result = await add_search_bot_as_channel_admin(
            client,
            "@target_forum",
            "@bot_search",
            {
                "manage_topics": True,
                "post_stories": True,
                "post_messages": True,
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["applicable_rights"]["manage_topics"])
        self.assertTrue(result["applicable_rights"]["post_stories"])
        self.assertFalse(result["applicable_rights"]["post_messages"])


class ManualSubmissionAccountTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SearchBot.__table__.create(self.engine)
        MyChannel.__table__.create(self.engine)
        SearchBotChannelSubmission.__table__.create(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        db = self.session_factory()
        try:
            db.add(SearchBot(id=1, name="搜索机器人", username="@search_bot"))
            db.add(MyChannel(
                id=1,
                title="上海频道",
                username="@shanghai_channel",
                group_name="上海",
                status="enabled",
            ))
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.engine.dispose()

    def test_manual_account_id_is_stored_separately(self):
        with patch.object(
            crud_search_bots,
            "SessionLocal",
            self.session_factory,
        ):
            item = crud_search_bots.create_submission(
                1,
                1,
                None,
                "https://t.me/shanghai_channel",
                manual_account_id="5397112677",
                submit_status="manual",
            )

        self.assertIsNone(item["account_id"])
        self.assertEqual(item["manual_account_id"], "5397112677")


if __name__ == "__main__":
    unittest.main()
