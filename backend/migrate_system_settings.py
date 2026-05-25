import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from db.database import engine


DEFAULT_SEND_SETTINGS = {
    "global_send_delay": (
        "3",
        "任意两次 Bot API 发送之间的全局最小间隔秒数",
    ),
    "send_retry_count": (
        "2",
        "发送异常时的重试次数，只重试抛异常的发送，不重试业务失败",
    ),
    "send_retry_delay": (
        "5",
        "发送异常重试前等待秒数",
    ),
}


def get_db_path():
    url = str(engine.url)

    if not url.startswith("sqlite:///"):
        raise RuntimeError(f"当前数据库不是 SQLite：{url}")

    db_path = url.replace("sqlite:///", "", 1)

    if db_path.startswith("./"):
        db_path = db_path[2:]

    return Path(db_path).resolve()


def table_exists(cur, table_name):
    cur.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    )
    return cur.fetchone() is not None


def main():
    db_path = get_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"数据库文件不存在：{db_path}")

    backup_path = db_path.with_name(
        f"{db_path.name}.bak_system_settings_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(db_path, backup_path)
    print(f"数据库已备份：{backup_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not table_exists(cur, "system_settings"):
        cur.execute(
            """
            CREATE TABLE system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key VARCHAR NOT NULL UNIQUE,
                value TEXT DEFAULT '',
                remark TEXT DEFAULT '',
                updated_at DATETIME
            )
            """
        )
        print("已创建表：system_settings")
    else:
        print("表已存在：system_settings")

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_system_settings_key
        ON system_settings(key)
        """
    )

    for key, (value, remark) in DEFAULT_SEND_SETTINGS.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO system_settings (key, value, remark, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (key, value, remark),
        )
        print(f"已确认配置：{key}={value}")

    conn.commit()
    conn.close()

    print("系统发送配置迁移完成")


if __name__ == "__main__":
    main()
