import asyncio
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bot.handlers import get_registered_listener_snapshot, reload_handlers
from bot.clone_manager import clone_manager

from db.crud_bot import get_bot
from bot.bot_sender import bot_get_me, bot_send_text, request_post

from bot.notifier import notify_text
from bot.message_links import parse_message_url
from bot.clone_send_events import get_clone_send_events
from bot.listener_events import get_listener_send_events
from bot.bulk_replace import execute_bulk_replace, preview_bulk_replace
from bot.account_login import account_login_manager
from bot.runtime_queue import runtime_queue_state
from bot.listener_auto_catchup import catchup_latest_listener_message
from bot.listener_catchup import build_listener_catchup_plan
from accounts.manager import account_manager
from bot.channel_utils import normalize_channel_identifier, normalize_channel_list_json
from bot.support_bot import (
    check_group_topic_permission,
    get_recent_support_updates,
    get_token_for_support_bot,
    test_support_bot_config,
)
from bot.support_media import save_uploaded_media

from db.crud import (
    get_all_rules,
    create_rule,
    delete_rule,
    update_rule,
    get_all_accounts,
    create_account,
    update_account,
    delete_account,
    sync_clone_task_to_channel_rules,
    delete_channel_rules_by_clone_task_id,
)

from db.crud_listener import (
    create_listener_task,
    delete_listener_task,
    delete_listener_tasks_by_clone_task_id,
    get_all_listener_tasks,
    get_listener_task,
    parse_target_channels as parse_listener_targets,
    sync_clone_task_to_listener_tasks,
    update_listener_status,
    update_listener_task,
)

from db.crud_clone import (
    get_all_clone_tasks,
    get_clone_task,
    create_clone_task,
    update_clone_task,
    delete_clone_task,
)

from db.crud_settings import (
    ensure_default_settings,
    get_send_settings,
    update_send_settings,
)

from db.crud_support import (
    create_quick_reply,
    create_support_bot,
    create_tag,
    delete_support_bot,
    delete_quick_reply,
    ensure_support_defaults,
    get_conversation_detail,
    get_customer_detail,
    get_support_settings,
    get_support_bot_config,
    list_support_bots,
    list_customers,
    list_conversations,
    list_messages,
    list_quick_replies,
    list_tags,
    mark_conversation_read,
    set_customer_blocked,
    set_customer_tags,
    update_conversation_status,
    update_quick_reply,
    update_support_bot,
    update_support_settings,
)

from db.crud_bot import (
    get_all_bots,
    create_bot,
    update_bot,
    delete_bot,
    get_all_bindings,
    create_binding,
    update_binding,
    delete_binding,
    get_enabled_bots,
)

from db.crud_my_channels import (
    create_my_channel,
    delete_my_channel,
    get_my_channel,
    list_my_channels,
    my_channel_to_dict,
    set_my_channel_check_result,
    update_my_channel,
)
from db.crud_clone_channels import (
    clone_channel_to_dict,
    create_clone_channel,
    delete_clone_channel,
    get_clone_channel,
    list_clone_channels,
    update_clone_channel,
)

from db.crud_templates import (
    create_template,
    create_template_rule,
    delete_template,
    delete_template_rule,
    get_all_templates,
    get_template_rules,
    update_template_rule,
    update_template,
)

app = FastAPI(title="CloneBot API")


ADMIN_PASSWORD = "0909"
ADMIN_TOKEN = "clonebot-admin-0909"
AUTH_EXEMPT_PATHS = {
    "/api/auth/login",
}


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_admin_auth(request: Request, call_next):
    path = request.url.path

    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)

    if path in AUTH_EXEMPT_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("authorization") or ""
    token = auth_header.removeprefix("Bearer ").strip()

    if not secrets.compare_digest(token, ADMIN_TOKEN):
        return JSONResponse(
            status_code=401,
            content={"detail": "未登录或登录已失效"},
        )

    return await call_next(request)


class LoginRequest(BaseModel):
    password: str


class RuleCreate(BaseModel):
    source: str
    target: str
    enabled: bool = True
    blocked_keywords: str = "[]"
    replace_words: str = "{}"
    footer: str = ""
    remove_contact_lines: bool = True

class RuleUpdate(BaseModel):
    source: str
    target: str
    enabled: bool = True
    blocked_keywords: str = "[]"
    replace_words: str = "{}"
    footer: str = ""
    remove_contact_lines: bool = True


class ListenerTaskCreate(BaseModel):
    name: str
    source_channel: str
    target_channels: str = "[]"
    account_id: int = 1
    bot_id: Optional[int] = None
    enabled: bool = True
    status: str = "running"
    blocked_keywords: str = "[]"
    listen_required_keywords: str = "[]"
    replace_words: str = "{}"
    footer: str = ""
    remove_contact_lines: bool = True
    filter_qr_code: bool = True
    use_random_head: bool = False
    use_random_body: bool = False
    use_random_footer: bool = False
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
    selected_filter_template_group_id: Optional[int] = None
    selected_link_template_group_id: Optional[int] = None
    selected_contact_template_group_id: Optional[int] = None
    selected_head_template_id: Optional[int] = None
    selected_body_template_id: Optional[int] = None
    selected_footer_template_id: Optional[int] = None
    album_wait_seconds: int = 3


class ListenerTaskUpdate(BaseModel):
    name: Optional[str] = None
    source_channel: Optional[str] = None
    target_channels: Optional[str] = None
    account_id: Optional[int] = None
    bot_id: Optional[int] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None
    blocked_keywords: Optional[str] = None
    listen_required_keywords: Optional[str] = None
    replace_words: Optional[str] = None
    footer: Optional[str] = None
    remove_contact_lines: Optional[bool] = None
    filter_qr_code: Optional[bool] = None
    use_random_head: Optional[bool] = None
    use_random_body: Optional[bool] = None
    use_random_footer: Optional[bool] = None
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
    selected_filter_template_group_id: Optional[int] = None
    selected_link_template_group_id: Optional[int] = None
    selected_contact_template_group_id: Optional[int] = None
    selected_head_template_id: Optional[int] = None
    selected_body_template_id: Optional[int] = None
    selected_footer_template_id: Optional[int] = None
    album_wait_seconds: Optional[int] = None


class ContentTemplateCreate(BaseModel):
    name: str = ""
    type: str
    content: str = ""
    parent_id: Optional[int] = None
    enabled: bool = True
    weight: int = 1


class ContentTemplateUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    parent_id: Optional[int] = None
    enabled: Optional[bool] = None
    weight: Optional[int] = None


class ContentTemplateRuleItem(BaseModel):
    id: Optional[int] = None
    name: str = ""
    content: str = ""
    enabled: bool = True
    weight: int = 1


class ContentTemplateRuleCreate(BaseModel):
    name: str = ""
    type: str
    enabled: bool = True
    items: List[ContentTemplateRuleItem] = []


class ContentTemplateRuleUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    items: Optional[List[ContentTemplateRuleItem]] = None


class AccountCreate(BaseModel):
    name: str
    username: str = ""
    session_path: str
    proxy: str = ""
    remark: str = ""


class AccountUpdate(BaseModel):
    name: str
    username: str = ""
    session_path: str
    proxy: str = ""
    enabled: bool = True
    remark: str = ""


