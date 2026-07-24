from datetime import datetime

from telethon.errors import ChatAdminRequiredError, UserAlreadyParticipantError
from telethon.tl.functions.channels import EditAdminRequest, InviteToChannelRequest
from telethon.tl.types import ChatAdminRights

from accounts.manager import account_manager
from bot.logger import logger
from db.crud_search_bots import (
    get_search_bot,
    get_submission,
    update_submission_runtime,
)


ADMIN_RIGHT_FIELDS = (
    "change_info",
    "post_messages",
    "edit_messages",
    "delete_messages",
    "ban_users",
    "invite_users",
    "pin_messages",
    "add_admins",
    "anonymous",
    "manage_call",
    "manage_topics",
    "post_stories",
    "edit_stories",
    "delete_stories",
    "manage_direct_messages",
    "manage_ranks",
)

_BROADCAST_UNSUPPORTED = {"ban_users", "pin_messages", "manage_topics"}
_GROUP_UNSUPPORTED = {
    "post_messages",
    "edit_messages",
    "post_stories",
    "edit_stories",
    "delete_stories",
    "manage_direct_messages",
}


class PermissionApplicationError(Exception):
    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage


def normalize_admin_rights(value):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("机器人管理员权限配置格式无效")

    unknown = sorted(set(value) - set(ADMIN_RIGHT_FIELDS))
    if unknown:
        raise ValueError(f"包含不支持的机器人管理员权限：{', '.join(unknown)}")

    invalid_values = sorted(
        key for key, enabled in value.items()
        if not isinstance(enabled, bool)
    )
    if invalid_values:
        raise ValueError(f"机器人管理员权限必须为布尔值：{', '.join(invalid_values)}")

    return {
        field: bool(value.get(field, False))
        for field in ADMIN_RIGHT_FIELDS
    }


def _channel_reference(submission):
    username = str(submission.get("channel_username") or "").strip()
    if username:
        return username

    chat_id = str(submission.get("channel_chat_id") or "").strip()
    if chat_id.lstrip("-").isdigit():
        return int(chat_id)
    return chat_id


def _channel_kind(channel):
    if getattr(channel, "broadcast", False):
        return "broadcast"
    if getattr(channel, "megagroup", False):
        return "forum" if getattr(channel, "forum", False) else "megagroup"
    return "unknown"


def _applicable_admin_rights(channel, requested):
    kind = _channel_kind(channel)
    unsupported = (
        _BROADCAST_UNSUPPORTED
        if kind == "broadcast"
        else _GROUP_UNSUPPORTED
        if kind in {"megagroup", "forum"}
        else set()
    )
    applied = {
        key: enabled and key not in unsupported
        for key, enabled in normalize_admin_rights(requested).items()
    }
    ignored = [
        key for key, enabled in normalize_admin_rights(requested).items()
        if enabled and key in unsupported
    ]
    return kind, applied, ignored


def _build_admin_rights(value):
    return ChatAdminRights(other=True, **normalize_admin_rights(value))


def _read_actual_admin_rights(permissions):
    participant = getattr(permissions, "participant", None)
    raw_rights = getattr(participant, "admin_rights", None)
    result = {}
    for field in ADMIN_RIGHT_FIELDS:
        value = getattr(raw_rights, field, None)
        if value is None:
            value = getattr(permissions, field, False)
        result[field] = bool(value)
    return normalize_admin_rights(result)


async def add_search_bot_as_channel_admin(
    client,
    channel_reference,
    bot_username,
    admin_rights=None,
):
    if not channel_reference:
        raise PermissionApplicationError(
            "locate_channel",
            "频道缺少 username 或 chat_id，无法由 Telegram 用户号定位",
        )

    try:
        channel = await client.get_entity(channel_reference)
        bot_entity = await client.get_entity(bot_username)
    except Exception as exc:
        raise PermissionApplicationError(
            "locate_target",
            f"无法定位频道或搜索机器人：{_readable_error(exc)}",
        ) from exc

    if not getattr(bot_entity, "bot", False):
        raise PermissionApplicationError("validate_bot", "配置的 Telegram 用户不是机器人")

    channel_kind, applicable_rights, ignored_rights = _applicable_admin_rights(
        channel,
        admin_rights,
    )
    already_member = False
    try:
        await client(InviteToChannelRequest(channel=channel, users=[bot_entity]))
    except UserAlreadyParticipantError:
        already_member = True
    except Exception as exc:
        raise PermissionApplicationError(
            "invite_bot",
            f"把搜索机器人加入频道失败：{_readable_error(exc)}",
        ) from exc

    already_admin = False
    try:
        permissions = await client.get_permissions(channel, bot_entity)
        already_admin = bool(
            getattr(permissions, "is_admin", False)
            or getattr(permissions, "is_creator", False)
        )
    except Exception:
        pass

    try:
        await client(EditAdminRequest(
            channel=channel,
            user_id=bot_entity,
            admin_rights=_build_admin_rights(applicable_rights),
            rank="搜索机器人",
        ))
    except Exception as exc:
        state = "机器人已在频道内" if already_member else "机器人已加入频道"
        raise PermissionApplicationError(
            "apply_permissions",
            f"{state}，但设置管理员权限失败：{_readable_error(exc)}",
        ) from exc

    try:
        permissions = await client.get_permissions(channel, bot_entity)
        actual_rights = _read_actual_admin_rights(permissions)
    except Exception as exc:
        raise PermissionApplicationError(
            "verify_permissions",
            f"管理员权限已提交，但回查 Telegram 实际权限失败：{_readable_error(exc)}",
        ) from exc

    mismatched = [
        key for key in ADMIN_RIGHT_FIELDS
        if actual_rights.get(key, False) != applicable_rights.get(key, False)
    ]
    return {
        "ok": not mismatched,
        "target_channel": str(channel_reference),
        "bot_username": bot_username,
        "already_member": already_member,
        "already_admin": already_admin,
        "channel_kind": channel_kind,
        "requested_rights": normalize_admin_rights(admin_rights),
        "applicable_rights": applicable_rights,
        "actual_rights": actual_rights,
        "ignored_rights": ignored_rights,
        "mismatched_rights": mismatched,
    }


