"""Channel-centred task, delivery-bot and search-bot read models."""

from collections import defaultdict

from sqlalchemy import func, inspect

from bot.channel_utils import channel_identifier_key, normalize_channel_list
from db.database import SessionLocal
from db.models import (
    BotAccount,
    CloneTask,
    ListenerSentMessage,
    ListenerTask,
    MyChannel,
    SearchBot,
    SearchBotChannelSubmission,
    SentMessage,
    TargetBotBinding,
    TaskChannelLink,
)
from utils.redaction import redact_sensitive_text


TASK_MODELS = {"listener": ListenerTask, "clone": CloneTask}


def _channel_index(channels):
    index = defaultdict(set)
    for channel in channels:
        for value in (channel.username, channel.chat_id):
            key = channel_identifier_key(value)
            if key:
                index[key].add(channel.id)
    return index


def _task_values(task):
    values = [("target", value) for value in normalize_channel_list(task.target_channels)]
    source = str(task.source_channel or "").strip()
    if source:
        values.append(("source", source))
    return values


def reconcile_task_links(db, task_type, task):
    """Keep stable links when the channel username changes but task text does not."""
    if task_type not in TASK_MODELS:
        raise ValueError("unsupported task type")
    if not task.id or not task.owner_user_id:
        return
    if not inspect(db.connection()).has_table(TaskChannelLink.__tablename__):
        return

    channels = db.query(MyChannel).filter(MyChannel.owner_user_id == task.owner_user_id).all()
    channel_ids = _channel_index(channels)
    existing = db.query(TaskChannelLink).filter(
        TaskChannelLink.owner_user_id == task.owner_user_id,
        TaskChannelLink.task_type == task_type,
        TaskChannelLink.task_id == task.id,
    ).all()
    previous = defaultdict(set)
    for link in existing:
        previous[(link.role, channel_identifier_key(link.channel_value))].add(link.my_channel_id)

    desired = {}
    for role, value in _task_values(task):
        key = channel_identifier_key(value)
        matches = previous.get((role, key)) or channel_ids.get(key, set())
        if len(matches) == 1:
            desired[(role, next(iter(matches)))] = value

    retained = set()
    for link in existing:
        identity = (link.role, link.my_channel_id)
        if identity in desired:
            link.channel_value = desired[identity]
            retained.add(identity)
        else:
            db.delete(link)
    for identity, value in desired.items():
        if identity not in retained:
            db.add(TaskChannelLink(
                owner_user_id=task.owner_user_id,
                task_type=task_type,
                task_id=task.id,
                my_channel_id=identity[1],
                role=identity[0],
                channel_value=value,
            ))


def backfill_task_links(db):
    for task_type, model in TASK_MODELS.items():
        for task in db.query(model).all():
            reconcile_task_links(db, task_type, task)
    db.commit()


def reconcile_owner_tasks(db, owner_user_id):
    inspector = inspect(db.connection())
    if not inspector.has_table(TaskChannelLink.__tablename__):
        return
    for task_type, model in TASK_MODELS.items():
        if not inspector.has_table(model.__tablename__):
            continue
        for task in db.query(model).filter(model.owner_user_id == owner_user_id).all():
            reconcile_task_links(db, task_type, task)


def delete_task_links(db, task_type, task_id, owner_user_id):
    if inspect(db.connection()).has_table(TaskChannelLink.__tablename__):
        db.query(TaskChannelLink).filter(
            TaskChannelLink.owner_user_id == owner_user_id,
            TaskChannelLink.task_type == task_type,
            TaskChannelLink.task_id == task_id,
        ).delete(synchronize_session=False)


def delete_channel_links(db, channel):
    if inspect(db.connection()).has_table(TaskChannelLink.__tablename__):
        db.query(TaskChannelLink).filter(
            TaskChannelLink.owner_user_id == channel.owner_user_id,
            TaskChannelLink.my_channel_id == channel.id,
        ).delete(synchronize_session=False)


def _latest_submissions(db, channel):
    rows = db.query(SearchBotChannelSubmission, SearchBot).join(
        SearchBot,
        SearchBot.id == SearchBotChannelSubmission.search_bot_id,
    ).filter(
        SearchBotChannelSubmission.owner_user_id == channel.owner_user_id,
        SearchBotChannelSubmission.my_channel_id == channel.id,
        SearchBot.owner_user_id == channel.owner_user_id,
    ).order_by(SearchBotChannelSubmission.id.desc()).all()
    latest = {}
    for row, bot in rows:
        if bot.id not in latest:
            latest[bot.id] = {
                "search_bot_id": bot.id,
                "name": bot.name or bot.username or f"机器人 #{bot.id}",
                "username": bot.username or "",
                "bot_status": bot.status or "unknown",
                "submit_status": row.submit_status or "unknown",
                "review_status": row.review_status or "unknown",
                "collection_status": row.collection_status or "unknown",
                "block_status": row.block_status or "unknown",
                "is_current": bool(row.is_current),
                "last_error": redact_sensitive_text(row.last_error),
                "last_checked_at": str(row.last_checked_at or ""),
                "submitted_at": str(row.submitted_at or ""),
            }
    return list(latest.values())


