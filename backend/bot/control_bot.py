import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from bot.bot_sender import BotApiError, request_post
from bot.clone_manager import clone_manager
from bot.control_config import control_config
from bot.handlers import reload_handlers
from bot.logger import logger
from db.crud import get_all_accounts
from db.crud_clone import (
    create_clone_task,
    get_all_clone_tasks,
    get_clone_task,
    update_clone_task,
)
from db.crud_listener import (
    create_listener_task,
    get_all_listener_tasks,
    get_listener_task,
    parse_target_channels,
    update_listener_status,
    update_listener_task,
)
from db.database import SessionLocal
from db.models import ControlCommandLog


_polling_task = None
_offset = None
_webhook_deleted = False
_drafts = {}
_startup_notice_logged = False
_last_error_log_at = 0


def get_text_message(update):
    return update.get("message") or update.get("channel_post") or {}


def update_chat_id(update):
    message = get_text_message(update)
    chat = message.get("chat") or {}
    return str(chat.get("id") or "")


def update_thread_id(update):
    message = get_text_message(update)
    value = message.get("message_thread_id")
    return str(value) if value is not None else ""


def update_user(update):
    message = get_text_message(update)
    return message.get("from") or {}


def update_text(update):
    message = get_text_message(update)
    return (message.get("text") or "").strip()


def command_name(text):
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@")[0].lower()


def command_args(text):
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def audit_log(update, command, status="received", result="", error="", parsed_args=None):
    message = get_text_message(update)
    user = update_user(update)
    db = SessionLocal()

    try:
        item = ControlCommandLog(
            chat_id=update_chat_id(update),
            message_id=message.get("message_id"),
            user_id=str(user.get("id") or ""),
            username=user.get("username") or "",
            command=command or "",
            raw_text=update_text(update),
            parsed_args=json.dumps(parsed_args or {}, ensure_ascii=False),
            status=status,
            result_message=result or "",
            error_message=error or "",
            created_at=datetime.utcnow(),
        )
        db.add(item)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"写入云台命令审计失败 | {e}")
    finally:
        db.close()


async def send_control_text(text, thread_id=""):
    config = control_config()
    data = {
        "chat_id": config["chat_id"],
        "text": text[:3900],
        "disable_web_page_preview": True,
    }
    target_thread_id = thread_id or config.get("command_thread_id") or ""
    if target_thread_id:
        data["message_thread_id"] = target_thread_id
    return await asyncio.to_thread(request_post, config["token"], "sendMessage", data, None)


async def ensure_control_polling_mode():
    global _webhook_deleted
    config = control_config()
    if _webhook_deleted or not config["token"]:
        return
    await asyncio.to_thread(
        request_post,
        config["token"],
        "deleteWebhook",
        {"drop_pending_updates": False},
        None,
    )
    _webhook_deleted = True
    logger.info("云台 Bot 已切换到 polling 模式：deleteWebhook ok")


def is_authorized(update):
    config = control_config()
    message = get_text_message(update)
    user = update_user(update)
    user_id = str(user.get("id") or "")

    if not user_id:
        if message and config.get("allow_channel_commands"):
            return True
        return False

    return user_id in config["admin_ids"]


def is_allowed_chat(update):
    config = control_config()
    if update_chat_id(update) != str(config["chat_id"]):
        return False

    command_thread_id = str(config.get("command_thread_id") or "")
    if command_thread_id and update_thread_id(update) != command_thread_id:
        return False

    return True


def short_targets(value, limit=80):
    targets = parse_target_channels(value)
    text = ",".join(targets)
    return text[:limit] + ("..." if len(text) > limit else "")


def parse_key_values(text):
    result = {}
    for line in text.splitlines()[1:]:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "启用"}


def normalize_targets(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        item.strip()
        for item in str(value or "").replace("，", ",").split(",")
        if item.strip()
    ]


def get_recent_errors(limit=10):
    log_file = Path("logs/clonebot.log")
    if not log_file.exists():
        return []

    lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    errors = [
        line
        for line in lines
        if "ERROR" in line or "WARNING" in line or "异常" in line or "失败" in line
    ]
    return errors[-limit:]


