import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from auth.tenant import tenant_scope
from bot import support_bot, support_media
from bot.bot_sender import BotApiError
from db import crud_support


class SupportMediaTenantIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_dir.name) / "support_media"
        self.media_dir_patch = patch.object(
            support_media,
            "SUPPORT_MEDIA_DIR",
            self.media_root,
        )
        self.media_dir_patch.start()

    def tearDown(self):
        self.media_dir_patch.stop()
        self.temp_dir.cleanup()

    async def test_upload_and_resolve_are_scoped_to_current_tenant(self):
        with tenant_scope(101):
            result = support_media.save_uploaded_media("welcome image.png", b"owner-one")
            resolved = support_media.validate_uploaded_media_ref(result["media_ref"])

        self.assertTrue(result["media_ref"].startswith("support_upload:v2:101:"))
        self.assertEqual(resolved.parent, self.media_root / "101")
        self.assertEqual(resolved.read_bytes(), b"owner-one")

        with tenant_scope(202):
            with self.assertRaises(support_media.SupportMediaAccessError):
                support_media.resolve_uploaded_media_path(result["media_ref"])

        with tenant_scope(None):
            with self.assertRaises(support_media.SupportMediaOwnerRequiredError):
                support_media.resolve_uploaded_media_path(result["media_ref"])

    async def test_cross_tenant_send_fails_before_bot_api_request(self):
        result = support_media.save_uploaded_media(
            "welcome.png",
            b"private-image",
            owner_user_id=101,
        )

        request_mock = AsyncMock(return_value={"ok": True, "result": {"message_id": 1}})
        with patch.object(support_bot, "request_post_with_retry", request_mock):
            with self.assertRaises(BotApiError):
                await support_bot.send_telegram_by_type(
                    "123:token",
                    999,
                    "photo",
                    {"file_id": result["media_ref"]},
                    owner_user_id=202,
                )

        request_mock.assert_not_awaited()

        with self.assertRaises(ValueError):
            crud_support._validated_welcome_media_ref(
                result["media_ref"],
                owner_user_id=202,
            )

        self.assertEqual(
            crud_support._validated_welcome_media_ref(
                result["media_ref"],
                owner_user_id=101,
            ),
            result["media_ref"],
        )

    async def test_matching_owner_can_send_uploaded_media(self):
        result = support_media.save_uploaded_media(
            "welcome.png",
            b"private-image",
            owner_user_id=101,
        )

        request_mock = AsyncMock(return_value={"ok": True, "result": {"message_id": 1}})
        with patch.object(support_bot, "request_post_with_retry", request_mock):
            response = await support_bot.send_telegram_by_type(
                "123:token",
                999,
                "photo",
                {"file_id": result["media_ref"]},
                owner_user_id=101,
            )

        self.assertTrue(response["ok"])
        request_mock.assert_awaited_once()

    async def test_legacy_ref_is_fail_closed_until_explicit_migration(self):
        self.media_root.mkdir(parents=True)
        legacy_file = self.media_root / "legacy.png"
        legacy_file.write_bytes(b"legacy-image")
        legacy_ref = "support_upload:legacy.png"

        with self.assertRaises(support_media.SupportMediaReferenceError):
            support_media.resolve_uploaded_media_path(legacy_ref, owner_user_id=101)

        migrated_ref = support_media.migrate_legacy_uploaded_media_ref(
            legacy_ref,
            owner_user_id=101,
        )
        migrated_path = support_media.validate_uploaded_media_ref(
            migrated_ref,
            owner_user_id=101,
        )

        self.assertTrue(legacy_file.exists())
        self.assertEqual(legacy_file.read_bytes(), b"legacy-image")
        self.assertEqual(migrated_path.parent, self.media_root / "101")
        self.assertEqual(migrated_path.read_bytes(), b"legacy-image")

        with self.assertRaises(support_media.SupportMediaAccessError):
            support_media.validate_uploaded_media_ref(
                migrated_ref,
                owner_user_id=202,
            )


if __name__ == "__main__":
    unittest.main()
