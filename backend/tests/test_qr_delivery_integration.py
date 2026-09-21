import copy
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import cloner, handlers


def task_view(task_id=1, *, enabled=True):
    return SimpleNamespace(
        id=task_id,
        name=f"qr-task-{task_id}",
        account_id=1,
        bot_id=1,
        source_channel="@source",
        target_channels='["@target"]',
        filter_qr_code=enabled,
    )


def media_payload(files):
    return {
        "ok": True,
        "type": "album" if len(files) > 1 else "single",
        "files": list(files),
        "text": "原始说明",
        "_raw_text": "原始说明",
        "_source_payload": SimpleNamespace(message="原始说明", entities=[]),
        "temp_dir": "test-downloads",
    }


class QrDeliveryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_listener(self, prepared, tasks, *, before_queue=None, qr_files=None, during_scan=None):
        sent_payloads = []

        def scan_files(_files):
            if during_scan:
                during_scan()
            return qr_files if qr_files is not None else ["qr.jpg"]

        async def network_send(_target, payload, **_kwargs):
            sent_payloads.append(copy.deepcopy(payload))
            return {"target_message_ids": [7]}

        async def queue(sender, *args, **kwargs):
            if before_queue:
                before_queue()
            return await sender(*args, **{
                key: kwargs[key]
                for key in ("task", "state", "prepared", "result", "raw_text")
            })

        with ExitStack() as stack:
            scan = stack.enter_context(patch.object(
                handlers, "find_qr_code_files", side_effect=scan_files,
            ))
            process = stack.enter_context(patch.object(
                handlers, "process_content_async",
                AsyncMock(return_value={"text": "改写说明", "blocked": False}),
            ))
            stack.enter_context(patch.object(
                handlers, "format_prepared_text",
                side_effect=lambda _source, text, **_kwargs: {"text": text, "plain_text": text},
            ))
            stack.enter_context(patch.object(handlers, "target_already_sent", return_value=False))
            stack.enter_context(patch.object(handlers, "update_listener_status"))
            mark = stack.enter_context(patch.object(handlers, "mark_listener_message_sent"))
            events = stack.enter_context(patch.object(handlers, "add_listener_send_event"))
            stack.enter_context(patch.object(handlers.send_queue, "send", side_effect=queue))
            network = stack.enter_context(patch.object(handlers, "send_prepared_by_bot", side_effect=network_send))
            result = await handlers.send_prepared_to_tasks(prepared, tasks, 10, grouped_id=20)

        return SimpleNamespace(result=result, payloads=sent_payloads, scan=scan,
                               process=process, mark=mark, events=events, network=network)

    async def run_clone(self, prepared, task, *, before_queue=None, qr_files=None, during_scan=None):
        sent_payloads = []

        def scan_files(_files):
            if during_scan:
                during_scan()
            return qr_files if qr_files is not None else ["qr.jpg"]

        async def network_send(_target, payload, **_kwargs):
            sent_payloads.append(copy.deepcopy(payload))
            return {"target_message_ids": [8]}

        async def queue(sender, *args, **kwargs):
            if before_queue:
                before_queue()
            return await sender(*args, **{
                key: kwargs[key]
                for key in ("task", "state", "source_payload", "text", "raw_text")
            })

        with ExitStack() as stack:
            scan = stack.enter_context(patch.object(
                cloner, "find_qr_code_files", side_effect=scan_files,
            ))
            stack.enter_context(patch.object(cloner, "is_album_sent", return_value=False))
            stack.enter_context(patch.object(cloner, "prepare_album", AsyncMock(return_value=prepared)))
            stack.enter_context(patch.object(
                cloner, "format_prepared_text",
                side_effect=lambda _source, text, **_kwargs: {"text": text, "plain_text": text},
            ))
            mark = stack.enter_context(patch.object(cloner, "mark_message_sent"))
            events = stack.enter_context(patch.object(cloner, "add_clone_send_event"))
            cleanup = stack.enter_context(patch.object(cloner, "cleanup_prepared"))
            stack.enter_context(patch.object(cloner.send_queue, "send", side_effect=queue))
            network = stack.enter_context(patch.object(cloner, "send_prepared_by_bot", side_effect=network_send))
            result = await cloner.send_to_targets(
                None, task, ["@target"], 10, 20, "album", [],
                {"text": "改写说明", "_runtime_raw_text": "原始说明"}, delay=0,
            )

        return SimpleNamespace(result=result, payloads=sent_payloads, scan=scan,
                               mark=mark, events=events, cleanup=cleanup, network=network)

    async def test_listener_mixed_album_preserves_shared_media_for_disabled_task(self):
        original = ["qr.jpg", "photo.jpg", "video.mp4"]
        prepared = media_payload(original)
        outcome = await self.run_listener(prepared, [task_view(), task_view(2, enabled=False)])
        self.assertTrue(outcome.result)
        self.assertEqual(len(outcome.payloads), 2)
        self.assertEqual(outcome.payloads[0]["files"], original[1:])
        self.assertEqual(outcome.payloads[0]["type"], "album")
        self.assertEqual(outcome.payloads[0]["text"], "改写说明")
        self.assertEqual(outcome.payloads[1]["files"], original)
        self.assertEqual(prepared["files"], original)
        outcome.scan.assert_called_once_with(original)

    async def test_listener_qr_only_caption_is_filtered_without_ai_or_network(self):
        outcome = await self.run_listener(media_payload(["qr.jpg"]), [task_view()])
        self.assertEqual(outcome.result, 0)
        outcome.process.assert_not_awaited()
        outcome.network.assert_not_awaited()
        outcome.mark.assert_not_called()
        self.assertEqual(outcome.events.call_args.kwargs["event_type"], "filtered")

    async def test_listener_two_media_with_qr_keeps_existing_whole_message_filter(self):
        outcome = await self.run_listener(media_payload(["qr.jpg", "photo.jpg"]), [task_view()])
        outcome.network.assert_not_awaited()
        self.assertEqual(outcome.events.call_args.kwargs["event_type"], "filtered")

    async def test_listener_album_downgrades_to_single_remaining_video(self):
        outcome = await self.run_listener(
            media_payload(["qr.jpg", "qr2.jpg", "video.mp4"]), [task_view()],
            qr_files=["qr.jpg", "qr2.jpg"],
        )
        self.assertEqual(outcome.payloads[0]["files"], ["video.mp4"])
        self.assertEqual(outcome.payloads[0]["type"], "single")
        self.assertEqual(outcome.payloads[0]["text"], "改写说明")

    async def test_listener_queue_enable_filters_without_success_or_failure_event(self):
        task = task_view(enabled=False)
        outcome = await self.run_listener(
            media_payload(["qr.jpg"]), [task],
            before_queue=lambda: setattr(task, "filter_qr_code", True),
        )
        outcome.network.assert_not_awaited()
        outcome.mark.assert_not_called()
        self.assertEqual(outcome.result, 0)
        self.assertEqual([c.kwargs["event_type"] for c in outcome.events.call_args_list],
                         ["sending", "filtered"])
        outcome.scan.assert_called_once()

    async def test_listener_queue_disable_restores_original_media_and_caption(self):
        task = task_view()
        original = ["qr.jpg", "photo.jpg", "video.mp4"]
        outcome = await self.run_listener(
            media_payload(original), [task],
            before_queue=lambda: setattr(task, "filter_qr_code", False),
        )
        self.assertEqual(outcome.payloads[0]["files"], original)
        self.assertEqual(outcome.payloads[0]["text"], "原始说明")
        self.assertFalse(outcome.payloads[0]["_qr_removed_files"])

    async def test_clone_mixed_album_removes_qr_and_cleans_all_original_files(self):
        original = ["qr.jpg", "qr2.jpg", "video.mp4"]
        prepared = media_payload(original)
        outcome = await self.run_clone(prepared, task_view(), qr_files=original[:2])
        self.assertTrue(outcome.result)
        self.assertEqual(outcome.payloads[0]["files"], ["video.mp4"])
        self.assertEqual(outcome.payloads[0]["type"], "single")
        self.assertEqual(outcome.payloads[0]["text"], "改写说明")
        self.assertEqual(prepared["files"], original)
        outcome.cleanup.assert_called_once_with(prepared)
        self.assertEqual(outcome.cleanup.call_args.args[0]["files"], original)
        self.assertEqual(outcome.mark.call_args.kwargs["grouped_id"], 20)

    async def test_clone_qr_only_is_filtered_and_deduped_even_with_caption(self):
        prepared = media_payload(["qr.jpg"])
        outcome = await self.run_clone(prepared, task_view())
        self.assertEqual(outcome.result, "filtered")
        outcome.network.assert_not_awaited()
        outcome.mark.assert_called_once()
        outcome.cleanup.assert_called_once_with(prepared)
        self.assertEqual(outcome.events.call_args.kwargs["event_type"], "filtered")

    async def test_clone_queue_enable_detects_and_filters_with_no_false_success(self):
        task = task_view(enabled=False)
        prepared = media_payload(["qr.jpg"])
        outcome = await self.run_clone(
            prepared, task, before_queue=lambda: setattr(task, "filter_qr_code", True),
        )
        self.assertEqual(outcome.result, "filtered")
        outcome.network.assert_not_awaited()
        outcome.scan.assert_called_once_with(["qr.jpg"])
        self.assertEqual([c.kwargs["event_type"] for c in outcome.events.call_args_list], ["filtered"])
        outcome.mark.assert_called_once()
        outcome.cleanup.assert_called_once_with(prepared)

    async def test_clone_queue_disable_restores_original_media(self):
        task = task_view()
        original = ["qr.jpg", "photo.jpg", "video.mp4"]
        outcome = await self.run_clone(
            media_payload(original), task,
            before_queue=lambda: setattr(task, "filter_qr_code", False),
        )
        self.assertTrue(outcome.result)
        self.assertEqual(outcome.payloads[0]["files"], original)
        self.assertEqual(outcome.payloads[0]["text"], "原始说明")
        self.assertFalse(outcome.payloads[0]["_qr_removed_files"])

    async def test_listener_disable_during_scan_does_not_filter_stale_task_policy(self):
        task = task_view()
        outcome = await self.run_listener(
            media_payload(["qr.jpg"]), [task],
            during_scan=lambda: setattr(task, "filter_qr_code", False),
        )
        self.assertTrue(outcome.result)
        self.assertEqual(outcome.payloads[0]["files"], ["qr.jpg"])
        self.assertEqual(outcome.events.call_args.kwargs["event_type"], "success")

    async def test_clone_disable_during_scan_does_not_filter_stale_task_policy(self):
        task = task_view()
        outcome = await self.run_clone(
            media_payload(["qr.jpg"]), task,
            during_scan=lambda: setattr(task, "filter_qr_code", False),
        )
        self.assertTrue(outcome.result)
        self.assertEqual(outcome.payloads[0]["files"], ["qr.jpg"])
        self.assertEqual(outcome.events.call_args.kwargs["event_type"], "success")


if __name__ == "__main__":
    unittest.main()