class AccountLoginStart(BaseModel):
    phone: str
    name: str = ""
    session_path: str = ""
    proxy: str = ""
    remark: str = ""
    account_id: Optional[int] = None
    update_existing: bool = False


class AccountLoginVerify(BaseModel):
    login_id: str
    code: str
    password: str = ""


class CloneTaskCreate(BaseModel):
    name: str
    source_channel: str
    target_channels: str = "[]"
    account_id: int = 1
    bot_id: Optional[int] = None

    clone_limit: int = 100
    start_message_url: str = ""
    end_message_url: str = ""
    single_delay: int = 3
    album_delay: int = 8
    target_delay: int = 2

    blocked_keywords: str = "[]"
    replace_words: str = "{}"
    footer: str = ""

    remove_contact_lines: bool = True
    filter_qr_code: bool = True
    enable_listener: bool = False

    use_random_head: bool = False
    use_random_body: bool = False
    use_random_footer: bool = False
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
    selected_filter_template_group_id: Optional[int] = None
    selected_link_template_group_id: Optional[int] = None
    selected_contact_template_group_id: Optional[int] = None
    selected_head_template_id: Optional[int] = None
    selected_body_template_id: Optional[int] = None
    selected_footer_template_id: Optional[int] = None


class CloneTaskUpdate(BaseModel):
    name: Optional[str] = None
    source_channel: Optional[str] = None
    target_channels: Optional[str] = None
    account_id: Optional[int] = None
    bot_id: Optional[int] = None

    clone_limit: Optional[int] = None
    start_message_url: Optional[str] = None
    end_message_url: Optional[str] = None
    single_delay: Optional[int] = None
    album_delay: Optional[int] = None
    target_delay: Optional[int] = None

    blocked_keywords: Optional[str] = None
    replace_words: Optional[str] = None
    footer: Optional[str] = None

    remove_contact_lines: Optional[bool] = None
    filter_qr_code: Optional[bool] = None
    enable_listener: Optional[bool] = None

    use_random_head: Optional[bool] = None
    use_random_body: Optional[bool] = None
    use_random_footer: Optional[bool] = None
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
    selected_filter_template_group_id: Optional[int] = None
    selected_link_template_group_id: Optional[int] = None
    selected_contact_template_group_id: Optional[int] = None
    selected_head_template_id: Optional[int] = None
    selected_body_template_id: Optional[int] = None
    selected_footer_template_id: Optional[int] = None

    enabled: Optional[bool] = None
    status: Optional[str] = None
    last_message_id: Optional[int] = None


class SupportQuickReplyCreate(BaseModel):
    title: str
    content: str
    sort: int = 0
    enabled: bool = True


class SupportQuickReplyUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    sort: Optional[int] = None
    enabled: Optional[bool] = None


class SupportSettingsUpdate(BaseModel):
    support_bot_id: Optional[str] = None
    support_bot_token: Optional[str] = None
    support_polling_enabled: Optional[str] = None
    support_group_chat_id: Optional[str] = None
    support_backend_base_url: Optional[str] = None
    welcome_message: Optional[str] = None
    off_hours_message: Optional[str] = None
    business_hours_enabled: Optional[str] = None
    business_start_hour: Optional[str] = None
    business_end_hour: Optional[str] = None


class SupportBotCreate(BaseModel):
    name: str = "客服 Bot"
    bot_id: Optional[int] = None
    bot_token: str = ""
    price: str = ""
    support_group_chat_id: str = ""
    polling_enabled: bool = False
    welcome_message: str = ""
    welcome_text_type: str = "plain"
    welcome_media_type: str = "text"
    welcome_media_file_id: str = ""
    off_hours_message: str = ""
    business_hours_enabled: bool = False
    business_start_hour: int = 9
    business_end_hour: int = 22
    backend_base_url: str = ""
    status: str = "enabled"


class SupportBotUpdate(BaseModel):
    name: Optional[str] = None
    bot_id: Optional[int] = None
    bot_token: Optional[str] = None
    price: Optional[str] = None
    support_group_chat_id: Optional[str] = None
    polling_enabled: Optional[bool] = None
    welcome_message: Optional[str] = None
    welcome_text_type: Optional[str] = None
    welcome_media_type: Optional[str] = None
    welcome_media_file_id: Optional[str] = None
    off_hours_message: Optional[str] = None
    business_hours_enabled: Optional[bool] = None
    business_start_hour: Optional[int] = None
    business_end_hour: Optional[int] = None
    backend_base_url: Optional[str] = None
    status: Optional[str] = None


class SupportTagCreate(BaseModel):
    name: str
    color: str = ""


class SupportCustomerTagsUpdate(BaseModel):
    tag_ids: List[int] = []


class BotCreate(BaseModel):
    name: str
    token: str
    enabled: bool = True
    remark: str = ""


class BotUpdate(BaseModel):
    name: Optional[str] = None
    token: Optional[str] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None
    last_error: Optional[str] = None


class BotBindingCreate(BaseModel):
    target_channel: str
    bot_id: int
    enabled: bool = True
    remark: str = ""


class BotBindingUpdate(BaseModel):
    target_channel: Optional[str] = None
    bot_id: Optional[int] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None


class SendSettingsUpdate(BaseModel):
    global_send_delay: Optional[int] = None
    send_retry_count: Optional[int] = None
    send_retry_delay: Optional[int] = None


class BotSendTestRequest(BaseModel):
    chat_id: str
    text: str = "Bot 测试发送"


class MyChannelCreate(BaseModel):
    title: str = ""
    username: str = ""
    chat_id: str = ""
    channel_type: str = ""
    group_name: str = ""
    tags: str = "[]"
    bot_id: Optional[int] = None
    status: str = "enabled"
    delivery_status: str = ""
    collection_status: str = ""
    is_default: bool = False
    remark: str = ""


class MyChannelUpdate(BaseModel):
    title: Optional[str] = None
    username: Optional[str] = None
    chat_id: Optional[str] = None
    channel_type: Optional[str] = None
    group_name: Optional[str] = None
    tags: Optional[str] = None
    bot_id: Optional[int] = None
    status: Optional[str] = None
    delivery_status: Optional[str] = None
    collection_status: Optional[str] = None
    is_default: Optional[bool] = None
    remark: Optional[str] = None


class CloneChannelCreate(BaseModel):
    title: str = ""
    channel_link: str
    group_name: str = ""
    channel_type: str = ""
    remark: str = ""


class CloneChannelUpdate(BaseModel):
    title: Optional[str] = None
    channel_link: Optional[str] = None
    group_name: Optional[str] = None
    channel_type: Optional[str] = None
    remark: Optional[str] = None


class BulkReplacePreviewRequest(BaseModel):
    channel_ids: List[int] = []
    old_text: str
    new_text: str = ""
    message_type: str = "all"
    date_range: Optional[List[str]] = None
    limit: int = 500
    source_type: str = "all"


class BulkReplaceExecuteRequest(BaseModel):
    records: List[dict] = []
    old_text: str
    new_text: str = ""
    channel_ids: List[int] = []
    message_type: str = "all"
    source_type: str = "all"
    dry_run: bool = False


class ListenerCatchupRequest(BaseModel):
    force: bool = True
    limit: int = 500
    background: bool = False

