from db.crud_bot import (
    get_bot,
    get_bot_for_target,
    normalize_target_channel,
    update_bot_error,
)
from bot.bot_sender import bot_send_prepared
from bot.logger import logger
from bot.message_links import build_message_urls, extract_message_ids
from bot.notifier import notify_error


def is_network_error(error: str) -> bool:
    lowered = (error or "").lower()
    return (
        "bot api 网络异常" in lowered
        or "ssl 连接被中断" in lowered
        or "sslerror" in lowered
        or "connectionerror" in lowered
        or "proxyerror" in lowered
        or "timeout" in lowered
        or "网络连接失败" in lowered
        or "请求超时" in lowered
    )


def is_permission_error(error: str) -> bool:
    lowered = (error or "").lower()
    return (
        "403" in lowered
        or "forbidden" in lowered
        or "bot is not a member of the channel chat" in lowered
        or "not enough rights" in lowered
    )


def build_error_detail(
    bot,
    raw_target_channel,
    target_channel,
    error,
    error_type,
):
    return (
        f"Bot ID：{bot.id}\n"
        f"Bot 名称：{bot.name}\n"
        f"原始目标频道：{raw_target_channel}\n"
        f"目标频道：{target_channel}\n"
        f"错误类型：{error_type}\n"
        f"错误信息：{error}"
    )


async def send_prepared_by_bot(target_channel: str, prepared: dict, bot_id=None):
    """
    官方 Bot API 分发入口。

    单个目标发送失败时返回 False，不向上抛出，避免整组任务中断。
    """
    raw_target_channel = target_channel
    target_channel = normalize_target_channel(target_channel)
    bot = None

    if bot_id:
        bot = get_bot(int(bot_id))

        if bot and not bot.enabled:
            message = (
                "Bot 分发失败：任务指定的 Bot 未启用 | "
                f"bot_id={bot_id} | bot_name={bot.name} | "
                f"raw_target={raw_target_channel} | target={target_channel}"
            )
            logger.error(message)
            await notify_error(
                title="Bot 分发失败",
                detail=message,
                target=target_channel,
            )
            prepared["_last_error"] = message
            prepared["_last_error_target"] = target_channel
            return False

        if not bot:
            message = (
                "Bot 分发失败：任务指定的 Bot 不存在 | "
                f"bot_id={bot_id} | raw_target={raw_target_channel} | "
                f"target={target_channel}"
            )
            logger.error(message)
            await notify_error(
                title="Bot 分发失败",
                detail=message,
                target=target_channel,
            )
            prepared["_last_error"] = message
            prepared["_last_error_target"] = target_channel
            return False
    else:
        bot = get_bot_for_target(target_channel)

    if not bot:
        message = (
            "Bot 分发失败：没有可用 Bot | "
            f"raw_target={raw_target_channel} | target={target_channel}"
        )
        logger.error(message)
        await notify_error(
            title="Bot 分发失败",
            detail=message,
            target=target_channel,
        )
        prepared["_last_error"] = message
        prepared["_last_error_target"] = target_channel
        return False

    try:
        logger.info(
            f"Bot 分发开始 | bot_id={bot.id} | bot_name={bot.name} | "
            f"raw_target={raw_target_channel} | target={target_channel}"
        )

        result = await bot_send_prepared(
            token=bot.token,
            chat_id=target_channel,
            prepared=prepared,
        )

        message_ids = extract_message_ids(result)
        target_message_urls = build_message_urls(target_channel, message_ids)
        update_bot_error(bot.id, "")
        prepared.pop("_last_error", None)
        prepared.pop("_last_error_target", None)

        logger.info(
            f"Bot 分发成功 | bot_id={bot.id} | raw_target={raw_target_channel} | "
            f"target={target_channel} | target_message_ids={message_ids} | "
            f"target_message_url={(target_message_urls[0] if target_message_urls else '')} | "
            f"target_message_urls={target_message_urls}"
        )

        return {
            "ok": True,
            "bot_id": bot.id,
            "bot_name": bot.name,
            "target_channel": target_channel,
            "target_message_ids": message_ids,
            "target_message_url": (
                target_message_urls[0] if target_message_urls else None
            ),
            "target_message_urls": target_message_urls,
            "raw_result": result,
        }

    except Exception as e:
        error = str(e)
        network_error = is_network_error(error)
        permission_error = is_permission_error(error)
        error_type = (
            "网络异常"
            if network_error
            else "权限错误"
            if permission_error
            else "发送异常"
        )

        prepared["_last_error"] = error
        prepared["_last_error_target"] = target_channel
        update_bot_error(bot.id, error)

        if permission_error:
            logger.error(
                f"Bot 分发权限失败 | bot_id={bot.id} | bot_name={bot.name} | "
                f"raw_target={raw_target_channel} | target={target_channel} | "
                f"error={error}"
            )
        elif network_error:
            logger.warning(
                f"Bot API 网络异常，发送失败但任务继续 | bot_id={bot.id} | "
                f"bot_name={bot.name} | raw_target={raw_target_channel} | "
                f"target={target_channel} | error={error}"
            )
        else:
            logger.exception(
                f"Bot 分发异常 | bot_id={bot.id} | bot_name={bot.name} | "
                f"raw_target={raw_target_channel} | target={target_channel} | "
                f"{error}"
            )

        await notify_error(
            title="Bot 分发失败",
            detail=build_error_detail(
                bot=bot,
                raw_target_channel=raw_target_channel,
                target_channel=target_channel,
                error=error,
                error_type=error_type,
            ),
            target=target_channel,
        )

        return False
