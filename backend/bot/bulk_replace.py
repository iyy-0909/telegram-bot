import asyncio
import ast
import json
from datetime import datetime

from db.database import SessionLocal
from db.models import (
    BotAccount,
    BulkReplaceJob,
    BulkReplaceJobItem,
    CloneSendEvent,
    ListenerSendEvent,
    MyChannel,
)
from bot.bot_sender import (
    BotApiError,
    bot_edit_message_caption,
    bot_edit_message_text,
    request_post,
)
from bot.logger import logger


SOURCE_MODELS = {
    "clone": CloneSendEvent,
    "listener": ListenerSendEvent,
}


def normalize_key(value):
    return str(value or "").strip().lower()


def channel_keys(channel):
    keys = {
        normalize_key(channel.username),
        normalize_key(channel.chat_id),
    }
    return {item for item in keys if item}


def record_target_keys(record):
    keys = {
        normalize_key(getattr(record, "target", "")),
        normalize_key(getattr(record, "target_chat_id", "")),
    }
    return {item for item in keys if item}


def extract_edit_text(record):
    text = getattr(record, "text", "") or ""
    caption = getattr(record, "caption", "") or ""

    if text:
        return "text", text

    if caption:
        return "caption", caption

    return "", ""


def replace_text(original, old_text, new_text):
    return (original or "").replace(old_text, new_text)


def serialize_channel_ids(channel_ids):
    return json.dumps(channel_ids or [], ensure_ascii=False)


def get_selected_channels(db, channel_ids):
    ids = []
    for item in channel_ids or []:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue

    if not ids:
        return []

    return db.query(MyChannel).filter(MyChannel.id.in_(ids)).all()


def record_matches_channels(record, channel_key_set):
    return bool(record_target_keys(record) & channel_key_set)


def build_preview_item(record, source_type, channel, old_text, new_text):
    content_type, original_text = extract_edit_text(record)
    target_message_id = getattr(record, "target_message_id", None)
    target_chat_id = (
        getattr(record, "target_chat_id", "")
        or getattr(record, "target", "")
        or getattr(channel, "chat_id", "")
        or getattr(channel, "username", "")
    )
    bot_id = getattr(record, "bot_id", None) or getattr(channel, "bot_id", None)
    can_edit = True
    reason = ""

    if not target_chat_id:
        can_edit = False
        reason = "缺少 target_chat_id"
    elif not target_message_id:
        can_edit = False
        reason = "缺少 target_message_id"
    elif not content_type or not original_text:
        can_edit = False
        reason = "本地记录未保存文本或 caption，无法安全替换"
    elif old_text not in original_text:
        can_edit = False
        reason = "本地记录未命中旧内容"
    elif not bot_id:
        can_edit = False
        reason = "缺少发送 Bot"

    return {
        "record_id": record.id,
        "source_type": source_type,
        "target_chat_id": target_chat_id,
        "target_message_id": target_message_id,
        "channel_id": channel.id if channel else None,
        "channel_title": (
            getattr(channel, "title", "")
            or getattr(channel, "username", "")
            or getattr(channel, "chat_id", "")
            or getattr(record, "target", "")
        ),
        "message_type": content_type or getattr(record, "message_type", "") or "",
        "original_text": original_text,
        "replaced_text": replace_text(original_text, old_text, new_text),
        "created_at": str(getattr(record, "created_at", "") or ""),
        "can_edit": can_edit,
        "reason": reason,
        "bot_id": bot_id,
    }


def source_types_for_filter(source_type):
    if source_type in SOURCE_MODELS:
        return [source_type]
    return list(SOURCE_MODELS.keys())