def clone_task_to_dict(task):
    return {
        "id": task.id,
        "name": task.name,
        "source_channel": task.source_channel,
        "target_channels": task.target_channels,
        "account_id": task.account_id,
        "bot_id": getattr(task, "bot_id", None),
        "status": task.status,
        "last_message_id": task.last_message_id,
        "clone_limit": task.clone_limit,
        "start_message_url": getattr(task, "start_message_url", "") or "",
        "end_message_url": getattr(task, "end_message_url", "") or "",
        "single_delay": task.single_delay,
        "album_delay": task.album_delay,
        "target_delay": task.target_delay,
        "blocked_keywords": task.blocked_keywords,
        "replace_words": task.replace_words,
        "footer": task.footer,
        "remove_contact_lines": getattr(task, "remove_contact_lines", True),
        "filter_qr_code": getattr(task, "filter_qr_code", True),
        "enable_listener": getattr(task, "enable_listener", False),
        "use_random_head": getattr(task, "use_random_head", False),
        "use_random_body": getattr(task, "use_random_body", False),
        "use_random_footer": getattr(task, "use_random_footer", False),
        "selected_head_template_group_id": getattr(task, "selected_head_template_group_id", None),
        "selected_body_template_group_id": getattr(task, "selected_body_template_group_id", None),
        "selected_footer_template_group_id": getattr(task, "selected_footer_template_group_id", None),
        "selected_filter_template_group_id": getattr(task, "selected_filter_template_group_id", None),
        "selected_link_template_group_id": getattr(task, "selected_link_template_group_id", None),
        "selected_contact_template_group_id": getattr(task, "selected_contact_template_group_id", None),
        "selected_head_template_id": getattr(task, "selected_head_template_id", None),
        "selected_body_template_id": getattr(task, "selected_body_template_id", None),
        "selected_footer_template_id": getattr(task, "selected_footer_template_id", None),
        "enabled": task.enabled,
        "worker_running": clone_manager.is_running(task.id),
    }


def content_template_to_dict(template):
    return {
        "id": template.id,
        "parent_id": getattr(template, "parent_id", None),
        "name": template.name,
        "type": template.type,
        "content": template.content,
        "enabled": template.enabled,
        "weight": template.weight,
        "created_at": str(template.created_at) if template.created_at else "",
        "updated_at": str(template.updated_at) if template.updated_at else "",
    }



def content_template_rule_to_dict(rule):
    group = rule.get("group")
    items = rule.get("items") or []

    data = content_template_to_dict(group)
    data["items"] = [
        content_template_to_dict(item)
        for item in items
    ]
    data["item_count"] = len(data["items"])
    return data


def normalize_task_channels(data):
    payload = dict(data)

    if "source_channel" in payload and payload.get("source_channel") is not None:
        payload["source_channel"] = normalize_channel_identifier(payload.get("source_channel"))

    if "target_channels" in payload and payload.get("target_channels") is not None:
        payload["target_channels"] = normalize_channel_list_json(payload.get("target_channels"))

    return payload


def rule_to_dict(rule):
    return {
        "id": rule.id,
        "source": rule.source,
        "target": rule.target,
        "account_id": getattr(rule, "account_id", 1),
        "enabled": rule.enabled,
        "blocked_keywords": getattr(rule, "keywords", None)
        or getattr(rule, "blocked_keywords", "[]")
        or "[]",
        "replace_words": rule.replace_words,
        "footer": rule.footer,
        "remove_contact_lines": getattr(rule, "remove_contact_lines", True),
        "clone_task_id": getattr(rule, "clone_task_id", None),
        "last_message_id": rule.last_message_id,
    }


def listener_task_to_dict(task):
    return {
        "id": task.id,
        "name": task.name,
        "source_channel": task.source_channel,
        "target_channels": task.target_channels,
        "target_count": len(parse_listener_targets(task.target_channels)),
        "account_id": task.account_id,
        "bot_id": getattr(task, "bot_id", None),
        "enabled": task.enabled,
        "status": task.status,
        "blocked_keywords": task.blocked_keywords,
        "listen_required_keywords": getattr(task, "listen_required_keywords", "[]") or "[]",
        "replace_words": task.replace_words,
        "footer": task.footer,
        "remove_contact_lines": task.remove_contact_lines,
        "filter_qr_code": getattr(task, "filter_qr_code", True),
        "use_random_head": getattr(task, "use_random_head", False),
        "use_random_body": getattr(task, "use_random_body", False),
        "use_random_footer": getattr(task, "use_random_footer", False),
        "selected_head_template_group_id": getattr(task, "selected_head_template_group_id", None),
        "selected_body_template_group_id": getattr(task, "selected_body_template_group_id", None),
        "selected_footer_template_group_id": getattr(task, "selected_footer_template_group_id", None),
        "selected_filter_template_group_id": getattr(task, "selected_filter_template_group_id", None),
        "selected_link_template_group_id": getattr(task, "selected_link_template_group_id", None),
        "selected_contact_template_group_id": getattr(task, "selected_contact_template_group_id", None),
        "selected_head_template_id": getattr(task, "selected_head_template_id", None),
        "selected_body_template_id": getattr(task, "selected_body_template_id", None),
        "selected_footer_template_id": getattr(task, "selected_footer_template_id", None),
        "album_wait_seconds": task.album_wait_seconds,
        "last_error": task.last_error,
        "last_received_at": str(task.last_received_at) if getattr(task, "last_received_at", None) else "",
        "clone_task_id": getattr(task, "clone_task_id", None),
        "created_at": str(task.created_at) if task.created_at else "",
        "updated_at": str(task.updated_at) if task.updated_at else "",
    }


def account_to_dict(account):
    return {
        "id": account.id,
        "name": account.name,
        "username": getattr(account, "username", "") or "",
        "phone": getattr(account, "phone", "") or "",
        "session_path": account.session_path,
        "proxy": account.proxy,
        "enabled": account.enabled,
        "remark": account.remark,
        "updated_at": str(account.updated_at) if getattr(account, "updated_at", None) else "",
    }

def bot_to_dict(bot):
    return {
        "id": bot.id,
        "name": bot.name,
        "token": mask_secret(bot.token),
        "has_token": bool(bot.token),
        "username": getattr(bot, "username", "") or "",
        "bot_link": getattr(bot, "bot_link", "") or "",
        "enabled": bot.enabled,
        "remark": bot.remark,
        "last_error": bot.last_error,
        "created_at": str(bot.created_at) if bot.created_at else "",
        "updated_at": str(bot.updated_at) if bot.updated_at else "",
    }


def mask_secret(value):
    text = str(value or "")

    if not text:
        return ""

    if len(text) <= 12:
        return "******"

    return f"{text[:8]}...{text[-6:]}"


async def refresh_bot_profile(bot):
    try:
        result = await bot_get_me(bot.token)
        profile = result.get("result") or {}
        username = profile.get("username") or ""
        update_bot(bot.id, {
            "username": username,
            "bot_link": f"https://t.me/{username}" if username else "",
            "last_error": "",
        })
        refreshed = get_bot(bot.id)
        return refreshed or bot
    except Exception:
        return bot


def bot_binding_to_dict(binding):
    return {
        "id": binding.id,
        "target_channel": binding.target_channel,
        "bot_id": binding.bot_id,
        "enabled": binding.enabled,
        "remark": binding.remark,
        "created_at": str(binding.created_at) if binding.created_at else "",
    }


