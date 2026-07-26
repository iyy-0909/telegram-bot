import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from notification.config import NotificationConfig
from notification.formatter import message_summary, notification_priority
from notification.mute import is_muted_until
from notification.ntfy_client import (
    NtfyClient,
    NtfyPublishError,
    generate_ntfy_topic,
    generate_ntfy_url,
    normalize_ntfy_topic,
    parse_ntfy_url,
)
from notification.service import NotificationService


class FakeEvent:
    def __init__(self, *, private=False, channel=False, group=False, message=None):
        self.is_private = private
        self.is_channel = channel
        self.is_group = group
        self.chat_id = 1001
        self.client = SimpleNamespace(
            get_me=AsyncMock(
                return_value=SimpleNamespace(username="collector_account")
            ),
            get_input_entity=AsyncMock(return_value="fallback-input-peer"),
        )
        self.input_chat = SimpleNamespace(user_id=1001, access_hash=2002)
        self.message = message or SimpleNamespace(
            id=7,
            date=datetime(2026, 7, 27, tzinfo=timezone.utc),
            message="hello",
            mentioned=False,
        )

    async def get_chat(self):
        return SimpleNamespace(title="测试群", username="test_group")

    async def get_sender(self):
        return SimpleNamespace(first_name="测试用户", last_name="", username="tester")

    async def get_input_chat(self):
        return self.input_chat


def make_config(*, enabled=True, only_unmuted=True):
    return NotificationConfig(
        enabled=enabled,
        server="https://ntfy.sh",
        topic="test-topic",
        only_unmuted=only_unmuted,
    )


class NotificationFormatterTests(unittest.TestCase):
    def test_photo_with_caption(self):
        message = SimpleNamespace(
            photo=object(),
            video=None,
            video_note=None,
            voice=None,
            audio=None,
            sticker=None,
            gif=None,
            contact=None,
            geo=None,
            poll=None,
            document=None,
            action=None,
            message="图片说明",
        )
        self.assertEqual(message_summary(message), "[图片]\n图片说明")

    def test_document_includes_file_name(self):
        message = SimpleNamespace(
            photo=None,
            video=None,
            video_note=None,
            voice=None,
            audio=None,
            sticker=None,
            gif=None,
            contact=None,
            geo=None,
            poll=None,
            document=object(),
            file=SimpleNamespace(name="report.pdf"),
            action=None,
            message="",
        )
        self.assertEqual(message_summary(message), "[文件] report.pdf")

    def test_private_and_mention_are_high_priority(self):
        private_event = FakeEvent(private=True)
        mentioned_event = FakeEvent(
            group=True,
            message=SimpleNamespace(mentioned=True),
        )
        group_event = FakeEvent(group=True)
        self.assertEqual(notification_priority(private_event), "high")
        self.assertEqual(notification_priority(mentioned_event), "high")
        self.assertEqual(notification_priority(group_event), "default")


