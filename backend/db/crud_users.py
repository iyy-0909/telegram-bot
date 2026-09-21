import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from auth.access import (
    DEFAULT_ADVERTISEMENT_SEND_TIME,
    DEFAULT_FREE_ADVERTISEMENT_TEXT,
    FREE_PLAN_TASK_OVERRIDES,
    PLAN_FREE,
    access_summary,
    dump_feature_keys_json,
    effective_feature_keys,
    normalize_plan_tier,
    normalize_utc_datetime,
    plan_feature_keys,
)
from auth.security import hash_session_token
from db.database import SessionLocal
from db.models import CloneTask, ListenerTask, UserAccount, UserSession


class UsernameAlreadyExists(ValueError):
    pass


def user_to_dict(user):
    feature_keys = effective_feature_keys(
        user.role,
        getattr(user, "feature_keys_json", "[]"),
        getattr(user, "plan_tier", None),
    )
    plan_tier = normalize_plan_tier(getattr(user, "plan_tier", PLAN_FREE))
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "plan_tier": plan_tier,
        "feature_keys": feature_keys,
        "advertisement_text": (
            getattr(user, "advertisement_text", "")
            or DEFAULT_FREE_ADVERTISEMENT_TEXT
        ),
        "advertisement_send_time": (
            getattr(user, "advertisement_send_time", "")
            or DEFAULT_ADVERTISEMENT_SEND_TIME
        ),
        **access_summary(
            role=user.role,
            status=user.status,
            feature_keys=feature_keys,
            access_expires_at=getattr(user, "access_expires_at", None),
        ),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def get_user_by_username(username):
    db = SessionLocal()
    try:
        return db.query(UserAccount).filter(UserAccount.username == username).first()
    finally:
        db.close()


def get_user_by_id(user_id):
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        return user_to_dict(user) if user else None
    finally:
        db.close()


def get_single_active_admin():
    """Return the only active database administrator, or fail closed."""
    db = SessionLocal()
    try:
        admins = (
            db.query(UserAccount)
            .filter(
                UserAccount.role == "admin",
                UserAccount.status == "active",
            )
            .order_by(UserAccount.id.asc())
            .limit(2)
            .all()
        )
        return user_to_dict(admins[0]) if len(admins) == 1 else None
    finally:
        db.close()


def create_user(username, password_hash):
    db = SessionLocal()
    try:
        user = UserAccount(
            username=username,
            password_hash=password_hash,
            role="user",
            status="active",
            plan_tier=PLAN_FREE,
            feature_keys_json=dump_feature_keys_json(plan_feature_keys(PLAN_FREE)),
            access_expires_at=None,
            advertisement_text=DEFAULT_FREE_ADVERTISEMENT_TEXT,
            advertisement_send_time=DEFAULT_ADVERTISEMENT_SEND_TIME,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise UsernameAlreadyExists("用户名已被使用") from exc
        db.refresh(user)
        return user
    finally:
        db.close()


def record_login_failure(user_id, lock_threshold=5, lock_minutes=15):
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not user:
            return None
        user.failed_login_count = int(user.failed_login_count or 0) + 1
        if user.failed_login_count >= lock_threshold:
            user.locked_until = datetime.utcnow() + timedelta(minutes=lock_minutes)
            user.failed_login_count = 0
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def record_login_success(user_id):
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not user:
            return None
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def create_user_session(user_id, session_days=7):
    raw_token = secrets.token_urlsafe(48)
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.expires_at <= now,
        ).delete(synchronize_session=False)
        session = UserSession(
            user_id=user_id,
            token_hash=hash_session_token(raw_token),
            expires_at=now + timedelta(days=session_days),
            created_at=now,
            last_seen_at=now,
        )
        db.add(session)
        db.commit()
        return raw_token, session.expires_at
    finally:
        db.close()


def get_user_by_session_token(raw_token):
    token_hash = hash_session_token(raw_token)
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        row = (
            db.query(UserAccount, UserSession)
            .join(UserSession, UserSession.user_id == UserAccount.id)
            .filter(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserAccount.status == "active",
            )
            .first()
        )
        if not row:
            return None
        user, session = row
        return user_to_dict(user), session.id
    finally:
        db.close()


def revoke_user_session(raw_token):
    token_hash = hash_session_token(raw_token)
    db = SessionLocal()
    try:
        session = (
            db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .first()
        )
        if not session or session.revoked_at:
            return False
        session.revoked_at = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()


def list_users():
    db = SessionLocal()
    try:
        users = (
            db.query(UserAccount)
            .order_by(UserAccount.created_at.desc(), UserAccount.id.desc())
            .all()
        )
        return [user_to_dict(user) for user in users]
    finally:
        db.close()


def update_user_access(
    user_id,
    *,
    plan_tier=None,
    advertisement_text=None,
    advertisement_text_provided=False,
    advertisement_send_time=None,
    advertisement_send_time_provided=False,
    access_expires_at=None,
    access_expires_at_provided=False,
    status=None,
):
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not user:
            return None
        if str(user.role or "").strip().lower() == "admin":
            raise ValueError("管理员账号的权限和使用期限不可在此修改")

        if plan_tier is not None:
            normalized_plan = normalize_plan_tier(plan_tier, strict=True)
            previous_plan = normalize_plan_tier(
                getattr(user, "plan_tier", PLAN_FREE)
            )
            user.plan_tier = normalized_plan
            user.feature_keys_json = dump_feature_keys_json(
                plan_feature_keys(normalized_plan)
            )

            if normalized_plan == PLAN_FREE and previous_plan != PLAN_FREE:
                for model in (ListenerTask, CloneTask):
                    updates = {
                        field: value
                        for field, value in FREE_PLAN_TASK_OVERRIDES.items()
                        if hasattr(model, field)
                    }
                    if hasattr(model, "updated_at"):
                        updates["updated_at"] = datetime.utcnow()
                    (
                        db.query(model)
                        .filter(model.owner_user_id == user.id)
                        .update(updates, synchronize_session=False)
                    )

        if advertisement_text_provided:
            user.advertisement_text = (
                str(advertisement_text or "").strip()
                or DEFAULT_FREE_ADVERTISEMENT_TEXT
            )
        if advertisement_send_time_provided:
            user.advertisement_send_time = (
                str(advertisement_send_time or "").strip()
                or DEFAULT_ADVERTISEMENT_SEND_TIME
            )
        if access_expires_at_provided:
            user.access_expires_at = normalize_utc_datetime(access_expires_at)
        if status is not None:
            user.status = status
            if status == "disabled":
                now = datetime.utcnow()
                (
                    db.query(UserSession)
                    .filter(
                        UserSession.user_id == user.id,
                        UserSession.revoked_at.is_(None),
                    )
                    .update({UserSession.revoked_at: now}, synchronize_session=False)
                )

        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user_to_dict(user)
    finally:
        db.close()
