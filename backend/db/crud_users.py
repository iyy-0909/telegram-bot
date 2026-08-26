import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from auth.security import hash_session_token
from db.database import SessionLocal
from db.models import UserAccount, UserSession


class UsernameAlreadyExists(ValueError):
    pass


def user_to_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def get_user_by_username(username):
    db = SessionLocal()
    try:
        return db.query(UserAccount).filter(UserAccount.username == username).first()
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
