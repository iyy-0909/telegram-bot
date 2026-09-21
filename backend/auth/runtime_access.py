from dataclasses import dataclass
from datetime import datetime

from auth.access import access_summary, effective_feature_keys
from db.database import SessionLocal
from db.models import UserAccount


RUNTIME_ACCESS_MESSAGES = {
    "allowed": "",
    "owner_missing": "资源未绑定用户，后台任务已停止",
    "user_missing": "归属用户不存在，后台任务已停止",
    "disabled": "用户已停用，后台任务已停止",
    "expired": "用户使用期限已到期，后台任务已停止",
    "pending": "用户尚未开通功能，后台任务已停止",
    "feature_revoked": "运行所需功能未授权，后台任务已停止",
}


@dataclass(frozen=True)
class RuntimeAccessDecision:
    allowed: bool
    reason: str
    owner_user_id: int | None
    feature_key: str

    @property
    def message(self):
        return RUNTIME_ACCESS_MESSAGES.get(
            self.reason,
            "用户权限不可用，后台任务已停止",
        )


def evaluate_user_runtime_access(user, feature_key, *, now=None):
    """Evaluate one persisted user for a background runtime feature.

    This intentionally reuses the same plan/feature and expiry semantics as the
    API authorization layer.  Callers query fresh state at each reconciliation,
    so disabling, expiry and plan changes take effect without a restart.
    """
    owner_user_id = getattr(user, "id", None) if user is not None else None
    if user is None:
        return RuntimeAccessDecision(False, "user_missing", None, feature_key)

    feature_keys = effective_feature_keys(
        getattr(user, "role", ""),
        getattr(user, "feature_keys_json", "[]"),
        getattr(user, "plan_tier", None),
    )
    summary = access_summary(
        role=getattr(user, "role", ""),
        status=getattr(user, "status", ""),
        feature_keys=feature_keys,
        access_expires_at=getattr(user, "access_expires_at", None),
        now=now,
    )
    if not summary["available"]:
        return RuntimeAccessDecision(
            False,
            summary["access_state"],
            int(owner_user_id),
            feature_key,
        )
    if feature_key not in feature_keys:
        return RuntimeAccessDecision(
            False,
            "feature_revoked",
            int(owner_user_id),
            feature_key,
        )
    return RuntimeAccessDecision(
        True,
        "allowed",
        int(owner_user_id),
        feature_key,
    )


def get_owner_runtime_access(owner_user_id, feature_key, *, now=None, db=None):
    if owner_user_id in (None, "", 0, "0"):
        return RuntimeAccessDecision(False, "owner_missing", None, feature_key)

    owns_session = db is None
    session = db or SessionLocal()
    try:
        user = (
            session.query(UserAccount)
            .filter(UserAccount.id == int(owner_user_id))
            .first()
        )
        decision = evaluate_user_runtime_access(
            user,
            feature_key,
            now=now or datetime.utcnow(),
        )
        if user is None:
            return RuntimeAccessDecision(
                False,
                "user_missing",
                int(owner_user_id),
                feature_key,
            )
        return decision
    finally:
        if owns_session:
            session.close()


def owner_has_runtime_access(owner_user_id, feature_key, *, now=None, db=None):
    return get_owner_runtime_access(
        owner_user_id,
        feature_key,
        now=now,
        db=db,
    ).allowed