def resolve_default_bot(bot_id=None):
    if bot_id:
        bot = get_bot(bot_id)
        if bot and bot.enabled:
            return bot

    bots = get_enabled_bots()
    return bots[0] if bots else None


def member_permissions(member):
    status = member.get("status") or ""
    is_member = status in {"creator", "administrator", "member"}
    is_admin = status in {"creator", "administrator"}

    return {
        "bot_is_member": is_member,
        "bot_is_admin": is_admin,
        "can_post_messages": bool(
            member.get("can_post_messages")
            or member.get("can_send_messages")
            or status == "creator"
        ),
        "can_edit_messages": bool(member.get("can_edit_messages") or status == "creator"),
        "can_delete_messages": bool(member.get("can_delete_messages") or status == "creator"),
        "can_manage_topics": bool(member.get("can_manage_topics") or status == "creator"),
    }


async def fetch_channel_member_count(bot_token, chat_id):
    try:
        result = await asyncio.to_thread(
            request_post,
            bot_token,
            "getChatMemberCount",
            {"chat_id": chat_id},
            None,
        )
        count = result.get("result")
        return {
            "member_count": int(count) if count is not None else None,
            "can_view_member_count": count is not None,
        }
    except Exception:
        return {
            "member_count": None,
            "can_view_member_count": False,
        }


async def fetch_channel_creator(bot_token, chat_id):
    try:
        result = await asyncio.to_thread(
            request_post,
            bot_token,
            "getChatAdministrators",
            {"chat_id": chat_id},
            None,
        )
        admins = result.get("result") or []
        creator = next(
            (
                admin.get("user") or {}
                for admin in admins
                if admin.get("status") == "creator"
            ),
            None,
        )

        if not creator:
            return {
                "creator_user_id": "",
                "creator_username": "",
                "creator_name": "",
                "can_view_creator": False,
            }

        full_name = " ".join(
            part
            for part in [
                creator.get("first_name") or "",
                creator.get("last_name") or "",
            ]
            if part
        ).strip()
        username = creator.get("username") or ""

        return {
            "creator_user_id": str(creator.get("id") or ""),
            "creator_username": f"@{username}" if username else "",
            "creator_name": full_name,
            "can_view_creator": True,
        }
    except Exception:
        return {
            "creator_user_id": "",
            "creator_username": "",
            "creator_name": "",
            "can_view_creator": False,
        }


async def check_my_channel_permissions(channel):
    bot = resolve_default_bot(getattr(channel, "bot_id", None))

    if not bot:
        updated = set_my_channel_check_result(
            channel.id,
            {
                "status": "error",
                "last_error": "没有可用 Bot，请先添加并启用 Bot",
            },
        )
        return my_channel_to_dict(updated)

    target = channel.chat_id or channel.username

    if not target:
        updated = set_my_channel_check_result(
            channel.id,
            {
                "status": "error",
                "last_error": "频道 username 和 chat_id 为空",
            },
        )
        return my_channel_to_dict(updated)

    try:
        chat_result = await asyncio.to_thread(
            request_post,
            bot.token,
            "getChat",
            {"chat_id": target},
            None,
        )
        chat = chat_result.get("result") or {}
        bot_info = await bot_get_me(bot.token)
        bot_user_id = (bot_info.get("result") or {}).get("id")
        member_result = await asyncio.to_thread(
            request_post,
            bot.token,
            "getChatMember",
            {
                "chat_id": chat.get("id") or target,
                "user_id": bot_user_id,
            },
            None,
        )
        member = member_result.get("result") or {}
        permissions = member_permissions(member)
        resolved_chat_id = chat.get("id") or target
        member_count_info, creator_info = await asyncio.gather(
            fetch_channel_member_count(bot.token, resolved_chat_id),
            fetch_channel_creator(bot.token, resolved_chat_id),
        )
        status = "enabled" if permissions["bot_is_member"] else "error"
        last_error = "" if permissions["bot_is_member"] else "Bot 不在频道或群内"

        updated = set_my_channel_check_result(
            channel.id,
            {
                "title": chat.get("title") or channel.title,
                "username": f"@{chat.get('username')}".lower() if chat.get("username") else channel.username,
                "chat_id": str(chat.get("id") or channel.chat_id or ""),
                "channel_type": chat.get("type") or channel.channel_type,
                "bot_id": bot.id,
                "status": status,
                "last_error": last_error,
                **permissions,
                **member_count_info,
                **creator_info,
            },
        )
        return my_channel_to_dict(updated)

    except Exception as e:
        updated = set_my_channel_check_result(
            channel.id,
            {
                "status": "error",
                "last_error": str(e)[:1000],
                "bot_id": bot.id,
                "bot_is_member": False,
                "bot_is_admin": False,
                "can_post_messages": False,
                "can_edit_messages": False,
                "can_delete_messages": False,
                "can_manage_topics": False,
                "member_count": None,
                "can_view_member_count": False,
                "creator_user_id": "",
                "creator_username": "",
                "creator_name": "",
                "can_view_creator": False,
            },
        )
        return my_channel_to_dict(updated)


@app.post("/api/auth/login")
async def api_auth_login(payload: LoginRequest):
    if not secrets.compare_digest(payload.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="密码错误")

    return {
        "ok": True,
        "token": ADMIN_TOKEN,
    }


@app.get("/api/status")
def status():
    listener_tasks = get_all_listener_tasks()

    return {
        "status": "running",
        "rules_count": len(listener_tasks),
    }


@app.get("/api/runtime/listener-handlers")
def api_runtime_listener_handlers():
    listener_tasks = get_all_listener_tasks()
    registered_groups = get_registered_listener_snapshot()
    registered_task_ids = {
        task_id
        for group in registered_groups
        for task_id in group.get("task_ids", [])
    }

    client_states = {}
    for account_id, client in account_manager.clients.items():
        connected = None
        try:
            if hasattr(client, "is_connected"):
                connected = bool(client.is_connected())
        except Exception:
            connected = None

        client_states[int(account_id)] = {
            "loaded": True,
            "connected": connected,
        }

    tasks = []
    for task in listener_tasks:
        account_id = getattr(task, "account_id", None)
        client_state = client_states.get(int(account_id or 0), {
            "loaded": False,
            "connected": False,
        })
        targets = parse_listener_targets(task.target_channels)

        tasks.append({
            "id": task.id,
            "name": task.name,
            "enabled": bool(task.enabled),
            "status": task.status,
            "source_channel": task.source_channel,
            "target_channels": targets,
            "account_id": account_id,
            "client_loaded": client_state.get("loaded", False),
            "client_connected": client_state.get("connected"),
            "registered": task.id in registered_task_ids,
            "last_received_at": str(task.last_received_at) if getattr(task, "last_received_at", None) else "",
            "last_error": task.last_error or "",
        })

    return {
        "registered_groups": registered_groups,
        "registered_count": len(registered_groups),
        "client_states": client_states,
        "tasks": tasks,
    }


