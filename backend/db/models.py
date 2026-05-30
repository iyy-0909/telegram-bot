from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import Text
from sqlalchemy import DateTime
from datetime import datetime
from db.database import Base
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime

class ChannelRule(Base):
    __tablename__ = "channel_rules"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    target = Column(String, nullable=False)
    account_id = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)

    keywords = Column(Text, default="[]")
    replace_words = Column(Text, default="{}")
    footer = Column(Text, default="")
    last_message_id = Column(Integer, default=0)

    # 从克隆任务同步过来的监听规则
    clone_task_id = Column(Integer, nullable=True, index=True)

    # 是否删除旧联系方式
    remove_contact_lines = Column(Boolean, default=True)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, default="")
    phone = Column(String, default="")
    session_path = Column(String, nullable=False)
    proxy = Column(String, default="")
    enabled = Column(Boolean, default=True)
    remark = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CloneTask(Base):
    __tablename__ = "clone_tasks"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    source_channel = Column(String, nullable=False)
    target_channels = Column(Text, default="[]")

    account_id = Column(Integer, default=1)
    bot_id = Column(Integer, nullable=True, index=True)

    # idle / running / paused / stopped / done / error
    status = Column(String, default="idle")


    enable_listener = Column(Boolean, default=False)
    
    last_message_id = Column(Integer, default=0)
    clone_limit = Column(Integer, default=100)
    start_message_url = Column(Text, default="")
    end_message_url = Column(Text, default="")

    single_delay = Column(Integer, default=3)
    album_delay = Column(Integer, default=8)
    target_delay = Column(Integer, default=2)

    blocked_keywords = Column(Text, default="[]")
    replace_words = Column(Text, default="{}")
    footer = Column(Text, default="")
    remove_contact_lines = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)

    use_random_head = Column(Boolean, default=False)
    use_random_body = Column(Boolean, default=False)
    use_random_footer = Column(Boolean, default=False)
    selected_head_template_group_id = Column(Integer, nullable=True)
    selected_body_template_group_id = Column(Integer, nullable=True)
    selected_footer_template_group_id = Column(Integer, nullable=True)
    selected_filter_template_group_id = Column(Integer, nullable=True)
    selected_head_template_id = Column(Integer, nullable=True)
    selected_body_template_id = Column(Integer, nullable=True)
    selected_footer_template_id = Column(Integer, nullable=True)


