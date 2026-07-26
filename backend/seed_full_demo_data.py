"""Seed safe, repeatable demo data for every major admin feature."""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from db.database import SessionLocal
from db.models import (
    Account,
    BotAccount,
    BulkReplaceJob,
    BulkReplaceJobItem,
    ChannelRule,
    CloneChannel,
    CloneSendEvent,
    CloneTask,
    ControlAckAlert,
    ControlCommandLog,
    ListenerSendEvent,
    ListenerSentMessage,
    ListenerTask,
    MyChannel,
    NotificationAccountSetting,
    SearchBot,
    SearchBotChannelSubmission,
    SentMessage,
    SupportBot,
    SupportConversation,
    SupportCustomer,
    SupportCustomerTag,
    SupportMessage,
    SupportQuickReply,
    SupportTag,
    TargetBotBinding,
)


DEMO_PREFIX = "\u5168\u529f\u80fd\u6f14\u793a"
DEMO_COUNT = 20
NOW = datetime.now()


def backup_sqlite_database():
    database_url = os.getenv("DATABASE_URL", "sqlite:///data/clonebot.db")
    if not database_url.startswith("sqlite:///"):
        print("database backup skipped: non-SQLite DATABASE_URL")
        return None

    database_path = Path(database_url.removeprefix("sqlite:///")).resolve()
    if not database_path.exists():
        return None

    backup_path = database_path.with_name(
        f"{database_path.name}.bak_full_demo_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(database_path, backup_path)
    print(f"database backup: {backup_path}")
    return backup_path


def first_or_create(db, model, defaults=None, **filters):
    row = db.query(model).filter_by(**filters).first()
    if row is not None:
        return row, False
    row = model(**filters, **(defaults or {}))
    db.add(row)
    db.flush()
    return row, True


def count_created(stats, label, created):
    if created:
        stats[label] = stats.get(label, 0) + 1


def seed_accounts(db, stats):
    accounts = []
    bots = []
    for index in range(1, DEMO_COUNT + 1):
        account, created = first_or_create(
            db,
            Account,
            name=f"{DEMO_PREFIX}\u00b7\u91c7\u96c6\u8d26\u53f7\u00b7{index:02d}",
            defaults={
                "username": f"demo_collector_{index:02d}",
                "phone": f"+861390000{index:04d}",
                "session_path": f"data/sessions/demo_collector_{index:02d}",
                "enabled": False,
                "is_default": False,
                "remark": "\u672c\u5730\u754c\u9762\u6f14\u793a\u6570\u636e\uff0c\u4e0d\u4f1a\u767b\u5f55 Telegram",
            },
        )
        accounts.append(account)
        count_created(stats, "accounts", created)

        _, created = first_or_create(
            db,
            NotificationAccountSetting,
            account_id=account.id,
            defaults={
                "ntfy_url": f"demo-topic-{index:02d}",
                "enabled": False,
                "last_test_status": ["success", "failed", ""][index % 3],
                "last_test_message": "\u6f14\u793a\u901a\u77e5\u914d\u7f6e\uff0c\u5df2\u505c\u7528",
                "last_test_at": NOW - timedelta(hours=index),
            },
        )
        count_created(stats, "notification_account_settings", created)

        bot, created = first_or_create(
            db,
            BotAccount,
            name=f"{DEMO_PREFIX}\u00b7\u5206\u53d1 Bot\u00b7{index:02d}",
            defaults={
                "token": f"0000000000:DEMO_TOKEN_{index:02d}_NOT_USABLE",
                "username": f"demo_delivery_bot_{index:02d}",
                "bot_link": f"https://t.me/demo_delivery_bot_{index:02d}",
                "enabled": False,
                "remark": "\u672c\u5730\u6f14\u793a Bot\uff0c\u7981\u6b62\u53d1\u9001",
            },
        )
        bots.append(bot)
        count_created(stats, "bot_accounts", created)
    return accounts, bots


def seed_channels_and_search(db, stats, accounts, bots):
    channels = []
    search_bots = []
    groups = ["\u4e0a\u6d77", "\u5317\u4eac", "\u5e7f\u5dde", "\u6df1\u5733"]
    collection_states = ["collected", "not_collected", "unknown", "unknown"]
    review_states = ["approved", "reviewing", "pending", "rejected"]
    block_states = ["normal", "normal", "normal", "blocked"]

    for index in range(1, DEMO_COUNT + 1):
        group = groups[(index - 1) % len(groups)]
        channel, created = first_or_create(
            db,
            MyChannel,
            username=f"@demo_managed_channel_{index:02d}",
            defaults={
                "title": f"{DEMO_PREFIX}\u00b7{group}\u9891\u9053\u00b7{index:02d}",
                "chat_id": f"-10090000{index:04d}",
                "channel_type": "channel",
                "group_name": group,
                "tags": json.dumps(["\u6f14\u793a", group], ensure_ascii=False),
                "bot_id": bots[index - 1].id,
                "status": "enabled" if index % 5 else "disabled",
                "clone_status": ["", "\u514b\u9686\u5b8c\u6210", "\u5f85\u514b\u9686"][index % 3],
                "delivery_status": ["\u5df2\u6295\u653e", "\u672a\u6295\u653e", ""][index % 3],
                "collection_status": ["\u5df2\u6536\u5f55", "\u5ba1\u6838\u4e2d", "\u672a\u6536\u5f55"][index % 3],
                "remark": "\u7528\u4e8e\u9a8c\u8bc1\u9891\u9053\u7ba1\u7406\u8868\u683c\u548c\u641c\u7d22",
                "bot_is_member": index % 4 != 0,
                "bot_is_admin": index % 4 in (1, 2),
                "can_post_messages": index % 4 in (1, 2),
                "can_edit_messages": index % 4 == 1,
                "can_delete_messages": index % 4 == 1,
                "member_count": 1800 + index * 137,
                "can_view_member_count": True,
                "creator_user_id": f"880000{index:04d}",
                "creator_username": f"demo_creator_{index:02d}",
                "creator_name": f"\u6f14\u793a\u521b\u5efa\u4eba {index:02d}",
                "can_view_creator": True,
                "last_check_at": NOW - timedelta(hours=index),
            },
        )
        channels.append(channel)
        count_created(stats, "my_channels", created)

        _, created = first_or_create(
            db,
            CloneChannel,
            channel_link=f"@demo_source_channel_{index:02d}",
            defaults={
                "title": f"{DEMO_PREFIX}\u00b7\u6e90\u9891\u9053\u00b7{index:02d}",
                "group_name": group,
                "channel_type": "channel",
                "remark": "\u6f14\u793a\u514b\u9686\u9891\u9053\u8bb0\u5f55",
            },
        )
        count_created(stats, "clone_channels", created)

        search_bot, created = first_or_create(
            db,
            SearchBot,
            username=f"@demo_search_bot_{index:02d}",
            defaults={
                "name": f"{DEMO_PREFIX}\u00b7\u641c\u7d22\u673a\u5668\u4eba\u00b7{index:02d}",
                "bot_link": f"https://t.me/demo_search_bot_{index:02d}",
                "account_id": accounts[index - 1].id,
                "status": "disabled",
                "submit_template": "{{channel_link}}",
                "remark": f"\u6f14\u793a\u5907\u6ce8 {index:02d}",
                "last_check_at": NOW - timedelta(hours=index),
            },
        )
        search_bots.append(search_bot)
        count_created(stats, "search_bots", created)

        state_index = (index - 1) % 4
        _, created = first_or_create(
            db,
            SearchBotChannelSubmission,
            search_bot_id=search_bot.id,
            my_channel_id=channel.id,
            defaults={
                "account_id": accounts[index - 1].id,
                "manual_account_id": "",
                "submit_status": "manual" if index % 3 == 0 else "success",
                "review_status": review_states[state_index],
                "collection_status": collection_states[state_index],
                "block_status": block_states[state_index],
                "is_current": collection_states[state_index] == "collected",
                "submitted_text": f"https://t.me/demo_managed_channel_{index:02d}",
                "admin_rights_json": json.dumps(
                    {"post_messages": True, "edit_messages": index % 2 == 0}
                ),
                "applied_admin_rights_json": json.dumps({"post_messages": True}),
                "permission_status": "verified",
                "telegram_message_id": 7000 + index,
                "submitted_at": NOW - timedelta(days=index),
                "last_checked_at": NOW - timedelta(hours=index),
            },
        )
        count_created(stats, "search_bot_channel_submissions", created)

        _, created = first_or_create(
            db,
            TargetBotBinding,
            target_channel=channel.username,
            bot_id=bots[index - 1].id,
            defaults={
                "enabled": False,
                "remark": "\u6f14\u793a\u7ed1\u5b9a\uff0c\u5df2\u505c\u7528",
            },
        )
        count_created(stats, "target_bot_bindings", created)
    return channels, search_bots


def seed_tasks_and_logs(db, stats, accounts, bots, channels):
    clone_tasks = []
    listener_tasks = []
    event_states = [
        ("success", "success", "\u53d1\u9001\u6210\u529f", ""),
        ("filtered", "filtered", "\u547d\u4e2d\u5173\u952e\u8bcd\u8fc7\u6ee4", ""),
        ("failed", "error", "\u53d1\u9001\u5931\u8d25", "\u6f14\u793a\u9519\u8bef\uff1a\u76ee\u6807\u9891\u9053\u4e0d\u53ef\u7528"),
        ("duplicate", "skipped", "\u5185\u5bb9\u5df2\u53bb\u91cd", ""),
    ]

    for index in range(1, DEMO_COUNT + 1):
        source = f"@demo_source_channel_{index:02d}"
        target = channels[index - 1].username
        clone_task, created = first_or_create(
            db,
            CloneTask,
            name=f"{DEMO_PREFIX}\u00b7\u514b\u9686\u4efb\u52a1\u00b7{index:02d}",
            defaults={
                "source_channel": source,
                "target_channels": json.dumps([target]),
                "account_id": accounts[index - 1].id,
                "bot_id": bots[index - 1].id,
                "status": ["stopped", "done", "error", "paused"][index % 4],
                "enable_listener": False,
                "last_message_id": 1000 + index,
                "clone_limit": 20 + index,
                "single_delay": 3,
                "album_delay": 8,
                "target_delay": 2,
                "blocked_keywords": json.dumps(["\u6f14\u793a\u5e7f\u544a", "\u65e0\u6548\u5185\u5bb9"], ensure_ascii=False),
                "replace_words": json.dumps({"\u65e7\u8bcd": "\u65b0\u8bcd"}, ensure_ascii=False),
                "remove_contact_lines": True,
                "filter_qr_code": True,
                "enabled": False,
            },
        )
        clone_tasks.append(clone_task)
        count_created(stats, "clone_tasks", created)

        listener_task, created = first_or_create(
            db,
            ListenerTask,
            name=f"{DEMO_PREFIX}\u00b7\u76d1\u542c\u4efb\u52a1\u00b7{index:02d}",
            defaults={
                "source_channel": source,
                "target_channels": json.dumps([target]),
                "account_id": accounts[index - 1].id,
                "bot_id": bots[index - 1].id,
                "enabled": False,
                "status": "stopped",
                "blocked_keywords": json.dumps(["\u6f14\u793a\u5e7f\u544a"], ensure_ascii=False),
                "listen_required_keywords": json.dumps(["\u88ab\u76d1\u542c\u5185\u5bb9"], ensure_ascii=False),
                "replace_words": json.dumps({"\u6d4b\u8bd5": "\u6f14\u793a"}, ensure_ascii=False),
                "remove_contact_lines": True,
                "filter_qr_code": True,
                "album_wait_seconds": 3,
                "last_received_at": NOW - timedelta(hours=index),
            },
        )
        listener_tasks.append(listener_task)
        count_created(stats, "listener_tasks", created)

        event_type, status, message, error = event_states[(index - 1) % len(event_states)]
        source_message_id = 50000 + index
        _, created = first_or_create(
            db,
            SentMessage,
            task_id=clone_task.id,
            source_message_id=source_message_id,
            defaults={"grouped_id": f"demo-clone-group-{index:02d}"},
        )
        count_created(stats, "sent_messages", created)

        _, created = first_or_create(
            db,
            CloneSendEvent,
            task_id=clone_task.id,
            source_message_id=source_message_id,
            target=target,
            defaults={
                "time": (NOW - timedelta(minutes=index)).isoformat(sep=" ", timespec="seconds"),
                "target_chat_id": channels[index - 1].chat_id,
                "target_message_id": 8000 + index if status == "success" else None,
                "source_message_url": f"https://t.me/demo_source_channel_{index:02d}/{source_message_id}",
                "target_message_url": f"https://t.me/demo_managed_channel_{index:02d}/{8000 + index}" if status == "success" else "",
                "event_type": event_type,
                "status": status,
                "message": message,
                "error": error,
                "message_type": ["text", "photo", "video", "document"][index % 4],
                "text": f"\u514b\u9686\u6f14\u793a\u6d88\u606f {index:02d}",
                "bot_id": bots[index - 1].id,
                "bot_name": bots[index - 1].name,
                "created_at": NOW - timedelta(minutes=index),
            },
        )
        count_created(stats, "clone_send_events", created)

        _, created = first_or_create(
            db,
            ListenerSentMessage,
            listener_task_id=listener_task.id,
            target_channel=target,
            source_message_id=source_message_id,
            defaults={"grouped_id": f"demo-listener-group-{index:02d}"},
        )
        count_created(stats, "listener_sent_messages", created)

        _, created = first_or_create(
            db,
            ListenerSendEvent,
            task_id=listener_task.id,
            source_message_id=source_message_id,
            target=target,
            defaults={
                "time": (NOW - timedelta(minutes=index)).isoformat(sep=" ", timespec="seconds"),
                "task_name": listener_task.name,
                "event_type": event_type,
                "source_channel": source,
                "target_chat_id": channels[index - 1].chat_id,
                "account_id": accounts[index - 1].id,
                "account_name": accounts[index - 1].name,
                "target_message_id": 9000 + index if status == "success" else None,
                "source_message_url": f"https://t.me/demo_source_channel_{index:02d}/{source_message_id}",
                "target_message_url": f"https://t.me/demo_managed_channel_{index:02d}/{9000 + index}" if status == "success" else "",
                "message_type": ["text", "photo", "video", "document"][index % 4],
                "text": f"\u76d1\u542c\u6f14\u793a\u6d88\u606f {index:02d}",
                "status": status,
                "message": message,
                "error": error,
                "bot_id": bots[index - 1].id,
                "bot_name": bots[index - 1].name,
                "created_at": NOW - timedelta(minutes=index),
            },
        )
        count_created(stats, "listener_send_events", created)

        _, created = first_or_create(
            db,
            ChannelRule,
            source=source,
            target=target,
            clone_task_id=clone_task.id,
            defaults={
                "account_id": accounts[index - 1].id,
                "enabled": False,
                "keywords": json.dumps(["\u6f14\u793a\u8fc7\u6ee4\u8bcd"], ensure_ascii=False),
                "replace_words": json.dumps({"\u539f\u6587": "\u66ff\u6362\u6587"}, ensure_ascii=False),
                "footer": "\u6f14\u793a\u5e95\u90e8\u5185\u5bb9",
                "last_message_id": source_message_id,
                "remove_contact_lines": True,
            },
        )
        count_created(stats, "channel_rules", created)
    return clone_tasks, listener_tasks


def seed_bulk_replace(db, stats, channels):
    statuses = ["completed", "completed", "failed", "cancelled"]
    for index in range(1, DEMO_COUNT + 1):
        old_text = f"{DEMO_PREFIX}\u00b7\u5f85\u66ff\u6362\u6587\u5b57\u00b7{index:02d}"
        job, created = first_or_create(
            db,
            BulkReplaceJob,
            old_text=old_text,
            created_by=DEMO_PREFIX,
            defaults={
                "new_text": f"\u66ff\u6362\u540e\u5185\u5bb9 {index:02d}",
                "channel_ids": json.dumps([channels[index - 1].id]),
                "message_type": ["all", "text", "caption"][index % 3],
                "source_type": ["all", "clone", "listener"][index % 3],
                "status": statuses[(index - 1) % len(statuses)],
                "total_count": 10,
                "success_count": 8 if index % 4 != 3 else 6,
                "failed_count": 2 if index % 4 == 3 else 0,
                "skipped_count": 2,
                "created_at": NOW - timedelta(days=index),
                "updated_at": NOW - timedelta(days=index, minutes=-5),
            },
        )
        count_created(stats, "bulk_replace_jobs", created)

        _, created = first_or_create(
            db,
            BulkReplaceJobItem,
            job_id=job.id,
            source_record_id=60000 + index,
            defaults={
                "source_type": "clone" if index % 2 else "listener",
                "target_chat_id": channels[index - 1].chat_id,
                "target_message_id": 10000 + index,
                "message_type": "text",
                "original_text": old_text,
                "replaced_text": f"\u66ff\u6362\u540e\u5185\u5bb9 {index:02d}",
                "status": "success" if index % 4 != 3 else "failed",
                "error_message": "" if index % 4 != 3 else "\u6f14\u793a\u5931\u8d25\u539f\u56e0",
                "created_at": NOW - timedelta(days=index),
                "updated_at": NOW - timedelta(days=index, minutes=-5),
            },
        )
        count_created(stats, "bulk_replace_job_items", created)


def seed_support(db, stats, bots):
    support_bots = []
    customers = []
    tags = []
    colors = ["#409eff", "#67c23a", "#e6a23c", "#f56c6c"]

    for index in range(1, DEMO_COUNT + 1):
        support_bot, created = first_or_create(
            db,
            SupportBot,
            name=f"{DEMO_PREFIX}\u00b7\u5ba2\u670d Bot\u00b7{index:02d}",
            defaults={
                "bot_id": bots[index - 1].id,
                "bot_token": f"0000000000:DEMO_SUPPORT_TOKEN_{index:02d}",
                "price": str(99 + index),
                "support_group_chat_id": f"-10080000{index:04d}",
                "polling_enabled": False,
                "welcome_message": "\u60a8\u597d\uff0c\u8fd9\u662f\u6f14\u793a\u5ba2\u670d\u6b22\u8fce\u8bed\u3002",
                "welcome_text_type": "plain",
                "off_hours_message": "\u5f53\u524d\u4e3a\u975e\u670d\u52a1\u65f6\u95f4\uff0c\u6211\u4eec\u4f1a\u5c3d\u5feb\u56de\u590d\u3002",
                "business_hours_enabled": True,
                "business_start_hour": 9,
                "business_end_hour": 22,
                "status": "disabled",
            },
        )
        support_bots.append(support_bot)
        count_created(stats, "support_bots", created)

        customer, created = first_or_create(
            db,
            SupportCustomer,
            telegram_user_id=f"990000{index:04d}",
            support_bot_id=support_bot.id,
            defaults={
                "telegram_chat_id": f"990000{index:04d}",
                "username": f"demo_customer_{index:02d}",
                "first_name": f"\u6f14\u793a\u5ba2\u6237 {index:02d}",
                "language_code": "zh-hans",
                "source": "\u672c\u5730\u6f14\u793a",
                "status": "active" if index % 4 else "closed",
                "blocked": index % 10 == 0,
                "last_message_at": NOW - timedelta(minutes=index * 3),
            },
        )
        customers.append(customer)
        count_created(stats, "support_customers", created)

        conversation, created = first_or_create(
            db,
            SupportConversation,
            customer_id=customer.id,
            support_bot_id=support_bot.id,
            defaults={
                "status": "open" if index % 4 else "closed",
                "support_thread_id": 11000 + index,
                "support_topic_name": f"\u6f14\u793a\u5ba2\u6237 {index:02d}",
                "support_topic_created_at": NOW - timedelta(days=index),
                "last_message": f"\u8bf7\u95ee\u6f14\u793a\u670d\u52a1 {index:02d} \u5982\u4f55\u529e\u7406\uff1f",
                "last_message_at": NOW - timedelta(minutes=index * 3),
                "unread_count": index % 4,
            },
        )
        count_created(stats, "support_conversations", created)

        _, created = first_or_create(
            db,
            SupportMessage,
            conversation_id=conversation.id,
            customer_id=customer.id,
            telegram_message_id=12000 + index,
            defaults={
                "support_bot_id": support_bot.id,
                "sender_type": "customer",
                "sender_id": customer.telegram_user_id,
                "message_type": ["text", "photo", "video", "document"][index % 4],
                "text": f"\u6f14\u793a\u5ba2\u6237\u6d88\u606f {index:02d}",
                "caption": "\u6f14\u793a\u5a92\u4f53\u8bf4\u660e" if index % 4 else "",
                "file_name": f"demo_file_{index:02d}.pdf" if index % 4 == 3 else "",
                "send_status": "success" if index % 5 else "failed",
                "error_message": "\u6f14\u793a\u53d1\u9001\u5931\u8d25" if index % 5 == 0 else "",
                "status": "sent",
                "created_at": NOW - timedelta(minutes=index * 3),
            },
        )
        count_created(stats, "support_messages", created)

        _, created = first_or_create(
            db,
            SupportQuickReply,
            title=f"{DEMO_PREFIX}\u00b7\u5feb\u6377\u56de\u590d\u00b7{index:02d}",
            defaults={
                "content": f"\u60a8\u597d\uff0c\u8fd9\u662f\u7b2c {index:02d} \u6761\u5feb\u6377\u56de\u590d\u6f14\u793a\u5185\u5bb9\u3002",
                "sort": index,
                "enabled": index % 5 != 0,
            },
        )
        count_created(stats, "support_quick_replies", created)

        tag, created = first_or_create(
            db,
            SupportTag,
            name=f"{DEMO_PREFIX}\u00b7\u6807\u7b7e\u00b7{index:02d}",
            defaults={"color": colors[(index - 1) % len(colors)]},
        )
        tags.append(tag)
        count_created(stats, "support_tags", created)

        _, created = first_or_create(
            db,
            SupportCustomerTag,
            customer_id=customer.id,
            tag_id=tag.id,
        )
        count_created(stats, "support_customer_tags", created)

    return support_bots, customers


def seed_control_data(db, stats, support_bots, customers):
    for index in range(1, DEMO_COUNT + 1):
        _, created = first_or_create(
            db,
            ControlCommandLog,
            chat_id=f"-10070000{index:04d}",
            message_id=13000 + index,
            defaults={
                "user_id": f"660000{index:04d}",
                "username": f"demo_admin_{index:02d}",
                "command": ["/status", "/tasks", "/errors", "/help"][index % 4],
                "raw_text": "/status",
                "parsed_args": "{}",
                "status": "success" if index % 5 else "failed",
                "result_message": "\u6f14\u793a\u4e91\u53f0\u547d\u4ee4\u7ed3\u679c",
                "error_message": "\u6f14\u793a\u9519\u8bef" if index % 5 == 0 else "",
                "created_at": NOW - timedelta(hours=index),
            },
        )
        count_created(stats, "control_command_logs", created)

        _, created = first_or_create(
            db,
            ControlAckAlert,
            alert_key=f"full-demo-alert-{index:02d}",
            defaults={
                "module": ["listener_health", "support_bot", "clone_task"][index % 3],
                "title": f"{DEMO_PREFIX}\u00b7\u5df2\u786e\u8ba4\u544a\u8b66\u00b7{index:02d}",
                "detail": "\u7528\u4e8e\u9a8c\u8bc1\u544a\u8b66\u5217\u8868\u7684\u672c\u5730\u6f14\u793a\u6570\u636e\u3002",
                "status": "acknowledged",
                "support_bot_id": support_bots[index - 1].id,
                "customer_id": customers[index - 1].id,
                "repeat_count": index % 4,
                "first_sent_at": NOW - timedelta(hours=index + 1),
                "last_sent_at": NOW - timedelta(hours=index),
                "acknowledged_by": "\u6f14\u793a\u7ba1\u7406\u5458",
                "acknowledged_at": NOW - timedelta(hours=index),
            },
        )
        count_created(stats, "control_ack_alerts", created)


def main():
    backup_sqlite_database()
    db = SessionLocal()
    stats = {}
    try:
        accounts, bots = seed_accounts(db, stats)
        channels, _ = seed_channels_and_search(db, stats, accounts, bots)
        seed_tasks_and_logs(db, stats, accounts, bots, channels)
        seed_bulk_replace(db, stats, channels)
        support_bots, customers = seed_support(db, stats, bots)
        seed_control_data(db, stats, support_bots, customers)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if not stats:
        print("full demo data already exists: created 0")
        return
    print("full demo data complete")
    for label in sorted(stats):
        print(f"{label}: created {stats[label]}")
    print(f"total created: {sum(stats.values())}")


if __name__ == "__main__":
    main()