def preview_bulk_replace(
    *,
    channel_ids,
    old_text,
    new_text,
    message_type="all",
    source_type="all",
    start_time=None,
    end_time=None,
    limit=500,
):
    old_text = old_text or ""
    if not old_text:
        raise ValueError("old_text 不能为空")

    try:
        limit = max(1, min(int(limit or 500), 5000))
    except (TypeError, ValueError):
        limit = 500

    db = SessionLocal()

    try:
        channels = get_selected_channels(db, channel_ids)
        channel_key_set = set()
        channel_by_key = {}

        for channel in channels:
            for key in channel_keys(channel):
                channel_key_set.add(key)
                channel_by_key[key] = channel

        if not channel_key_set:
            return {
                "total": 0,
                "items": [],
                "unavailable_count": 0,
                "message": "未选择有效频道",
            }

        items = []
        unavailable_count = 0

        for current_source_type in source_types_for_filter(source_type):
            model = SOURCE_MODELS[current_source_type]
            query = db.query(model).order_by(model.id.desc())

            if start_time:
                query = query.filter(model.created_at >= start_time)

            if end_time:
                query = query.filter(model.created_at <= end_time)

            for record in query.limit(limit).all():
                matching_keys = record_target_keys(record) & channel_key_set
                if not matching_keys:
                    continue

                channel = channel_by_key.get(next(iter(matching_keys)))
                content_type, original_text = extract_edit_text(record)

                if message_type in ["text", "caption"] and content_type != message_type:
                    continue

                if not original_text or old_text not in original_text:
                    if not original_text:
                        unavailable_count += 1
                    continue

                items.append(
                    build_preview_item(
                        record,
                        current_source_type,
                        channel,
                        old_text,
                        new_text,
                    )
                )

                if len(items) >= limit:
                    break

            if len(items) >= limit:
                break

        return {
            "total": len(items),
            "items": items,
            "unavailable_count": unavailable_count,
        }

    finally:
        db.close()


def parse_retry_after(error):
    try:
        payload = ast.literal_eval(str(error))
        parameters = payload.get("parameters") or {}
        retry_after = parameters.get("retry_after")
        return int(retry_after) if retry_after else None
    except Exception:
        return None


def error_text(error):
    return str(error)[:1000]


def get_record(db, source_type, record_id):
    model = SOURCE_MODELS.get(source_type)
    if not model:
        return None
    return db.query(model).filter(model.id == int(record_id)).first()


def get_bot_for_record(db, record, channel):
    bot_id = getattr(record, "bot_id", None) or getattr(channel, "bot_id", None)
    if not bot_id:
        return None
    return db.query(BotAccount).filter(BotAccount.id == bot_id).first()


async def check_edit_permission(bot, chat_id):
    try:
        me = await asyncio.to_thread(request_post, bot.token, "getMe", {}, None)
        bot_user_id = (me.get("result") or {}).get("id")
        member_result = await asyncio.to_thread(
            request_post,
            bot.token,
            "getChatMember",
            {
                "chat_id": chat_id,
                "user_id": bot_user_id,
            },
            None,
        )
        member = member_result.get("result") or {}
        status = member.get("status")
        is_admin = status in ["administrator", "creator"]
        can_edit = bool(member.get("can_edit_messages") or status == "creator")

        if not is_admin:
            return False, "Bot 不是频道管理员"

        if not can_edit:
            return False, "Bot 缺少编辑消息权限"

        return True, ""

    except Exception as e:
        return False, error_text(e)


