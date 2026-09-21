import json
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from auth.access import PLAN_FREE
from db.database import SessionLocal
from db.crud_bot import build_target_lookup_keys
from db.models import (
    BotAccount,
    CloneTask,
    DailyAdvertisementDelivery,
    ListenerTask,
    TargetBotBinding,
    UserAccount,
)
from utils.redaction import redact_sensitive_text


MAX_DAILY_ATTEMPTS = 5


def _parse_targets(value):
    if isinstance(value, list):
        items = value
    else:
        try:
            items = json.loads(value or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _resolve_owned_bot(db, *, owner_user_id, bot_id, target_channel):
    """Resolve a sender without ever leaving the owning tenant's DB scope."""
    base_filter = (
        BotAccount.owner_user_id == owner_user_id,
        BotAccount.enabled == True,
        func.length(func.trim(BotAccount.token)) > 0,
    )
    if bot_id not in (None, "", 0, "0"):
        return (
            db.query(BotAccount)
            .filter(BotAccount.id == int(bot_id), *base_filter)
            .first()
        )

    lookup_keys = build_target_lookup_keys(target_channel)
    binding = (
        db.query(TargetBotBinding)
        .filter(
            TargetBotBinding.owner_user_id == owner_user_id,
            func.lower(func.trim(TargetBotBinding.target_channel)).in_(lookup_keys),
            TargetBotBinding.enabled == True,
        )
        .first()
    )
    if binding:
        bound_bot = (
            db.query(BotAccount)
            .filter(BotAccount.id == binding.bot_id, *base_filter)
            .first()
        )
        if bound_bot:
            return bound_bot

    return (
        db.query(BotAccount)
        .filter(*base_filter)
        .order_by(BotAccount.id.asc())
        .first()
    )


def list_due_advertisement_targets(now=None):
    current = now or datetime.now()
    access_current = now or datetime.utcnow()
    current_time = current.strftime("%H:%M")
    current_date = current.strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        users = (
            db.query(UserAccount)
            .filter(
                UserAccount.role != "admin",
                UserAccount.status == "active",
                UserAccount.plan_tier == PLAN_FREE,
                or_(
                    UserAccount.access_expires_at.is_(None),
                    UserAccount.access_expires_at > access_current,
                ),
                UserAccount.advertisement_send_time <= current_time,
            )
            .all()
        )
        items = []
        for user in users:
            task_rows = []
            task_rows.extend(
                db.query(
                    ListenerTask.bot_id,
                    ListenerTask.target_channels,
                )
                .filter(
                    ListenerTask.owner_user_id == user.id,
                    ListenerTask.enabled == True,
                )
                .all()
            )
            task_rows.extend(
                db.query(
                    CloneTask.bot_id,
                    CloneTask.target_channels,
                )
                .filter(
                    CloneTask.owner_user_id == user.id,
                    CloneTask.enabled == True,
                )
                .all()
            )

            seen = set()
            for bot_id, target_channels in task_rows:
                for target_channel in _parse_targets(target_channels):
                    bot = _resolve_owned_bot(
                        db,
                        owner_user_id=user.id,
                        bot_id=bot_id,
                        target_channel=target_channel,
                    )
                    if (
                        not bot
                        or int(getattr(bot, "owner_user_id", 0) or 0) != int(user.id)
                        or not bool(getattr(bot, "enabled", False))
                        or not str(getattr(bot, "token", "") or "").strip()
                    ):
                        continue

                    resolved_bot_id = int(bot.id)
                    target_key = (resolved_bot_id, target_channel)
                    if target_key in seen:
                        continue
                    seen.add(target_key)

                    delivery = (
                        db.query(DailyAdvertisementDelivery)
                        .filter(
                            DailyAdvertisementDelivery.user_id == user.id,
                            DailyAdvertisementDelivery.delivery_date == current_date,
                            DailyAdvertisementDelivery.bot_id == resolved_bot_id,
                            DailyAdvertisementDelivery.target_channel == target_channel,
                        )
                        .first()
                    )
                    if delivery and (
                        delivery.status == "sent"
                        or int(delivery.attempt_count or 0) >= MAX_DAILY_ATTEMPTS
                    ):
                        continue

                    items.append(
                        {
                            "user_id": user.id,
                            "delivery_date": current_date,
                            "bot_id": resolved_bot_id,
                            "bot_token": bot.token,
                            "target_channel": target_channel,
                            "advertisement_text": user.advertisement_text,
                        }
                    )
        return items
    finally:
        db.close()


def reserve_advertisement_delivery(item):
    db = SessionLocal()
    try:
        delivery = (
            db.query(DailyAdvertisementDelivery)
            .filter(
                DailyAdvertisementDelivery.user_id == item["user_id"],
                DailyAdvertisementDelivery.delivery_date == item["delivery_date"],
                DailyAdvertisementDelivery.bot_id == item["bot_id"],
                DailyAdvertisementDelivery.target_channel == item["target_channel"],
            )
            .first()
        )
        if delivery and (
            delivery.status == "sent"
            or int(delivery.attempt_count or 0) >= MAX_DAILY_ATTEMPTS
        ):
            return None
        if not delivery:
            delivery = DailyAdvertisementDelivery(
                user_id=item["user_id"],
                delivery_date=item["delivery_date"],
                bot_id=item["bot_id"],
                target_channel=item["target_channel"],
                status="pending",
            )
            db.add(delivery)
        delivery.status = "pending"
        delivery.attempt_count = int(delivery.attempt_count or 0) + 1
        delivery.updated_at = datetime.utcnow()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        db.refresh(delivery)
        return delivery.id
    finally:
        db.close()


def finish_advertisement_delivery(delivery_id, *, sent, error=""):
    db = SessionLocal()
    try:
        delivery = (
            db.query(DailyAdvertisementDelivery)
            .filter(DailyAdvertisementDelivery.id == delivery_id)
            .first()
        )
        if not delivery:
            return False
        delivery.status = "sent" if sent else "error"
        delivery.last_error = "" if sent else redact_sensitive_text(error)
        delivery.sent_at = datetime.utcnow() if sent else None
        delivery.updated_at = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()
