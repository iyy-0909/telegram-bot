import asyncio
import json
import mimetypes
import os
import re
from pathlib import Path

import requests
from requests import exceptions as request_exceptions

from db.crud_bot import normalize_target_channel
from bot.logger import logger
from utils.proxy_utils import is_production
from utils.proxy_utils import normalize_bot_api_proxy_for_runtime


BOT_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT = 180
DEFAULT_BOT_API_PROXY = "http://127.0.0.1:7897"


def get_bot_api_proxy():
    proxy = (
        os.getenv("BOT_API_PROXY")
        or os.getenv("TELEGRAM_PROXY")
    )

    if not proxy and not is_production():
        proxy = DEFAULT_BOT_API_PROXY

    return normalize_bot_api_proxy_for_runtime(proxy)


def get_bot_api_proxies():
    proxy = get_bot_api_proxy()

    if not proxy:
        return {}

    return {
        "http": proxy,
        "https": proxy,
    }


class BotApiError(Exception):
    pass


class BotApiNetworkError(BotApiError):
    pass


def redact_bot_token(text: str) -> str:
    return re.sub(r"/bot[^/\s]+", "/bot<hidden>", text or "")


def is_parse_mode_error(error: Exception) -> bool:
    message = str(error).lower()

    return (
        "can't parse entities" in message
        or "can't parse message text" in message
        or "can't parse message caption" in message
        or "parse entities" in message
        or ("offset" in message and "entity" in message)
        or "entities are not valid" in message
        or "entity" in message and "invalid" in message
    )


def build_url(token: str, method: str) -> str:
    token = (token or "").strip()
    return f"{BOT_API_BASE}/bot{token}/{method}"


def normalize_chat_id(chat_id: str) -> str:
    return normalize_target_channel(chat_id)


def encode_entities(entities):
    if not entities:
        return None

    return json.dumps(entities, ensure_ascii=False)


def describe_request_error(error: Exception, method: str) -> str:
    proxies = get_bot_api_proxies()
    proxy = proxies.get("https") or proxies.get("http") or "未配置"
    error_name = type(error).__name__
    raw_error = redact_bot_token(str(error))

    if isinstance(error, request_exceptions.SSLError):
        reason = "SSL 连接被中断，通常是本机代理或网络节点不稳定"
    elif isinstance(error, request_exceptions.ProxyError):
        reason = "代理连接失败，请检查本机代理端口和代理软件状态"
    elif isinstance(error, request_exceptions.Timeout):
        reason = "请求超时，Telegram Bot API 未在限定时间内响应"
    elif isinstance(error, request_exceptions.ConnectionError):
        reason = "网络连接失败，可能是代理断流或网络不可达"
    else:
        reason = "Bot API 网络请求失败"

    return (
        f"Bot API 网络异常：{reason}；"
        f"请求方法={method}；代理={proxy}；异常类型={error_name}；"
        f"原始错误={raw_error[:500]}"
    )


def request_post(token: str, method: str, data=None, files=None):
    url = build_url(token, method)
    session = requests.Session()
    session.trust_env = False
    proxies = get_bot_api_proxies()

    try:
        response = session.post(
            url,
            data=data or {},
            files=files,
            timeout=REQUEST_TIMEOUT,
            proxies=proxies,
        )
    except request_exceptions.RequestException as e:
        raise BotApiNetworkError(describe_request_error(e, method)) from e

    try:
        result = response.json()
    except Exception:
        raise BotApiError(f"Bot API returned non-JSON response: {response.text}")

    if not result.get("ok"):
        raise BotApiError(str(result))

    return result


def request_get(token: str, method: str):
    url = build_url(token, method)
    session = requests.Session()
    session.trust_env = False
    proxies = get_bot_api_proxies()

    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            proxies=proxies,
        )
    except request_exceptions.RequestException as e:
        raise BotApiNetworkError(describe_request_error(e, method)) from e

    try:
        result = response.json()
    except Exception:
        raise BotApiError(f"Bot API returned non-JSON response: {response.text}")

    if not result.get("ok"):
        raise BotApiError(str(result))

    return result


