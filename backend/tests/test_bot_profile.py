import asyncio
import json
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Request, UploadFile

from api import server
from bot import bot_sender
from bot import botfather_profile
from bot.profile_photo import (
    MAX_PROFILE_PHOTO_BYTES,
    ProfilePhotoValidationError,
    normalize_static_profile_photo,
)


class BotSenderProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_public_profile_reads_text_and_largest_photo(self):
        def fake_get(_token, method):
            return {
                "getMe": {"ok": True, "result": {"id": 77, "username": "demo_bot"}},
                "getMyName": {"ok": True, "result": {"name": "演示机器人"}},
                "getMyDescription": {
                    "ok": True,
                    "result": {"description": "完整简介"},
                },
                "getMyShortDescription": {
                    "ok": True,
                    "result": {"short_description": "短简介"},
                },
            }[method]

        def fake_post(_token, method, _data, _files):
            if method == "getMyCommands":
                return {
                    "ok": True,
                    "result": [
                        {"command": "start", "description": "Start the bot"},
                    ],
                }
            if method == "getUserProfilePhotos":
                return {
                    "ok": True,
                    "result": {
                        "total_count": 1,
                        "photos": [[
                            {"file_id": "small", "width": 80, "height": 80},
                            {"file_id": "large", "width": 640, "height": 640},
                        ]],
                    },
                }
            raise AssertionError(method)

        with (
            patch("bot.bot_sender.request_get", side_effect=fake_get),
            patch("bot.bot_sender.request_post", side_effect=fake_post) as post,
        ):
            profile = await bot_sender.bot_get_public_profile("secret-token")

        self.assertEqual(profile["name"], "演示机器人")
        self.assertEqual(profile["description"], "完整简介")
        self.assertEqual(profile["short_description"], "短简介")
        self.assertEqual(profile["username"], "demo_bot")
        self.assertEqual(profile["bot_link"], "https://t.me/demo_bot")
        self.assertTrue(profile["has_photo"])
        self.assertEqual(profile["photo_file_id"], "large")
        self.assertEqual(
            profile["commands"],
            [{"command": "start", "description": "Start the bot"}],
        )
        self.assertEqual(profile["about"], profile["short_description"])
        self.assertNotIn("secret-token", json.dumps(profile, ensure_ascii=False))
        self.assertEqual(post.call_args.args[1], "getUserProfilePhotos")
        self.assertEqual(post.call_args.args[2]["user_id"], 77)

    async def test_set_and_delete_default_commands(self):
        refreshed = {"commands": []}

        with (
            patch("bot.bot_sender.request_post", return_value={"ok": True}) as post,
            patch(
                "bot.bot_sender.bot_get_public_profile",
                new=AsyncMock(return_value=refreshed),
            ),
        ):
            await bot_sender.bot_set_commands(
                "secret-token",
                [{"command": "start", "description": "Start"}],
            )
            self.assertEqual(post.call_args.args[1], "setMyCommands")
            self.assertEqual(
                json.loads(post.call_args.args[2]["commands"]),
                [{"command": "start", "description": "Start"}],
            )

            post.reset_mock()
            await bot_sender.bot_set_commands("secret-token", [])
            self.assertEqual(post.call_args.args[1], "deleteMyCommands")
            self.assertEqual(post.call_args.args[2], {})

    async def test_update_public_profile_only_sends_supplied_fields(self):
        refreshed_profile = {"name": "新名字", "has_photo": False}

        with (
            patch("bot.bot_sender.request_post", return_value={"ok": True}) as post,
            patch(
                "bot.bot_sender.bot_get_public_profile",
                new=AsyncMock(return_value=refreshed_profile),
            ),
        ):
            result = await bot_sender.bot_update_public_profile(
                "secret-token",
                name="新名字",
                short_description="",
            )

        self.assertEqual(result, refreshed_profile)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].args[1], "setMyName")
        self.assertEqual(post.call_args_list[0].args[2], {"name": "新名字"})
        self.assertEqual(post.call_args_list[1].args[1], "setMyShortDescription")
        self.assertEqual(
            post.call_args_list[1].args[2],
            {"short_description": ""},
        )

    async def test_update_public_profile_reports_partial_success(self):
        def fake_post(_token, method, _data, _files):
            if method == "setMyDescription":
                raise bot_sender.BotApiError("description rejected")
            return {"ok": True}

        refreshed = {
            "name": "New name",
            "description": "Old description",
            "short_description": "New about",
        }
        with (
            patch("bot.bot_sender.request_post", side_effect=fake_post),
            patch(
                "bot.bot_sender.bot_get_public_profile",
                new=AsyncMock(return_value=refreshed),
            ),
        ):
            with self.assertRaises(
                bot_sender.BotProfilePartialUpdateError
            ) as caught:
                await bot_sender.bot_update_public_profile(
                    "secret-token",
                    name="New name",
                    description="New description",
                    short_description="New about",
                )

        error = caught.exception
        self.assertEqual(error.updated_fields, ["name", "short_description"])
        self.assertEqual(list(error.failed_fields), ["description"])
        self.assertEqual(error.profile, refreshed)

    async def test_set_profile_photo_uses_input_profile_photo_payload(self):
        with patch(
            "bot.bot_sender.request_post",
            return_value={"ok": True, "result": True},
        ) as post:
            await bot_sender.bot_set_profile_photo(
                "secret-token",
                b"jpeg-content",
                "profile.jpg",
            )

        args = post.call_args.args
        self.assertEqual(args[1], "setMyProfilePhoto")
        self.assertEqual(
            json.loads(args[2]["photo"]),
            {"type": "static", "photo": "attach://profile_photo"},
        )
        filename, content, content_type = args[3]["profile_photo"]
        self.assertEqual(filename, "profile.jpg")
        self.assertEqual(content, b"jpeg-content")
        self.assertEqual(content_type, "image/jpeg")

    async def test_download_profile_photo_returns_proxied_bytes(self):
        def fake_post(_token, method, _data, _files):
            if method == "getUserProfilePhotos":
                return {
                    "ok": True,
                    "result": {
                        "photos": [[{"file_id": "photo-file", "width": 100}]],
                    },
                }
            if method == "getFile":
                return {
                    "ok": True,
                    "result": {"file_path": "photos/current.jpg"},
                }
            raise AssertionError(method)

        with (
            patch(
                "bot.bot_sender.bot_get_me",
                new=AsyncMock(return_value={"result": {"id": 77}}),
            ),
            patch("bot.bot_sender.request_post", side_effect=fake_post),
            patch(
                "bot.bot_sender.request_file_download",
                return_value={"content": b"image", "content_type": "image/jpeg"},
            ) as download,
        ):
            result = await bot_sender.bot_download_profile_photo("secret-token")

        self.assertEqual(result["content"], b"image")
        download.assert_called_once_with("secret-token", "photos/current.jpg")