def cleanup_drafts():
    now = datetime.utcnow()
    expired = [
        draft_id
        for draft_id, draft in _drafts.items()
        if draft["expires_at"] < now
    ]
    for draft_id in expired:
        _drafts.pop(draft_id, None)


def make_draft(kind, data, user_id):
    cleanup_drafts()
    draft_id = uuid.uuid4().hex[:8]
    _drafts[draft_id] = {
        "kind": kind,
        "data": data,
        "user_id": str(user_id or ""),
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }
    return draft_id


def validate_listener_payload(data):
    missing = [
        key
        for key in ["name", "account_id", "source", "targets"]
        if not str(data.get(key) or "").strip()
    ]
    if missing:
        return False, f"缺少字段：{', '.join(missing)}"

    account_ids = {account.id for account in get_all_accounts()}
    try:
        account_id = int(data.get("account_id"))
    except (TypeError, ValueError):
        return False, "account_id 必须是数字"

    if account_id not in account_ids:
        return False, f"账号不存在：account_id={account_id}"

    if not normalize_targets(data.get("targets")):
        return False, "targets 不能为空"

    return True, ""


def validate_clone_payload(data):
    missing = [
        key
        for key in ["name", "source", "targets"]
        if not str(data.get(key) or "").strip()
    ]
    if missing:
        return False, f"缺少字段：{', '.join(missing)}"

    if data.get("account_id"):
        account_ids = {account.id for account in get_all_accounts()}
        try:
            account_id = int(data.get("account_id"))
        except (TypeError, ValueError):
            return False, "account_id 必须是数字"
        if account_id not in account_ids:
            return False, f"账号不存在：account_id={account_id}"

    if not normalize_targets(data.get("targets")):
        return False, "targets 不能为空"

    return True, ""


def format_help():
    return "\n".join([
        "云台 Bot 命令：",
        "/help 查看帮助",
        "/whoami 查看当前 Telegram user_id",
        "/status 查看系统状态",
        "/accounts 查看采集账号",
        "/listeners 查看监听任务",
        "/clones 查看克隆任务",
        "/task listener <id> 查看监听任务详情",
        "/task clone <id> 查看克隆任务详情",
        "/recent_errors [数量] 查看最近错误",
        "/pause listener <id> 暂停监听任务",
        "/resume listener <id> 恢复监听任务",
        "/pause clone <id> 暂停克隆任务",
        "/resume clone <id> 恢复克隆任务",
        "/run clone <id> 手动启动克隆任务",
        "/listener_create 多行创建监听任务草稿",
        "/clone_create 多行创建克隆任务草稿",
        "/confirm <draft_id> 确认草稿",
        "/cancel <draft_id> 取消草稿",
    ])


async def handle_status():
    accounts = get_all_accounts()
    listeners = get_all_listener_tasks()
    clones = get_all_clone_tasks()
    errors = get_recent_errors(20)
    snapshot = clone_manager.snapshot()
    return "\n".join([
        "系统状态：运行中",
        f"账号数量：{len(accounts)}",
        f"启用账号：{len([item for item in accounts if item.enabled])}",
        f"监听任务：{len(listeners)}",
        f"克隆任务：{len(clones)}",
        f"克隆运行中：{snapshot.get('total_running')}",
        f"最近错误：{len(errors)}",
        "云台 polling：运行中",
    ])


def handle_accounts():
    accounts = get_all_accounts()
    if not accounts:
        return "暂无采集账号。"
    lines = ["账号列表："]
    for account in accounts[:30]:
        lines.append(
            f"#{account.id} {account.name} @{account.username or '-'} "
            f"enabled={bool(account.enabled)}"
        )
    return "\n".join(lines)


def handle_listeners():
    tasks = get_all_listener_tasks()
    if not tasks:
        return "暂无监听任务。"
    lines = ["监听任务："]
    for task in tasks[:30]:
        lines.append(
            f"#{task.id} {task.name} account={task.account_id} "
            f"source={task.source_channel} targets={short_targets(task.target_channels)} "
            f"enabled={bool(task.enabled)} status={task.status}"
        )
    return "\n".join(lines)


