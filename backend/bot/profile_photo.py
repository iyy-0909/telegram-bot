MAX_PROFILE_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_PROFILE_PHOTO_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


class ProfilePhotoValidationError(ValueError):
    pass


def _has_supported_signature(content: bytes) -> bool:
    return (
        content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"\x89PNG\r\n\x1a\n")
        or (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        )
    )


def normalize_static_profile_photo(
    content: bytes,
    *,
    content_type: str = "",
):
    """Validate a common web image and convert it to Telegram's required JPG."""
    if not content:
        raise ProfilePhotoValidationError("头像文件不能为空")

    if len(content) > MAX_PROFILE_PHOTO_BYTES:
        raise ProfilePhotoValidationError("头像文件不能超过 10 MB")

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()

    if (
        normalized_content_type
        and normalized_content_type not in ALLOWED_PROFILE_PHOTO_TYPES
    ):
        raise ProfilePhotoValidationError("仅支持 JPG、PNG 或 WebP 图片")

    if not _has_supported_signature(content):
        raise ProfilePhotoValidationError("仅支持 JPG、PNG 或 WebP 图片")

    try:
        import cv2
        import numpy as np

        encoded_source = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(encoded_source, cv2.IMREAD_UNCHANGED)
    except Exception as exc:
        raise ProfilePhotoValidationError("头像图片解析失败") from exc

    if image is None or len(image.shape) < 2:
        raise ProfilePhotoValidationError("头像图片格式无效或文件已损坏")

    height, width = image.shape[:2]

    if width <= 0 or height <= 0:
        raise ProfilePhotoValidationError("头像图片尺寸无效")

    if width + height > 10000:
        raise ProfilePhotoValidationError("头像图片宽度与高度之和不能超过 10000 像素")

    if max(width, height) / min(width, height) > 20:
        raise ProfilePhotoValidationError("头像图片宽高比不能超过 20:1")

    if len(image.shape) == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    try:
        success, encoded_jpeg = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), 92],
        )
    except Exception as exc:
        raise ProfilePhotoValidationError("头像转换为 JPG 失败") from exc

    if not success:
        raise ProfilePhotoValidationError("头像转换为 JPG 失败")

    jpeg_content = encoded_jpeg.tobytes()

    if len(jpeg_content) > MAX_PROFILE_PHOTO_BYTES:
        raise ProfilePhotoValidationError("转换后的头像文件不能超过 10 MB")

    return jpeg_content
