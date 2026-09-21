import re
import shutil
import uuid
from pathlib import Path

from auth.tenant import current_tenant_user_id


UPLOAD_REF_PREFIX = "support_upload:"
UPLOAD_REF_VERSION = "v2"
SUPPORT_MEDIA_DIR = Path("data/support_media")


class SupportMediaError(ValueError):
    """Base error for private support media references."""


class SupportMediaOwnerRequiredError(SupportMediaError):
    """Raised when support media is accessed without an authenticated owner."""


class SupportMediaAccessError(SupportMediaError):
    """Raised when a media reference belongs to another owner."""


class SupportMediaReferenceError(SupportMediaError):
    """Raised when a support media reference is malformed or unavailable."""


def _required_owner_user_id(owner_user_id=None):
    value = current_tenant_user_id() if owner_user_id is None else owner_user_id
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise SupportMediaOwnerRequiredError("support media owner is required") from exc
    if normalized <= 0:
        raise SupportMediaOwnerRequiredError("support media owner is required")
    return normalized


def _stored_filename(filename):
    text = str(filename or "").strip()
    if (
        not text
        or text in {".", ".."}
        or "\x00" in text
        or Path(text).name != text
        or "/" in text
        or "\\" in text
    ):
        raise SupportMediaReferenceError("invalid support media filename")
    return text


def _owner_media_dir(owner_user_id):
    owner_user_id = _required_owner_user_id(owner_user_id)
    media_root = SUPPORT_MEDIA_DIR.resolve()
    owner_dir = SUPPORT_MEDIA_DIR / str(owner_user_id)
    resolved_owner_dir = owner_dir.resolve()
    try:
        resolved_owner_dir.relative_to(media_root)
    except ValueError as exc:
        raise SupportMediaAccessError("support media directory is outside media root") from exc
    if owner_dir.exists() and owner_dir.is_symlink():
        raise SupportMediaAccessError("support media owner directory cannot be a symlink")
    return owner_dir


def safe_upload_filename(filename):
    raw_name = Path(filename or "media").name
    suffix = Path(raw_name).suffix.lower()
    stem = Path(raw_name).stem or "media"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "media"
    return f"{uuid.uuid4().hex}_{safe_stem}{suffix}"


def make_uploaded_media_ref(filename, owner_user_id=None):
    owner_user_id = _required_owner_user_id(owner_user_id)
    filename = _stored_filename(filename)
    return f"{UPLOAD_REF_PREFIX}{UPLOAD_REF_VERSION}:{owner_user_id}:{filename}"


def is_uploaded_media_ref(value):
    return str(value or "").strip().startswith(UPLOAD_REF_PREFIX)


def is_legacy_uploaded_media_ref(value):
    text = str(value or "").strip()
    return is_uploaded_media_ref(text) and not text.startswith(
        f"{UPLOAD_REF_PREFIX}{UPLOAD_REF_VERSION}:"
    )


def parse_uploaded_media_ref(value):
    text = str(value or "").strip()
    if not is_uploaded_media_ref(text):
        raise SupportMediaReferenceError("not a support media reference")
    payload = text.removeprefix(UPLOAD_REF_PREFIX)
    parts = payload.split(":", 2)
    if len(parts) != 3 or parts[0] != UPLOAD_REF_VERSION:
        raise SupportMediaReferenceError("legacy or malformed support media reference")
    try:
        reference_owner_user_id = int(parts[1])
    except (TypeError, ValueError) as exc:
        raise SupportMediaReferenceError("invalid support media owner") from exc
    if reference_owner_user_id <= 0:
        raise SupportMediaReferenceError("invalid support media owner")
    return reference_owner_user_id, _stored_filename(parts[2])


def resolve_uploaded_media_path(value, owner_user_id=None):
    owner_user_id = _required_owner_user_id(owner_user_id)
    reference_owner_user_id, filename = parse_uploaded_media_ref(value)
    if reference_owner_user_id != owner_user_id:
        raise SupportMediaAccessError("support media belongs to another owner")

    owner_dir = _owner_media_dir(owner_user_id)
    path = owner_dir / filename
    try:
        path.resolve().relative_to(owner_dir.resolve())
    except ValueError as exc:
        raise SupportMediaAccessError("support media path is outside owner directory") from exc
    if path.is_symlink():
        raise SupportMediaAccessError("support media file cannot be a symlink")
    return path


def validate_uploaded_media_ref(value, owner_user_id=None, *, require_exists=True):
    path = resolve_uploaded_media_path(value, owner_user_id=owner_user_id)
    if require_exists and (not path.exists() or not path.is_file()):
        raise SupportMediaReferenceError("support media file does not exist")
    return path


def save_uploaded_media(filename, content, owner_user_id=None):
    owner_user_id = _required_owner_user_id(owner_user_id)
    owner_dir = _owner_media_dir(owner_user_id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_upload_filename(filename)
    path = owner_dir / safe_name
    path.write_bytes(bytes(content or b""))
    return {
        "media_ref": make_uploaded_media_ref(safe_name, owner_user_id=owner_user_id),
        "filename": safe_name,
        "path": str(path),
        "size": len(content or b""),
    }


def migrate_legacy_uploaded_media_ref(value, owner_user_id):
    """Copy a legacy global upload into one owner's directory and return its v2 ref.

    The legacy file is kept in place. Update the owning SupportBot row only after
    this function succeeds.
    """

    owner_user_id = _required_owner_user_id(owner_user_id)
    text = str(value or "").strip()
    if not is_uploaded_media_ref(text):
        return text
    if not is_legacy_uploaded_media_ref(text):
        validate_uploaded_media_ref(text, owner_user_id=owner_user_id)
        return text

    legacy_filename = _stored_filename(text.removeprefix(UPLOAD_REF_PREFIX))
    legacy_path = SUPPORT_MEDIA_DIR / legacy_filename
    media_root = SUPPORT_MEDIA_DIR.resolve()
    try:
        legacy_path.resolve().relative_to(media_root)
    except ValueError as exc:
        raise SupportMediaAccessError("legacy support media path is outside media root") from exc
    if legacy_path.is_symlink() or not legacy_path.exists() or not legacy_path.is_file():
        raise SupportMediaReferenceError("legacy support media file does not exist")

    owner_dir = _owner_media_dir(owner_user_id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    target_name = safe_upload_filename(legacy_filename)
    target_path = owner_dir / target_name
    shutil.copy2(legacy_path, target_path)
    return make_uploaded_media_ref(target_name, owner_user_id=owner_user_id)