def handle_clones():
    tasks = get_all_clone_tasks()
    if not tasks:
        return "暂无克隆任务。"
    lines = ["克隆任务："]
    for task in tasks[:30]:
        lines.append(
            f"#{task.id} {task.name} source={task.source_channel} "
            f"targets={short_targets(task.target_channels)} bot={getattr(task, 'bot_id', None) or '-'} "
            f"enabled={bool(task.enabled)} status={task.status}"
        )
    return "\n".join(lines)


def handle_task_detail(args):
    parts = args.split()
    if len(parts) < 2:
        return "用法：/task listener <id> 或 /task clone <id>"
    task_type, task_id = parts[0], parts[1]
    try:
        task_id = int(task_id)
    except ValueError:
        return "任务 ID 必须是数字。"

    if task_type == "listener":
        task = get_listener_task(task_id)
        if not task:
            return "监听任务不存在。"
        return "\n".join([
            f"监听任务 #{task.id}",
            f"名称：{task.name}",
            f"账号：{task.account_id}",
            f"Bot：{getattr(task, 'bot_id', None) or '-'}",
            f"源频道：{task.source_channel}",
            f"目标：{short_targets(task.target_channels, 500)}",
            f"启用：{bool(task.enabled)}",
            f"状态：{task.status}",
            f"错误：{task.last_error or '-'}",
        ])

    if task_type == "clone":
        task = get_clone_task(task_id)
        if not task:
            return "克隆任务不存在。"
        return "\n".join([
            f"克隆任务 #{task.id}",
            f"名称：{task.name}",
            f"账号：{task.account_id}",
            f"Bot：{getattr(task, 'bot_id', None) or '-'}",
            f"源频道：{task.source_channel}",
            f"目标：{short_targets(task.target_channels, 500)}",
            f"启用：{bool(task.enabled)}",
            f"状态：{task.status}",
            f"进度：{task.last_message_id}",
        ])

    return "任务类型只能是 listener 或 clone。"


async def handle_pause_resume(action, args):
    parts = args.split()
    if len(parts) < 2:
        return f"用法：/{action} listener <id> 或 /{action} clone <id>"

    task_type, task_id = parts[0], parts[1]
    try:
        task_id = int(task_id)
    except ValueError:
        return "任务 ID 必须是数字。"

    if task_type == "listener":
        task = get_listener_task(task_id)
        if not task:
            return "监听任务不存在。"
        enabled = action == "resume"
        update_listener_status(
            task_id,
            enabled=enabled,
            status="running" if enabled else "stopped",
            last_error="" if enabled else None,
        )
        reload_handlers()
        return f"已{'恢复' if enabled else '暂停'}监听任务：#{task_id} {task.name}"

    if task_type == "clone":
        task = get_clone_task(task_id)
        if not task:
            return "克隆任务不存在。"
        if action == "pause":
            result = clone_manager.pause(task_id)
        else:
            result = await clone_manager.resume(task_id)
        return f"克隆任务操作完成：#{task_id} {task.name}\n{result.get('message')}"

    return "任务类型只能是 listener 或 clone。"


async def handle_run(args):
    parts = args.split()
    if len(parts) < 2:
        return "用法：/run clone <id> 或 /run listener <id>"
    task_type, task_id = parts[0], parts[1]
    try:
        task_id = int(task_id)
    except ValueError:
        return "任务 ID 必须是数字。"

    if task_type == "clone":
        task = get_clone_task(task_id)
        if not task:
            return "克隆任务不存在。"
        result = await clone_manager.start(task_id)
        return f"克隆任务已触发：#{task_id}\n{result.get('message')}"

    if task_type == "listener":
        return "监听任务暂不支持手动触发，请使用补齐按钮或保持监听开启。"

    return "任务类型只能是 listener 或 clone。"


def preview_draft(kind, draft_id, data):
    lines = [
        f"即将创建{'监听' if kind == 'listener' else '克隆'}任务：",
        f"name={data.get('name')}",
        f"account_id={data.get('account_id') or '-'}",
        f"source={data.get('source')}",
        f"targets={data.get('targets')}",
        f"bot_id={data.get('bot_id') or '-'}",
        f"enabled={data.get('enabled', 'false')}",
        "",
        f"请回复：/confirm {draft_id}",
        f"取消：/cancel {draft_id}",
    ]
    return "\n".join(lines)


