from datetime import datetime
import json
import re

from sqlalchemy import func, or_

from db.database import SessionLocal
from db.models import Account, MyChannel, SearchBot, SearchBotChannelSubmission
from db.search_utils import build_channel_search_terms


def normalize_bot_username(value):
    text = str(value or "").strip()
    match = re.search(r"(?:https?://)?t\.me/([^/?#]+)", text, re.I)
    if match:
        text = match.group(1)
    text = text.lstrip("@").strip().lower()
    if not text:
        raise ValueError("机器人 username 不能为空")
    return f"@{text}"


def search_bot_to_dict(bot, stats=None):
    stats = stats or {}
    return {
        "id": bot.id,
        "name": bot.name or "",
        "username": bot.username or "",
        "bot_link": bot.bot_link or "",
        "group_name": bot.group_name or "",
        "account_id": bot.account_id,
        "account_name": stats.get("account_name", ""),
        "monthly_active_users": bot.monthly_active_users,
        "status": bot.status or "enabled",
        "submit_template": bot.submit_template or "{{channel_link}}",
        "remark": bot.remark or "",
        "last_check_at": str(bot.last_check_at) if bot.last_check_at else "",
        "last_error": bot.last_error or "",
        "submission_count": int(stats.get("submission_count") or 0),
        "current_channel_count": int(stats.get("current_channel_count") or 0),
        "blocked_channel_count": int(stats.get("blocked_channel_count") or 0),
        "created_at": str(bot.created_at) if bot.created_at else "",
        "updated_at": str(bot.updated_at) if bot.updated_at else "",
    }


def submission_to_dict(row, bot=None, channel=None, account=None):
    admin_rights = _parse_rights_json(getattr(row, "admin_rights_json", ""))
    applied_admin_rights = _parse_rights_json(
        getattr(row, "applied_admin_rights_json", "")
    )

    return {
        "id": row.id,
        "search_bot_id": row.search_bot_id,
        "search_bot_name": bot.name if bot else "",
        "search_bot_username": bot.username if bot else "",
        "my_channel_id": row.my_channel_id,
        "channel_title": channel.title if channel else "",
        "channel_username": channel.username if channel else "",
        "channel_chat_id": channel.chat_id if channel else "",
        "channel_type": channel.channel_type if channel else "",
        "group_name": (channel.group_name if channel else ""),
        "account_id": row.account_id,
        "account_name": account.name if account else "",
        "manual_account_id": getattr(row, "manual_account_id", "") or "",
        "submit_status": row.submit_status or "queued",
        "review_status": row.review_status or "unknown",
        "collection_status": row.collection_status or "unknown",
        "block_status": row.block_status or "unknown",
        "is_current": bool(row.is_current),
        "submitted_text": row.submitted_text or "",
        "admin_rights": {
            str(key): bool(value)
            for key, value in admin_rights.items()
        },
        "applied_admin_rights": {
            str(key): bool(value)
            for key, value in applied_admin_rights.items()
        },
        "permission_status": getattr(row, "permission_status", "") or "pending",
        "permission_last_error": getattr(row, "permission_last_error", "") or "",
        "permissions_applied_at": (
            str(row.permissions_applied_at)
            if getattr(row, "permissions_applied_at", None)
            else ""
        ),
        "telegram_message_id": row.telegram_message_id,
        "last_error": row.last_error or "",
        "submitted_at": str(row.submitted_at) if row.submitted_at else "",
        "last_checked_at": str(row.last_checked_at) if row.last_checked_at else "",
        "created_at": str(row.created_at) if row.created_at else "",
        "updated_at": str(row.updated_at) if row.updated_at else "",
    }


def _parse_rights_json(value):
    try:
        result = json.loads(value or "{}")
    except (TypeError, ValueError):
        result = {}
    return result if isinstance(result, dict) else {}


def _normalize_bot_data(data, existing=None):
    merged = {
        "name": getattr(existing, "name", ""),
        "username": getattr(existing, "username", ""),
        "group_name": getattr(existing, "group_name", ""),
        "account_id": getattr(existing, "account_id", None),
        "monthly_active_users": getattr(existing, "monthly_active_users", None),
        "status": getattr(existing, "status", "enabled"),
        "submit_template": getattr(existing, "submit_template", "{{channel_link}}"),
        "remark": getattr(existing, "remark", ""),
    }
    merged.update(data or {})
    name = str(merged.get("name") or "").strip()
    if not name:
        raise ValueError("机器人名称不能为空")
    username = normalize_bot_username(merged.get("username"))
    monthly = merged.get("monthly_active_users")
    if monthly in ("", None):
        monthly = None
    else:
        monthly = int(monthly)
        if monthly < 0:
            raise ValueError("月活不能小于 0")
    return {
        "name": name,
        "username": username,
        "bot_link": f"https://t.me/{username.lstrip('@')}",
        # Search bots are global resources. Grouping belongs to MyChannel only.
        "group_name": "",
        "account_id": int(merged["account_id"]) if merged.get("account_id") else None,
        "monthly_active_users": monthly,
        "status": str(merged.get("status") or "enabled").strip(),
        "submit_template": str(merged.get("submit_template") or "{{channel_link}}").strip(),
        "remark": str(merged.get("remark") or "").strip(),
    }


