"""Read and mutate BotFather-only public profile fields safely."""

import asyncio
import io
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any, Mapping

from telethon import functions


BOTFATHER_USERNAME = "@BotFather"
BOTFATHER_FLOW_TIMEOUT = 90
BOTFATHER_STEP_TIMEOUT = 20
BOTFATHER_LOCKS: dict[int, asyncio.Lock] = {}
VERIFY_DELAYS = (0, 0.5, 1, 2, 3)


class BotProfileCapabilityError(RuntimeError):
    """The bot is readable, but no loaded account is allowed to edit it."""


class BotProfileReadError(RuntimeError):
    """Every loaded Telegram account failed while querying this bot."""


class BotFatherFlowError(RuntimeError):
    """BotFather rejected, timed out, or could not verify an operation."""


@dataclass
class OwnedBotContext:
    account_id: int
    client: Any
    entity: Any
    bot_info: Any


@dataclass
class BotContextScan:
    readable: OwnedBotContext
    owner: OwnedBotContext | None
    successful_queries: int


def _clean_username(username: str) -> str:
    return str(username or "").strip().lstrip("@").casefold()


def _button_text(value: Any) -> str:
    text = getattr(value, "text", value)
    return " ".join(str(text or "").strip().casefold().split())


def _buttons(message: Any):
    for row in (getattr(message, "buttons", None) or []):
        for button in (row or []):
            yield button


def _username_mentions(value: Any):
    return {
        match.group(1).casefold()
        for match in re.finditer(
            r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{5,32})(?![A-Za-z0-9_])",
            str(value or ""),
        )
    }


def _find_bot_button(message: Any, username: str):
    """Match an exact username token, never a prefix/sub-string."""
    target = _clean_username(username)
    for button in _buttons(message):
        text = str(getattr(button, "text", "") or "").strip()
        if target in _username_mentions(text):
            return button
        if text.startswith("@") and _clean_username(text) == target:
            return button
    return None


def _message_targets_username(message: Any, username: str) -> bool:
    target = _clean_username(username)
    text = str(
        getattr(message, "raw_text", None)
        or getattr(message, "text", None)
        or ""
    )
    return target in _username_mentions(text)


def _find_button(message: Any, aliases):
    normalized_aliases = [_button_text(alias) for alias in aliases]
    for button in _buttons(message):
        text = _button_text(button)
        compact = re.sub(r"[^\w@]+", " ", text, flags=re.UNICODE).strip()
        if any(
            alias == text or alias in text or alias in compact
            for alias in normalized_aliases
        ):
            return button
    return None


def _message_signature(message: Any):
    return (
        getattr(message, "id", None),
        str(
            getattr(message, "raw_text", None)
            or getattr(message, "text", None)
            or ""
        ),
        tuple(str(getattr(button, "text", "") or "") for button in _buttons(message)),
    )


async def _query_context(account_id: int, client: Any, username: str):
    if hasattr(client, "is_connected") and not client.is_connected():
        await asyncio.wait_for(client.connect(), timeout=BOTFATHER_STEP_TIMEOUT)

    entity = await asyncio.wait_for(
        client.get_entity(f"@{_clean_username(username)}"),
        timeout=BOTFATHER_STEP_TIMEOUT,
    )
    result = await asyncio.wait_for(
        client(functions.users.GetFullUserRequest(id=entity)),
        timeout=BOTFATHER_STEP_TIMEOUT,
    )
    full_user = getattr(result, "full_user", None)
    return OwnedBotContext(
        account_id=int(account_id),
        client=client,
        entity=entity,
        bot_info=getattr(full_user, "bot_info", None),
    )