class NotificationMuteTests(unittest.TestCase):
    def test_future_mute_is_muted(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(is_muted_until(now + timedelta(minutes=1), now))

    def test_expired_mute_is_not_muted(self):
        now = datetime.now(timezone.utc)
        self.assertFalse(is_muted_until(now - timedelta(seconds=1), now))


class NtfyClientTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_full_ntfy_address(self):
        server, topic = parse_ntfy_url("https://notify.example.com/base/account_4")
        self.assertEqual(server, "https://notify.example.com/base")
        self.assertEqual(topic, "account_4")

    def test_reject_address_without_topic(self):
        with self.assertRaises(ValueError):
            parse_ntfy_url("https://ntfy.sh")

    def test_generate_account_specific_ntfy_address(self):
        address = generate_ntfy_url("https://ntfy.sh", 4)
        server, topic = parse_ntfy_url(address)
        self.assertEqual(server, "https://ntfy.sh")
        self.assertTrue(topic.startswith("telegram_4_"))
        self.assertGreaterEqual(len(topic), 24)

    def test_generate_account_specific_topic_without_server_prefix(self):
        topic = generate_ntfy_topic(4)
        self.assertTrue(topic.startswith("telegram_4_"))
        self.assertNotIn("https://", topic)

    def test_legacy_full_address_is_normalized_to_topic(self):
        self.assertEqual(
            normalize_ntfy_topic("https://ntfy.sh/legacy_topic"),
            "legacy_topic",
        )

    def test_topic_rejects_slashes_and_spaces(self):
        with self.assertRaises(ValueError):
            normalize_ntfy_topic("bad topic/name")

    @patch("notification.ntfy_client.requests.post")
    def test_priority_names_are_mapped_to_ntfy_values(self, post):
        post.return_value = SimpleNamespace(ok=True, status_code=200, text="")
        client = NtfyClient("https://ntfy.sh", "topic")

        client._publish_sync("title", "message", "high")

        self.assertEqual(post.call_args.kwargs["json"]["priority"], 4)
        self.assertEqual(post.call_args.kwargs["json"]["topic"], "topic")

    async def test_http_error_includes_status(self):
        client = NtfyClient("https://ntfy.sh", "topic")
        response = SimpleNamespace(ok=False, status_code=403, text="forbidden")
        client._publish_sync = Mock(return_value=response)

        with self.assertRaises(NtfyPublishError) as context:
            await client.publish("title", "message", "default")

        self.assertEqual(context.exception.status_code, 403)


class NotificationServiceTests(unittest.IsolatedAsyncioTestCase):
    def make_service(self, config, ntfy):
        service = NotificationService(
            config,
            ntfy,
            setting_loader=lambda _account_id: None,
        )
        service.resolve_ntfy_client = AsyncMock(return_value=(ntfy, ""))
        return service

    async def test_muted_chat_is_not_published(self):
        ntfy = SimpleNamespace(publish=AsyncMock())
        service = self.make_service(make_config(), ntfy)

        with patch("notification.service.is_chat_muted", AsyncMock(return_value=True)):
            await service.handle_event(3, FakeEvent(group=True))

        ntfy.publish.assert_not_awaited()

    async def test_unjoined_group_is_not_published(self):
        ntfy = SimpleNamespace(publish=AsyncMock())
        service = self.make_service(make_config(), ntfy)

        with (
            patch(
                "notification.service.is_chat_member",
                AsyncMock(return_value=False),
            ),
            patch("notification.service.is_chat_muted", AsyncMock()) as mute_check,
        ):
            await service.handle_event(3, FakeEvent(group=True))

        mute_check.assert_not_awaited()
        ntfy.publish.assert_not_awaited()

    async def test_membership_check_error_fails_closed(self):
        ntfy = SimpleNamespace(publish=AsyncMock())
        service = self.make_service(make_config(), ntfy)

        with patch(
            "notification.service.is_chat_member",
            AsyncMock(side_effect=RuntimeError("Telegram unavailable")),
        ):
            await service.handle_event(3, FakeEvent(channel=True))

        ntfy.publish.assert_not_awaited()

    async def test_unmuted_private_message_is_published_as_high(self):
        ntfy = SimpleNamespace(publish=AsyncMock(return_value=200))
        service = self.make_service(make_config(), ntfy)
        event = FakeEvent(private=True)

        with patch(
            "notification.service.is_chat_muted",
            AsyncMock(return_value=False),
        ) as mute_check:
            await service.handle_event(3, event)

        ntfy.publish.assert_awaited_once()
        self.assertIs(
            mute_check.await_args.kwargs["input_peer"],
            event.input_chat,
        )
        kwargs = ntfy.publish.await_args.kwargs
        self.assertEqual(kwargs["title"], "@collector_account")
        self.assertEqual(kwargs["priority"], "high")
        self.assertIn("测试群", kwargs["message"])
        self.assertIn("@tester", kwargs["message"])
        self.assertIn("hello", kwargs["message"])

    async def test_per_account_listener_starts_when_legacy_global_switch_is_disabled(self):
        config = make_config(enabled=False)
        service = NotificationService(config, setting_loader=lambda _account_id: None)

        service.start(SimpleNamespace(clients={}))
        await asyncio.sleep(0)

        self.assertIsNotNone(service.sync_task)
        await service.stop()

    async def test_notify_setting_error_fails_closed(self):
        ntfy = SimpleNamespace(publish=AsyncMock())
        service = self.make_service(make_config(), ntfy)

        with patch(
            "notification.service.is_chat_muted",
            AsyncMock(side_effect=RuntimeError("Telegram unavailable")),
        ):
            await service.handle_event(3, FakeEvent(channel=True))

        ntfy.publish.assert_not_awaited()

    async def test_mute_check_can_be_disabled(self):
        ntfy = SimpleNamespace(publish=AsyncMock(return_value=200))
        service = self.make_service(make_config(only_unmuted=False), ntfy)

        with patch("notification.service.is_chat_muted", AsyncMock()) as mute_check:
            await service.handle_event(3, FakeEvent(group=True))

        mute_check.assert_not_awaited()
        ntfy.publish.assert_awaited_once()

    async def test_account_address_overrides_global_client(self):
        account_client = SimpleNamespace(publish=AsyncMock())
        setting = {
            "has_setting": True,
            "configured": True,
            "enabled": True,
            "account_enabled": True,
            "ntfy_url": "account_3",
        }
        service = NotificationService(
            make_config(),
            SimpleNamespace(publish=AsyncMock()),
            setting_loader=lambda _account_id: setting,
        )

        with patch("notification.service.NtfyClient.from_topic", return_value=account_client):
            resolved, reason = await service.resolve_ntfy_client(3)

        self.assertIs(resolved, account_client)
        self.assertEqual(reason, "")

    async def test_disabled_account_setting_does_not_fall_back_to_global(self):
        setting = {
            "has_setting": True,
            "configured": True,
            "enabled": False,
            "account_enabled": True,
            "ntfy_url": "account_3",
        }
        service = NotificationService(
            make_config(),
            SimpleNamespace(publish=AsyncMock()),
            setting_loader=lambda _account_id: setting,
        )

        resolved, reason = await service.resolve_ntfy_client(3)

        self.assertIsNone(resolved)
        self.assertEqual(reason, "account_notification_disabled")


if __name__ == "__main__":
    unittest.main()