def list_search_bots(keyword="", group_name="", status=""):
    db = SessionLocal()
    try:
        query = db.query(SearchBot)
        text = str(keyword or "").strip()
        if text:
            terms = build_channel_search_terms(text) or [text]
            query = query.filter(or_(*[
                field.like(f"%{term}%")
                for term in terms
                for field in (SearchBot.name, SearchBot.username, SearchBot.remark)
            ]))
        if status:
            query = query.filter(SearchBot.status == status)
        bots = query.order_by(SearchBot.id.desc()).all()
        result = []
        for bot in bots:
            account = db.query(Account).filter(Account.id == bot.account_id).first() if bot.account_id else None
            submission_count = db.query(func.count(SearchBotChannelSubmission.id)).filter(
                SearchBotChannelSubmission.search_bot_id == bot.id
            ).scalar()
            current_count = db.query(func.count(SearchBotChannelSubmission.id)).filter(
                SearchBotChannelSubmission.search_bot_id == bot.id,
                SearchBotChannelSubmission.is_current.is_(True),
            ).scalar()
            blocked_count = db.query(func.count(SearchBotChannelSubmission.id)).filter(
                SearchBotChannelSubmission.search_bot_id == bot.id,
                SearchBotChannelSubmission.block_status == "blocked",
            ).scalar()
            result.append(search_bot_to_dict(bot, {
                "account_name": account.name if account else "",
                "submission_count": submission_count,
                "current_channel_count": current_count,
                "blocked_channel_count": blocked_count,
            }))
        return result
    finally:
        db.close()


def get_search_bot(bot_id):
    db = SessionLocal()
    try:
        return db.query(SearchBot).filter(SearchBot.id == bot_id).first()
    finally:
        db.close()