class ContentTemplate(Base):
    """内容模板规则"""

    __tablename__ = "content_templates"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, nullable=True, index=True)
    name = Column(String, default="")
    type = Column(String, nullable=False, index=True)
    content = Column(Text, default="")
    enabled = Column(Boolean, default=True)
    weight = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SentMessage(Base):
    """已发送消息去重表"""

    __tablename__ = "sent_messages"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(Integer, index=True, nullable=False)
    source_message_id = Column(Integer, index=True, nullable=False)

    # 当前数据库里 grouped_id 是旧字段，不要加 target_channel/message_type
    # 用 String 更稳，因为 Telegram grouped_id 很长，只做去重，不做数学计算
    grouped_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class ListenerTask(Base):
    """实时监听任务"""

    __tablename__ = "listener_tasks"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    source_channel = Column(String, nullable=False, index=True)
    target_channels = Column(Text, default="[]")
    account_id = Column(Integer, default=1, index=True)
    bot_id = Column(Integer, nullable=True, index=True)

    enabled = Column(Boolean, default=True)
    status = Column(String, default="stopped")

    blocked_keywords = Column(Text, default="[]")
    replace_words = Column(Text, default="{}")
    footer = Column(Text, default="")
    remove_contact_lines = Column(Boolean, default=True)
    use_random_head = Column(Boolean, default=False)
    use_random_body = Column(Boolean, default=False)
    use_random_footer = Column(Boolean, default=False)
    selected_head_template_group_id = Column(Integer, nullable=True)
    selected_body_template_group_id = Column(Integer, nullable=True)
    selected_footer_template_group_id = Column(Integer, nullable=True)
    selected_filter_template_group_id = Column(Integer, nullable=True)
    selected_head_template_id = Column(Integer, nullable=True)
    selected_body_template_id = Column(Integer, nullable=True)
    selected_footer_template_id = Column(Integer, nullable=True)

    album_wait_seconds = Column(Integer, default=3)
    last_error = Column(Text, default="")
    clone_task_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ListenerSentMessage(Base):
    """监听任务按目标频道去重"""

    __tablename__ = "listener_sent_messages"

    id = Column(Integer, primary_key=True, index=True)

    listener_task_id = Column(Integer, index=True, nullable=False)
    target_channel = Column(String, index=True, nullable=False)
    source_message_id = Column(Integer, index=True, nullable=False)
    grouped_id = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class CloneSendEvent(Base):
    """Clone task send cache, only latest rows are kept by CRUD."""

    __tablename__ = "clone_send_events"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(String, default="")
    task_id = Column(Integer, index=True, nullable=True)
    target = Column(String, default="", index=True)
    source_message_id = Column(Integer, nullable=True, index=True)
    target_chat_id = Column(String, default="", index=True)
    target_message_id = Column(Integer, nullable=True, index=True)
    grouped_id = Column(String, nullable=True)
    source_message_url = Column(Text, default="")
    target_message_url = Column(Text, default="")
    event_type = Column(String, default="success", index=True)
    status = Column(String, default="success", index=True)
    message = Column(Text, default="")
    error = Column(Text, default="")
    message_type = Column(String, default="", index=True)
    text = Column(Text, default="")
    caption = Column(Text, default="")
    bot_id = Column(Integer, nullable=True, index=True)
    bot_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ListenerSendEvent(Base):
    """Listener task send cache, only latest rows are kept by CRUD."""

    __tablename__ = "listener_send_events"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(String, default="")
    task_id = Column(Integer, index=True, nullable=True)
    task_name = Column(String, default="")
    event_type = Column(String, default="success", index=True)
    source_channel = Column(String, default="", index=True)
    target = Column(String, default="", index=True)
    target_chat_id = Column(String, default="", index=True)
    account_id = Column(Integer, nullable=True, index=True)
    account_name = Column(String, default="")
    source_message_id = Column(Integer, nullable=True, index=True)
    target_message_id = Column(Integer, nullable=True, index=True)
    grouped_id = Column(String, nullable=True)
    source_message_url = Column(Text, default="")
    target_message_url = Column(Text, default="")
    message_type = Column(String, default="", index=True)
    text = Column(Text, default="")
    caption = Column(Text, default="")
    status = Column(String, default="success", index=True)
    message = Column(Text, default="")
    error = Column(Text, default="")
    bot_id = Column(Integer, nullable=True)
    bot_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BulkReplaceJob(Base):
    __tablename__ = "bulk_replace_jobs"

    id = Column(Integer, primary_key=True, index=True)
    old_text = Column(Text, default="")
    new_text = Column(Text, default="")
    channel_ids = Column(Text, default="[]")
    message_type = Column(String, default="all", index=True)
    source_type = Column(String, default="all", index=True)
    status = Column(String, default="pending", index=True)
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class BulkReplaceJobItem(Base):
    __tablename__ = "bulk_replace_job_items"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True, nullable=False)
    source_type = Column(String, default="", index=True)
    source_record_id = Column(Integer, index=True, nullable=False)
    target_chat_id = Column(String, default="", index=True)
    target_message_id = Column(Integer, nullable=True, index=True)
    message_type = Column(String, default="", index=True)
    original_text = Column(Text, default="")
    replaced_text = Column(Text, default="")
    status = Column(String, default="pending", index=True)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ControlCommandLog(Base):
    __tablename__ = "control_command_logs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, default="", index=True)
    message_id = Column(Integer, nullable=True, index=True)
    user_id = Column(String, default="", index=True)
    username = Column(String, default="")
    command = Column(String, default="", index=True)
    raw_text = Column(Text, default="")
    parsed_args = Column(Text, default="")
    status = Column(String, default="received", index=True)
    result_message = Column(Text, default="")
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BotAccount(Base):
    """官方 Bot 分发账号"""

    __tablename__ = "bot_accounts"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    token = Column(Text, nullable=False)
    username = Column(String, default="")
    bot_link = Column(String, default="")

    enabled = Column(Boolean, default=True)
    remark = Column(Text, default="")
    last_error = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TargetBotBinding(Base):
    """目标频道绑定 Bot"""

    __tablename__ = "target_bot_bindings"

    id = Column(Integer, primary_key=True, index=True)

    target_channel = Column(String, nullable=False, index=True)
    bot_id = Column(Integer, nullable=False, index=True)

    enabled = Column(Boolean, default=True)
    remark = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)


