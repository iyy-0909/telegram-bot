import re
import uuid
from pathlib import Path


UPLOAD_REF_PREFIX = "support_upload:"
SUPPORT_MEDIA_DIR = Path("data/support_media")


def safe_upload_filename(filename):
    raw_name = Path(filename or "media").name
    suffix = Path(raw_name).suffix.lower()
    stem = Path(raw_name).stem or "media"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "media"
    return f"{uuid.uuid4().hex}_{safe_stem}{suffix}"


def make_uploaded_media_ref(filename):
    return f"{UPLOAD_REF_PREFIX}{filename}"


def is_uploaded_media_ref(value):
    return str(value or "").startswith(UPLOAD_REF_PREFIX)


def resolve_uploaded_media_path(value):
    text = str(value or "").strip()
    filename = text.removeprefix(UPLOAD_REF_PREFIX)
    filename = Path(filename).name
    if not filename:
        return None
    return SUPPORT_MEDIA_DIR / filename


def save_uploaded_media(filename, content):
    SUPPORT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = safe_upload_filename(filename)
    path = SUPPORT_MEDIA_DIR / safe_name
    path.write_bytes(content)
    return {
        "media_ref": make_uploaded_media_ref(safe_name),
        "filename": safe_name,
        "path": str(path),
        "size": len(content or b""),
    }