async def handle_create_draft(kind, text, user_id):
    data = parse_key_values(text)
    validator = validate_listener_payload if kind == "listener" else validate_clone_payload
    ok, error = validator(data)
    if not ok:
        return error

    draft_id = make_draft(kind, data, user_id)
    return preview_draft(kind, draft_id, data)


def handle_cancel(args, user_id):
    draft_id = args.strip()
    draft = _drafts.get(draft_id)
    if not draft:
        return "草稿不存在或已过期。"
    if draft["user_id"] != str(user_id or ""):
        return "只能取消自己创建的草稿。"
    _drafts.pop(draft_id, None)
    return f"已取消草稿：{draft_id}"


def handle_confirm(args, user_id):
    draft_id = args.strip()
    draft = _drafts.get(draft_id)
    if not draft:
        return "草稿不存在或已过期。"
    if draft["user_id"] != str(user_id or ""):
        return "只能确认自己创建的草稿。"

    data = draft["data"]
    targets = normalize_targets(data.get("targets"))
    enabled = parse_bool(data.get("enabled"), False)

    if draft["kind"] == "listener":
        task = create_listener_task({
            "name": data.get("name"),
            "account_id": int(data.get("account_id")),
            "source_channel": data.get("source"),
            "target_channels": targets,
            "enabled": enabled,
            "status": "running" if enabled else "stopped",
            "bot_id": int(data["bot_id"]) if str(data.get("bot_id") or "").isdigit() else None,
        })
        if enabled:
            reload_handlers()
        _drafts.pop(draft_id, None)
        return f"监听任务已创建：#{task.id} {task.name}"

    task = create_clone_task({
        "name": data.get("name"),
        "account_id": int(data.get("account_id") or 1),
        "source_channel": data.get("source"),
        "target_channels": json.dumps(targets, ensure_ascii=False),
        "enabled": enabled,
        "status": "idle",
        "bot_id": int(data["bot_id"]) if str(data.get("bot_id") or "").isdigit() else None,
    })
    _drafts.pop(draft_id, None)
    return f"克隆任务已创建：#{task.id} {task.name}"


def handle_task_set(args):
    parts = args.split(maxsplit=3)
    if len(parts) < 4:
        return "用法：/task_set listener <id> enabled false"
    task_type, task_id, field, value = parts
    try:
        task_id = int(task_id)
    except ValueError:
        return "任务 ID 必须是数字。"

    if field not in {"enabled", "name"}:
        return "第一版只支持直接修改 enabled/name；source/targets/bot_id 后续走确认草稿。"

    if task_type == "listener":
        task = get_listener_task(task_id)
        if not task:
            return "监听任务不存在。"
        payload = {field: parse_bool(value) if field == "enabled" else value}
        update_listener_task(task_id, payload)
        reload_handlers()
        return f"监听任务已更新：#{task_id} {field}={value}"

    if task_type == "clone":
        task = get_clone_task(task_id)
        if not task:
            return "克隆任务不存在。"
        update_clone_task(task_id, {field: parse_bool(value) if field == "enabled" else value})
        return f"克隆任务已更新：#{task_id} {field}={value}"

    return "任务类型只能是 listener 或 clone。"


