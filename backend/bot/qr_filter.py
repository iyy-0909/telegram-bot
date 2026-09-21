from pathlib import Path

from bot.logger import logger


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def should_scan_file(file_path) -> bool:
    return Path(str(file_path or "")).suffix.lower() in IMAGE_SUFFIXES


def default_image_reader(file_path):
    import cv2
    import numpy as np

    # imread cannot reliably open non-ASCII paths on Windows.
    image_bytes = Path(file_path).read_bytes()
    if not image_bytes:
        return None
    return cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)


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


def has_valid_qr_points(points, image) -> bool:
    """Accept QR detector locations, excluding empty/degenerate polygons."""
    if points is None:
        return False

    import cv2
    import numpy as np

    try:
        candidates = np.asarray(points, dtype=np.float32)
        if candidates.size == 0 or candidates.shape[-2:] != (4, 2):
            return False
        candidates = candidates.reshape(-1, 4, 2)
    except (TypeError, ValueError):
        return False

    shape = getattr(image, "shape", None)
    for corners in candidates:
        if not np.isfinite(corners).all():
            continue
        edges = np.linalg.norm(corners - np.roll(corners, 1, axis=0), axis=1)
        if edges.min() < 2 or cv2.contourArea(corners) < 16:
            continue
        if not cv2.isContourConvex(corners):
            continue
        if shape is not None and len(shape) >= 2:
            height, width = shape[:2]
            if (corners[:, 0] < -width * 0.1).any() or (corners[:, 0] > width * 1.1).any():
                continue
            if (corners[:, 1] < -height * 0.1).any() or (corners[:, 1] > height * 1.1).any():
                continue
        return True
    return False


def detector_decodes_image(detector, image) -> bool:
    # Filtering needs to recognise a QR code, even when a logo/compression makes
    # its payload unreadable. OpenCV's QR-specific locator is sufficient evidence.
    for method_name in ("detectAndDecode", "detectAndDecodeMulti", "detect", "detectMulti"):
        method = getattr(detector, method_name, None)
        if method is None:
            continue
        try:
            result = method(image)
            if method_name == "detectAndDecode":
                if detector_result_has_text(result):
                    return True
                points = result[1] if isinstance(result, tuple) and len(result) >= 2 else None
            elif method_name == "detectAndDecodeMulti":
                if not isinstance(result, tuple) or len(result) < 3:
                    continue
                decoded = result[1]
                if isinstance(decoded, (list, tuple)):
                    if any(str(item or "").strip() for item in decoded):
                        return True
                elif detector_result_has_text(decoded):
                    return True
                points = result[2]
            else:
                if not isinstance(result, tuple) or len(result) < 2 or not result[0]:
                    continue
                points = result[1]
            if has_valid_qr_points(points, image):
                return True
        except Exception as error:
            # One unsupported decoder must not disable the remaining locators.
            logger.debug(f"二维码检测方法失败，尝试其他方法 | method={method_name} | {error}")

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
