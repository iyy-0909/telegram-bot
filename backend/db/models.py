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
    session_path = Column(String, nullable=False)
    proxy = Column(String, default="")
    enabled = Column(Boolean, default=True)
    remark = Column(Text, default="")


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
    grouped_id = Column(String, nullable=True)
    source_message_url = Column(Text, default="")
    target_message_url = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ListenerSendEvent(Base):
    """Listener task send cache, only latest rows are kept by CRUD."""

    __tablename__ = "listener_send_events"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(String, default="")
    task_id = Column(Integer, index=True, nullable=True)
    task_name = Column(String, default="")
    target = Column(String, default="", index=True)
    source_message_id = Column(Integer, nullable=True, index=True)
    grouped_id = Column(String, nullable=True)
    source_message_url = Column(Text, default="")
    target_message_url = Column(Text, default="")
    status = Column(String, default="success", index=True)
    message = Column(Text, default="")
    error = Column(Text, default="")
    bot_id = Column(Integer, nullable=True)
    bot_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BotAccount(Base):
    """官方 Bot 分发账号"""

    __tablename__ = "bot_accounts"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    token = Column(Text, nullable=False)

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


class SystemSetting(Base):
    """系统级配置"""

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(Text, default="")
    remark = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)