def _readable_error(exc):
    if isinstance(exc, ChatAdminRequiredError):
        return "操作账号不是频道管理员，或没有添加成员、添加管理员权限"
    return str(exc) or exc.__class__.__name__


async def apply_submission_permissions(
    submission,
    admin_rights,
    account_id=None,
    update_submit_status=False,
):
    submission_id = submission["id"]
    requested = normalize_admin_rights(admin_rights)
    bot = get_search_bot(submission["search_bot_id"])
    base_fields = {
        "admin_rights_json": requested,
        "permission_status": "applying",
        "permission_last_error": "",
    }
    if account_id:
        base_fields["account_id"] = account_id
    if update_submit_status:
        base_fields.update({"submit_status": "submitting", "last_error": ""})
    update_submission_runtime(submission_id, **base_fields)

    if not bot:
        return _permission_failure(
            submission_id,
            "搜索机器人不存在",
            update_submit_status,
        )

    operation_account_id = account_id or submission.get("account_id") or bot.account_id
    client = account_manager.get_client(operation_account_id) if operation_account_id else None
    if not client:
        return _permission_failure(
            submission_id,
            "操作账号未加载或已失效",
            update_submit_status,
        )

    channel_reference = _channel_reference(submission)
    try:
        result = await add_search_bot_as_channel_admin(
            client,
            channel_reference,
            bot.username,
            admin_rights=requested,
        )
        if result["mismatched_rights"]:
            names = "、".join(result["mismatched_rights"])
            error = f"Telegram 实际权限与申请权限不一致：{names}"
            fields = {
                "applied_admin_rights_json": result["actual_rights"],
                "permission_status": "mismatch",
                "permission_last_error": error,
                "permissions_applied_at": datetime.utcnow(),
            }
            if update_submit_status:
                fields.update({"submit_status": "failed", "last_error": error})
            return update_submission_runtime(submission_id, **fields)

        fields = {
            "applied_admin_rights_json": result["actual_rights"],
            "permission_status": "applied",
            "permission_last_error": "",
            "permissions_applied_at": datetime.utcnow(),
        }
        if update_submit_status:
            fields.update({
                "submit_status": "success",
                "review_status": "pending",
                "block_status": "normal",
                "telegram_message_id": None,
                "submitted_at": datetime.utcnow(),
                "last_error": "",
            })
        item = update_submission_runtime(submission_id, **fields)
        logger.info(
            "搜索机器人频道权限已应用并回查 | "
            f"submission_id={submission_id} | bot={bot.username} | "
            f"channel={channel_reference} | kind={result['channel_kind']} | "
            f"ignored={result['ignored_rights']} | "
            f"admin_rights={[key for key, enabled in result['actual_rights'].items() if enabled]}"
        )
        return item
    except Exception as exc:
        error = (
            str(exc)
            if isinstance(exc, PermissionApplicationError)
            else _readable_error(exc)
        ) or "应用机器人频道权限失败"
        item = _permission_failure(
            submission_id,
            error,
            update_submit_status,
        )
        logger.warning(
            "搜索机器人频道权限应用失败 | "
            f"submission_id={submission_id} | bot={bot.username} | "
            f"channel={channel_reference} | error={error}"
        )
        return item


def _permission_failure(submission_id, error, update_submit_status):
    fields = {
        "permission_status": "failed",
        "permission_last_error": error,
    }
    if update_submit_status:
        fields.update({"submit_status": "failed", "last_error": error})
    return update_submission_runtime(submission_id, **fields)


async def run_search_bot_submission(submission):
    return await apply_submission_permissions(
        submission,
        submission.get("admin_rights"),
        update_submit_status=True,
    )


async def update_search_bot_submission_permissions(
    submission_id,
    admin_rights,
    account_id=None,
):
    submission = get_submission(submission_id)
    if not submission:
        return None
    return await apply_submission_permissions(
        submission,
        admin_rights,
        account_id=account_id,
        update_submit_status=False,
    )
