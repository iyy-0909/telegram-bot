import os
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Any

from telethon.tl.types import Message

from bot.logger import logger


DOWNLOAD_DIR = Path("data/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOAD_TIMEOUT = 180
SEND_TIMEOUT = 180
MAX_MEDIA_SIZE = 50 * 1024 * 1024


class MediaTooLargeError(Exception):
    pass


def safe_remove(path):
    """安全删除临时文件"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info(f"已删除临时文件：{path}")
    except Exception as e:
        logger.warning(f"删除临时文件失败：{path} | {e}")


def get_media_size(message: Message):
    file_info = getattr(message, "file", None)

    if file_info and getattr(file_info, "size", None):
        return file_info.size

    document = getattr(message, "document", None)

    if document and getattr(document, "size", None):
        return document.size

    return None


def has_downloadable_media(message: Message) -> bool:
    return bool(
        getattr(message, "file", None)
        or getattr(message, "document", None)
        or getattr(message, "photo", None)
    )


def is_media_too_large(size) -> bool:
    return bool(size and size > MAX_MEDIA_SIZE)


def format_size(size) -> str:
    if not size:
        return "unknown"

    return f"{size / 1024 / 1024:.2f}MB"


async def download_media_with_timeout(message: Message, download_dir=None):
    """下载单个媒体，带超时。每个任务使用独立目录，避免文件名冲突。"""
    try:
        client = getattr(message, "_client", None)
        if client and hasattr(client, "is_connected") and not client.is_connected():
            logger.warning(
                f"媒体下载前检测到 Telethon 已断开，尝试重连 | message_id={message.id}"
            )
            await client.connect()

        target_dir = Path(download_dir) if download_dir else DOWNLOAD_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"开始下载媒体 | message_id={message.id} | dir={target_dir}"
        )

        file_path = await asyncio.wait_for(
            message.download_media(file=str(target_dir)),
            timeout=DOWNLOAD_TIMEOUT,
        )

        if not file_path:
            logger.warning(f"媒体下载为空 | message_id={message.id}")
            return None

        file_size = os.path.getsize(file_path)

        if is_media_too_large(file_size):
            logger.warning(
                f"媒体文件超过大小限制，跳过整条内容 | "
                f"message_id={message.id} | "
                f"size={format_size(file_size)} | "
                f"limit={format_size(MAX_MEDIA_SIZE)} | file={file_path}"
            )
            raise MediaTooLargeError(file_path)

        logger.info(
            f"媒体下载完成 | message_id={message.id} | file={file_path}"
        )

        return file_path

    except asyncio.TimeoutError:
        logger.error(
            f"媒体下载超时，跳过 | "
            f"message_id={message.id} | timeout={DOWNLOAD_TIMEOUT}s"
        )
        return None

    except MediaTooLargeError:
        raise

    except Exception as e:
        logger.exception(f"媒体下载失败 | message_id={message.id} | {e}")
        return None


async def prepare_single_message(message: Message, text: str = "") -> Dict[str, Any]:
    """
    准备普通消息。

    每条消息独立临时目录，避免并发下载同名文件互相覆盖。
    """
    files = []

    batch_dir = DOWNLOAD_DIR / f"single_{message.id}_{uuid.uuid4().hex}"

    if message.media and not has_downloadable_media(message):
        logger.info(
            f"消息包含非文件媒体，按文本处理 | "
            f"message_id={message.id} | media_type={type(message.media).__name__}"
        )

    if message.media and has_downloadable_media(message):
        media_size = get_media_size(message)

        if is_media_too_large(media_size):
            logger.warning(
                f"单媒体超过大小限制，跳过整条内容 | "
                f"message_id={message.id} | "
                f"size={format_size(media_size)} | "
                f"limit={format_size(MAX_MEDIA_SIZE)}"
            )

            return {
                "ok": False,
                "error": "media_too_large",
                "error_message": (
                    f"单媒体超过大小限制，跳过整条内容 | "
                    f"size={format_size(media_size)} | "
                    f"limit={format_size(MAX_MEDIA_SIZE)}"
                ),
                "type": "single",
                "text": text or "",
                "files": [],
                "message_id": message.id,
                "temp_dir": str(batch_dir),
            }

        try:
            file_path = await download_media_with_timeout(
                message,
                download_dir=batch_dir,
            )
        except MediaTooLargeError:
            return {
                "ok": False,
                "error": "media_too_large_after_download",
                "error_message": (
                    f"媒体下载后超过大小限制，跳过整条内容 | "
                    f"limit={format_size(MAX_MEDIA_SIZE)}"
                ),
                "type": "single",
                "text": text or "",
                "files": [],
                "message_id": message.id,
                "temp_dir": str(batch_dir),
            }

        if file_path:
            files.append(file_path)
        else:
            return {
                "ok": False,
                "error": "media_download_failed",
                "error_message": "媒体下载失败或下载结果为空",
                "type": "single",
                "text": text or "",
                "files": [],
                "message_id": message.id,
                "temp_dir": str(batch_dir),
            }

    return {
        "ok": True,
        "type": "single",
        "text": text or "",
        "files": files,
        "message_id": message.id,
        "temp_dir": str(batch_dir),
    }


async def prepare_album(messages: List[Message], text: str = "") -> Dict[str, Any]:
    """
    准备相册。

    每组相册独立临时目录，避免和其他任务/监听下载文件冲突。
    """
    files = []
    message_ids = [message.id for message in messages]

    grouped_id = None
    for message in messages:
        if getattr(message, "grouped_id", None):
            grouped_id = message.grouped_id
            break

    batch_name = grouped_id or "_".join(str(mid) for mid in message_ids)
    batch_dir = DOWNLOAD_DIR / f"album_{batch_name}_{uuid.uuid4().hex}"

    logger.info(
        f"开始准备相册 | 数量={len(messages)} | "
        f"message_ids={message_ids} | dir={batch_dir}"
    )

    for message in messages:
        if not message.media:
            continue

        if not has_downloadable_media(message):
            logger.info(
                f"相册消息包含非文件媒体，跳过下载 | "
                f"message_id={message.id} | media_type={type(message.media).__name__}"
            )
            continue

        media_size = get_media_size(message)

        if is_media_too_large(media_size):
            logger.warning(
                f"相册存在超过大小限制的媒体，跳过整条内容 | "
                f"message_id={message.id} | message_ids={message_ids} | "
                f"size={format_size(media_size)} | "
                f"limit={format_size(MAX_MEDIA_SIZE)}"
            )

            return {
                "ok": False,
                "type": "album",
                "text": text or "",
                "files": files,
                "message_ids": message_ids,
                "temp_dir": str(batch_dir),
            }

        try:
            file_path = await download_media_with_timeout(
                message,
                download_dir=batch_dir,
            )
        except MediaTooLargeError as e:
            logger.warning(
                f"相册媒体下载后超过大小限制，跳过整条内容 | "
                f"message_id={message.id} | message_ids={message_ids}"
            )

            return {
                "ok": False,
                "type": "album",
                "text": text or "",
                "files": files + [str(e)],
                "message_ids": message_ids,
                "temp_dir": str(batch_dir),
            }

        if file_path:
            files.append(file_path)

    if len(files) >= 2:
        logger.info(
            f"相册准备完成 | 文件数={len(files)} | "
            f"message_ids={message_ids} | dir={batch_dir}"
        )

        return {
            "ok": True,
            "type": "album",
            "text": text or "",
            "files": files,
            "message_ids": message_ids,
            "temp_dir": str(batch_dir),
        }

    if len(files) == 1:
        logger.warning(
            f"相册仅成功下载 1 个媒体，降级单媒体发送 | "
            f"message_ids={message_ids} | file={files[0]}"
        )

        return {
            "ok": True,
            "type": "single",
            "text": text or "",
            "files": files,
            "message_ids": message_ids,
            "temp_dir": str(batch_dir),
        }

    logger.warning(
        f"相册没有成功下载的媒体，跳过 | message_ids={message_ids}"
    )

    return {
        "ok": False,
        "type": "album",
        "text": text or "",
        "files": [],
        "message_ids": message_ids,
        "temp_dir": str(batch_dir),
    }

async def send_prepared(client, target: str, prepared: Dict[str, Any]) -> bool:
    """
    发送已经准备好的消息。

    不下载媒体，只复用 prepared.files。
    """
    try:
        text = prepared.get("text") or ""
        files = prepared.get("files") or []
        message_type = prepared.get("type")

        if files:
            logger.info(
                f"开始发送已准备媒体 | target={target} | "
                f"type={message_type} | files={len(files)}"
            )

            if message_type == "album":
                await asyncio.wait_for(
                    client.send_file(
                        target,
                        files,
                        caption=text if text else None,
                    ),
                    timeout=SEND_TIMEOUT,
                )
            else:
                await asyncio.wait_for(
                    client.send_file(
                        target,
                        files[0],
                        caption=text if text else None,
                    ),
                    timeout=SEND_TIMEOUT,
                )

            logger.info(
                f"已准备媒体发送成功 | target={target} | "
                f"type={message_type} | files={len(files)}"
            )

            return True

        if text and text.strip():
            logger.info(f"开始发送已准备文本 | target={target}")

            await asyncio.wait_for(
                client.send_message(target, text),
                timeout=SEND_TIMEOUT,
            )

            logger.info(f"已准备文本发送成功 | target={target}")
            return True

        logger.warning(f"空 prepared 消息，跳过 | target={target}")
        return False

    except asyncio.TimeoutError:
        logger.error(
            f"发送已准备消息超时 | target={target} | "
            f"timeout={SEND_TIMEOUT}s"
        )
        return False

    except Exception as e:
        logger.exception(
            f"发送已准备消息失败 | target={target} | {e}"
        )
        return False


def cleanup_prepared(prepared: Dict[str, Any]):
    """统一清理 prepared 里的临时文件和独立目录"""
    files = prepared.get("files") or []

    for file_path in files:
        safe_remove(file_path)

    temp_dir = prepared.get("temp_dir")

    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"已删除临时目录：{temp_dir}")
        except Exception as e:
            logger.warning(f"删除临时目录失败：{temp_dir} | {e}")


# ------------------------------------------------------------
# 兼容旧逻辑：保留 send_message / send_album
# listener 或旧 send_queue 如果还在调用，不会报错
# ------------------------------------------------------------

async def send_message(client, target, message: Message, text=""):
    """
    兼容旧版单条发送。

    注意：
    这个函数仍然是下载一次、发送一次、删除一次。
    clone 系统后面会改用 prepare_single_message + send_prepared。
    """
    prepared = await prepare_single_message(message, text)

    try:
        if not prepared.get("ok"):
            return False

        return await send_prepared(client, target, prepared)

    finally:
        cleanup_prepared(prepared)


async def send_album(client, target, messages, text=""):
    """
    兼容旧版相册发送。

    注意：
    这个函数仍然是下载一次、发送一次、删除一次。
    clone 系统后面会改用 prepare_album + send_prepared。
    """
    prepared = await prepare_album(messages, text)

    try:
        if not prepared.get("ok"):
            return False

        return await send_prepared(client, target, prepared)

    finally:
        cleanup_prepared(prepared)
