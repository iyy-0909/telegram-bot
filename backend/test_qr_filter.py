import unittest
import tempfile
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

    def test_multi_code_decode_checks_all_payloads(self):
        class MultiDetector:
            def detectAndDecodeMulti(self, _image):
                return True, ("", "https://t.me/demo"), None, None

        self.assertTrue(has_qr_code("photo.jpg", lambda _: object(), MultiDetector))

    def test_multi_code_success_without_text_or_location_is_not_a_match(self):
        class MultiDetector:
            def detectAndDecodeMulti(self, _image):
                return True, ("", ""), None, None

        self.assertFalse(has_qr_code("photo.jpg", lambda _: object(), MultiDetector))


class RealQrFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import cv2
        except ImportError:
            raise unittest.SkipTest("opencv-python-headless is not installed")

        if not hasattr(cv2, "QRCodeEncoder_create"):
            raise unittest.SkipTest("OpenCV QRCodeEncoder is unavailable")
        cls.cv2 = cv2

    def write_image(self, directory, image, name="qr.png"):
        path = Path(directory) / name
        success, encoded = self.cv2.imencode(path.suffix, image)
        self.assertTrue(success)
        path.write_bytes(encoded.tobytes())
        return path

    def test_has_qr_code_detects_real_generated_small_qr_image(self):
        image = self.cv2.QRCodeEncoder_create().encode("https://t.me/demo")
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_image(directory, image)
            self.assertTrue(has_qr_code(path))

    def test_has_qr_code_reads_unicode_image_paths(self):
        image = self.cv2.QRCodeEncoder_create().encode("https://t.me/demo")
        with tempfile.TemporaryDirectory(prefix="二维码测试") as directory:
            path = self.write_image(directory, image, "频道二维码.png")
            self.assertTrue(has_qr_code(path))

    def test_damaged_qr_is_detected_even_when_payload_cannot_be_decoded(self):
        cv2 = self.cv2
        image = cv2.QRCodeEncoder_create().encode("https://t.me/demo")
        image = cv2.resize(image, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
        height, width = image.shape
        cv2.rectangle(
            image,
            (width // 2 - width // 10, height // 2 - height // 10),
            (width // 2 + width // 10, height // 2 + height // 10),
            255,
            -1,
        )
        decoded, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
        self.assertEqual(decoded, "")
        self.assertIsNotNone(points)
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_image(directory, image)
            self.assertTrue(has_qr_code(path))

    def test_blank_and_ordinary_graphic_images_are_not_qr_codes(self):
        import numpy as np

        image = np.full((300, 300, 3), 255, dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(has_qr_code(self.write_image(directory, image, "blank.png")))
            self.cv2.rectangle(image, (30, 30), (270, 270), (0, 0, 0), 8)
            self.cv2.circle(image, (150, 150), 60, (0, 0, 0), 8)
            self.cv2.putText(image, "SALE", (70, 160), self.cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            self.assertFalse(has_qr_code(self.write_image(directory, image, "graphic.png")))

    def test_degenerate_non_finite_and_out_of_image_locations_are_rejected(self):
        import numpy as np

        image = np.zeros((100, 100, 3), dtype=np.uint8)
        candidates = [
            [[[1, 1], [1, 1], [1, 1], [1, 1]]],
            [[[0, 0], [10, 0], [20, 0], [30, 0]]],
            [[[0, 0], [20, 20], [0, 20], [20, 0]]],
            [[[0, 0], [20, 0], [20, float("nan")], [0, 20]]],
            [[[2000, 2000], [2200, 2000], [2200, 2200], [2000, 2200]]],
        ]
        for points in candidates:
            with self.subTest(points=points):
                detector = FakeDetector(("", points, None))
                self.assertFalse(has_qr_code("image.png", lambda _: image, lambda: detector))

    def test_locator_still_runs_if_decoder_raises(self):
        class DecoderFailure:
            def detectAndDecode(self, _image):
                raise ValueError("cannot decode")

            def detect(self, _image):
                return True, [[[10, 10], [40, 10], [40, 40], [10, 40]]]

        self.assertTrue(has_qr_code("image.png", lambda _: object(), DecoderFailure))


if __name__ == "__main__":
    unittest.main()