@app.get("/api/runtime/dashboard")
def api_runtime_dashboard():
    queue_snapshot = runtime_queue_state.snapshot()
    listener_tasks = get_all_listener_tasks()
    clone_snapshot = clone_manager.snapshot()
    loaded_account_ids = sorted(account_manager.clients.keys())

    enabled_listener_count = len([
        task for task in listener_tasks
        if getattr(task, "enabled", False)
    ])

    queue_stats = queue_snapshot.get("stats", {})
    stats = {
        **queue_stats,
        "clone_running_count": clone_snapshot.get("total_running", 0),
        "listener_enabled_count": enabled_listener_count,
        "loaded_account_count": len(loaded_account_ids),
    }

    return {
        "queue": queue_snapshot,
        "clone_workers": clone_snapshot,
        "listener": {
            "enabled_count": enabled_listener_count,
            "total_count": len(listener_tasks),
        },
        "accounts": {
            "loaded_count": len(loaded_account_ids),
            "loaded_ids": loaded_account_ids,
        },
        "stats": stats,
    }


@app.get("/api/my-channels")
def api_get_my_channels(
    keyword: str = "",
    status: str = "",
    group_name: str = "",
    bot_id: Optional[int] = None,
):
    return {
        "items": [
            my_channel_to_dict(channel)
            for channel in list_my_channels(
                keyword=keyword,
                status=status,
                group_name=group_name,
                bot_id=bot_id,
            )
        ],
    }


@app.post("/api/my-channels/batch-check")
async def api_batch_check_my_channels():
    result = []

    for channel in list_my_channels():
        result.append(await check_my_channel_permissions(channel))

    return {
        "ok": True,
        "items": result,
    }


@app.get("/api/my-channels/{channel_id}")
def api_get_my_channel(channel_id: int):
    channel = get_my_channel(channel_id)

    if not channel:
        return {
            "ok": False,
            "message": "channel not found",
        }

    return {
        "ok": True,
        "item": my_channel_to_dict(channel),
    }


