import unittest
from unittest.mock import patch

from auth.tenant import tenant_scope
from bot import support_bot


def group_chat(chat_id, title):
    return {
        "id": chat_id,
        "title": title,
        "type": "supergroup",
        "username": "",
    }


class SupportRecentGroupTenantIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        support_bot._recent_group_chats.clear()

    def tearDown(self):
        support_bot._recent_group_chats.clear()

    def test_recent_groups_are_bucketed_by_current_tenant(self):
        with tenant_scope(101):
            support_bot.remember_group_chat(group_chat(-1001, "Tenant A"))

        with tenant_scope(202):
            support_bot.remember_group_chat(group_chat(-2001, "Tenant B"))

        with tenant_scope(101):
            groups = support_bot.get_recent_group_chats()
            self.assertEqual([item["chat_id"] for item in groups], ["-1001"])

        with tenant_scope(202):
            groups = support_bot.get_recent_group_chats()
            self.assertEqual([item["chat_id"] for item in groups], ["-2001"])

        with tenant_scope(None):
            self.assertEqual(support_bot.get_recent_group_chats(), [])

    async def test_recent_updates_only_falls_back_to_calling_tenant_bucket(self):
        support_bot.remember_group_chat(
            group_chat(-1001, "Tenant A"),
            owner_user_id=101,
        )
        support_bot.remember_group_chat(
            group_chat(-2001, "Tenant B"),
            owner_user_id=202,
        )

        with patch.object(
            support_bot,
            "get_support_token_and_settings",
            return_value=(None, {}),
        ):
            with tenant_scope(101):
                tenant_a = await support_bot.get_recent_support_updates()
            with tenant_scope(202):
                tenant_b = await support_bot.get_recent_support_updates()

        self.assertEqual(
            [item["chat_id"] for item in tenant_a["groups"]],
            ["-1001"],
        )
        self.assertEqual(
            [item["chat_id"] for item in tenant_b["groups"]],
            ["-2001"],
        )

    async def test_background_update_uses_support_bot_owner_without_context(self):
        settings_a = support_bot.support_bot_settings(
            {"id": 11, "_owner_user_id": 101}
        )
        settings_b = support_bot.support_bot_settings(
            {"id": 22, "_owner_user_id": 202}
        )

        with tenant_scope(None):
            await support_bot.handle_support_update(
                {"message": {"chat": group_chat(-1001, "Tenant A")}},
                token=None,
                settings=settings_a,
            )
            await support_bot.handle_support_update(
                {"message": {"chat": group_chat(-2001, "Tenant B")}},
                token=None,
                settings=settings_b,
            )

        self.assertEqual(
            [
                item["chat_id"]
                for item in support_bot.get_recent_group_chats(owner_user_id=101)
            ],
            ["-1001"],
        )
        self.assertEqual(
            [
                item["chat_id"]
                for item in support_bot.get_recent_group_chats(owner_user_id=202)
            ],
            ["-2001"],
        )
        self.assertEqual(support_bot.get_recent_group_chats(owner_user_id=None), [])

    def test_per_tenant_capacity_does_not_evict_other_tenant(self):
        support_bot.remember_group_chat(
            group_chat(-2001, "Tenant B"),
            owner_user_id=202,
        )
        for index in range(support_bot.RECENT_GROUP_CHAT_LIMIT + 1):
            support_bot.remember_group_chat(
                group_chat(-(1000 + index), f"Tenant A {index}"),
                owner_user_id=101,
            )

        tenant_a = support_bot.get_recent_group_chats(owner_user_id=101)
        tenant_b = support_bot.get_recent_group_chats(owner_user_id=202)

        self.assertEqual(len(tenant_a), support_bot.RECENT_GROUP_CHAT_LIMIT)
        self.assertNotIn("-1000", {item["chat_id"] for item in tenant_a})
        self.assertEqual([item["chat_id"] for item in tenant_b], ["-2001"])


if __name__ == "__main__":
    unittest.main()
