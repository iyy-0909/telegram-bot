import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = os.getenv("CLONEBOT_LOG_LEVEL", "INFO").upper()


class CleanConsoleFilter(logging.Filter):
    """
    控制台日志过滤器。

    目的：
    1. 保留关键任务状态
    2. 保留 warning / error
    3. 隐藏太碎的下载、清理、接口访问、Telethon 内部日志
    """

    SKIP_KEYWORDS = [
        # Telethon 内部下载/同步日志
        "Starting direct file download",
        "Got difference for channel",
        "Handling differences",

        # 太碎的媒体日志
        "开始下载媒体",
        "媒体下载完成",
        "已删除临时文件",
        "已删除临时目录",

        # 监听热更新频繁刷屏
        "开始热更新监听规则",
        "旧监听已卸载",
        "已注册监听",
        "已注册 1 条聚合监听",
        "已注册 2 条聚合监听",
        "已注册 3 条聚合监听",
        "监听规则热更新完成",

        # Bot prepared 太细
        "Bot prepared 发送入口",
        "Bot 分发开始",
        "Bot 分发成功",
        "Bot 开始发送文本",
        "Bot 文本发送成功",
        "Bot 开始发送单媒体",
        "Bot 单媒体发送成功",
        "Bot 开始发送相册",
        "Bot 相册发送成功",

        # 全局锁细节
        "进入全局发送锁",
        "释放全局发送锁",
        "进入全局发送队列",
        "全局发送间隔检查",
        "全局发送完成",

        # 克隆过程日志不进终端，后台表格只看发送成败
        "开始克隆",
        "clone range",
        "克隆扫描完成",
        "没有需要克隆的新消息",
        "消息准备失败，跳过",
        "单媒体超过大小限制",
        "媒体文件超过大小限制",
        "相册媒体超过大小限制",
        "克隆单条处理完成",
        "克隆相册处理完成",
        "目标分发完成",
        "跳过重复消息",
        "跳过重复相册",
        "克隆跳过",
        "克隆完成",
    ]

    SEND_RESULT_KEYWORDS = [
        "主目标发送成功",
        "附加目标发送成功",
        "主目标发送失败",
        "附加目标发送失败",
        "所有目标发送失败",
    ]

    def filter(self, record):
        message = record.getMessage()

        for keyword in self.SEND_RESULT_KEYWORDS:
            if keyword in message:
                return True

        for keyword in self.SKIP_KEYWORDS:
            if keyword in message:
                return False

        # 没有明确被过滤的 warning / error 仍然保留，避免真正异常消失
        if record.levelno >= logging.WARNING:
            return True

        return True


def setup_logger():
    logger = logging.getLogger("clonebot")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False

    # 防止重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    # 控制台：精简日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CleanConsoleFilter())

    # 文件：保留完整日志，方便排查
    file_handler = RotatingFileHandler(
        LOG_DIR / "clonebot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()


# =========================
# 降低第三方库日志噪音
# =========================

logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("telethon.network").setLevel(logging.WARNING)
logging.getLogger("telethon.client").setLevel(logging.WARNING)

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
