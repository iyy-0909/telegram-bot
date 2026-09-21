import unittest
from copy import deepcopy
from pathlib import Path

from bot.qr_media_policy import filter_qr_media


class QrMediaPolicyTests(unittest.TestCase):
    def prepared(self, files):
        return {"ok": True, "type": "album" if len(files) > 1 else "single",
                "files": files, "text": "原始说明", "entities": [{"type": "bold"}],
                "message_ids": [11, 12, 13], "temp_dir": "downloads/batch"}

    def test_mixed_photo_video_removes_qr_only_and_keeps_order_caption(self):
        source = self.prepared(["cover.jpg", "qr.png", "clip.mp4", "detail.jpg"])
        original = deepcopy(source)
        result = filter_qr_media(source, qr_files=["qr.png"])
        self.assertFalse(result["_qr_filter_blocked"])
        self.assertEqual(result["files"], ["cover.jpg", "clip.mp4", "detail.jpg"])
        self.assertEqual(result["type"], "album")
        for key in ("text", "entities", "message_ids", "temp_dir"):
            self.assertEqual(result[key], source[key])
        self.assertEqual(source, original)

    def test_three_media_can_become_one_video(self):
        result = filter_qr_media(self.prepared(["qr1.png", "clip.mp4", "qr2.jpg"]),
                                 qr_files=["qr1.png", "qr2.jpg"])
        self.assertEqual(result["files"], ["clip.mp4"])
        self.assertEqual(result["type"], "single")
        self.assertFalse(result["_qr_filter_blocked"])

    def test_all_qr_blocks_regardless_of_count_or_caption(self):
        for count in (1, 2, 3, 5):
            with self.subTest(count=count):
                files = [f"qr{i}.png" for i in range(count)]
                result = filter_qr_media(self.prepared(files), qr_files=files)
                self.assertTrue(result["_qr_filter_blocked"])
                self.assertIn("全部", result["_qr_filter_message"])

    def test_exactly_two_media_keeps_whole_message_filter(self):
        result = filter_qr_media(self.prepared(["qr.png", "clip.mp4"]), qr_files=["qr.png"])
        self.assertTrue(result["_qr_filter_blocked"])
        self.assertIn("不超过 2", result["_qr_filter_message"])

    def test_documents_and_audio_do_not_satisfy_picture_video_threshold(self):
        result = filter_qr_media(self.prepared(["qr.png", "clip.mp4", "a.pdf", "b.mp3"]),
                                 qr_files=["qr.png"])
        self.assertTrue(result["_qr_filter_blocked"])

    def test_disabled_filter_restores_source_for_other_tasks_and_runtime_changes(self):
        source = self.prepared(["a.jpg", "qr.png", "v.mp4"])
        enabled = filter_qr_media(source, qr_files=["qr.png"])
        disabled = filter_qr_media(enabled, enabled=False)
        self.assertEqual(disabled["files"], source["files"])
        self.assertEqual(disabled["type"], "album")
        self.assertFalse(disabled["_qr_filter_blocked"])
        self.assertEqual(disabled["_qr_removed_files"], [])
        self.assertEqual(filter_qr_media(disabled)["files"], enabled["files"])
        disabled["files"].clear()
        self.assertEqual(len(source["files"]), 3)

    def test_no_qr_and_text_messages_keep_their_type_and_files(self):
        for files in ([], ["cover.jpg"], ["a.jpg", "b.mp4"]):
            with self.subTest(files=files):
                source = self.prepared(files)
                result = filter_qr_media(source, qr_files=[])
                self.assertFalse(result["_qr_filter_blocked"])
                self.assertEqual(result["files"], files)
                self.assertEqual(result["type"], source["type"])

    def test_disabled_unscanned_media_does_not_create_an_empty_scan_cache(self):
        source = self.prepared(["qr.png", "a.jpg", "v.mp4"])
        disabled = filter_qr_media(source, enabled=False)
        self.assertNotIn("_qr_code_files", disabled)
        enabled = filter_qr_media(disabled, qr_files=["qr.png"])
        self.assertEqual(enabled["files"], ["a.jpg", "v.mp4"])

    def test_scanner_string_paths_match_path_objects_and_ignore_non_images(self):
        source = self.prepared([Path("qr.png"), Path("a.jpg"), Path("v.mp4")])
        result = filter_qr_media(source, qr_files=["qr.png", "v.mp4", "missing.jpg"])
        self.assertEqual(result["files"], [Path("a.jpg"), Path("v.mp4")])
        self.assertEqual(result["_qr_removed_files"], [Path("qr.png")])


if __name__ == "__main__":
    unittest.main()
