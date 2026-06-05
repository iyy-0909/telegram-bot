from pathlib import Path

from bot.logger import logger


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def should_scan_file(file_path) -> bool:
    return Path(str(file_path or "")).suffix.lower() in IMAGE_SUFFIXES


def default_image_reader(file_path):
    import cv2

    return cv2.imread(str(file_path))


def default_detector_factory():
    import cv2

    return cv2.QRCodeDetector()


def detector_result_has_text(result) -> bool:
    if isinstance(result, tuple):
        first = result[0] if result else ""
    else:
        first = result

    if isinstance(first, (list, tuple)):
        return any(str(item or "").strip() for item in first)

    return bool(str(first or "").strip())


def detector_decodes_image(detector, image) -> bool:
    if hasattr(detector, "detectAndDecode"):
        if detector_result_has_text(detector.detectAndDecode(image)):
            return True

    if hasattr(detector, "detectAndDecodeMulti"):
        result = detector.detectAndDecodeMulti(image)
        if isinstance(result, tuple) and len(result) >= 2:
            decoded = result[1]
            return detector_result_has_text(decoded)

    return False


def maybe_upscale_small_image(image):
    shape = getattr(image, "shape", None)

    if not shape or len(shape) < 2:
        return None

    height, width = shape[:2]
    max_side = max(height, width)

    if max_side >= 600 or max_side <= 0:
        return None

    try:
        import cv2

        scale = max(2, min(12, 600 // max_side))
        return cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_NEAREST,
        )
    except Exception as e:
        logger.debug(f"二维码小图放大失败，跳过放大重试 | file_shape={shape} | {e}")
        return None


def has_qr_code(file_path, image_reader=None, detector_factory=None) -> bool:
    if not should_scan_file(file_path):
        return False

    reader = image_reader or default_image_reader
    factory = detector_factory or default_detector_factory

    try:
        image = reader(file_path)

        if image is None:
            return False

        detector = factory()

        if detector_decodes_image(detector, image):
            return True

        upscaled = maybe_upscale_small_image(image)

        if upscaled is not None and detector_decodes_image(detector, upscaled):
            return True

        return False

    except ImportError as e:
        logger.warning(f"二维码检测依赖未安装，跳过检测 | file={file_path} | {e}")
        return False
    except Exception as e:
        logger.warning(f"二维码检测失败，跳过检测 | file={file_path} | {e}")
        return False


def find_qr_code_files(file_paths) -> list:
    matched = []

    for file_path in file_paths or []:
        if has_qr_code(file_path):
            matched.append(str(file_path))

    return matched