@app.post("/api/my-channels")
def api_create_my_channel(data: MyChannelCreate):
    try:
        channel = create_my_channel(data.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return my_channel_to_dict(channel)


@app.put("/api/my-channels/{channel_id}")
def api_update_my_channel(channel_id: int, data: MyChannelUpdate):
    try:
        channel = update_my_channel(
            channel_id,
            data.dict(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not channel:
        return {
            "ok": False,
            "message": "channel not found",
        }

    return my_channel_to_dict(channel)


@app.delete("/api/my-channels/{channel_id}")
def api_delete_my_channel(channel_id: int):
    ok = delete_my_channel(channel_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "channel not found",
    }


@app.get("/api/clone-channels")
def api_get_clone_channels(
    keyword: str = "",
    group_name: str = "",
    channel_type: str = "",
):
    return {
        "items": [
            clone_channel_to_dict(channel)
            for channel in list_clone_channels(
                keyword=keyword,
                group_name=group_name,
                channel_type=channel_type,
            )
        ],
    }


@app.get("/api/clone-channels/{channel_id}")
def api_get_clone_channel(channel_id: int):
    channel = get_clone_channel(channel_id)

    if not channel:
        return {
            "ok": False,
            "message": "channel not found",
        }

    return {
        "ok": True,
        "item": clone_channel_to_dict(channel),
    }


@app.post("/api/clone-channels")
def api_create_clone_channel(data: CloneChannelCreate):
    try:
        channel = create_clone_channel(data.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return clone_channel_to_dict(channel)


@app.put("/api/clone-channels/{channel_id}")
def api_update_clone_channel(channel_id: int, data: CloneChannelUpdate):
    try:
        channel = update_clone_channel(
            channel_id,
            data.dict(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not channel:
        return {
            "ok": False,
            "message": "channel not found",
        }

    return clone_channel_to_dict(channel)


@app.delete("/api/clone-channels/{channel_id}")
def api_delete_clone_channel(channel_id: int):
    ok = delete_clone_channel(channel_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "channel not found",
    }


def parse_optional_datetime(value):
    text = (value or "").strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


@app.post("/api/bulk-replace/preview")
def api_bulk_replace_preview(payload: BulkReplacePreviewRequest):
    date_range = payload.date_range or []
    start_time = parse_optional_datetime(date_range[0]) if len(date_range) >= 1 else None
    end_time = parse_optional_datetime(date_range[1]) if len(date_range) >= 2 else None

    try:
        return preview_bulk_replace(
            channel_ids=payload.channel_ids,
            old_text=payload.old_text,
            new_text=payload.new_text,
            message_type=payload.message_type,
            source_type=payload.source_type,
            start_time=start_time,
            end_time=end_time,
            limit=payload.limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bulk-replace/execute")
async def api_bulk_replace_execute(payload: BulkReplaceExecuteRequest):
    try:
        return await execute_bulk_replace(
            records=payload.records,
            old_text=payload.old_text,
            new_text=payload.new_text,
            channel_ids=payload.channel_ids,
            message_type=payload.message_type,
            source_type=payload.source_type,
            dry_run=payload.dry_run,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/my-channels/{channel_id}/check")
async def api_check_my_channel(channel_id: int):
    channel = get_my_channel(channel_id)

    if not channel:
        return {
            "ok": False,
            "message": "channel not found",
        }

    checked = await check_my_channel_permissions(channel)
    return {
        "ok": checked.get("status") != "error",
        "item": checked,
        "message": checked.get("last_error") or "ok",
    }


@app.get("/api/rules")
def rules():
    rules = get_all_rules()

    return [
        rule_to_dict(rule)
        for rule in rules
    ]


@app.post("/api/rules")
def add_rule(rule: RuleCreate):
    new_rule = create_rule(
        source=rule.source,
        target=rule.target,
        enabled=rule.enabled,
        blocked_keywords=rule.blocked_keywords,
        replace_words=rule.replace_words,
        footer=rule.footer,
        remove_contact_lines=rule.remove_contact_lines,
    )

    reload_handlers()

    return rule_to_dict(new_rule)


@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: int):
    delete_rule(rule_id)
    reload_handlers()

    return {
        "message": "ok",
    }


@app.put("/api/rules/{rule_id}")
def edit_rule(rule_id: int, data: RuleUpdate):
    updated = update_rule(
        rule_id,
        data.dict(),
    )

    if not updated:
        return {
            "message": "rule not found",
        }

    reload_handlers()

    return rule_to_dict(updated)


@app.get("/api/logs")
def get_logs(limit: int = 200):
    log_file = Path("logs/clonebot.log")

    if not log_file.exists():
        return {
            "logs": [],
        }

    lines = log_file.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    return {
        "logs": lines[-limit:],
    }


@app.get("/api/clone-send-events")
def api_get_clone_send_events(limit: int = 20):
    return {
        "events": get_clone_send_events(limit),
    }


@app.get("/api/listener-send-events")
def api_get_listener_send_events(limit: int = 200):
    return {
        "events": get_listener_send_events(limit),
    }


@app.get("/api/support/conversations")
def api_support_conversations(status: str = "all", q: str = "", limit: int = 100):
    return {
        "conversations": list_conversations(status=status, q=q, limit=limit),
    }


@app.get("/api/support/customers")
def api_support_customers(q: str = "", limit: int = 100):
    return {
        "customers": list_customers(q=q, limit=limit),
    }


@app.get("/api/support/customers/{customer_id}")
def api_support_customer_detail(customer_id: int):
    customer = get_customer_detail(customer_id)

    if not customer:
        return {
            "ok": False,
            "message": "customer not found",
        }

    return {
        "ok": True,
        "customer": customer,
    }


@app.get("/api/support/conversations/{conversation_id}")
def api_support_conversation_detail(conversation_id: int):
    detail = get_conversation_detail(conversation_id)

    if not detail:
        return {
            "ok": False,
            "message": "conversation not found",
        }

    mark_conversation_read(conversation_id)
    detail["ok"] = True
    return detail


@app.post("/api/support/conversations/{conversation_id}/close")
def api_support_close_conversation(conversation_id: int):
    conversation = update_conversation_status(conversation_id, "closed")

    if not conversation:
        return {
            "ok": False,
            "message": "conversation not found",
        }

    return {
        "ok": True,
        "message": "conversation closed",
    }


@app.post("/api/support/customers/{customer_id}/block")
def api_support_block_customer(customer_id: int):
    customer = set_customer_blocked(customer_id, True)

    if not customer:
        return {
            "ok": False,
            "message": "customer not found",
        }

    return {
        "ok": True,
        "message": "customer blocked",
    }


@app.post("/api/support/customers/{customer_id}/unblock")
def api_support_unblock_customer(customer_id: int):
    customer = set_customer_blocked(customer_id, False)

    if not customer:
        return {
            "ok": False,
            "message": "customer not found",
        }

    return {
        "ok": True,
        "message": "customer unblocked",
    }


@app.get("/api/support/messages")
def api_support_messages(conversation_id: Optional[int] = None, customer_id: Optional[int] = None, limit: int = 200):
    return {
        "messages": list_messages(
            conversation_id=conversation_id,
            customer_id=customer_id,
            limit=limit,
        ),
    }


@app.get("/api/support/conversations/{conversation_id}/messages")
def api_support_conversation_messages(conversation_id: int, limit: int = 200):
    return {
        "messages": list_messages(conversation_id=conversation_id, limit=limit),
    }


@app.get("/api/support/quick-replies")
def api_support_quick_replies(include_disabled: bool = True):
    return {
        "items": list_quick_replies(include_disabled=include_disabled),
    }


@app.post("/api/support/quick-replies")
def api_support_create_quick_reply(data: SupportQuickReplyCreate):
    return create_quick_reply(data.dict())


@app.put("/api/support/quick-replies/{reply_id}")
def api_support_update_quick_reply(reply_id: int, data: SupportQuickReplyUpdate):
    reply = update_quick_reply(reply_id, data.dict(exclude_unset=True))

    if not reply:
        return {
            "ok": False,
            "message": "quick reply not found",
        }

    return reply


@app.delete("/api/support/quick-replies/{reply_id}")
def api_support_delete_quick_reply(reply_id: int):
    ok = delete_quick_reply(reply_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "quick reply not found",
    }


@app.get("/api/support/settings")
def api_support_settings():
    ensure_support_defaults()

    return {
        "settings": get_support_settings(),
    }


@app.put("/api/support/settings")
def api_support_update_settings(data: SupportSettingsUpdate):
    return {
        "settings": update_support_settings(data.dict(exclude_unset=True)),
    }


@app.get("/api/support/bots")
def api_support_bots():
    return {
        "items": list_support_bots(include_disabled=True),
    }


@app.post("/api/support/bots")
def api_create_support_bot(data: SupportBotCreate):
    return create_support_bot(data.dict())


@app.put("/api/support/bots/{support_bot_id}")
def api_update_support_bot(support_bot_id: int, data: SupportBotUpdate):
    item = update_support_bot(support_bot_id, data.dict(exclude_unset=True))
    if not item:
        return {
            "ok": False,
            "message": "support bot not found",
        }
    return item


@app.delete("/api/support/bots/{support_bot_id}")
def api_delete_support_bot(support_bot_id: int):
    ok = delete_support_bot(support_bot_id)
    return {
        "ok": ok,
        "message": "ok" if ok else "support bot not found",
    }


@app.post("/api/support/bots/{support_bot_id}/test")
async def api_test_support_bot_item(support_bot_id: int):
    config = get_support_bot_config(support_bot_id)
    if not config:
        return {
            "ok": False,
            "message": "support bot not found",
        }
    token = get_token_for_support_bot(config)
    if not token:
        return {
            "ok": False,
            "message": "support bot token empty",
        }
    try:
        result = await bot_get_me(token)
        group_chat_id = (config.get("support_group_chat_id") or "").strip()
        permission = (
            await check_group_topic_permission(token, group_chat_id)
            if group_chat_id
            else None
        )
        return {
            "ok": True,
            "mode": "polling",
            "bot": result.get("result") or {},
            "group_permission": permission,
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": "polling",
            "message": str(e),
        }


@app.post("/api/support/media/upload")
async def api_upload_support_media(file: UploadFile = File(...)):
    content = await file.read()
    max_size = 50 * 1024 * 1024

    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="上传文件不能超过 50MB")

    result = save_uploaded_media(file.filename or "welcome-media", content)
    return {
        "ok": True,
        "media_ref": result["media_ref"],
        "filename": result["filename"],
        "size": result["size"],
        "content_type": file.content_type or "",
    }


@app.post("/api/support/bot/test")
async def api_support_test_bot():
    return await test_support_bot_config()


@app.get("/api/support/updates/recent")
async def api_support_recent_updates(limit: int = 30):
    return await get_recent_support_updates(limit=limit)


@app.get("/api/support/tags")
def api_support_tags():
    return {
        "items": list_tags(),
    }


@app.post("/api/support/tags")
def api_support_create_tag(data: SupportTagCreate):
    return create_tag(data.dict())


@app.put("/api/support/customers/{customer_id}/tags")
def api_support_update_customer_tags(customer_id: int, data: SupportCustomerTagsUpdate):
    return {
        "items": set_customer_tags(customer_id, data.tag_ids),
    }


@app.get("/api/content-templates")
def api_get_content_templates():
    return [
        content_template_to_dict(template)
        for template in get_all_templates()
    ]


@app.get("/api/content-template-rules")
def api_get_content_template_rules():
    return [
        content_template_rule_to_dict(rule)
        for rule in get_template_rules()
    ]


@app.post("/api/content-template-rules")
def api_create_content_template_rule(data: ContentTemplateRuleCreate):
    template = create_template_rule(data.dict())
    return content_template_to_dict(template)


@app.put("/api/content-template-rules/{rule_id}")
def api_update_content_template_rule(rule_id: int, data: ContentTemplateRuleUpdate):
    template = update_template_rule(
        rule_id,
        data.dict(exclude_unset=True),
    )

    if not template:
        return {
            "ok": False,
            "message": "template rule not found",
        }

    return content_template_to_dict(template)


@app.delete("/api/content-template-rules/{rule_id}")
def api_delete_content_template_rule(rule_id: int):
    ok = delete_template_rule(rule_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "template rule not found",
    }


@app.post("/api/content-templates")
def api_create_content_template(data: ContentTemplateCreate):
    template = create_template(data.dict())
    return content_template_to_dict(template)


@app.put("/api/content-templates/{template_id}")
def api_update_content_template(template_id: int, data: ContentTemplateUpdate):
    template = update_template(
        template_id,
        data.dict(exclude_unset=True),
    )

    if not template:
        return {
            "ok": False,
            "message": "template not found",
        }

    return content_template_to_dict(template)


@app.delete("/api/content-templates/{template_id}")
def api_delete_content_template(template_id: int):
    ok = delete_template(template_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "template not found",
    }


@app.get("/api/listener-tasks")
def api_get_listener_tasks():
    return [
        listener_task_to_dict(task)
        for task in get_all_listener_tasks()
    ]


@app.post("/api/listener-tasks")
def api_create_listener_task(data: ListenerTaskCreate):
    task = create_listener_task(normalize_task_channels(data.dict()))
    reload_handlers()
    return listener_task_to_dict(task)


@app.put("/api/listener-tasks/{task_id}")
def api_update_listener_task(task_id: int, data: ListenerTaskUpdate):
    task = update_listener_task(
        task_id,
        normalize_task_channels(data.dict(exclude_unset=True)),
    )

    if not task:
        return {
            "ok": False,
            "message": "listener task not found",
        }

    reload_handlers()
    return listener_task_to_dict(task)


@app.delete("/api/listener-tasks/{task_id}")
def api_delete_listener_task(task_id: int):
    ok = delete_listener_task(task_id)
    reload_handlers()

    return {
        "ok": ok,
        "message": "ok" if ok else "listener task not found",
    }


@app.post("/api/listener-tasks/{task_id}/start")
async def api_start_listener_task(task_id: int):
    task = update_listener_status(
        task_id,
        enabled=True,
        status="running",
        last_error="",
    )

    if not task:
        return {
            "ok": False,
            "message": "listener task not found",
        }

    if not account_manager.get_client(task.account_id):
        await account_manager.load_accounts()

    if not account_manager.get_client(task.account_id):
        error = f"监听账号不存在或未加载：account_id={task.account_id}"
        task = update_listener_status(
            task_id,
            enabled=False,
            status="stopped",
            last_error=error,
        )
        reload_handlers()
        return {
            "ok": False,
            "message": error,
            "task": listener_task_to_dict(task) if task else None,
        }

    reload_handlers()

    return {
        "ok": True,
        "message": "listener task started",
        "task": listener_task_to_dict(task),
    }


@app.post("/api/listener-tasks/{task_id}/stop")
def api_stop_listener_task(task_id: int):
    task = update_listener_status(
        task_id,
        enabled=False,
        status="stopped",
    )

    if not task:
        return {
            "ok": False,
            "message": "listener task not found",
        }

    reload_handlers()

    return {
        "ok": True,
        "message": "listener task stopped",
        "task": listener_task_to_dict(task),
    }


@app.post("/api/listener-tasks/{task_id}/catchup-check")
async def api_listener_catchup_check(task_id: int):
    task = get_listener_task(task_id)

    if not task:
        return {
            "ok": False,
            "consistent": False,
            "message": "listener task not found",
        }

    plan = await build_listener_catchup_plan(task)
    plan.pop("_pending_items", None)
    return plan


@app.post("/api/listener-tasks/{task_id}/catchup-latest")
async def api_listener_catchup_latest(
    task_id: int,
    payload: Optional[ListenerCatchupRequest] = None,
):
    task = get_listener_task(task_id)

    if not task:
        return {
            "ok": False,
            "message": "listener task not found",
        }

    force = bool(payload.force) if payload else True
    limit = payload.limit if payload else 500
    background = bool(payload.background) if payload else False

    if background:
        asyncio.create_task(
            catchup_latest_listener_message(
                task,
                force=force,
                limit=limit,
            )
        )
        return {
            "ok": True,
            "message": "补齐任务已开始，发送进度会显示在首页排队任务列表",
            "background": True,
        }

    return await catchup_latest_listener_message(task, force=force, limit=limit)


@app.get("/api/accounts")
def accounts():
    return [
        account_to_dict(account)
        for account in get_all_accounts()
    ]


@app.post("/api/accounts")
def add_account(data: AccountCreate):
    account = create_account(
        name=data.name,
        username=data.username,
        session_path=data.session_path,
        proxy=data.proxy,
        remark=data.remark,
    )

    return account_to_dict(account)


@app.post("/api/accounts/login/start")
async def api_account_login_start(data: AccountLoginStart):
    result = await account_login_manager.start_login(
        phone=data.phone,
        name=data.name,
        session_path=data.session_path,
        proxy=data.proxy,
        remark=data.remark,
        account_id=data.account_id,
        update_existing=data.update_existing,
    )

    account = result.get("account") if isinstance(result, dict) else None
    if result.get("ok") and account and account.get("id"):
        result["runtime_loaded"] = await account_manager.load_account(account["id"])

    return result


@app.post("/api/accounts/login/verify")
async def api_account_login_verify(data: AccountLoginVerify):
    result = await account_login_manager.verify_code(
        login_id=data.login_id,
        code=data.code,
        password=data.password,
    )

    account = result.get("account") if isinstance(result, dict) else None
    if result.get("ok") and account and account.get("id"):
        result["runtime_loaded"] = await account_manager.load_account(account["id"])

    return result


@app.put("/api/accounts/{account_id}")
def edit_account(account_id: int, data: AccountUpdate):
    account = update_account(
        account_id,
        data.dict(),
    )

    if not account:
        return {
            "message": "account not found",
        }

    return account_to_dict(account)


@app.delete("/api/accounts/{account_id}")
def remove_account(account_id: int):
    delete_account(account_id)

    return {
        "message": "ok",
    }


@app.get("/api/clone-tasks")
def api_get_clone_tasks():
    """获取克隆任务列表"""
    tasks = get_all_clone_tasks()

    return [
        clone_task_to_dict(task)
        for task in tasks
    ]


@app.post("/api/clone-tasks")
def api_create_clone_task(data: CloneTaskCreate):
    """创建克隆任务"""
    task_data = normalize_task_channels(data.dict())
    task_data = validate_clone_task_message_range(task_data)

    task = create_clone_task(task_data)

    sync_result = sync_clone_task_to_listener_tasks(task)
    legacy_sync_result = sync_clone_task_to_channel_rules(task)

    reload_handlers()

    result = clone_task_to_dict(task)
    result["listener_sync"] = sync_result
    result["legacy_listener_sync"] = legacy_sync_result

    return result


@app.put("/api/clone-tasks/{task_id}")
def api_update_clone_task(task_id: int, data: CloneTaskUpdate):
    """更新克隆任务"""
    update_data = normalize_task_channels(data.dict(exclude_unset=True))
    update_data = validate_clone_task_update_message_range(task_id, update_data)

    task = update_clone_task(
        task_id,
        update_data,
    )

    if not task:
        return {
            "message": "clone task not found",
        }

    sync_result = sync_clone_task_to_listener_tasks(task)
    legacy_sync_result = sync_clone_task_to_channel_rules(task)

    reload_handlers()

    result = clone_task_to_dict(task)
    result["listener_sync"] = sync_result
    result["legacy_listener_sync"] = legacy_sync_result

    return result


@app.delete("/api/clone-tasks/{task_id}")
def api_delete_clone_task(task_id: int):
    """删除克隆任务"""
    if clone_manager.is_running(task_id):
        return {
            "ok": False,
            "message": "clone task is running, stop it before delete",
        }

    deleted_listener_tasks = delete_listener_tasks_by_clone_task_id(task_id)
    deleted_listener_rules = delete_channel_rules_by_clone_task_id(task_id)

    ok = delete_clone_task(task_id)

    reload_handlers()

    return {
        "ok": ok,
        "message": "ok" if ok else "clone task not found",
        "deleted_listener_tasks": deleted_listener_tasks,
        "deleted_listener_rules": deleted_listener_rules,
    }


@app.post("/api/clone-tasks/{task_id}/start")
async def api_start_clone_task(task_id: int):
    """开始克隆任务"""
    return await clone_manager.start(task_id)


@app.post("/api/clone-tasks/{task_id}/pause")
def api_pause_clone_task(task_id: int):
    """暂停克隆任务"""
    return clone_manager.pause(task_id)


@app.post("/api/clone-tasks/{task_id}/resume")
async def api_resume_clone_task(task_id: int):
    """继续克隆任务"""
    return await clone_manager.resume(task_id)


@app.post("/api/clone-tasks/{task_id}/stop")
async def api_stop_clone_task(task_id: int):
    """停止克隆任务"""
    return await clone_manager.stop(task_id)


@app.post("/api/clone-tasks/{task_id}/reset")
def api_reset_clone_task(task_id: int):
    """重置克隆进度"""
    task = update_clone_task(
        task_id,
        {
            "status": "idle",
            "last_message_id": 0,
        },
    )

    if not task:
        return {
            "ok": False,
            "message": "clone task not found",
        }

    sync_result = sync_clone_task_to_listener_tasks(task)
    legacy_sync_result = sync_clone_task_to_channel_rules(task)

    reload_handlers()

    return {
        "ok": True,
        "message": "clone reset",
        "listener_sync": sync_result,
        "legacy_listener_sync": legacy_sync_result,
    }


@app.get("/api/clone-workers")
def api_clone_workers():
    """查看当前真实运行中的 clone worker"""
    return clone_manager.snapshot()


@app.get("/api/settings/send")
def api_get_send_settings():
    ensure_default_settings()
    return get_send_settings()


@app.put("/api/settings/send")
def api_update_send_settings(data: SendSettingsUpdate):
    return update_send_settings(data.dict(exclude_unset=True))


# =========================
# Bot 分发端管理
# =========================

@app.get("/api/bots")
def api_get_bots():
    """获取 Bot 列表"""
    bots = get_all_bots()

    return [
        bot_to_dict(bot)
        for bot in bots
    ]


@app.post("/api/bots")
async def api_create_bot(data: BotCreate):
    """添加 Bot"""
    bot = create_bot(data.dict())
    bot = await refresh_bot_profile(bot)

    return bot_to_dict(bot)


@app.put("/api/bots/{bot_id}")
async def api_update_bot(bot_id: int, data: BotUpdate):
    """更新 Bot"""
    update_data = data.dict(exclude_unset=True)

    bot = update_bot(bot_id, update_data)

    if not bot:
        return {
            "ok": False,
            "message": "bot not found",
        }

    if "token" in update_data:
        bot = await refresh_bot_profile(bot)

    return bot_to_dict(bot)


@app.delete("/api/bots/{bot_id}")
def api_delete_bot(bot_id: int):
    """删除 Bot"""
    ok = delete_bot(bot_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "bot not found",
    }


# =========================
# 目标频道绑定 Bot
# =========================

@app.get("/api/bot-bindings")
def api_get_bot_bindings():
    """获取目标频道 Bot 绑定列表"""
    bindings = get_all_bindings()

    return [
        bot_binding_to_dict(binding)
        for binding in bindings
    ]


@app.post("/api/bot-bindings")
def api_create_bot_binding(data: BotBindingCreate):
    """创建目标频道 Bot 绑定"""
    binding = create_binding(data.dict())

    return bot_binding_to_dict(binding)


@app.put("/api/bot-bindings/{binding_id}")
def api_update_bot_binding(binding_id: int, data: BotBindingUpdate):
    """更新目标频道 Bot 绑定"""
    update_data = data.dict(exclude_unset=True)

    binding = update_binding(binding_id, update_data)

    if not binding:
        return {
            "ok": False,
            "message": "binding not found",
        }

    return bot_binding_to_dict(binding)


@app.delete("/api/bot-bindings/{binding_id}")
def api_delete_bot_binding(binding_id: int):
    """删除目标频道 Bot 绑定"""
    ok = delete_binding(binding_id)

    return {
        "ok": ok,
        "message": "ok" if ok else "binding not found",
    }

@app.get("/api/bots/{bot_id}/test")
async def api_test_bot(bot_id: int):
    """测试 Bot Token 是否可用"""
    bot = get_bot(bot_id)

    if not bot:
        return {
            "ok": False,
            "message": "bot not found",
        }

    try:
        result = await bot_get_me(bot.token)
        profile = result.get("result") or {}
        username = profile.get("username") or ""
        update_bot(bot.id, {
            "username": username,
            "bot_link": f"https://t.me/{username}" if username else "",
            "last_error": "",
        })

        return {
            "ok": True,
            "message": "bot ok",
            "bot": result.get("result"),
        }

    except Exception as e:
        return {
            "ok": False,
            "message": str(e),
        }
    

@app.post("/api/bots/{bot_id}/send-test")
async def api_bot_send_test(bot_id: int, data: BotSendTestRequest):
    """测试 Bot 是否能发送到目标频道"""
    bot = get_bot(bot_id)

    if not bot:
        return {
            "ok": False,
            "message": "bot not found",
        }

    if not data.chat_id:
        return {
            "ok": False,
            "message": "chat_id required",
        }

    try:
        result = await bot_send_text(
            token=bot.token,
            chat_id=data.chat_id,
            text=data.text or "Bot 测试发送",
        )

        return {
            "ok": True,
            "message": "send ok",
            "result": result.get("result"),
        }

    except Exception as e:
        return {
            "ok": False,
            "message": str(e),
        }
    
@app.get("/api/notify/test")
async def api_notify_test():
    ok = await notify_text("✅ CloneBot 告警频道测试成功")

    return {
        "ok": ok,
        "message": "sent" if ok else "failed",
    }


def validate_clone_task_message_range(data: dict):
    start_url = (data.get("start_message_url") or "").strip()
    end_url = (data.get("end_message_url") or "").strip()

    try:
        start_id = parse_message_url(start_url) if start_url else None
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"start_message_url 解析失败：{e}",
        )

    try:
        end_id = parse_message_url(end_url) if end_url else None
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"end_message_url 解析失败：{e}",
        )

    if start_id and end_id and start_id > end_id:
        raise HTTPException(
            status_code=400,
            detail="开始内容链接的 message_id 不能大于结束内容链接",
        )

    data["start_message_url"] = start_url
    data["end_message_url"] = end_url

    return data


def validate_clone_task_update_message_range(task_id: int, data: dict):
    current = get_clone_task(task_id)

    if not current:
        return validate_clone_task_message_range(data)

    merged = {
        "start_message_url": getattr(current, "start_message_url", "") or "",
        "end_message_url": getattr(current, "end_message_url", "") or "",
    }
    merged.update(data)

    validate_clone_task_message_range(merged)

    if "start_message_url" in data:
        data["start_message_url"] = merged["start_message_url"]

    if "end_message_url" in data:
        data["end_message_url"] = merged["end_message_url"]

    return data
