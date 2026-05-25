from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.handlers import reload_handlers
from bot.clone_manager import clone_manager

from db.crud_bot import get_bot
from bot.bot_sender import bot_get_me, bot_send_text

from bot.notifier import notify_text
from bot.message_links import parse_message_url
from bot.clone_send_events import get_clone_send_events
from bot.listener_events import get_listener_send_events
from bot.listener_catchup import check_latest_content_consistency

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

from db.crud_bot import (
    get_all_bots,
    create_bot,
    update_bot,
    delete_bot,
    get_all_bindings,
    create_binding,
    update_binding,
    delete_binding,
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
    replace_words: str = "{}"
    footer: str = ""
    remove_contact_lines: bool = True
    use_random_head: bool = False
    use_random_body: bool = False
    use_random_footer: bool = False
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
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
    replace_words: Optional[str] = None
    footer: Optional[str] = None
    remove_contact_lines: Optional[bool] = None
    use_random_head: Optional[bool] = None
    use_random_body: Optional[bool] = None
    use_random_footer: Optional[bool] = None
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
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
    session_path: str
    proxy: str = ""
    remark: str = ""


class AccountUpdate(BaseModel):
    name: str
    session_path: str
    proxy: str = ""
    enabled: bool = True
    remark: str = ""


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
    enable_listener: bool = False

    use_random_head: bool = False
    use_random_body: bool = False
    use_random_footer: bool = False
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
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
    enable_listener: Optional[bool] = None

    use_random_head: Optional[bool] = None
    use_random_body: Optional[bool] = None
    use_random_footer: Optional[bool] = None
    selected_head_template_group_id: Optional[int] = None
    selected_body_template_group_id: Optional[int] = None
    selected_footer_template_group_id: Optional[int] = None
    selected_head_template_id: Optional[int] = None
    selected_body_template_id: Optional[int] = None
    selected_footer_template_id: Optional[int] = None

    enabled: Optional[bool] = None
    status: Optional[str] = None
    last_message_id: Optional[int] = None


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
        "enable_listener": getattr(task, "enable_listener", False),
        "use_random_head": getattr(task, "use_random_head", False),
        "use_random_body": getattr(task, "use_random_body", False),
        "use_random_footer": getattr(task, "use_random_footer", False),
        "selected_head_template_group_id": getattr(task, "selected_head_template_group_id", None),
        "selected_body_template_group_id": getattr(task, "selected_body_template_group_id", None),
        "selected_footer_template_group_id": getattr(task, "selected_footer_template_group_id", None),
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
        "replace_words": task.replace_words,
        "footer": task.footer,
        "remove_contact_lines": task.remove_contact_lines,
        "use_random_head": getattr(task, "use_random_head", False),
        "use_random_body": getattr(task, "use_random_body", False),
        "use_random_footer": getattr(task, "use_random_footer", False),
        "selected_head_template_group_id": getattr(task, "selected_head_template_group_id", None),
        "selected_body_template_group_id": getattr(task, "selected_body_template_group_id", None),
        "selected_footer_template_group_id": getattr(task, "selected_footer_template_group_id", None),
        "selected_head_template_id": getattr(task, "selected_head_template_id", None),
        "selected_body_template_id": getattr(task, "selected_body_template_id", None),
        "selected_footer_template_id": getattr(task, "selected_footer_template_id", None),
        "album_wait_seconds": task.album_wait_seconds,
        "last_error": task.last_error,
        "clone_task_id": getattr(task, "clone_task_id", None),
        "created_at": str(task.created_at) if task.created_at else "",
        "updated_at": str(task.updated_at) if task.updated_at else "",
    }


def account_to_dict(account):
    return {
        "id": account.id,
        "name": account.name,
        "session_path": account.session_path,
        "proxy": account.proxy,
        "enabled": account.enabled,
        "remark": account.remark,
    }

def bot_to_dict(bot):
    return {
        "id": bot.id,
        "name": bot.name,
        "token": bot.token,
        "enabled": bot.enabled,
        "remark": bot.remark,
        "last_error": bot.last_error,
        "created_at": str(bot.created_at) if bot.created_at else "",
        "updated_at": str(bot.updated_at) if bot.updated_at else "",
    }


def bot_binding_to_dict(binding):
    return {
        "id": binding.id,
        "target_channel": binding.target_channel,
        "bot_id": binding.bot_id,
        "enabled": binding.enabled,
        "remark": binding.remark,
        "created_at": str(binding.created_at) if binding.created_at else "",
    }


@app.get("/api/status")
def status():
    listener_tasks = get_all_listener_tasks()

    return {
        "status": "running",
        "rules_count": len(listener_tasks),
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
def api_get_listener_send_events(limit: int = 20):
    return {
        "events": get_listener_send_events(limit),
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
    task = create_listener_task(data.dict())
    reload_handlers()
    return listener_task_to_dict(task)


@app.put("/api/listener-tasks/{task_id}")
def api_update_listener_task(task_id: int, data: ListenerTaskUpdate):
    task = update_listener_task(
        task_id,
        data.dict(exclude_unset=True),
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
def api_start_listener_task(task_id: int):
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

    return await check_latest_content_consistency(task)


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
        session_path=data.session_path,
        proxy=data.proxy,
        remark=data.remark,
    )

    return account_to_dict(account)


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
    task_data = data.dict()
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
    update_data = data.dict(exclude_unset=True)
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
def api_create_bot(data: BotCreate):
    """添加 Bot"""
    bot = create_bot(data.dict())

    return bot_to_dict(bot)


@app.put("/api/bots/{bot_id}")
def api_update_bot(bot_id: int, data: BotUpdate):
    """更新 Bot"""
    update_data = data.dict(exclude_unset=True)

    bot = update_bot(bot_id, update_data)

    if not bot:
        return {
            "ok": False,
            "message": "bot not found",
        }

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
