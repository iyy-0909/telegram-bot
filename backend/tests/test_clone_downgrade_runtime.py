import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot import cloner
from db import crud_users
from db.models import CloneTask, ListenerTask, UserAccount


class CloneDowngradeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "clone-downgrade.db"
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
            patch.object(cloner, "SessionLocal", self.session_local),
        ]
        for item in self.session_patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.session_patches):
            item.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def seed_clone(self, *, plan_tier="paid"):
        db = self.session_local()
        try:
            user = UserAccount(
                username=f"clone-{plan_tier}",
                password_hash="test-hash",
                role="user",
                status="active",
                plan_tier=plan_tier,
                feature_keys_json="[]",
            )
            db.add(user)
            db.flush()
            task = CloneTask(
                owner_user_id=user.id,
                name="runtime-clone",
                source_channel="@source",
                target_channels='["@old-target"]',
                account_id=11,
                bot_id=21,
                enabled=True,
                status="running",
                blocked_keywords='["blocked"]',
                replace_words='{"original":"paid"}',
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
                selected_link_template_group_id=105,
                selected_contact_template_group_id=106,
            )
            db.add(task)
            db.commit()
            return user.id, task
        finally:
            db.close()

    def downgrade_and_update_targets(self, user_id, task_id, target="@new-target"):
        crud_users.update_user_access(user_id, plan_tier="free")
        db = self.session_local()
        try:
            task = db.query(CloneTask).filter(CloneTask.id == task_id).one()
            task.target_channels = f'["{target}"]'
            db.commit()
        finally:
            db.close()

    async def test_legacy_dirty_free_task_bypasses_all_paid_processing(self):
        _user_id, dirty_free_task = self.seed_clone(plan_tier="free")
        raw_text = "original blocked paid-footer"

        with patch.object(cloner, "process_content_async", AsyncMock()) as process:
            runtime_task, result = await cloner.process_current_clone_content(
                raw_text,
                dirty_free_task,
            )

        process.assert_not_awaited()
        self.assertFalse(runtime_task._runtime_content_processing_enabled)
        self.assertEqual(runtime_task.blocked_keywords, "[]")
        self.assertEqual(runtime_task.replace_words, "{}")
        self.assertFalse(runtime_task.remove_contact_lines)
        self.assertFalse(runtime_task.filter_qr_code)
        self.assertFalse(runtime_task.ai_rewrite_enabled)
        self.assertIsNone(runtime_task.selected_link_template_group_id)
        self.assertTrue(result["_runtime_passthrough"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["text"], raw_text)

    async def test_downgrade_during_ai_await_discards_paid_result(self):
        user_id, stale_paid_task = self.seed_clone()
        raw_text = "original content"

        async def paid_processing(_raw_text, _task):
            crud_users.update_user_access(user_id, plan_tier="free")
            return {
                "blocked": False,
                "text": "PAID AI RESULT",
                "ai_rewritten": True,
            }

        with patch.object(
            cloner,
            "process_content_async",
            side_effect=paid_processing,
        ) as process:
            runtime_task, result = await cloner.process_current_clone_content(
                raw_text,
                stale_paid_task,
            )

        process.assert_awaited_once()
        self.assertFalse(runtime_task._runtime_content_processing_enabled)
        self.assertTrue(result["_runtime_passthrough"])
        self.assertEqual(result["text"], raw_text)
        self.assertNotIn("ai_rewritten", result)

    async def test_paid_policy_change_during_await_also_uses_original(self):
        _user_id, stale_paid_task = self.seed_clone()
        raw_text = "original under changing template"

        async def processing_while_policy_changes(_raw_text, _task):
            db = self.session_local()
            try:
                current = (
                    db.query(CloneTask)
                    .filter(CloneTask.id == stale_paid_task.id)
                    .one()
                )
                current.footer = "new-paid-footer"
                db.commit()
            finally:
                db.close()
            return {"blocked": False, "text": "OLD PAID POLICY RESULT"}

        with patch.object(
            cloner,
            "process_content_async",
            side_effect=processing_while_policy_changes,
        ):
            runtime_task, result = await cloner.process_current_clone_content(
                raw_text,
                stale_paid_task,
            )

        self.assertTrue(runtime_task._runtime_content_processing_enabled)
        self.assertEqual(runtime_task.footer, "new-paid-footer")
        self.assertTrue(result["_runtime_passthrough"])
        self.assertEqual(result["text"], raw_text)
        self.assertNotIn("OLD PAID POLICY RESULT", result.values())

    async def test_media_prepare_await_refreshes_free_policy_and_targets(self):
        user_id, stale_paid_task = self.seed_clone()
        raw_text = "original caption"
        paid_text = {
            "text": "PAID AI CAPTION",
            "plain_text": "PAID AI CAPTION",
            "_runtime_raw_text": raw_text,
            "_runtime_passthrough": False,
            "_runtime_policy_signature": cloner._clone_content_policy_signature(
                cloner.load_current_clone_runtime_task(stale_paid_task)
            ),
        }

        async def prepare_after_downgrade(_source, _text):
            self.downgrade_and_update_targets(
                user_id,
                stale_paid_task.id,
            )
            return {
                "ok": True,
                "files": ["photo.jpg"],
                "text": "PAID AI CAPTION",
            }

        with (
            patch.object(cloner, "is_message_sent", return_value=False),
            patch.object(
                cloner,
                "prepare_single_message",
                side_effect=prepare_after_downgrade,
            ),
            patch.object(
                cloner,
                "format_prepared_text",
                side_effect=lambda _source, value, **_kwargs: {
                    "text": value,
                    "plain_text": value,
                },
            ),
            patch.object(cloner, "mark_message_sent"),
            patch.object(cloner, "add_clone_send_event"),
            patch.object(cloner, "cleanup_prepared"),
            patch.object(
                cloner.send_queue,
                "send",
                AsyncMock(return_value={"target_message_ids": [7]}),
            ) as send,
        ):
            sent = await cloner.send_to_targets(
                client=None,
                task=stale_paid_task,
                targets=["@old-target"],
                source_message_id=91,
                grouped_id=None,
                message_type="single",
                source_payload=SimpleNamespace(message=raw_text, entities=[]),
                text=paid_text,
                delay=0,
            )

        self.assertTrue(sent)
        self.assertEqual(send.await_args.args[1], "@new-target")
        payload = send.await_args.args[2]
        self.assertEqual(payload["text"], raw_text)
        self.assertEqual(payload["plain_text"], raw_text)
        self.assertEqual(payload["files"], ["photo.jpg"])
        self.assertNotIn("PAID AI CAPTION", payload.values())

    async def test_queue_wait_downgrade_rechecks_at_network_boundary(self):
        user_id, stale_paid_task = self.seed_clone()
        raw_text = "original queue caption"
        runtime_task = cloner.load_current_clone_runtime_task(stale_paid_task)
        paid_text = {
            "text": "PAID QUEUED RESULT",
            "plain_text": "PAID QUEUED RESULT",
            "_runtime_raw_text": raw_text,
            "_runtime_passthrough": False,
            "_runtime_policy_signature": cloner._clone_content_policy_signature(
                runtime_task
            ),
        }

        async def queue_wait_then_send(sender, *args, **kwargs):
            crud_users.update_user_access(user_id, plan_tier="free")
            return await sender(
                *args,
                task=kwargs["task"],
                state=kwargs["state"],
                source_payload=kwargs["source_payload"],
                text=kwargs["text"],
                raw_text=kwargs["raw_text"],
            )

        with (
            patch.object(cloner, "is_message_sent", return_value=False),
            patch.object(
                cloner,
                "prepare_single_message",
                AsyncMock(
                    return_value={
                        "ok": True,
                        "files": ["photo.jpg"],
                        "text": "PAID QUEUED RESULT",
                    }
                ),
            ),
            patch.object(
                cloner,
                "format_prepared_text",
                side_effect=lambda _source, value, **_kwargs: {
                    "text": value,
                    "plain_text": value,
                },
            ),
            patch.object(cloner, "mark_message_sent"),
            patch.object(cloner, "add_clone_send_event"),
            patch.object(cloner, "cleanup_prepared"),
            patch.object(
                cloner,
                "send_prepared_by_bot",
                AsyncMock(return_value={"target_message_ids": [8]}),
            ) as network_send,
            patch.object(
                cloner.send_queue,
                "send",
                side_effect=queue_wait_then_send,
            ),
        ):
            sent = await cloner.send_to_targets(
                client=None,
                task=stale_paid_task,
                targets=["@old-target"],
                source_message_id=92,
                grouped_id=None,
                message_type="single",
                source_payload=SimpleNamespace(message=raw_text, entities=[]),
                text=paid_text,
                delay=0,
            )

        self.assertTrue(sent)
        network_payload = network_send.await_args.args[1]
        self.assertEqual(network_payload["text"], raw_text)
        self.assertEqual(network_payload["plain_text"], raw_text)
        self.assertEqual(network_payload["files"], ["photo.jpg"])
        self.assertNotIn("PAID QUEUED RESULT", network_payload.values())


if __name__ == "__main__":
    unittest.main()
