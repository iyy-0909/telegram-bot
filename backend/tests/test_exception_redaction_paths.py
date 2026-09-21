import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot import (
    bot_distributor,
    clone_manager,
    cloner,
    control_bot,
    handlers,
    send_queue,
    support_bot,
)


class BotDistributorRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_error_is_redacted_before_state_database_and_notification(self):
        secret = "distributor-private-password"
        bot = SimpleNamespace(
            id=7,
            name="delivery",
            token="123456789:AAExampleSecretTokenValue",
            enabled=True,
        )
        prepared = {}

        with (
            patch.object(bot_distributor, "get_bot", return_value=bot),
            patch.object(
                bot_distributor,
                "bot_send_prepared",
                AsyncMock(side_effect=RuntimeError(f"Timeout password={secret}")),
            ),
            patch.object(bot_distributor, "update_bot_error") as update_error,
            patch.object(bot_distributor, "notify_error", AsyncMock()) as notify_error,
        ):
            result = await bot_distributor.send_prepared_by_bot(
                "@target",
                prepared,
                bot_id=bot.id,
            )

        self.assertFalse(result)
        self.assertNotIn(secret, prepared["_last_error"])
        self.assertNotIn(secret, update_error.call_args.args[1])
        self.assertNotIn(secret, notify_error.await_args.kwargs["detail"])


class SendQueueRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_and_final_runtime_queue_errors_are_redacted(self):
        secret = "queue-private-token"
        queue = send_queue.SendQueue()
        state = MagicMock()
        state.waiting = {}
        state.add_waiting.return_value = "queue-item"
        sender = AsyncMock(side_effect=RuntimeError(f"access_token={secret}"))

        with (
            patch.object(send_queue, "runtime_queue_state", state),
            patch.object(
                send_queue,
                "get_send_settings",
                return_value={
                    "global_send_delay": 0,
                    "send_retry_count": 1,
                    "send_retry_delay": 1,
                },
            ),
            patch.object(send_queue, "wait_or_stop", AsyncMock(return_value=False)),
        ):
            result = await queue.send(sender, task_id=3, target="@target")

        self.assertFalse(result)
        retry_error = state.update_current.call_args.kwargs["error"]
        final_error = state.finish.call_args.kwargs["error"]
        self.assertNotIn(secret, retry_error)
        self.assertNotIn(secret, final_error)
        self.assertEqual(sender.await_count, 2)


class CloneManagerRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_failure_summary_is_redacted(self):
        secret = "restore-private-token"
        manager = clone_manager.CloneWorkerManager()
        manager.start = AsyncMock(
            side_effect=RuntimeError(f"session_token={secret}")
        )
        task = SimpleNamespace(id=31, status="running", enabled=True)

        with patch.object(clone_manager, "get_all_clone_tasks", return_value=[task]):
            result = await manager.restore_running_tasks()

        self.assertEqual(len(result["failed"]), 1)
        self.assertNotIn(secret, result["failed"][0]["message"])


class ListenerAndCloneEventRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_listener_exception_is_redacted_before_status_and_event(self):
        secret = "listener-private-token"
        task = SimpleNamespace(
            id=11,
            name="listener",
            account_id=2,
            source_channel="@source",
            target_channels='["@target"]',
            bot_id=5,
            filter_qr_code=False,
        )
        prepared = {
            "files": [],
            "_raw_text": "hello",
            "_source_payload": SimpleNamespace(),
        }

        with (
            patch.object(
                handlers,
                "process_content_async",
                AsyncMock(return_value={"text": "hello"}),
            ),
            patch.object(
                handlers,
                "format_prepared_text",
                return_value={"text": "hello", "plain_text": "hello"},
            ),
            patch.object(handlers, "target_already_sent", return_value=False),
            patch.object(
                handlers.send_queue,
                "send",
                AsyncMock(side_effect=RuntimeError(f"session_token={secret}")),
            ),
            patch.object(handlers, "update_listener_status") as update_status,
            patch.object(handlers, "add_listener_send_event") as add_event,
        ):
            result = await handlers.send_prepared_to_tasks(
                prepared,
                [task],
                source_message_id=100,
            )

        self.assertFalse(result)
        self.assertNotIn(secret, update_status.call_args.kwargs["last_error"])
        self.assertNotIn(secret, add_event.call_args.kwargs["error"])

    async def test_clone_exception_is_redacted_before_event_storage(self):
        secret = "clone-private-token"
        task = SimpleNamespace(
            id=12,
            name="clone",
            source_channel="@source",
            bot_id=5,
            filter_qr_code=False,
        )
        prepared = {"ok": True, "files": [], "text": "hello"}

        with (
            patch.object(cloner, "is_message_sent", return_value=False),
            patch.object(
                cloner,
                "prepare_single_message",
                AsyncMock(return_value=prepared),
            ),
            patch.object(
                cloner.send_queue,
                "send",
                AsyncMock(side_effect=RuntimeError(f"api_key={secret}")),
            ),
            patch.object(cloner, "add_clone_send_event") as add_event,
            patch.object(cloner, "cleanup_prepared"),
        ):
            result = await cloner.send_to_targets(
                client=None,
                task=task,
                targets=["@target"],
                source_message_id=101,
                grouped_id=None,
                message_type="single",
                source_payload=SimpleNamespace(),
                text={"text": "hello", "plain_text": "hello"},
                delay=0,
            )

        self.assertFalse(result)
        self.assertNotIn(secret, add_event.call_args.kwargs["error"])


class ControlBotRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_exception_is_redacted_in_reply_and_audit(self):
        secret = "control-private-password"
        update = {
            "message": {
                "text": "/status",
                "chat": {"id": 1},
                "from": {"id": 9, "username": "admin"},
            }
        }

        with (
            patch.object(control_bot, "is_authorized", return_value=True),
            patch.object(
                control_bot,
                "handle_status",
                AsyncMock(side_effect=RuntimeError(f"password={secret}")),
            ),
            patch.object(control_bot, "audit_log") as audit_log,
        ):
            result = await control_bot.handle_command(update)

        self.assertNotIn(secret, result)
        self.assertNotIn(secret, audit_log.call_args.kwargs["error"])

    async def test_control_bot_send_boundary_redacts_text(self):
        secret = "control-send-private-token"
        request_post = MagicMock(return_value={"ok": True})

        with (
            patch.object(
                control_bot,
                "control_config",
                return_value={
                    "chat_id": "1",
                    "token": "control-token",
                    "command_thread_id": "",
                },
            ),
            patch.object(control_bot, "request_post", request_post),
        ):
            await control_bot.send_control_text(f"access_token={secret}")

        sent_data = request_post.call_args.args[2]
        self.assertNotIn(secret, sent_data["text"])


class ControlBotAuditRedactionTests(unittest.TestCase):
    def test_audit_record_redacts_raw_command_result_error_and_parsed_args(self):
        secrets = {
            "raw": "raw-private-password",
            "result": "result-private-token",
            "error": "error-private-token",
            "parsed": "parsed-private-token",
        }
        update = {
            "message": {
                "message_id": 1,
                "text": f"/task_set password={secrets['raw']}",
                "chat": {"id": 2},
                "from": {"id": 9, "username": "admin"},
            }
        }
        db = MagicMock()

        with (
            patch.object(control_bot, "SessionLocal", return_value=db),
            patch.object(
                control_bot,
                "get_single_active_admin",
                return_value={"id": 77},
            ),
        ):
            control_bot.audit_log(
                update,
                "/task_set",
                status="failed",
                result=f"token={secrets['result']}",
                error=f"session_token={secrets['error']}",
                parsed_args={"api_secret": secrets["parsed"]},
            )

        item = db.add.call_args.args[0]
        self.assertEqual(item.owner_user_id, 77)
        self.assertNotIn(secrets["raw"], item.raw_text)
        self.assertNotIn(secrets["result"], item.result_message)
        self.assertNotIn(secrets["error"], item.error_message)
        self.assertNotIn(secrets["parsed"], item.parsed_args)

    def test_historical_listener_error_is_redacted_in_control_reply(self):
        secret = "historical-private-token"
        task = SimpleNamespace(
            id=15,
            name="listener",
            account_id=2,
            bot_id=None,
            source_channel="@source",
            target_channels='["@target"]',
            enabled=True,
            status="running",
            last_error=f"access_token={secret}",
        )

        with patch.object(control_bot, "get_listener_task", return_value=task):
            result = control_bot.handle_task_detail("listener 15")

        self.assertNotIn(secret, result)


class SupportBotRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_test_error_response_is_redacted(self):
        secret = "support-config-private-token"

        with (
            patch.object(
                support_bot,
                "get_support_token_and_settings",
                return_value=("bot-token", {}),
            ),
            patch.object(support_bot, "ensure_polling_mode", AsyncMock()),
            patch.object(
                support_bot,
                "bot_get_me",
                AsyncMock(side_effect=RuntimeError(f"access_token={secret}")),
            ),
        ):
            result = await support_bot.test_support_bot_config()

        self.assertFalse(result["ok"])
        self.assertNotIn(secret, result["message"])

    async def test_group_permission_error_response_is_redacted(self):
        secret = "support-permission-private-token"

        with patch.object(
            support_bot,
            "get_bot_identity",
            AsyncMock(side_effect=RuntimeError(f"api_secret={secret}")),
        ):
            result = await support_bot.check_group_topic_permission(
                "bot-token",
                "-100123",
            )

        self.assertFalse(result["ok"])
        self.assertNotIn(secret, result["message"])

    async def test_recent_updates_error_response_is_redacted(self):
        secret = "support-updates-private-token"

        with (
            patch.object(
                support_bot,
                "get_support_token_and_settings",
                return_value=("bot-token", {}),
            ),
            patch.object(support_bot, "ensure_polling_mode", AsyncMock()),
            patch.object(
                support_bot,
                "request_post",
                MagicMock(side_effect=RuntimeError(f"password={secret}")),
            ),
            patch.object(support_bot, "get_recent_group_chats", return_value=[]),
        ):
            result = await support_bot.get_recent_support_updates()

        self.assertFalse(result["ok"])
        self.assertNotIn(secret, result["message"])


if __name__ == "__main__":
    unittest.main()
