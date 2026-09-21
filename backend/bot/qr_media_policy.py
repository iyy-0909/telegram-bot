"""Select outgoing media without changing shared downloads or source messages."""

import mimetypes
import os

from bot.qr_filter import should_scan_file


def _file_key(path):
    return os.path.normcase(os.path.normpath(str(path)))


def is_picture_or_video(path):
    if should_scan_file(path):
        return True
    mime_type, _ = mimetypes.guess_type(str(path))
    return bool(mime_type and mime_type.startswith(("image/", "video/")))


def filter_qr_media(prepared, enabled=True, qr_files=None):
    """Return a task-specific view; detection and download cleanup stay outside.

    More than two pictures/videos: remove QR images and retain other media.
    One/two media with QR images: retain the existing whole-message filter.
    All-QR messages are always blocked, even if they also have a caption.
    """
    view = dict(prepared)
    files = list(prepared.get("_qr_original_files", prepared.get("files") or []))
    original_type = prepared.get("_qr_original_type", prepared.get("type"))
    detected = list(qr_files if qr_files is not None else prepared.get("_qr_code_files") or [])
    view.update(
        files=list(files),
        _qr_original_files=files,
        _qr_original_type=original_type,
        _qr_filter_blocked=False,
        _qr_filter_message="",
        _qr_removed_files=[],
    )
    if qr_files is not None or "_qr_code_files" in prepared:
        view["_qr_code_files"] = detected
    if original_type is not None:
        view["type"] = original_type
    if not enabled or not detected:
        return view

    qr_keys = {_file_key(path) for path in detected}
    removed = [path for path in files if should_scan_file(path) and _file_key(path) in qr_keys]
    if not removed:
        return view
    removed_keys = {_file_key(path) for path in removed}
    remaining = [path for path in files if _file_key(path) not in removed_keys]
    media_count = sum(is_picture_or_video(path) for path in files)
    view["_qr_removed_files"] = list(removed)
    if not remaining:
        view["_qr_filter_blocked"] = True
        view["_qr_filter_message"] = f"二维码过滤：全部 {len(removed)} 个媒体均为二维码图片，已过滤整条消息"
    elif media_count <= 2:
        view["_qr_filter_blocked"] = True
        view["_qr_filter_message"] = (
            f"二维码过滤：图片/视频共 {media_count} 个（不超过 2 个），"
            f"检测到 {len(removed)} 张二维码图片，已过滤整条消息"
        )
    else:
        view["files"] = remaining
        view["type"] = "album" if len(remaining) >= 2 else "single"
        view["_qr_filter_message"] = (
            f"二维码过滤：图片/视频共 {media_count} 个，"
            f"已移除 {len(removed)} 张二维码图片，保留 {len(remaining)} 个媒体"
        )
    return view
