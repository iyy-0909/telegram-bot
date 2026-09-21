import os
import uuid
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SESSION_STORAGE_ROOT = Path(
    os.getenv("TELEGRAM_SESSION_STORAGE_ROOT", BACKEND_DIR / "data" / "sessions")
)


class SessionPathError(ValueError):
    """Raised when a Telegram session path is outside its tenant directory."""


def normalize_session_path(value) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    if normalized.lower().endswith(".session"):
        normalized = normalized[:-8]
    return normalized.rstrip("/")


def _positive_owner_id(owner_user_id) -> int:
    try:
        normalized = int(owner_user_id)
    except (TypeError, ValueError) as exc:
        raise SessionPathError("Telegram Session 缺少有效归属人") from exc
    if normalized <= 0:
        raise SessionPathError("Telegram Session 缺少有效归属人")
    return normalized


def owner_session_directory(owner_user_id, *, storage_root=None) -> Path:
    owner_id = _positive_owner_id(owner_user_id)
    root = Path(storage_root or SESSION_STORAGE_ROOT).resolve(strict=False)
    return (root / f"user_{owner_id}").resolve(strict=False)


def session_file_path(session_path) -> Path:
    path = Path(session_path)
    if path.suffix.lower() != ".session":
        path = path.with_suffix(".session")
    return path


def session_journal_path(session_path) -> Path:
    return Path(f"{session_file_path(session_path)}-journal")


def resolve_legacy_session_path(session_path, *, backend_dir=None) -> Path:
    """Resolve a pre-tenant path for read-only migration purposes."""
    normalized = normalize_session_path(session_path)
    if not normalized:
        raise SessionPathError("Telegram Session 路径为空")
    path = Path(normalized)
    if not path.is_absolute():
        path = Path(backend_dir or BACKEND_DIR) / path
    return path.resolve(strict=False)


def resolve_owner_session_path(
    owner_user_id,
    session_path,
    *,
    create_parent=False,
    backend_dir=None,
    storage_root=None,
) -> Path:
    """Return the absolute Telethon base path after a fail-closed owner check."""
    normalized = normalize_session_path(session_path)
    if not normalized:
        raise SessionPathError("Telegram Session 路径为空")

    base_dir = Path(backend_dir or BACKEND_DIR).resolve(strict=False)
    owner_dir = owner_session_directory(owner_user_id, storage_root=storage_root)
    candidate = Path(normalized)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    resolved = candidate.resolve(strict=False)

    # Generated sessions are deliberately flat. Requiring the direct parent also
    # prevents traversal and makes per-user backup/inspection predictable.
    if resolved.parent != owner_dir:
        raise SessionPathError(
            f"Telegram Session 不属于用户 {int(owner_user_id)} 的隔离目录"
        )
    if not resolved.name or resolved.name in {".", ".."}:
        raise SessionPathError("Telegram Session 文件名无效")
    if create_parent:
        owner_dir.mkdir(parents=True, exist_ok=True)
    return resolved


def stored_owner_session_path(
    owner_user_id,
    absolute_path,
    *,
    backend_dir=None,
    storage_root=None,
) -> str:
    base_dir = Path(backend_dir or BACKEND_DIR).resolve(strict=False)
    resolved = resolve_owner_session_path(
        owner_user_id,
        absolute_path,
        backend_dir=base_dir,
        storage_root=storage_root,
    )
    try:
        return resolved.relative_to(base_dir).as_posix()
    except ValueError:
        return resolved.as_posix()


def session_path_key(session_path, *, backend_dir=None) -> str:
    resolved = resolve_legacy_session_path(
        session_path,
        backend_dir=backend_dir,
    )
    return os.path.normcase(str(resolved)).casefold()


def generate_owner_session_path(
    owner_user_id,
    *,
    occupied_paths=(),
    create_parent=True,
    backend_dir=None,
    storage_root=None,
) -> str:
    base_dir = Path(backend_dir or BACKEND_DIR).resolve(strict=False)
    owner_dir = owner_session_directory(owner_user_id, storage_root=storage_root)
    if create_parent:
        owner_dir.mkdir(parents=True, exist_ok=True)

    occupied_keys = {
        session_path_key(path, backend_dir=base_dir)
        for path in occupied_paths
        if normalize_session_path(path)
    }
    for _attempt in range(100):
        absolute_path = owner_dir / uuid.uuid4().hex
        key = os.path.normcase(str(absolute_path.resolve(strict=False))).casefold()
        if key in occupied_keys:
            continue
        if session_file_path(absolute_path).exists():
            continue
        if session_journal_path(absolute_path).exists():
            continue
        return stored_owner_session_path(
            owner_user_id,
            absolute_path,
            backend_dir=base_dir,
            storage_root=storage_root,
        )
    raise SessionPathError("无法分配唯一的 Telegram Session 路径")