def collection_label(collections):
    if any(
        item["collection_status"] == "collected" and item["block_status"] != "blocked"
        for item in collections
    ):
        return "已收录"
    if any(item["review_status"] == "reviewing" for item in collections):
        return "审核中"
    return "未收录"


def _task_counts(db, model, column, owner_user_id, ids):
    if not ids:
        return {}
    return {
        int(task_id): int(count)
        for task_id, count in db.query(column, func.count(model.id)).filter(
            model.owner_user_id == owner_user_id,
            column.in_(ids),
        ).group_by(column).all()
    }


def get_channel_overview(channel_id, *, include_listener=True, include_clone=True):
    db = SessionLocal()
    try:
        channel = db.query(MyChannel).filter(MyChannel.id == channel_id).first()
        if channel is None:
            return None
        owner = channel.owner_user_id
        allowed_types = {
            task_type for task_type, allowed in (
                ("listener", include_listener), ("clone", include_clone),
            ) if allowed
        }
        links = db.query(TaskChannelLink).filter(
            TaskChannelLink.owner_user_id == owner,
            TaskChannelLink.my_channel_id == channel.id,
            TaskChannelLink.task_type.in_(allowed_types),
        ).all() if allowed_types else []
        ids_by_type = defaultdict(set)
        roles_by_task = defaultdict(set)
        values_by_task = defaultdict(set)
        for link in links:
            ids_by_type[link.task_type].add(link.task_id)
            roles_by_task[(link.task_type, link.task_id)].add(link.role)
            values_by_task[(link.task_type, link.task_id)].add(link.channel_value)

        listener_ids = ids_by_type["listener"]
        clone_ids = ids_by_type["clone"]
        listener_counts = _task_counts(
            db, ListenerSentMessage, ListenerSentMessage.listener_task_id, owner, listener_ids,
        )
        clone_counts = _task_counts(db, SentMessage, SentMessage.task_id, owner, clone_ids)
        task_rows = []
        task_bot_ids = set()
        for task_type, model, counts in (
            ("listener", ListenerTask, listener_counts),
            ("clone", CloneTask, clone_counts),
        ):
            ids = ids_by_type[task_type]
            if not ids:
                continue
            tasks = db.query(model).filter(model.id.in_(ids), model.owner_user_id == owner).all()
            for task in tasks:
                if task_type == "listener" and task.clone_task_id:
                    continue  # Clone-created listener mirrors are represented by their clone task.
                if task.bot_id:
                    task_bot_ids.add(task.bot_id)
                task_rows.append({
                    "id": task.id,
                    "type": task_type,
                    "name": task.name or f"任务 #{task.id}",
                    "roles": sorted(roles_by_task[(task_type, task.id)]),
                    "status": task.status or "unknown",
                    "enabled": bool(task.enabled),
                    "bot_id": task.bot_id,
                    "source_channel": task.source_channel,
                    "target_values": sorted(values_by_task[(task_type, task.id)]),
                    "sent_count": counts.get(task.id, 0),
                    "last_message_id": task.last_message_id if task_type == "clone" else None,
                    "clone_limit": task.clone_limit if task_type == "clone" else None,
                    "last_received_at": str(task.last_received_at or "") if task_type == "listener" else "",
                    "last_error": redact_sensitive_text(getattr(task, "last_error", "")),
                    "updated_at": str(getattr(task, "updated_at", "") or ""),
                })

        identifiers = {
            channel_identifier_key(value)
            for value in (channel.username, channel.chat_id)
            if value
        }
        identifiers.update(
            channel_identifier_key(link.channel_value)
            for link in links if link.role == "target"
        )
        bindings = [
            binding for binding in db.query(TargetBotBinding).filter(
                TargetBotBinding.owner_user_id == owner,
            ).all()
            if channel_identifier_key(binding.target_channel) in identifiers
        ]
        bot_sources = defaultdict(set)
        if channel.bot_id:
            bot_sources[channel.bot_id].add("频道关联")
        for binding in bindings:
            bot_sources[binding.bot_id].add("目标绑定" if binding.enabled else "目标绑定已停用")
        for task in task_rows:
            if task["bot_id"]:
                bot_sources[task["bot_id"]].add("任务指定")
        bot_ids = set(bot_sources) | task_bot_ids
        bots = db.query(BotAccount).filter(
            BotAccount.id.in_(bot_ids), BotAccount.owner_user_id == owner,
        ).all() if bot_ids else []
        bot_names = {bot.id: bot.name or bot.username or f"Bot #{bot.id}" for bot in bots}
        for task in task_rows:
            task["bot_name"] = bot_names.get(task["bot_id"], "") if task["bot_id"] else ""
        bot_rows = [{
            "id": bot.id,
            "name": bot_names[bot.id],
            "username": bot.username or "",
            "enabled": bool(bot.enabled),
            "sources": sorted(bot_sources[bot.id]),
        } for bot in bots]
        task_rows.sort(key=lambda row: (row["status"] not in {"error", "failed"}, row["name"].lower()))
        collections = _latest_submissions(db, channel)
        return {
            "channel_id": channel.id,
            "tasks": task_rows,
            "bots": bot_rows,
            "collections": collections,
            "collection_status": collection_label(collections),
            "permissions": {
                "listener_tasks": include_listener,
                "clone_tasks": include_clone,
            },
        }
    finally:
        db.close()