class MyChannel(Base):
    """Managed target channel."""

    __tablename__ = "my_channels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="")
    username = Column(String, default="", index=True)
    chat_id = Column(String, default="", index=True)
    channel_type = Column(String, default="")
    group_name = Column(String, default="", index=True)
    tags = Column(Text, default="[]")
    bot_id = Column(Integer, nullable=True, index=True)
    status = Column(String, default="enabled", index=True)
    is_default = Column(Boolean, default=False)
    remark = Column(Text, default="")

    bot_is_member = Column(Boolean, default=False)
    bot_is_admin = Column(Boolean, default=False)
    can_post_messages = Column(Boolean, default=False)
    can_edit_messages = Column(Boolean, default=False)
    can_delete_messages = Column(Boolean, default=False)
    can_manage_topics = Column(Boolean, default=False)

    last_check_at = Column(DateTime, nullable=True)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CloneChannel(Base):
    """Managed source channel for clone/listener tasks."""

    __tablename__ = "clone_channels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="")
    channel_link = Column(String, nullable=False, index=True)
    group_name = Column(String, default="", index=True)
    channel_type = Column(String, default="")
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    """系统级配置"""

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(Text, default="")
    remark = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class SupportCustomer(Base):
    """Customer who has initiated a private chat with the support bot."""

    __tablename__ = "support_customers"

    id = Column(Integer, primary_key=True, index=True)
    support_bot_id = Column(Integer, nullable=True, index=True)
    telegram_user_id = Column(String, nullable=False, index=True)
    telegram_chat_id = Column(String, nullable=False, index=True)
    username = Column(String, default="", index=True)
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    language_code = Column(String, default="")
    source = Column(String, default="", index=True)
    status = Column(String, default="active", index=True)
    blocked = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SupportConversation(Base):
    """Support conversation for a customer."""

    __tablename__ = "support_conversations"

    id = Column(Integer, primary_key=True, index=True)
    support_bot_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    status = Column(String, default="open", index=True)
    assigned_admin_id = Column(Integer, nullable=True, index=True)
    support_thread_id = Column(Integer, nullable=True, index=True)
    support_topic_name = Column(String, default="")
    support_topic_created_at = Column(DateTime, nullable=True)
    last_message = Column(Text, default="")
    last_message_at = Column(DateTime, default=datetime.utcnow, index=True)
    unread_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SupportMessage(Base):
    """Message in a support conversation."""

    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    support_bot_id = Column(Integer, nullable=True, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    sender_type = Column(String, nullable=False, index=True)
    sender_id = Column(String, default="")
    message_type = Column(String, default="text", index=True)
    text = Column(Text, default="")
    caption = Column(Text, default="")
    file_id = Column(Text, default="")
    file_unique_id = Column(String, default="")
    file_name = Column(String, default="")
    mime_type = Column(String, default="")
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)
    telegram_message_id = Column(Integer, nullable=True, index=True)
    support_group_message_id = Column(Integer, nullable=True, index=True)
    reply_to_support_group_message_id = Column(Integer, nullable=True, index=True)
    send_status = Column(String, default="success", index=True)
    error_message = Column(Text, default="")
    status = Column(String, default="sent", index=True)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SupportQuickReply(Base):
    """Reusable support reply."""

    __tablename__ = "support_quick_replies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, default="")
    sort = Column(Integer, default=0, index=True)
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SupportTag(Base):
    """Customer tag."""

    __tablename__ = "support_tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    color = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SupportCustomerTag(Base):
    """Many-to-many link between support customers and tags."""

    __tablename__ = "support_customer_tags"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SupportSetting(Base):
    """Support bot settings."""

    __tablename__ = "support_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(Text, default="")
    remark = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class SupportBot(Base):
    """Config for one support bot polling worker."""

    __tablename__ = "support_bots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="")
    bot_id = Column(Integer, nullable=True, index=True)
    bot_token = Column(Text, default="")
    support_group_chat_id = Column(String, default="", index=True)
    polling_enabled = Column(Boolean, default=False, index=True)
    welcome_message = Column(Text, default="")
    welcome_media_type = Column(String, default="text")
    welcome_media_file_id = Column(Text, default="")
    off_hours_message = Column(Text, default="")
    business_hours_enabled = Column(Boolean, default=False)
    business_start_hour = Column(Integer, default=9)
    business_end_hour = Column(Integer, default=22)
    backend_base_url = Column(Text, default="")
    status = Column(String, default="enabled", index=True)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