class ProfilePhotoValidationTests(unittest.TestCase):
    def test_png_is_converted_to_jpeg(self):
        import cv2
        import numpy as np

        source = np.zeros((12, 20, 3), dtype=np.uint8)
        success, png = cv2.imencode(".png", source)
        self.assertTrue(success)

        result = normalize_static_profile_photo(
            png.tobytes(),
            content_type="image/png",
        )

        self.assertTrue(result.startswith(b"\xff\xd8\xff"))

    def test_rejects_unsupported_type_and_oversized_file(self):
        with self.assertRaises(ProfilePhotoValidationError):
            normalize_static_profile_photo(b"not-an-image", content_type="text/plain")

        with self.assertRaises(ProfilePhotoValidationError):
            normalize_static_profile_photo(b"x" * (MAX_PROFILE_PHOTO_BYTES + 1))


class BotFatherProfileAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_owner_only_profile_fields(self):
        info = SimpleNamespace(
            description_photo=SimpleNamespace(id=1),
            description_document=None,
            privacy_policy_url="https://example.com/privacy",
        )
        entity = SimpleNamespace(
            bot_can_edit=True,
            username="demo_bot",
        )

        class FakeClient:
            def is_connected(self):
                return True

            async def get_entity(self, username):
                self.requested_username = username
                return entity

            async def __call__(self, request):
                self.request = request
                return SimpleNamespace(
                    full_user=SimpleNamespace(bot_info=info),
                )

        client = FakeClient()
        result = await botfather_profile.get_botfather_profile_fields(
            {4: client},
            "@demo_bot",
        )

        self.assertTrue(result["has_description_photo"])
        self.assertFalse(result["has_description_document"])
        self.assertEqual(result["description_media_type"], "photo")
        self.assertEqual(
            result["privacy_policy_url"],
            "https://example.com/privacy",
        )
        self.assertEqual(result["owner_account_id"], 4)
        self.assertEqual(client.requested_username, "@demo_bot")

    async def test_rejects_non_owner_account(self):
        class NonOwnerClient:
            def is_connected(self):
                return True

            async def get_entity(self, _username):
                return SimpleNamespace(bot_can_edit=False, username="demo_bot")

            async def __call__(self, _request):
                return SimpleNamespace(
                    full_user=SimpleNamespace(
                        bot_info=SimpleNamespace(
                            description_photo=None,
                            description_document=None,
                            privacy_policy_url="https://example.com/privacy",
                        )
                    )
                )

        with self.assertRaises(botfather_profile.BotProfileCapabilityError):
            await botfather_profile.find_owned_bot(
                {7: NonOwnerClient()},
                "demo_bot",
            )

        fields = await botfather_profile.get_botfather_profile_fields(
            {7: NonOwnerClient()},
            "demo_bot",
        )
        self.assertFalse(fields["owner_available"])
        self.assertEqual(fields["privacy_policy_url"], "https://example.com/privacy")

    async def test_all_query_errors_are_distinct_from_non_owner(self):
        class BrokenClient:
            def is_connected(self):
                return True

            async def get_entity(self, _username):
                raise RuntimeError("network unavailable")

        with self.assertRaises(botfather_profile.BotProfileReadError):
            await botfather_profile.get_botfather_profile_fields(
                {1: BrokenClient(), 2: BrokenClient()},
                "demo_bot",
            )

    async def test_description_video_is_readable_and_removable_capability(self):
        info = SimpleNamespace(
            description_photo=None,
            description_document=SimpleNamespace(id=88),
            privacy_policy_url="",
        )

        class VideoClient:
            def is_connected(self):
                return True

            async def get_entity(self, _username):
                return SimpleNamespace(bot_can_edit=True, username="demo_bot")

            async def __call__(self, _request):
                return SimpleNamespace(
                    full_user=SimpleNamespace(bot_info=info),
                )

        fields = await botfather_profile.get_botfather_profile_fields(
            {8: VideoClient()},
            "demo_bot",
        )
        self.assertTrue(fields["has_description_media"])
        self.assertTrue(fields["has_description_document"])
        self.assertEqual(fields["description_media_type"], "video")

    def test_dynamic_button_matching_uses_visible_text(self):
        description = SimpleNamespace(text="🖼 Edit Description Picture")
        privacy = SimpleNamespace(text="Edit Privacy Policy")
        bot = SimpleNamespace(text="@demo_bot")
        other_bot = SimpleNamespace(text="@demo_bot_backup")
        message = SimpleNamespace(
            buttons=[[description, privacy], [other_bot, bot]],
        )

        self.assertIs(
            botfather_profile._find_button(
                message,
                botfather_profile.DESCRIPTION_PICTURE_ALIASES,
            ),
            description,
        )
        self.assertIs(
            botfather_profile._find_button(
                message,
                botfather_profile.PRIVACY_POLICY_ALIASES,
            ),
            privacy,
        )
        self.assertIs(
            botfather_profile._find_bot_button(message, "demo_bot"),
            bot,
        )
        self.assertTrue(
            botfather_profile._message_targets_username(
                SimpleNamespace(raw_text="Editing @demo_bot settings"),
                "demo_bot",
            )
        )
        self.assertFalse(
            botfather_profile._message_targets_username(
                SimpleNamespace(raw_text="Editing @demo_bot_backup settings"),
                "demo_bot",
            )
        )

    def test_rejection_text_is_diagnostic_and_covers_rate_limits(self):
        for text in (
            "Sorry, this action is not allowed",
            "Please upload a valid picture",
            "Too many requests, try later",
            "FLOOD_WAIT",
        ):
            with self.assertRaises(botfather_profile.BotFatherFlowError):
                botfather_profile._raise_for_rejection(
                    SimpleNamespace(raw_text=text),
                    "测试操作",
                )

        self.assertEqual(
            botfather_profile._raise_for_rejection(
                SimpleNamespace(raw_text="Done"),
                "测试操作",
            ),
            "Done",
        )

    async def test_mutation_verifies_new_identity_inside_owner_lock(self):
        old_info = SimpleNamespace(
            description_photo=SimpleNamespace(id=1, access_hash=11),
            description_document=None,
            privacy_policy_url="",
        )
        new_info = SimpleNamespace(
            description_photo=SimpleNamespace(id=2, access_hash=22),
            description_document=None,
            privacy_policy_url="",
        )
        context = botfather_profile.OwnedBotContext(
            account_id=5,
            client=SimpleNamespace(),
            entity=SimpleNamespace(username="demo_bot", bot_can_edit=True),
            bot_info=old_info,
        )
        scan = botfather_profile.BotContextScan(context, context, 1)
        botfather_profile.BOTFATHER_LOCKS.clear()

        with (
            patch(
                "bot.botfather_profile._scan_bot_contexts",
                new=AsyncMock(return_value=scan),
            ),
            patch(
                "bot.botfather_profile._set_description_picture_flow",
                new=AsyncMock(return_value="Done"),
            ) as mutate,
            patch(
                "bot.botfather_profile._refresh_context",
                new=AsyncMock(side_effect=[
                    context,
                    SimpleNamespace(
                        account_id=5,
                        client=context.client,
                        entity=context.entity,
                        bot_info=new_info,
                    ),
                ]),
            ),
            patch("bot.botfather_profile.VERIFY_DELAYS", (0,)),
        ):
            fields = await botfather_profile.set_description_picture(
                {5: context.client},
                "demo_bot",
                b"jpeg",
            )

        mutate.assert_awaited_once_with(context, b"jpeg")
        self.assertTrue(fields["has_description_photo"])
        self.assertTrue(fields["owner_available"])

    async def test_delete_verifies_photo_and_video_are_both_empty(self):
        old_info = SimpleNamespace(
            description_photo=None,
            description_document=SimpleNamespace(id=7, access_hash=77),
            privacy_policy_url="",
        )
        empty_info = SimpleNamespace(
            description_photo=None,
            description_document=None,
            privacy_policy_url="",
        )
        context = botfather_profile.OwnedBotContext(
            account_id=9,
            client=SimpleNamespace(),
            entity=SimpleNamespace(username="demo_bot", bot_can_edit=True),
            bot_info=old_info,
        )
        scan = botfather_profile.BotContextScan(context, context, 1)
        botfather_profile.BOTFATHER_LOCKS.clear()
        with (
            patch(
                "bot.botfather_profile._scan_bot_contexts",
                new=AsyncMock(return_value=scan),
            ),
            patch(
                "bot.botfather_profile._set_description_picture_flow",
                new=AsyncMock(return_value="Done"),
            ),
            patch(
                "bot.botfather_profile._refresh_context",
                new=AsyncMock(side_effect=[
                    context,
                    SimpleNamespace(
                        account_id=9,
                        client=context.client,
                        entity=context.entity,
                        bot_info=empty_info,
                    ),
                ]),
            ),
            patch("bot.botfather_profile.VERIFY_DELAYS", (0,)),
        ):
            fields = await botfather_profile.set_description_picture(
                {9: context.client},
                "demo_bot",
                None,
            )

        self.assertFalse(fields["has_description_photo"])
        self.assertFalse(fields["has_description_document"])
        self.assertFalse(fields["has_description_media"])

    async def test_lock_wait_is_part_of_single_deadline(self):
        context = botfather_profile.OwnedBotContext(
            account_id=6,
            client=SimpleNamespace(),
            entity=SimpleNamespace(username="demo_bot", bot_can_edit=True),
            bot_info=SimpleNamespace(privacy_policy_url=""),
        )
        scan = botfather_profile.BotContextScan(context, context, 1)
        lock = asyncio.Lock()
        await lock.acquire()
        botfather_profile.BOTFATHER_LOCKS[6] = lock
        try:
            with (
                patch(
                    "bot.botfather_profile._scan_bot_contexts",
                    new=AsyncMock(return_value=scan),
                ),
                patch("bot.botfather_profile.BOTFATHER_FLOW_TIMEOUT", 0.01),
            ):
                with self.assertRaises(botfather_profile.BotFatherFlowError):
                    await botfather_profile.set_privacy_policy(
                        {6: context.client},
                        "demo_bot",
                        "https://example.com/privacy",
                    )
        finally:
            lock.release()
            botfather_profile.BOTFATHER_LOCKS.clear()

    async def test_privacy_policy_retries_until_exact_value(self):
        old_info = SimpleNamespace(
            description_photo=None,
            description_document=None,
            privacy_policy_url="https://example.com/old",
        )
        wrong_info = SimpleNamespace(
            description_photo=None,
            description_document=None,
            privacy_policy_url="https://example.com/privacy-extra",
        )
        exact_info = SimpleNamespace(
            description_photo=None,
            description_document=None,
            privacy_policy_url="https://example.com/privacy",
        )
        context = botfather_profile.OwnedBotContext(
            account_id=10,
            client=SimpleNamespace(),
            entity=SimpleNamespace(username="demo_bot", bot_can_edit=True),
            bot_info=old_info,
        )
        scan = botfather_profile.BotContextScan(context, context, 1)
        refreshed = [
            context,
            SimpleNamespace(
                account_id=10,
                client=context.client,
                entity=context.entity,
                bot_info=wrong_info,
            ),
            SimpleNamespace(
                account_id=10,
                client=context.client,
                entity=context.entity,
                bot_info=exact_info,
            ),
        ]
        botfather_profile.BOTFATHER_LOCKS.clear()
        with (
            patch(
                "bot.botfather_profile._scan_bot_contexts",
                new=AsyncMock(return_value=scan),
            ),
            patch(
                "bot.botfather_profile._set_privacy_policy_flow",
                new=AsyncMock(return_value="Done"),
            ),
            patch(
                "bot.botfather_profile._refresh_context",
                new=AsyncMock(side_effect=refreshed),
            ) as refresh,
            patch("bot.botfather_profile.VERIFY_DELAYS", (0, 0)),
        ):
            fields = await botfather_profile.set_privacy_policy(
                {10: context.client},
                "demo_bot",
                "https://example.com/privacy",
            )

        self.assertEqual(refresh.await_count, 3)
        self.assertEqual(
            fields["privacy_policy_url"],
            "https://example.com/privacy",
        )


class BotProfileApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.token = "123456:very-secret-token"
        self.bot = SimpleNamespace(id=9, token=self.token)

    async def test_get_profile_returns_wrapped_profile_without_token(self):
        telegram_profile = {
            "name": "演示机器人",
            "description": "简介",
            "short_description": "短简介",
            "username": "demo_bot",
            "has_photo": True,
            "photo_file_id": "photo-id",
        }

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=telegram_profile),
            ),
        ):
            response = await server.api_get_bot_profile(9)

        self.assertTrue(response["ok"])
        self.assertEqual(response["profile"]["name"], "演示机器人")
        self.assertEqual(
            response["profile"]["photo_url"],
            "/api/bots/9/profile/photo",
        )
        self.assertNotIn(self.token, json.dumps(response, ensure_ascii=False))

    async def test_update_profile_checks_character_limits(self):
        payload = server.BotProfileUpdate(name="x" * 65)

        with patch("api.server.get_bot", return_value=self.bot):
            with self.assertRaises(HTTPException) as caught:
                await server.api_update_bot_profile(9, payload)

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("64", caught.exception.detail)

    async def test_profile_api_redacts_raw_token_from_errors(self):
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(
                    side_effect=RuntimeError(
                        f"failed at /bot{self.token}/getMe token={self.token}"
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_get_bot_profile(9)

        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn(self.token, caught.exception.detail)

    async def test_upload_photo_normalizes_then_sends_jpeg(self):
        upload = UploadFile(filename="avatar.png", file=BytesIO(b"png-source"))
        profile = {"name": "机器人", "has_photo": True, "photo_file_id": "new"}

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.normalize_static_profile_photo",
                return_value=b"jpeg-result",
            ) as normalize,
            patch(
                "api.server.bot_set_profile_photo",
                new=AsyncMock(return_value={"ok": True}),
            ) as upload_photo,
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=profile),
            ),
        ):
            response = await server.api_upload_bot_profile_photo(9, upload)

        normalize.assert_called_once_with(b"png-source", content_type="")
        upload_photo.assert_awaited_once_with(
            self.token,
            b"jpeg-result",
            "profile.jpg",
        )
        self.assertTrue(response["profile"]["has_photo"])
        self.assertNotIn(self.token, json.dumps(response, ensure_ascii=False))

    async def test_get_photo_returns_binary_response_and_missing_is_404(self):
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_download_profile_photo",
                new=AsyncMock(
                    return_value={
                        "content": b"jpeg-content",
                        "content_type": "image/jpeg",
                    }
                ),
            ),
        ):
            response = await server.api_get_bot_profile_photo(9)

        self.assertEqual(response.body, b"jpeg-content")
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.headers["cache-control"], "private, no-store")

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_download_profile_photo",
                new=AsyncMock(return_value=None),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_get_bot_profile_photo(9)

        self.assertEqual(caught.exception.status_code, 404)

    async def test_enriched_profile_exposes_extended_fields_and_capabilities(self):
        base = {
            "name": "Demo",
            "short_description": "About",
            "username": "demo_bot",
            "commands": [],
        }
        owner = {
            "has_description_photo": True,
            "has_description_document": False,
            "description_media_type": "photo",
            "privacy_policy_url": "https://example.com/privacy",
            "owner_account_id": 3,
        }

        with (
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=base),
            ),
            patch(
                "api.server.get_botfather_profile_fields",
                new=AsyncMock(return_value=owner),
            ),
        ):
            profile = await server.get_enriched_bot_profile(self.bot)

        self.assertTrue(profile["has_description_photo"])
        self.assertEqual(
            profile["privacy_policy_url"],
            "https://example.com/privacy",
        )
        self.assertTrue(profile["capabilities"]["commands"]["write"])
        self.assertTrue(profile["capabilities"]["description_photo"]["write"])

    async def test_non_owner_can_read_extended_fields_but_cannot_write(self):
        base = {"username": "demo_bot", "commands": []}
        readable = {
            "has_description_photo": False,
            "has_description_document": True,
            "has_description_media": True,
            "description_media_type": "video",
            "privacy_policy_url": "https://example.com/privacy",
            "owner_available": False,
            "owner_account_id": None,
        }
        with (
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=base),
            ),
            patch(
                "api.server.get_botfather_profile_fields",
                new=AsyncMock(return_value=readable),
            ),
        ):
            profile = await server.get_enriched_bot_profile(self.bot)

        capability = profile["capabilities"]["description_media"]
        self.assertTrue(capability["read"])
        self.assertFalse(capability["write"])
        self.assertFalse(capability["remove"])
        self.assertTrue(profile["has_description_media"])
        self.assertEqual(profile["description_media_type"], "video")

    async def test_all_extended_profile_queries_failed_returns_502(self):
        base = {"username": "demo_bot", "commands": []}
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=base),
            ),
            patch(
                "api.server.get_botfather_profile_fields",
                new=AsyncMock(
                    side_effect=botfather_profile.BotProfileReadError(
                        "all account queries failed"
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_get_bot_profile(9)

        self.assertEqual(caught.exception.status_code, 502)

    async def test_basic_profile_partial_error_returns_updated_fields_and_profile(self):
        partial = {
            "name": "New name",
            "description": "Old description",
            "short_description": "New about",
            "username": "demo_bot",
        }
        error = bot_sender.BotProfilePartialUpdateError(
            ["name", "short_description"],
            {"description": RuntimeError(f"rejected {self.token}")},
            partial,
        )
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_update_public_profile",
                new=AsyncMock(side_effect=error),
            ),
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=partial),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_update_bot_profile(
                    9,
                    server.BotProfileUpdate(
                        name="New name",
                        description="New description",
                        short_description="New about",
                    ),
                )

        self.assertEqual(caught.exception.status_code, 502)
        detail = caught.exception.detail
        self.assertEqual(detail["updated_fields"], ["name", "short_description"])
        self.assertIn("description", detail["failed_fields"])
        self.assertEqual(detail["profile"]["name"], "New name")
        self.assertNotIn(self.token, json.dumps(detail, ensure_ascii=False))

    async def test_profile_mutations_require_admin_role_in_middleware(self):
        def build_request(method, path, token="user-token"):
            return Request({
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 8000),
            })

        protected = (
            ("PUT", "/api/bots/9/profile"),
            ("POST", "/api/bots/9/profile/photo"),
            ("DELETE", "/api/bots/9/profile/description-photo"),
            ("PUT", "/api/bots/9/profile/privacy-policy"),
        )
        with patch(
            "api.server.get_user_by_session_token",
            return_value=(
                {"id": 2, "username": "member", "role": "user"},
                10,
            ),
        ):
            for method, path in protected:
                call_next = AsyncMock(return_value=server.Response(status_code=204))
                response = await server.require_admin_auth(
                    build_request(method, path),
                    call_next,
                )
                self.assertEqual(response.status_code, 403)
                call_next.assert_not_awaited()

            read_next = AsyncMock(return_value=server.Response(status_code=200))
            response = await server.require_admin_auth(
                build_request("GET", "/api/bots/9/profile"),
                read_next,
            )
            self.assertEqual(response.status_code, 403)
            read_next.assert_not_awaited()

        admin_next = AsyncMock(return_value=server.Response(status_code=204))
        with patch.object(server, "ADMIN_TOKEN", "explicit-admin-token"):
            response = await server.require_admin_auth(
                build_request(
                    "PUT",
                    "/api/bots/9/profile",
                    "explicit-admin-token",
                ),
                admin_next,
            )
        self.assertEqual(response.status_code, 204)
        admin_next.assert_awaited_once()

    async def test_legacy_admin_is_disabled_without_explicit_config(self):
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        with (
            patch.object(server, "ADMIN_PASSWORD", ""),
            patch.object(server, "ADMIN_TOKEN", ""),
            patch("api.server._apply_auth_rate_limit"),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_auth_login(
                    server.LoginRequest(username="", password="any-password"),
                    request,
                )

        self.assertEqual(caught.exception.status_code, 403)

    async def test_legacy_admin_only_accepts_explicit_nonempty_config(self):
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        with (
            patch.object(server, "ADMIN_PASSWORD", "configured-password"),
            patch.object(server, "ADMIN_TOKEN", "configured-token"),
            patch("api.server._apply_auth_rate_limit"),
        ):
            response = await server.api_auth_login(
                server.LoginRequest(
                    username="",
                    password="configured-password",
                ),
                request,
            )

        self.assertTrue(response["ok"])
        self.assertEqual(response["token"], "configured-token")

    async def test_database_admin_session_still_passes_profile_middleware(self):
        request = Request({
            "type": "http",
            "http_version": "1.1",
            "method": "PUT",
            "scheme": "http",
            "path": "/api/bots/9/profile",
            "raw_path": b"/api/bots/9/profile",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer database-session")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        })
        call_next = AsyncMock(return_value=server.Response(status_code=204))
        with (
            patch.object(server, "ADMIN_PASSWORD", ""),
            patch.object(server, "ADMIN_TOKEN", ""),
            patch(
                "api.server.get_user_by_session_token",
                return_value=(
                    {"id": 1, "username": "db-admin", "role": "admin"},
                    11,
                ),
            ),
        ):
            response = await server.require_admin_auth(request, call_next)

        self.assertEqual(response.status_code, 204)
        call_next.assert_awaited_once()

    def test_all_profile_mutation_routes_have_endpoint_admin_guard(self):
        expected = {
            ("PUT", "/api/bots/{bot_id}/profile"),
            ("POST", "/api/bots/{bot_id}/profile/photo"),
            ("DELETE", "/api/bots/{bot_id}/profile/photo"),
            ("PUT", "/api/bots/{bot_id}/profile/commands"),
            ("POST", "/api/bots/{bot_id}/profile/description-photo"),
            ("DELETE", "/api/bots/{bot_id}/profile/description-photo"),
            ("PUT", "/api/bots/{bot_id}/profile/privacy-policy"),
            ("DELETE", "/api/bots/{bot_id}/profile/privacy-policy"),
        }
        guarded = set()
        for route in server.app.routes:
            dependencies = {
                dependency.call
                for dependency in getattr(route, "dependant", SimpleNamespace(dependencies=[])).dependencies
            }
            if server.require_bot_profile_admin not in dependencies:
                continue
            for method in getattr(route, "methods", set()):
                guarded.add((method, getattr(route, "path", "")))

        self.assertTrue(expected.issubset(guarded), expected - guarded)

    def test_plus_prefixed_bot_id_cannot_bypass_endpoint_admin_guard(self):
        request = Request({
            "type": "http",
            "http_version": "1.1",
            "method": "PUT",
            "scheme": "http",
            "path": "/api/bots/+9/profile",
            "raw_path": b"/api/bots/+9/profile",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        })
        request.state.current_user = {
            "id": 2,
            "username": "member",
            "role": "user",
        }

        with self.assertRaises(HTTPException) as caught:
            server.require_bot_profile_admin(request)

        self.assertEqual(caught.exception.status_code, 403)

    async def test_get_profile_hides_write_capabilities_from_regular_user(self):
        request = Request({
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/bots/9/profile",
            "raw_path": b"/api/bots/9/profile",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        })
        request.state.current_user = {
            "id": 2,
            "username": "member",
            "role": "user",
        }
        profile = {
            "username": "demo_bot",
            "capabilities": server.bot_profile_capabilities(True, True),
        }
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=profile),
            ),
        ):
            response = await server.api_get_bot_profile(9, request)

        for capability in response["profile"]["capabilities"].values():
            self.assertFalse(capability["write"])
            self.assertFalse(capability["remove"])
            self.assertIn("管理员", capability["reason"])

    async def test_commands_api_normalizes_and_saves_default_commands(self):
        payload = server.BotCommandsUpdate(
            commands=[
                server.BotCommandInput(command="/start", description=" Start "),
            ]
        )
        profile = {"username": "demo_bot", "commands": []}

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.bot_set_commands",
                new=AsyncMock(return_value=profile),
            ) as save,
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=profile),
            ),
        ):
            response = await server.api_update_bot_commands(9, payload)

        save.assert_awaited_once_with(
            self.token,
            [{"command": "start", "description": "Start"}],
        )
        self.assertTrue(response["ok"])
        self.assertNotIn(self.token, json.dumps(response, ensure_ascii=False))

    async def test_commands_validation_rejects_invalid_and_duplicate_items(self):
        invalid = server.BotCommandsUpdate(
            commands=[server.BotCommandInput(command="Bad-Command", description="x")]
        )
        duplicate = server.BotCommandsUpdate(
            commands=[
                server.BotCommandInput(command="start", description="one"),
                server.BotCommandInput(command="/start", description="two"),
            ]
        )

        with self.assertRaises(HTTPException):
            server.validate_bot_commands(invalid)
        with self.assertRaises(HTTPException):
            server.validate_bot_commands(duplicate)

        boundary = server.BotCommandsUpdate(
            commands=[
                server.BotCommandInput(
                    command="a" * 32,
                    description="d" * 256,
                )
            ]
        )
        self.assertEqual(len(server.validate_bot_commands(boundary)), 1)

        too_long_command = server.BotCommandsUpdate(
            commands=[
                server.BotCommandInput(command="a" * 33, description="x"),
            ]
        )
        too_long_description = server.BotCommandsUpdate(
            commands=[
                server.BotCommandInput(command="start", description="x" * 257),
            ]
        )
        too_many = server.BotCommandsUpdate(
            commands=[
                server.BotCommandInput(command=f"cmd_{index}", description="x")
                for index in range(101)
            ]
        )
        for payload in (too_long_command, too_long_description, too_many):
            with self.assertRaises(HTTPException):
                server.validate_bot_commands(payload)

    async def test_description_photo_upload_is_normalized_and_verified(self):
        upload = UploadFile(filename="description.png", file=BytesIO(b"source"))
        profile = {
            "username": "demo_bot",
            "has_description_photo": True,
        }

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.normalize_static_profile_photo",
                return_value=b"jpeg",
            ) as normalize,
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.set_description_picture",
                new=AsyncMock(return_value={
                    "has_description_photo": True,
                    "has_description_document": False,
                    "has_description_media": True,
                    "description_media_type": "photo",
                    "privacy_policy_url": "",
                    "owner_available": True,
                    "owner_account_id": 1,
                }),
            ) as save,
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=profile),
            ),
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=profile),
            ),
        ):
            response = await server.api_upload_bot_description_photo(9, upload)

        normalize.assert_called_once_with(b"source", content_type="")
        save.assert_awaited_once_with(
            server.account_manager.clients,
            "demo_bot",
            b"jpeg",
        )
        self.assertEqual(
            response["profile"]["description_photo_url"],
            "/api/bots/9/profile/description-photo",
        )

    async def test_description_photo_delete_uses_empty_flow_and_verifies(self):
        profile = {"username": "demo_bot", "has_description_photo": False}

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.set_description_picture",
                new=AsyncMock(return_value={
                    "has_description_photo": False,
                    "has_description_document": False,
                    "has_description_media": False,
                    "description_media_type": "",
                    "privacy_policy_url": "",
                    "owner_available": True,
                    "owner_account_id": 1,
                }),
            ) as remove,
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=profile),
            ),
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=profile),
            ),
        ):
            response = await server.api_delete_bot_description_photo(9)

        remove.assert_awaited_once_with(
            server.account_manager.clients,
            "demo_bot",
            None,
        )
        self.assertEqual(response["profile"]["description_photo_url"], "")

    async def test_description_photo_proxy_and_capability_error(self):
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.download_description_photo",
                new=AsyncMock(
                    return_value={
                        "content": b"description-image",
                        "content_type": "image/jpeg",
                    }
                ),
            ),
        ):
            response = await server.api_get_bot_description_photo(9)

        self.assertEqual(response.body, b"description-image")
        self.assertEqual(response.headers["cache-control"], "private, no-store")

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(
                    side_effect=botfather_profile.BotProfileCapabilityError(
                        f"owner missing {self.token}"
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_get_bot_description_photo(9)

        self.assertEqual(caught.exception.status_code, 409)
        self.assertNotIn(self.token, caught.exception.detail)

        upload = UploadFile(filename="description.jpg", file=BytesIO(b"source"))
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch("api.server.normalize_static_profile_photo", return_value=b"jpeg"),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.set_description_picture",
                new=AsyncMock(
                    side_effect=botfather_profile.BotProfileReadError(
                        "all account queries failed"
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as read_failed:
                await server.api_upload_bot_description_photo(9, upload)

        self.assertEqual(read_failed.exception.status_code, 502)

        upload = UploadFile(filename="description.jpg", file=BytesIO(b"source"))
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch("api.server.normalize_static_profile_photo", return_value=b"jpeg"),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.set_description_picture",
                new=AsyncMock(
                    side_effect=botfather_profile.BotProfileCapabilityError(
                        f"owner missing {self.token}"
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                await server.api_upload_bot_description_photo(9, upload)

        self.assertEqual(caught.exception.status_code, 409)
        self.assertNotIn(self.token, caught.exception.detail)

    async def test_privacy_policy_update_delete_and_validation(self):
        url = "https://example.com/privacy"
        profile = {"username": "demo_bot", "privacy_policy_url": url}

        with self.assertRaises(HTTPException):
            server.validate_privacy_policy_url("javascript:alert(1)")
        with self.assertRaises(HTTPException):
            server.validate_privacy_policy_url("https://user:pass@example.com")

        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.set_privacy_policy",
                new=AsyncMock(return_value={
                    "has_description_photo": False,
                    "has_description_document": False,
                    "has_description_media": False,
                    "description_media_type": "",
                    "privacy_policy_url": url,
                    "owner_available": True,
                    "owner_account_id": 1,
                }),
            ) as save,
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=profile),
            ),
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=profile),
            ),
        ):
            response = await server.api_update_bot_privacy_policy(
                9,
                server.BotPrivacyPolicyUpdate(url=url),
            )

        save.assert_awaited_once_with(
            server.account_manager.clients,
            "demo_bot",
            url,
        )
        self.assertEqual(response["profile"]["privacy_policy_url"], url)

        empty_profile = {"username": "demo_bot", "privacy_policy_url": ""}
        with (
            patch("api.server.get_bot", return_value=self.bot),
            patch(
                "api.server.get_bot_username_or_error",
                new=AsyncMock(return_value="demo_bot"),
            ),
            patch(
                "api.server.set_privacy_policy",
                new=AsyncMock(return_value={
                    "has_description_photo": False,
                    "has_description_document": False,
                    "has_description_media": False,
                    "description_media_type": "",
                    "privacy_policy_url": "",
                    "owner_available": True,
                    "owner_account_id": 1,
                }),
            ) as clear,
            patch(
                "api.server.bot_get_public_profile",
                new=AsyncMock(return_value=empty_profile),
            ),
            patch(
                "api.server.get_enriched_bot_profile",
                new=AsyncMock(return_value=empty_profile),
            ),
        ):
            await server.api_delete_bot_privacy_policy(9)

        clear.assert_awaited_once_with(
            server.account_manager.clients,
            "demo_bot",
            "",
        )


if __name__ == "__main__":
    unittest.main()
