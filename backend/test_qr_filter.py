import unittest
from pathlib import Path

from bot.qr_filter import has_qr_code, should_scan_file


class FakeDetector:
    def __init__(self, result):
        self.result = result

    def detectAndDecode(self, _image):
        return self.result


class QrFilterTest(unittest.TestCase):
    def test_should_scan_only_common_images(self):
        self.assertTrue(should_scan_file("photo.jpg"))
        self.assertTrue(should_scan_file("photo.jpeg"))
        self.assertTrue(should_scan_file("photo.png"))
        self.assertTrue(should_scan_file("photo.webp"))
        self.assertFalse(should_scan_file("video.mp4"))
        self.assertFalse(should_scan_file("document.pdf"))

    def test_has_qr_code_uses_detector_result(self):
        with self.subTest("decoded text means qr code"):
            self.assertTrue(
                has_qr_code(
                    Path("photo.jpg"),
                    image_reader=lambda _path: object(),
                    detector_factory=lambda: FakeDetector(("https://t.me/demo", None, None)),
                )
            )

    def test_has_qr_code_returns_false_without_decoded_text(self):
        self.assertFalse(
            has_qr_code(
                Path("photo.jpg"),
                image_reader=lambda _path: object(),
                detector_factory=lambda: FakeDetector(("", None, None)),
            )
        )

    def test_has_qr_code_detects_real_generated_qr_image(self):
        try:
            import cv2
        except ImportError:
            self.skipTest("opencv-python-headless is not installed")

        if not hasattr(cv2, "QRCodeEncoder_create"):
            self.skipTest("OpenCV QRCodeEncoder is unavailable")

        image = cv2.QRCodeEncoder_create().encode("https://t.me/demo")
        path = Path("data") / "tmp_qr_filter_test.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)

        try:
            self.assertTrue(has_qr_code(path))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