async def bot_get_me(token: str):
    return await asyncio.to_thread(request_get, token, "getMe")


def guess_media_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type:
        if mime_type.startswith("image/"):
            return "photo"

        if mime_type.startswith("video/"):
            return "video"

    suffix = Path(file_path).suffix.lower()

    if suffix in [".jpg", ".jpeg", ".png", ".webp"]:
        return "photo"

    if suffix in [".mp4", ".mov", ".m4v"]:
        return "video"

    return "document"


async def bot_send_text(
    token: str,
    chat_id: str,
    text: str,
    parse_mode: str = None,
    entities=None,
):
    chat_id = normalize_chat_id(chat_id)
    logger.info(f"Bot text send start | chat_id={chat_id}")

    data = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    if parse_mode:
        data["parse_mode"] = parse_mode
    elif entities:
        data["entities"] = encode_entities(entities)

    result = await asyncio.to_thread(request_post, token, "sendMessage", data, None)
    logger.info(f"Bot text send ok | chat_id={chat_id}")
    return result


async def bot_send_single_file(
    token: str,
    chat_id: str,
    file_path: str,
    caption: str = "",
    parse_mode: str = None,
    entities=None,
):
    chat_id = normalize_chat_id(chat_id)
    media_type = guess_media_type(file_path)

    logger.info(
        f"Bot single media send start | chat_id={chat_id} | "
        f"type={media_type} | file={file_path}"
    )

    method = {
        "photo": "sendPhoto",
        "video": "sendVideo",
        "document": "sendDocument",
    }.get(media_type, "sendDocument")
    field_name = {
        "photo": "photo",
        "video": "video",
        "document": "document",
    }.get(media_type, "document")

    data = {
        "chat_id": chat_id,
        "caption": caption or "",
    }

    if parse_mode and caption:
        data["parse_mode"] = parse_mode
    elif entities and caption:
        data["caption_entities"] = encode_entities(entities)

    with open(file_path, "rb") as file_obj:
        result = await asyncio.to_thread(
            request_post,
            token,
            method,
            data,
            {field_name: file_obj},
        )

    logger.info(
        f"Bot single media send ok | chat_id={chat_id} | "
        f"type={media_type} | file={file_path}"
    )
    return result


async def bot_send_album(
    token: str,
    chat_id: str,
    file_paths,
    caption: str = "",
    parse_mode: str = None,
    entities=None,
):
    chat_id = normalize_chat_id(chat_id)

    if not file_paths:
        raise BotApiError("album files empty")

    if len(file_paths) < 2:
        raise BotApiError("album requires at least 2 files")

    all_results = []
    chunks = []
    index = 0

    while index < len(file_paths):
        chunk = file_paths[index:index + 10]
        index += 10

        if len(chunk) == 1 and chunks:
            chunks[-1].append(chunk[0])
            chunk = chunks[-1]
            chunks[-1] = chunk[:-2]
            chunks.append(chunk[-2:])
            continue

        chunks.append(chunk)

    for chunk_index, chunk in enumerate(chunks):
        logger.info(
            f"Bot album send start | chat_id={chat_id} | "
            f"chunk={chunk_index + 1}/{len(chunks)} | files={len(chunk)}"
        )

        if len(chunk) < 2:
            raise BotApiError(
                f"album chunk has less than 2 files | "
                f"chat_id={chat_id} | chunk={chunk_index + 1}"
            )

        media = []
        files = {}
        opened_files = []

        try:
            for item_index, file_path in enumerate(chunk):
                media_type = guess_media_type(file_path)

                if media_type not in ["photo", "video"]:
                    raise BotApiError(
                        f"unsupported album media type | "
                        f"file={file_path} | type={media_type}"
                    )

                field_name = f"file{item_index}"
                item = {
                    "type": media_type,
                    "media": f"attach://{field_name}",
                }

                if item_index == 0 and caption:
                    item["caption"] = caption

                    if parse_mode:
                        item["parse_mode"] = parse_mode
                    elif entities:
                        item["caption_entities"] = entities

                media.append(item)

                file_obj = open(file_path, "rb")
                opened_files.append(file_obj)
                files[field_name] = file_obj

            result = await asyncio.to_thread(
                request_post,
                token,
                "sendMediaGroup",
                {
                    "chat_id": chat_id,
                    "media": json.dumps(media, ensure_ascii=False),
                },
                files,
            )
            all_results.append(result)
            logger.info(
                f"Bot album send ok | chat_id={chat_id} | "
                f"chunk={chunk_index + 1}/{len(chunks)}"
            )

        except Exception as e:
            logger.exception(
                f"Bot album send failed | chat_id={chat_id} | "
                f"chunk={chunk_index + 1}/{len(chunks)} | {e}"
            )
            raise

        finally:
            for file_obj in opened_files:
                try:
                    file_obj.close()
                except Exception:
                    pass

    return all_results