async def execute_bulk_replace(
    *,
    records,
    old_text,
    new_text,
    channel_ids=None,
    message_type="all",
    source_type="all",
    dry_run=False,
):
    old_text = old_text or ""
    if not old_text:
        raise ValueError("old_text 不能为空")

    db = SessionLocal()

    try:
        job = BulkReplaceJob(
            old_text=old_text,
            new_text=new_text or "",
            channel_ids=serialize_channel_ids(channel_ids or []),
            message_type=message_type or "all",
            source_type=source_type or "all",
            status="running",
            total_count=len(records or []),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        channel_map = {
            channel.id: channel
            for channel in get_selected_channels(db, channel_ids or [])
        }
        permission_cache = {}

        for record_ref in records or []:
            current_source_type = record_ref.get("source_type")
            source_record_id = record_ref.get("record_id") or record_ref.get("source_record_id")
            record = get_record(db, current_source_type, source_record_id)

            if not record:
                item = BulkReplaceJobItem(
                    job_id=job.id,
                    source_type=current_source_type or "",
                    source_record_id=int(source_record_id or 0),
                    status="failed",
                    error_message="发送记录不存在",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(item)
                job.failed_count += 1
                db.commit()
                continue

            channel = None
            if record_ref.get("channel_id"):
                channel = channel_map.get(int(record_ref["channel_id"]))

            content_type, original_text = extract_edit_text(record)
            target_chat_id = (
                getattr(record, "target_chat_id", "")
                or getattr(record, "target", "")
                or getattr(channel, "chat_id", "")
                or getattr(channel, "username", "")
            )
            target_message_id = getattr(record, "target_message_id", None)
            replaced_text = replace_text(original_text, old_text, new_text or "")
            item = BulkReplaceJobItem(
                job_id=job.id,
                source_type=current_source_type or "",
                source_record_id=record.id,
                target_chat_id=target_chat_id or "",
                target_message_id=target_message_id,
                message_type=content_type or "",
                original_text=original_text or "",
                replaced_text=replaced_text or "",
                status="running",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            try:
                if not target_chat_id or not target_message_id:
                    raise ValueError("缺少 target_chat_id 或 target_message_id")

                if not content_type or not original_text:
                    raise ValueError("本地记录未保存文本或 caption")

                if old_text not in original_text:
                    item.status = "skipped"
                    item.error_message = "当前记录已不再包含旧内容"
                    job.skipped_count += 1
                    db.commit()
                    continue

                bot = get_bot_for_record(db, record, channel)
                if not bot:
                    raise ValueError("缺少可用 Bot")

                permission_key = (bot.id, target_chat_id)
                if permission_key not in permission_cache:
                    permission_cache[permission_key] = await check_edit_permission(
                        bot,
                        target_chat_id,
                    )

                has_permission, reason = permission_cache[permission_key]
                if not has_permission:
                    raise ValueError(reason or "Bot 无编辑权限")

                if dry_run:
                    item.status = "skipped"
                    item.error_message = "dry_run 未执行 Telegram 编辑"
                    job.skipped_count += 1
                    db.commit()
                    continue

                try:
                    if content_type == "text":
                        await bot_edit_message_text(
                            bot.token,
                            target_chat_id,
                            target_message_id,
                            replaced_text,
                        )
                    else:
                        await bot_edit_message_caption(
                            bot.token,
                            target_chat_id,
                            target_message_id,
                            replaced_text,
                        )
                except BotApiError as e:
                    retry_after = parse_retry_after(e)
                    if retry_after:
                        await asyncio.sleep(min(retry_after, 60))
                        if content_type == "text":
                            await bot_edit_message_text(
                                bot.token,
                                target_chat_id,
                                target_message_id,
                                replaced_text,
                            )
                        else:
                            await bot_edit_message_caption(
                                bot.token,
                                target_chat_id,
                                target_message_id,
                                replaced_text,
                            )
                    elif "message is not modified" in str(e).lower():
                        item.status = "skipped"
                        item.error_message = "Telegram 返回：消息未变化"
                        job.skipped_count += 1
                        db.commit()
                        continue
                    else:
                        raise

                if content_type == "text":
                    record.text = replaced_text
                else:
                    record.caption = replaced_text

                item.status = "success"
                item.error_message = ""
                item.updated_at = datetime.utcnow()
                job.success_count += 1
                db.commit()
                await asyncio.sleep(0.8)

            except Exception as e:
                item.status = "failed"
                item.error_message = error_text(e)
                item.updated_at = datetime.utcnow()
                job.failed_count += 1
                db.commit()
                logger.warning(
                    f"批量替换单条失败 | job_id={job.id} | "
                    f"source={current_source_type}:{source_record_id} | {e}"
                )

        job.status = "done"
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)

        return job_to_dict(job, include_items=True, db=db)

    finally:
        db.close()


def job_item_to_dict(item):
    return {
        "id": item.id,
        "job_id": item.job_id,
        "source_type": item.source_type,
        "source_record_id": item.source_record_id,
        "target_chat_id": item.target_chat_id,
        "target_message_id": item.target_message_id,
        "message_type": item.message_type,
        "original_text": item.original_text,
        "replaced_text": item.replaced_text,
        "status": item.status,
        "error_message": item.error_message,
        "created_at": str(item.created_at) if item.created_at else "",
        "updated_at": str(item.updated_at) if item.updated_at else "",
    }


def job_to_dict(job, include_items=False, db=None):
    data = {
        "id": job.id,
        "old_text": job.old_text,
        "new_text": job.new_text,
        "channel_ids": job.channel_ids,
        "message_type": job.message_type,
        "source_type": job.source_type,
        "status": job.status,
        "total_count": job.total_count,
        "success_count": job.success_count,
        "failed_count": job.failed_count,
        "skipped_count": job.skipped_count,
        "created_by": job.created_by,
        "created_at": str(job.created_at) if job.created_at else "",
        "updated_at": str(job.updated_at) if job.updated_at else "",
    }

    if include_items and db is not None:
        items = (
            db.query(BulkReplaceJobItem)
            .filter(BulkReplaceJobItem.job_id == job.id)
            .order_by(BulkReplaceJobItem.id.asc())
            .all()
        )
        data["items"] = [job_item_to_dict(item) for item in items]

    return data
