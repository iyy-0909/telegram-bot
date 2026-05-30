from pathlib import Path

from bot.support_media import is_uploaded_media_ref
from bot.support_media import make_uploaded_media_ref
from bot.support_media import resolve_uploaded_media_path
from bot.support_media import safe_upload_filename


def test_safe_upload_filename_keeps_extension_and_removes_bad_chars():
    filename = safe_upload_filename("../../欢迎 图.png")

    assert filename.endswith(".png")
    assert "/" not in filename
    assert "\\" not in filename
    assert ".." not in filename


def test_uploaded_media_ref_resolves_inside_media_dir():
    media_ref = make_uploaded_media_ref("abc.png")

    assert is_uploaded_media_ref(media_ref)
    assert resolve_uploaded_media_path(media_ref) == Path("data/support_media/abc.png")


if __name__ == "__main__":
    test_safe_upload_filename_keeps_extension_and_removes_bad_chars()
    test_uploaded_media_ref_resolves_inside_media_dir()
    print("ok")