def create_search_bot(data):
    normalized = _normalize_bot_data(data)
    db = SessionLocal()
    try:
        if db.query(SearchBot).filter(SearchBot.username == normalized["username"]).first():
            raise ValueError("该搜索机器人已经存在")
        bot = SearchBot(**normalized, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.add(bot)
        db.commit()
        db.refresh(bot)
        return search_bot_to_dict(bot)
    finally:
        db.close()


def update_search_bot(bot_id, data):
    db = SessionLocal()
    try:
        bot = db.query(SearchBot).filter(SearchBot.id == bot_id).first()
        if not bot:
            return None
        normalized = _normalize_bot_data(data, bot)
        duplicate = db.query(SearchBot).filter(
            SearchBot.username == normalized["username"], SearchBot.id != bot_id
        ).first()
        if duplicate:
            raise ValueError("该搜索机器人已经存在")
        for key, value in normalized.items():
            setattr(bot, key, value)
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        return search_bot_to_dict(bot)
    finally:
        db.close()


def set_search_bot_check_result(bot_id, ok, error="", identity=None):
    db = SessionLocal()
    try:
        bot = db.query(SearchBot).filter(SearchBot.id == bot_id).first()
        if not bot:
            return None
        if bot.status != "disabled":
            bot.status = "enabled" if ok else "error"
        bot.last_check_at = datetime.utcnow()
        bot.last_error = str(error or "")
        identity = identity or {}
        if identity.get("username"):
            bot.username = normalize_bot_username(identity["username"])
            bot.bot_link = f"https://t.me/{bot.username.lstrip('@')}"
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        return search_bot_to_dict(bot)
    finally:
        db.close()


def delete_search_bot(bot_id):
    db = SessionLocal()
    try:
        bot = db.query(SearchBot).filter(SearchBot.id == bot_id).first()
        if not bot:
            return False
        has_history = db.query(SearchBotChannelSubmission.id).filter(
            SearchBotChannelSubmission.search_bot_id == bot_id
        ).first()
        if has_history:
            raise ValueError("该机器人已有提交记录，不能删除，请改为停用")
        db.delete(bot)
        db.commit()
        return True
    finally:
        db.close()


def create_submission(
    search_bot_id,
    my_channel_id,
    account_id,
    submitted_text,
    manual_account_id="",
    admin_rights=None,
    submit_status="queued",
    submitted_at=None,
):
    db = SessionLocal()
    try:
        bot = db.query(SearchBot).filter(SearchBot.id == search_bot_id).first()
        channel = db.query(MyChannel).filter(MyChannel.id == my_channel_id).first()
        if not bot:
            raise ValueError("搜索机器人不存在")
        if bot.status == "disabled":
            raise ValueError("搜索机器人已停用")
        if not channel:
            raise ValueError("频道不存在")
        if channel.status == "disabled":
            raise ValueError("频道已停用")
        if not channel.group_name:
            raise ValueError("频道尚未设置分组，请先完善频道资料")
        row = SearchBotChannelSubmission(
            search_bot_id=search_bot_id,
            my_channel_id=my_channel_id,
            account_id=account_id,
            manual_account_id=str(manual_account_id or "").strip(),
            submit_status=submit_status,
            submitted_text=submitted_text,
            admin_rights_json=json.dumps(admin_rights or {}, ensure_ascii=False, sort_keys=True),
            permission_status="unverified" if submit_status == "manual" else "pending",
            submitted_at=submitted_at,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return submission_to_dict(row, bot, channel)
    finally:
        db.close()


def update_submission_runtime(submission_id, **fields):
    db = SessionLocal()
    try:
        row = db.query(SearchBotChannelSubmission).filter(SearchBotChannelSubmission.id == submission_id).first()
        if not row:
            return None
        for key, value in fields.items():
            if hasattr(row, key):
                if key in {"admin_rights_json", "applied_admin_rights_json"} and isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        bot = db.query(SearchBot).filter(SearchBot.id == row.search_bot_id).first()
        channel = db.query(MyChannel).filter(MyChannel.id == row.my_channel_id).first()
        account = db.query(Account).filter(Account.id == row.account_id).first() if row.account_id else None
        return submission_to_dict(row, bot, channel, account)
    finally:
        db.close()


def get_submission(submission_id):
    db = SessionLocal()
    try:
        result = db.query(
            SearchBotChannelSubmission,
            SearchBot,
            MyChannel,
            Account,
        ).join(
            SearchBot, SearchBot.id == SearchBotChannelSubmission.search_bot_id
        ).join(
            MyChannel, MyChannel.id == SearchBotChannelSubmission.my_channel_id
        ).outerjoin(
            Account, Account.id == SearchBotChannelSubmission.account_id
        ).filter(
            SearchBotChannelSubmission.id == submission_id
        ).first()
        if not result:
            return None
        row, bot, channel, account = result
        return submission_to_dict(row, bot, channel, account)
    finally:
        db.close()


def update_submission_status(submission_id, data):
    allowed = {"review_status", "collection_status", "block_status", "is_current"}
    fields = {key: value for key, value in (data or {}).items() if key in allowed}
    db = SessionLocal()
    try:
        row = db.query(SearchBotChannelSubmission).filter(SearchBotChannelSubmission.id == submission_id).first()
        if not row:
            return None
        if fields.get("block_status") == "blocked":
            fields["is_current"] = False
        if fields.get("is_current"):
            db.query(SearchBotChannelSubmission).filter(
                SearchBotChannelSubmission.my_channel_id == row.my_channel_id,
                SearchBotChannelSubmission.id != row.id,
            ).update({SearchBotChannelSubmission.is_current: False}, synchronize_session=False)
        for key, value in fields.items():
            setattr(row, key, value)
        row.last_checked_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        bot = db.query(SearchBot).filter(SearchBot.id == row.search_bot_id).first()
        channel = db.query(MyChannel).filter(MyChannel.id == row.my_channel_id).first()
        account = db.query(Account).filter(Account.id == row.account_id).first() if row.account_id else None
        return submission_to_dict(row, bot, channel, account)
    finally:
        db.close()


def list_submissions(keyword="", group_name="", search_bot_id=None, my_channel_id=None, block_status=""):
    db = SessionLocal()
    try:
        query = db.query(SearchBotChannelSubmission, SearchBot, MyChannel, Account).join(
            SearchBot, SearchBot.id == SearchBotChannelSubmission.search_bot_id
        ).join(
            MyChannel, MyChannel.id == SearchBotChannelSubmission.my_channel_id
        ).outerjoin(Account, Account.id == SearchBotChannelSubmission.account_id)
        text = str(keyword or "").strip()
        if text:
            terms = build_channel_search_terms(text) or [text]
            query = query.filter(or_(*[
                field.like(f"%{term}%")
                for term in terms
                for field in (SearchBot.name, SearchBot.username, MyChannel.title, MyChannel.username, MyChannel.group_name)
            ]))
        if group_name:
            query = query.filter(MyChannel.group_name == group_name)
        if search_bot_id:
            query = query.filter(SearchBotChannelSubmission.search_bot_id == int(search_bot_id))
        if my_channel_id:
            query = query.filter(SearchBotChannelSubmission.my_channel_id == int(my_channel_id))
        if block_status:
            query = query.filter(SearchBotChannelSubmission.block_status == block_status)
        rows = query.order_by(SearchBotChannelSubmission.id.desc()).all()
        return [submission_to_dict(row, bot, channel, account) for row, bot, channel, account in rows]
    finally:
        db.close()


def render_submission_text(bot, channel):
    template = bot.submit_template or "{{channel_link}}"
    username = channel.username or ""
    channel_link = f"https://t.me/{username.lstrip('@')}" if username else (channel.chat_id or "")
    values = {
        "channel_name": channel.title or username or channel.chat_id or "",
        "channel_link": channel_link,
        "channel_username": username,
        "group_name": channel.group_name or "",
        "remark": channel.remark or "",
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value or ""))
    return template.strip()