async def _scan_bot_contexts(
    clients: Mapping[int, Any],
    username: str,
) -> BotContextScan:
    normalized = _clean_username(username)
    if not normalized:
        raise BotProfileCapabilityError("Telegram 未返回 Bot username")
    if not clients:
        raise BotProfileCapabilityError("系统当前没有已加载的 Telegram 用户账号")

    readable = None
    successful = 0
    failed_account_ids = []
    for account_id, client in sorted(clients.items(), key=lambda item: item[0]):
        try:
            context = await _query_context(account_id, client, normalized)
            successful += 1
            if readable is None:
                readable = context
            if bool(getattr(context.entity, "bot_can_edit", False)):
                return BotContextScan(
                    readable=context,
                    owner=context,
                    successful_queries=successful,
                )
        except Exception:
            failed_account_ids.append(str(account_id))

    if readable is not None:
        return BotContextScan(
            readable=readable,
            owner=None,
            successful_queries=successful,
        )

    suffix = ",".join(failed_account_ids[:10])
    raise BotProfileReadError(
        "所有已加载账号均无法读取该 Bot 信息"
        + (f"；失败账号 ID：{suffix}" if suffix else "")
    )


async def _with_deadline(coroutine, action: str):
    try:
        return await asyncio.wait_for(
            coroutine,
            timeout=BOTFATHER_FLOW_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        raise BotFatherFlowError(
            f"{action}超过 {BOTFATHER_FLOW_TIMEOUT} 秒，操作已取消"
        ) from exc


async def find_owned_bot(clients: Mapping[int, Any], username: str):
    scan = await _with_deadline(
        _scan_bot_contexts(clients, username),
        "检查 Bot 所有者",
    )
    if scan.owner is None:
        raise BotProfileCapabilityError(
            "已成功读取 Bot，但已加载账号均不是该 Bot 的所有者"
        )
    return scan.owner


def _media_identity(info: Any):
    if not info:
        return None
    photo = getattr(info, "description_photo", None)
    document = getattr(info, "description_document", None)
    media = photo or document
    if not media:
        return None
    return (
        "photo" if photo else "video",
        str(getattr(media, "id", "") or ""),
        str(getattr(media, "access_hash", "") or ""),
    )


def _profile_fields(context: OwnedBotContext, *, owner_available: bool):
    info = context.bot_info
    photo = getattr(info, "description_photo", None) if info else None
    document = getattr(info, "description_document", None) if info else None
    media_type = "photo" if photo else "video" if document else ""
    return {
        "has_description_photo": bool(photo),
        "has_description_document": bool(document),
        "has_description_media": bool(photo or document),
        "description_media_type": media_type,
        "privacy_policy_url": str(getattr(info, "privacy_policy_url", "") or ""),
        "owner_available": bool(owner_available),
        "owner_account_id": context.account_id if owner_available else None,
    }


async def get_botfather_profile_fields(clients: Mapping[int, Any], username: str):
    """Read BotInfo through any loaded account; owner status only gates writes."""
    scan = await _with_deadline(
        _scan_bot_contexts(clients, username),
        "读取 Bot 扩展资料",
    )
    context = scan.owner or scan.readable
    return _profile_fields(context, owner_available=scan.owner is not None)


async def _refresh_context(context: OwnedBotContext):
    result = await asyncio.wait_for(
        context.client(functions.users.GetFullUserRequest(id=context.entity)),
        timeout=BOTFATHER_STEP_TIMEOUT,
    )
    full_user = getattr(result, "full_user", None)
    return replace(context, bot_info=getattr(full_user, "bot_info", None))


async def _verify_with_retry(context, predicate, error_message):
    latest = context
    for delay in VERIFY_DELAYS:
        if delay:
            await asyncio.sleep(delay)
        latest = await _refresh_context(latest)
        if predicate(latest):
            return _profile_fields(latest, owner_available=True)
    raise BotFatherFlowError(error_message)


def _media_content_type(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


async def _download_description_photo(clients, username):
    scan = await _scan_bot_contexts(clients, username)
    context = scan.owner or scan.readable
    photo = getattr(context.bot_info, "description_photo", None) if context.bot_info else None
    if not photo:
        return None
    content = await asyncio.wait_for(
        context.client.download_media(photo, file=bytes),
        timeout=BOTFATHER_STEP_TIMEOUT,
    )
    if not content:
        return None
    content = bytes(content)
    return {
        "content": content,
        "content_type": _media_content_type(content),
    }


async def download_description_photo(clients: Mapping[int, Any], username: str):
    return await _with_deadline(
        _download_description_photo(clients, username),
        "下载 Bot 描述图片",
    )


async def _latest_message(client):
    messages = await client.get_messages(BOTFATHER_USERNAME, limit=1)
    try:
        return messages[0] if messages else None
    except Exception:
        return messages


async def _click_and_wait(client, message, button):
    before = _message_signature(message)
    result = await button.click()
    if result is not None and (
        hasattr(result, "buttons")
        or hasattr(result, "raw_text")
        or hasattr(result, "text")
    ):
        return result

    deadline = asyncio.get_running_loop().time() + BOTFATHER_STEP_TIMEOUT
    while asyncio.get_running_loop().time() < deadline:
        latest = await asyncio.wait_for(
            _latest_message(client),
            timeout=BOTFATHER_STEP_TIMEOUT,
        )
        if latest is not None and _message_signature(latest) != before:
            return latest
        await asyncio.sleep(0.25)
    raise BotFatherFlowError("BotFather 菜单点击后未响应")


EDIT_BOT_ALIASES = (
    "edit bot",
    "edit bot info",
    "编辑机器人",
    "编辑 bot",
)
DESCRIPTION_PICTURE_ALIASES = (
    "edit description picture",
    "edit description photo",
    "description picture",
    "description photo",
    "编辑描述图片",
    "描述图片",
)
PRIVACY_POLICY_ALIASES = (
    "edit privacy policy",
    "privacy policy",
    "隐私政策",
    "编辑隐私政策",
)
REMOVE_ALIASES = (
    "remove current",
    "remove picture",
    "delete picture",
    "clear picture",
    "remove description",
    "delete description",
    "移除",
    "删除",
    "清除",
)


@asynccontextmanager
async def _open_edit_feature(context: OwnedBotContext, aliases):
    client = context.client
    username = _clean_username(getattr(context.entity, "username", ""))
    if not username:
        raise BotFatherFlowError("无法确认 Bot username，已停止操作")

    async with client.conversation(
        BOTFATHER_USERNAME,
        timeout=BOTFATHER_STEP_TIMEOUT,
        exclusive=True,
    ) as conversation:
        sent = await conversation.send_message("/mybots")
        message = await conversation.get_response(sent, timeout=BOTFATHER_STEP_TIMEOUT)
        bot_button = _find_bot_button(message, username)
        if not bot_button:
            raise BotFatherFlowError("BotFather /mybots 中未找到目标 Bot")

        message = await _click_and_wait(client, message, bot_button)
        if not _message_targets_username(message, username):
            raise BotFatherFlowError("BotFather 返回的菜单未能确认目标 Bot，已停止操作")

        feature_button = _find_button(message, aliases)
        if not feature_button:
            edit_button = _find_button(message, EDIT_BOT_ALIASES)
            if not edit_button:
                raise BotFatherFlowError("BotFather 未显示 Edit Bot 菜单")
            message = await _click_and_wait(client, message, edit_button)
            feature_button = _find_button(message, aliases)

        if not feature_button:
            raise BotFatherFlowError("当前 BotFather 菜单不支持该配置项")

        prompt = await _click_and_wait(client, message, feature_button)
        yield conversation, prompt


def _response_text(message: Any) -> str:
    return str(
        getattr(message, "raw_text", None)
        or getattr(message, "text", None)
        or ""
    ).strip()


def _raise_for_rejection(message: Any, action_name: str):
    """Text is diagnostic only; successful state is always verified separately."""
    text = _response_text(message)
    normalized = text.casefold()
    rejection_markers = (
        "sorry",
        "error",
        "invalid",
        "wrong",
        "failed",
        "can't",
        "cannot",
        "not allowed",
        "please send",
        "please upload",
        "too many",
        "flood",
        "try again",
        "try later",
        "wait before",
        "temporarily unavailable",
        "错误",
        "无效",
        "失败",
        "不允许",
        "请发送",
        "请上传",
        "请求过多",
        "稍后再试",
    )
    if any(marker in normalized for marker in rejection_markers):
        raise BotFatherFlowError(f"BotFather 拒绝{action_name}：{text[:300]}")
    return text


async def _set_description_picture_flow(context, jpeg_content: bytes | None):
    async with _open_edit_feature(
        context,
        DESCRIPTION_PICTURE_ALIASES,
    ) as (conversation, prompt):
        if jpeg_content is None:
            remove_button = _find_button(prompt, REMOVE_ALIASES)
            if remove_button:
                response = await _click_and_wait(context.client, prompt, remove_button)
            else:
                sent = await conversation.send_message("/empty")
                response = await conversation.get_response(
                    sent,
                    timeout=BOTFATHER_STEP_TIMEOUT,
                )
        else:
            upload = io.BytesIO(jpeg_content)
            upload.name = "description.jpg"
            sent = await conversation.send_file(upload, force_document=False)
            response = await conversation.get_response(
                sent,
                timeout=BOTFATHER_STEP_TIMEOUT,
            )
        return _raise_for_rejection(response, "描述图片更新")


async def _mutate_description_picture(clients, username, jpeg_content):
    scan = await _scan_bot_contexts(clients, username)
    if scan.owner is None:
        raise BotProfileCapabilityError(
            "已成功读取 Bot，但已加载账号均不是该 Bot 的所有者"
        )
    context = scan.owner
    lock = BOTFATHER_LOCKS.setdefault(context.account_id, asyncio.Lock())
    async with lock:
        context = await _refresh_context(context)
        before_identity = _media_identity(context.bot_info)
        await _set_description_picture_flow(context, jpeg_content)

        if jpeg_content is None:
            return await _verify_with_retry(
                context,
                lambda current: _media_identity(current.bot_info) is None,
                "BotFather 已响应，但回查时描述图片或视频仍然存在",
            )

        return await _verify_with_retry(
            context,
            lambda current: (
                _media_identity(current.bot_info) is not None
                and _media_identity(current.bot_info)[0] == "photo"
                and _media_identity(current.bot_info) != before_identity
            ),
            "BotFather 已响应，但未回查到新的描述图片",
        )


async def set_description_picture(
    clients: Mapping[int, Any],
    username: str,
    jpeg_content: bytes | None,
):
    return await _with_deadline(
        _mutate_description_picture(clients, username, jpeg_content),
        "BotFather 描述图片操作",
    )


async def _set_privacy_policy_flow(context, url: str):
    async with _open_edit_feature(
        context,
        PRIVACY_POLICY_ALIASES,
    ) as (conversation, _prompt):
        sent = await conversation.send_message(url or "/empty")
        response = await conversation.get_response(sent, timeout=BOTFATHER_STEP_TIMEOUT)
        return _raise_for_rejection(response, "隐私政策更新")


async def _mutate_privacy_policy(clients, username, url):
    scan = await _scan_bot_contexts(clients, username)
    if scan.owner is None:
        raise BotProfileCapabilityError(
            "已成功读取 Bot，但已加载账号均不是该 Bot 的所有者"
        )
    context = scan.owner
    lock = BOTFATHER_LOCKS.setdefault(context.account_id, asyncio.Lock())
    async with lock:
        context = await _refresh_context(context)
        await _set_privacy_policy_flow(context, url)
        return await _verify_with_retry(
            context,
            lambda current: str(
                getattr(current.bot_info, "privacy_policy_url", "") or ""
            ) == url,
            "BotFather 已响应，但隐私政策回查结果不一致",
        )


async def set_privacy_policy(clients: Mapping[int, Any], username: str, url: str):
    normalized = str(url or "").strip()
    return await _with_deadline(
        _mutate_privacy_policy(clients, username, normalized),
        "BotFather 隐私政策操作",
    )
