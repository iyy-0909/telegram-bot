import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import server
from bot import handlers
from db import crud_users
from db.models import CloneTask, ListenerTask, UserAccount


class ListenerDowngradeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "listener-downgrade.db"
        self.engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
        )
        UserAccount.__table__.create(bind=self.engine)
        CloneTask.__table__.create(bind=self.engine)
        ListenerTask.__table__.create(bind=self.engine)
        self.session_patches = [
            patch.object(crud_users, "SessionLocal", self.session_local),
            patch.object(handlers, "SessionLocal", self.session_local),
        ]
        for item in self.session_patches:
            item.start()

    def tearDown(self):
        handlers.clear_handlers()
        handlers._handler_event_loop = None
        for item in reversed(self.session_patches):
            item.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def seed_paid_listener(self):
        db = self.session_local()
        try:
            user = UserAccount(
                username="downgrade-listener",
                password_hash="test-hash",
                role="user",
                status="active",
                plan_tier="paid",
                feature_keys_json="[]",
            )
            db.add(user)
            db.flush()
            task = ListenerTask(
                owner_user_id=user.id,
                name="paid-listener",
                source_channel="@source",
                target_channels='["@target"]',
                account_id=11,
                bot_id=21,
                enabled=True,
                status="running",
                blocked_keywords='["block"]',
                listen_required_keywords='["required"]',
                replace_words='{"a":"b"}',
                footer="paid-footer",
                remove_contact_lines=True,
                filter_qr_code=True,
                ai_rewrite_enabled=True,
                ai_rewrite_prompt="paid-ai",
                use_random_head=True,
                use_random_body=True,
                use_random_footer=True,
                selected_head_template_group_id=101,
                selected_body_template_group_id=102,
                selected_footer_template_group_id=103,
                selected_filter_template_group_id=104,
                selected_contact_template_group_id=105,
            )
            db.add(task)
            db.commit()
            return user.id, task
        finally:
            db.close()

    async def test_loaded_handler_uses_fresh_free_policy_after_downgrade(self):
        user_id, stale_paid_task = self.seed_paid_listener()
        client = SimpleNamespace(
            add_event_handler=Mock(),
            remove_event_handler=Mock(),
        )

        with (
            patch.object(
                handlers,
                "get_enabled_listener_tasks",
                return_value=[stale_paid_task],
            ),
            patch.object(handlers.account_manager, "get_client", return_value=client),
        ):
            handlers.register_handlers()

        loaded_handler = client.add_event_handler.call_args.args[0]
        crud_users.update_user_access(user_id, plan_tier="free")

        with patch.object(handlers, "process_message", AsyncMock()) as process_message:
            await loaded_handler(SimpleNamespace(message=SimpleNamespace(id=91)))

        process_message.assert_awaited_once()
        runtime_task = process_message.await_args.args[1][0]
        self.assertFalse(runtime_task._runtime_content_processing_enabled)
        self.assertEqual(runtime_task.blocked_keywords, "[]")
        self.assertEqual(runtime_task.listen_required_keywords, "[]")
        self.assertEqual(runtime_task.replace_words, "{}")
        self.assertFalse(runtime_task.remove_contact_lines)
        self.assertFalse(runtime_task.filter_qr_code)
        self.assertFalse(runtime_task.ai_rewrite_enabled)
        self.assertFalse(runtime_task.use_random_head)
        self.assertFalse(runtime_task.use_random_body)
        self.assertFalse(runtime_task.use_random_footer)
        self.assertIsNone(runtime_task.selected_filter_template_group_id)
        self.assertIsNone(runtime_task.selected_head_template_group_id)
        self.assertIsNone(runtime_task.selected_body_template_group_id)
        self.assertIsNone(runtime_task.selected_footer_template_group_id)

    async def test_stale_paid_task_bypasses_all_processing_and_sends_original(self):
        user_id, stale_paid_task = self.seed_paid_listener()
        crud_users.update_user_access(user_id, plan_tier="free")
        raw_text = "required block a paid-footer"
        prepared = {
            "files": [],
            "_raw_text": raw_text,
            "_source_payload": SimpleNamespace(),
        }

        with (
            patch.object(handlers, "process_content_async", AsyncMock()) as process,
            patch.object(handlers, "format_prepared_text") as format_text,
            patch.object(handlers, "target_already_sent", return_value=False),
            patch.object(handlers, "mark_listener_message_sent"),
            patch.object(handlers, "update_listener_status"),
            patch.object(handlers, "add_listener_send_event"),
            patch.object(
                handlers.send_queue,
                "send",
                AsyncMock(return_value={"target_message_ids": [7]}),
            ) as send,
        ):
            format_text.return_value = {
                "text": raw_text,
                "plain_text": raw_text,
            }
            sent = await handlers.send_prepared_to_tasks(
                prepared,
                [stale_paid_task],
                source_message_id=92,
            )

        self.assertTrue(sent)
        process.assert_not_awaited()
        format_text.assert_called_once()
        runtime_task = format_text.call_args.kwargs["task"]
        self.assertFalse(runtime_task._runtime_content_processing_enabled)
        send_payload = send.await_args.args[2]
        self.assertEqual(send_payload["text"], raw_text)
        self.assertEqual(send_payload["plain_text"], raw_text)
        self.assertNotIn("ai_rewritten", send_payload)

    async def test_queue_boundary_downgrade_discards_paid_payload(self):
        user_id, paid_task = self.seed_paid_listener()
        raw_text = "original source text"
        paid_text = "paid rewritten text"
        prepared = {
            "files": [],
            "_raw_text": raw_text,
            "_source_payload": SimpleNamespace(),
        }

        async def queue_after_downgrade(sender, *args, **kwargs):
            crud_users.update_user_access(user_id, plan_tier="free")
            return await sender(
                *args,
                task=kwargs["task"],
                state=kwargs["state"],
                prepared=kwargs["prepared"],
                result=kwargs["result"],
                raw_text=kwargs["raw_text"],
            )

        def format_text(_source, text, **_kwargs):
            return {"text": text, "plain_text": text}

        with (
            patch.object(
                handlers,
                "process_content_async",
                AsyncMock(return_value={"blocked": False, "text": paid_text}),
            ) as process,
            patch.object(handlers, "format_prepared_text", side_effect=format_text),
            patch.object(handlers, "target_already_sent", return_value=False),
            patch.object(handlers, "mark_listener_message_sent"),
            patch.object(handlers, "update_listener_status"),
            patch.object(handlers, "add_listener_send_event"),
            patch.object(
                handlers.send_queue,
                "send",
                AsyncMock(side_effect=queue_after_downgrade),
            ),
            patch.object(
                handlers,
                "send_prepared_by_bot",
                AsyncMock(return_value={"target_message_ids": [9]}),
            ) as network_send,
        ):
            sent = await handlers.send_prepared_to_tasks(
                prepared,
                [paid_task],
                source_message_id=93,
            )

        self.assertTrue(sent)
        process.assert_awaited_once()
        network_send.assert_awaited_once()
        network_payload = network_send.await_args.args[1]
        self.assertEqual(network_payload["text"], raw_text)
        self.assertEqual(network_payload["plain_text"], raw_text)
        self.assertNotEqual(network_payload["text"], paid_text)

    async def test_queue_boundary_skips_removed_target(self):
        _user_id, paid_task = self.seed_paid_listener()
        prepared = {
            "files": [],
            "_raw_text": "source",
            "_source_payload": SimpleNamespace(),
        }

        async def queue_after_target_change(sender, *args, **kwargs):
            db = self.session_local()
            try:
                current = db.query(ListenerTask).filter(
                    ListenerTask.id == paid_task.id
                ).one()
                current.target_channels = '["@other"]'
                db.commit()
            finally:
                db.close()
            return await sender(
                *args,
                task=kwargs["task"],
                state=kwargs["state"],
                prepared=kwargs["prepared"],
                result=kwargs["result"],
                raw_text=kwargs["raw_text"],
            )

        with (
            patch.object(
                handlers,
                "process_content_async",
                AsyncMock(return_value={"blocked": False, "text": "processed"}),
            ),
            patch.object(
                handlers,
                "format_prepared_text",
                return_value={"text": "processed", "plain_text": "processed"},
            ),
            patch.object(handlers, "target_already_sent", return_value=False),
            patch.object(handlers, "update_listener_status"),
            patch.object(handlers, "add_listener_send_event"),
            patch.object(
                handlers.send_queue,
                "send",
                AsyncMock(side_effect=queue_after_target_change),
            ),
            patch.object(handlers, "send_prepared_by_bot", AsyncMock()) as network_send,
        ):
            sent = await handlers.send_prepared_to_tasks(
                prepared,
                [paid_task],
                source_message_id=94,
            )

        self.assertFalse(sent)
        network_send.assert_not_awaited()

    async def test_queue_boundary_skips_disabled_owner(self):
        user_id, paid_task = self.seed_paid_listener()
        prepared = {
            "files": [],
            "_raw_text": "source",
            "_source_payload": SimpleNamespace(),
        }

        async def queue_after_owner_disable(sender, *args, **kwargs):
            db = self.session_local()
            try:
                owner = db.query(UserAccount).filter(UserAccount.id == user_id).one()
                owner.status = "disabled"
                db.commit()
            finally:
                db.close()
            return await sender(
                *args,
                task=kwargs["task"],
                state=kwargs["state"],
                prepared=kwargs["prepared"],
                result=kwargs["result"],
                raw_text=kwargs["raw_text"],
            )

        with (
            patch.object(
                handlers,
                "process_content_async",
                AsyncMock(return_value={"blocked": False, "text": "processed"}),
            ),
            patch.object(
                handlers,
                "format_prepared_text",
                return_value={"text": "processed", "plain_text": "processed"},
            ),
            patch.object(handlers, "target_already_sent", return_value=False),
            patch.object(handlers, "update_listener_status"),
            patch.object(handlers, "add_listener_send_event"),
            patch.object(
                handlers.send_queue,
                "send",
                AsyncMock(side_effect=queue_after_owner_disable),
            ),
            patch.object(handlers, "send_prepared_by_bot", AsyncMock()) as network_send,
        ):
            sent = await handlers.send_prepared_to_tasks(
                prepared,
                [paid_task],
                source_message_id=95,
            )

        self.assertFalse(sent)
        network_send.assert_not_awaited()

    async def test_admin_access_update_requests_thread_safe_handler_reload(self):
        user_id, _task = self.seed_paid_listener()
        request = SimpleNamespace(
            state=SimpleNamespace(current_user={"id": 999, "role": "admin"})
        )

        with patch.object(server, "request_reload_handlers") as request_reload:
            response = server.api_admin_update_user_access(
                user_id,
                server.UserAccessUpdate(plan_tier="free"),
                request,
            )

        self.assertTrue(response["ok"])
        self.assertEqual(response["user"]["plan_tier"], "free")
        request_reload.assert_called_once_with()

    async def test_sync_worker_reload_is_marshaled_to_application_event_loop(self):
        application_thread_id = threading.get_ident()
        handlers._handler_event_loop = asyncio.get_running_loop()
        reload_thread_ids = []

        with patch.object(
            handlers,
            "reload_handlers",
            side_effect=lambda: reload_thread_ids.append(threading.get_ident()),
        ):
            completed = await asyncio.to_thread(
                handlers.request_reload_handlers,
                1,
            )

        self.assertTrue(completed)
        self.assertEqual(reload_thread_ids, [application_thread_id])


if __name__ == "__main__":
    unittest.main()