async def bot_send_prepared_once(
    token: str,
    chat_id: str,
    text: str,
    files,
    message_type: str,
    parse_mode: str = None,
    entities=None,
):
    if files:
        if message_type == "album":
            if len(files) < 2:
                logger.warning(
                    f"Bot album has less than 2 files, downgrade to single | "
                    f"chat_id={chat_id} | files={len(files)}"
                )
                return await bot_send_single_file(
                    token=token,
                    chat_id=chat_id,
                    file_path=files[0],
                    caption=text,
                    parse_mode=parse_mode,
                    entities=entities,
                )

            return await bot_send_album(
                token=token,
                chat_id=chat_id,
                file_paths=files,
                caption=text,
                parse_mode=parse_mode,
                entities=entities,
            )

        return await bot_send_single_file(
            token=token,
            chat_id=chat_id,
            file_path=files[0],
            caption=text,
            parse_mode=parse_mode,
            entities=entities,
        )

    if text.strip():
        return await bot_send_text(
            token=token,
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            entities=entities,
        )

    logger.warning(f"Bot empty prepared message skipped | chat_id={chat_id}")
    return None


async def bot_send_prepared(token: str, chat_id: str, prepared: dict):
    text = prepared.get("text") or ""
    plain_text = prepared.get("plain_text") or text
    files = prepared.get("files") or []
    message_type = prepared.get("type")
    parse_mode = prepared.get("parse_mode")
    entities = prepared.get("entities") or []
    html_text = prepared.get("html_text") or ""
    format_level = prepared.get("format_level") or ""

    logger.info(
        f"Bot prepared send entry | chat_id={chat_id} | "
        f"type={message_type} | files={len(files)} | "
        f"has_text={bool(text.strip())} | parse_mode={parse_mode or ''} | "
        f"entities={len(entities)} | format_level={format_level}"
    )

    try:
        return await bot_send_prepared_once(
            token=token,
            chat_id=chat_id,
            text=text,
            files=files,
            message_type=message_type,
            parse_mode=parse_mode,
            entities=entities,
        )

    except BotApiError as e:
        if not (entities or parse_mode) or not is_parse_mode_error(e):
            raise

        logger.warning(
            f"Bot entity/HTML parse failed, downgrade | "
            f"chat_id={chat_id} | entities={len(entities)} | "
            f"parse_mode={parse_mode or ''} | error={e}"
        )

        if entities and html_text:
            try:
                logger.warning(
                    f"Bot entities failed, retry with HTML | chat_id={chat_id}"
                )
                return await bot_send_prepared_once(
                    token=token,
                    chat_id=chat_id,
                    text=html_text,
                    files=files,
                    message_type=message_type,
                    parse_mode="HTML",
                    entities=None,
                )
            except BotApiError as html_error:
                if not is_parse_mode_error(html_error):
                    raise

                logger.warning(
                    f"Bot HTML retry failed, retry with plain text | "
                    f"chat_id={chat_id} | error={html_error}"
                )

        return await bot_send_prepared_once(
            token=token,
            chat_id=chat_id,
            text=plain_text,
            files=files,
            message_type=message_type,
            parse_mode=None,
            entities=None,
        )