async def handle_command(update):
    text = update_text(update)
    cmd = command_name(text)
    args = command_args(text)
    user = update_user(update)
    user_id = str(user.get("id") or "")

    if cmd == "/whoami":
        result = f"user_id={user_id or '-'}\nusername={user.get('username') or '-'}"
        audit_log(update, cmd, "success", result)
        return result

    if not is_authorized(update):
        result = "无权限执行此命令"
        audit_log(update, cmd, "unauthorized", result)
        return result

    try:
        if cmd == "/help":
            result = format_help()
        elif cmd == "/status":
            result = await handle_status()
        elif cmd == "/accounts":
            result = handle_accounts()
        elif cmd == "/listeners":
            result = handle_listeners()
        elif cmd == "/clones":
            result = handle_clones()
        elif cmd == "/task":
            result = handle_task_detail(args)
        elif cmd == "/recent_errors":
            try:
                limit = max(1, min(int(args or 10), 50))
            except ValueError:
                limit = 10
            lines = get_recent_errors(limit)
            result = "\n".join(lines) if lines else "最近没有错误日志。"
        elif cmd in {"/pause", "/resume"}:
            result = await handle_pause_resume(cmd.lstrip("/"), args)
        elif cmd == "/run":
            result = await handle_run(args)
        elif cmd == "/listener_create":
            result = await handle_create_draft("listener", text, user_id)
        elif cmd == "/clone_create":
            result = await handle_create_draft("clone", text, user_id)
        elif cmd == "/confirm":
            result = handle_confirm(args, user_id)
        elif cmd == "/cancel":
            result = handle_cancel(args, user_id)
        elif cmd == "/task_set":
            result = handle_task_set(args)
        else:
            result = "未知命令，发送 /help 查看帮助。"

        audit_log(update, cmd, "success", result)
        return result

    except Exception as e:
        error = str(e)
        audit_log(update, cmd, "failed", error=error)
        logger.exception(f"云台命令执行失败 | command={cmd} | {e}")
        return f"命令执行失败：{error}"


async def process_update(update):
    config = control_config()
    text = update_text(update)
    if not text.startswith("/"):
        return

    if not is_allowed_chat(update):
        return

    if not config["commands_enabled"]:
        return

    response = await handle_command(update)
    await send_control_text(response, thread_id=update_thread_id(update))


async def control_polling_worker():
    global _offset
    global _last_error_log_at

    logger.info("Control Bot polling worker started")

    while True:
        config = control_config()
        if not config["enabled"] or not config["token"]:
            await asyncio.sleep(60)
            continue

        if not config["chat_id"]:
            await asyncio.sleep(60)
            continue

        if not config["admin_ids"] and config["commands_enabled"]:
            logger.warning("CONTROL_ADMIN_IDS 未配置，云台命令已禁用。")

        try:
            await ensure_control_polling_mode()
            data = {
                "timeout": config["polling_timeout"],
                "allowed_updates": json.dumps(["message", "channel_post"]),
            }
            if _offset is not None:
                data["offset"] = _offset

            result = await asyncio.to_thread(
                request_post,
                config["token"],
                "getUpdates",
                data,
                None,
            )

            for update in result.get("result") or []:
                _offset = int(update.get("update_id")) + 1
                await process_update(update)

        except Exception as e:
            now = datetime.utcnow().timestamp()
            if now - _last_error_log_at > 60:
                _last_error_log_at = now
                logger.warning(f"Control Bot polling error, retry later | {e}")
            await asyncio.sleep(10)


def start_control_polling():
    global _polling_task
    global _startup_notice_logged

    config = control_config()

    if not config["enabled"]:
        if not _startup_notice_logged:
            _startup_notice_logged = True
            logger.info("云台 Bot 已禁用：CONTROL_BOT_ENABLED=false")
        return None

    if not config["token"]:
        if not _startup_notice_logged:
            _startup_notice_logged = True
            logger.warning("CONTROL_BOT_TOKEN 未配置，云台 Bot 已禁用。")
        return None

    if not config["chat_id"]:
        if not _startup_notice_logged:
            _startup_notice_logged = True
            logger.warning("CONTROL_CHAT_ID 未配置，云台 Bot 命令与告警已禁用。")
        return None

    if _polling_task and not _polling_task.done():
        return _polling_task

    try:
        from db.crud_support import list_support_bots

        for support_bot in list_support_bots():
            support_token = (support_bot.get("bot_token") or "").strip()
            if support_token and support_token == config["token"]:
                logger.warning(
                    "云台 Bot Token 与客服 Bot Token 相同，不推荐共用，"
                    "可能导致 getUpdates polling 冲突。"
                )
                break
    except Exception:
        pass

    _polling_task = asyncio.create_task(control_polling_worker())
    return _polling_task
