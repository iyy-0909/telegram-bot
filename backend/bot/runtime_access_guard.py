import asyncio
from datetime import datetime

from auth.runtime_access import evaluate_user_runtime_access
from bot.logger import logger
from db.database import SessionLocal
from db.models import Account, CloneTask, ListenerTask, SupportBot, UserAccount
from utils.redaction import redact_sensitive_text


RUNTIME_ACCESS_CHECK_SECONDS = 5
_guard_task = None


def _runtime_stop_error(decision):
    return decision.message


def enforce_runtime_access_state(*, now=None):
    """Persistently stop every runtime whose owner can no longer use it."""
    current_time = now or datetime.utcnow()
    db = SessionLocal()
    try:
        users = {
            int(user.id): user
            for user in db.query(UserAccount).all()
        }
        stopped_clone_ids = []
        stopped_listener_ids = []
        stopped_support_bot_ids = []
        reasons = {}

        running_clones = (
            db.query(CloneTask)
            .filter(CloneTask.status == "running")
            .all()
        )
        for task in running_clones:
            owner_user_id = getattr(task, "owner_user_id", None)
            user = users.get(int(owner_user_id)) if owner_user_id else None
            decision = evaluate_user_runtime_access(
                user,
                "clone_tasks",
                now=current_time,
            )
            if decision.allowed:
                continue
            task.status = "stopped"
            stopped_clone_ids.append(int(task.id))
            reasons[f"clone:{task.id}"] = decision.reason

        enabled_listeners = (
            db.query(ListenerTask)
            .filter(ListenerTask.enabled == True)
            .all()
        )
        for task in enabled_listeners:
            owner_user_id = getattr(task, "owner_user_id", None)
            user = users.get(int(owner_user_id)) if owner_user_id else None
            decision = evaluate_user_runtime_access(
                user,
                "listener_tasks",
                now=current_time,
            )
            if decision.allowed:
                continue
            task.enabled = False
            task.status = "stopped"
            task.last_error = _runtime_stop_error(decision)
            if hasattr(task, "updated_at"):
                task.updated_at = current_time
            stopped_listener_ids.append(int(task.id))
            reasons[f"listener:{task.id}"] = decision.reason

        polling_support_bots = (
            db.query(SupportBot)
            .filter(SupportBot.polling_enabled == True)
            .all()
        )
        for support_bot in polling_support_bots:
            owner_user_id = getattr(support_bot, "owner_user_id", None)
            user = users.get(int(owner_user_id)) if owner_user_id else None
            decision = evaluate_user_runtime_access(
                user,
                "support",
                now=current_time,
            )
            if decision.allowed:
                continue
            support_bot.polling_enabled = False
            support_bot.last_error = _runtime_stop_error(decision)
            if hasattr(support_bot, "updated_at"):
                support_bot.updated_at = current_time
            stopped_support_bot_ids.append(int(support_bot.id))
            reasons[f"support:{support_bot.id}"] = decision.reason

        if stopped_clone_ids or stopped_listener_ids or stopped_support_bot_ids:
            db.commit()

        return {
            "stopped_clone_task_ids": stopped_clone_ids,
            "stopped_listener_task_ids": stopped_listener_ids,
            "stopped_support_bot_ids": stopped_support_bot_ids,
            "disconnected_account_ids": [],
            "reasons": reasons,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def find_unauthorized_account_clients(account_ids, *, now=None):
    normalized_ids = sorted({int(item) for item in account_ids or []})
    if not normalized_ids:
        return {}

    current_time = now or datetime.utcnow()
    db = SessionLocal()
    try:
        accounts = {
            int(account.id): account
            for account in (
                db.query(Account)
                .filter(Account.id.in_(normalized_ids))
                .all()
            )
        }
        owner_ids = {
            int(account.owner_user_id)
            for account in accounts.values()
            if getattr(account, "owner_user_id", None)
        }
        users = {
            int(user.id): user
            for user in (
                db.query(UserAccount)
                .filter(UserAccount.id.in_(owner_ids))
                .all()
            )
        }
        denied = {}
        for account_id in normalized_ids:
            account = accounts.get(account_id)
            if account is None:
                denied[account_id] = "account_missing"
                continue
            if not account.enabled:
                denied[account_id] = "account_disabled"
                continue
            owner_user_id = getattr(account, "owner_user_id", None)
            user = users.get(int(owner_user_id)) if owner_user_id else None
            decision = evaluate_user_runtime_access(
                user,
                "accounts",
                now=current_time,
            )
            if not decision.allowed:
                denied[account_id] = decision.reason
        return denied
    finally:
        db.close()


async def reconcile_runtime_access_once():
    result = enforce_runtime_access_state()

    from accounts.manager import account_manager

    denied_accounts = find_unauthorized_account_clients(
        list(account_manager.clients.keys())
    )
    for account_id, reason in denied_accounts.items():
        client = account_manager.clients.pop(account_id, None)
        if client:
            await account_manager._disconnect_safely(client)
        result["reasons"][f"account:{account_id}"] = reason
    result["disconnected_account_ids"] = list(denied_accounts.keys())

    if result["stopped_clone_task_ids"]:
        from bot.clone_manager import clone_manager

        for task_id in result["stopped_clone_task_ids"]:
            stop_event = clone_manager.stop_events.get(task_id)
            if stop_event:
                stop_event.set()

    if result["stopped_listener_task_ids"]:
        from bot.handlers import reload_handlers

        reload_handlers()

    if any(
        result[key]
        for key in (
            "stopped_clone_task_ids",
            "stopped_listener_task_ids",
            "stopped_support_bot_ids",
            "disconnected_account_ids",
        )
    ):
        logger.warning(f"runtime access guard stopped unauthorized work | {result}")

    return result


async def runtime_access_guard_worker():
    logger.info("runtime access guard started")
    while True:
        try:
            await reconcile_runtime_access_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            safe_error = redact_sensitive_text(exc)
            logger.exception(f"runtime access guard failed | {safe_error}")
        await asyncio.sleep(RUNTIME_ACCESS_CHECK_SECONDS)


def start_runtime_access_guard():
    global _guard_task
    if _guard_task and not _guard_task.done():
        return _guard_task
    _guard_task = asyncio.create_task(runtime_access_guard_worker())
    return _guard_task
