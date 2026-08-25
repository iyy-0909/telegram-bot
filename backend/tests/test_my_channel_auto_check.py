import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from api import server


class MyChannelAutoCheckTest(unittest.IsolatedAsyncioTestCase):
    async def test_basic_info_is_saved_when_permission_check_fails(self):
        channel = SimpleNamespace(
            id=7,
            title="",
            username="@source_channel",
            chat_id="",
            channel_type="",
            bot_id=1,
        )
        bot = SimpleNamespace(id=1, token="test-token")

        def request_post(_token, method, _payload, _timeout):
            if method == "getChat":
                return {
                    "result": {
                        "id": -100123456,
                        "title": "Telegram 频道名称",
                        "username": "source_channel",
                        "type": "channel",
                    }
                }
            if method == "getChatMember":
                raise RuntimeError("member list is inaccessible")
            raise AssertionError(f"unexpected method: {method}")

        def save_result(_channel_id, data, **_kwargs):
            return data

        with (
            patch.object(server, "resolve_default_bot", return_value=bot),
            patch.object(server, "request_post", side_effect=request_post),
            patch.object(server, "bot_get_me", AsyncMock(return_value={"result": {"id": 99}})),
            patch.object(server, "fetch_channel_member_count", AsyncMock(return_value={"member_count": None, "can_view_member_count": False})),
            patch.object(server, "fetch_channel_creator", AsyncMock(return_value={"creator_user_id": "", "creator_username": "", "creator_name": "", "can_view_creator": False})),
            patch.object(server, "set_my_channel_check_result", side_effect=save_result),
            patch.object(server, "my_channel_to_dict", side_effect=lambda item: item),
        ):
            result = await server.check_my_channel_permissions(
                channel,
                fill_empty_only=True,
                preserve_disabled_status=True,
            )

        self.assertEqual(result["title"], "Telegram 频道名称")
        self.assertEqual(result["chat_id"], "-100123456")
        self.assertEqual(result["channel_type"], "channel")
        self.assertEqual(result["status"], "error")
        self.assertIn("member list is inaccessible", result["last_error"])


if __name__ == "__main__":
    unittest.main()
