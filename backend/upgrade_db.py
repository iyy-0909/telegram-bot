import sqlite3
from pathlib import Path

from db.database import engine


def get_db_path():
    url = str(engine.url)

    print("当前 engine.url =", url)

    if not url.startswith("sqlite:///"):
        raise RuntimeError(f"当前数据库不是 SQLite：{url}")

    db_path = url.replace("sqlite:///", "", 1)

    if db_path.startswith("./"):
        db_path = db_path[2:]

    return Path(db_path).resolve()


def column_exists(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cur.fetchall()]
    return column_name in columns


def add_column_if_missing(cur, table_name, column_name, sql):
    if not column_exists(cur, table_name, column_name):
        cur.execute(sql)
        print(f"已添加字段：{table_name}.{column_name}")
    else:
        print(f"字段已存在：{table_name}.{column_name}")


def table_exists(cur, table_name):
    cur.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    )
    return cur.fetchone() is not None


def create_table_if_missing(cur, table_name, sql):
    if not table_exists(cur, table_name):
        cur.execute(sql)
        print(f"已创建表：{table_name}")
    else:
        print(f"表已存在：{table_name}")


def main():
    db_path = get_db_path()

    print(f"数据库路径：{db_path}")

    if not db_path.exists():
        print("数据库文件不存在，请检查路径")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # =========================
    # 兼容旧表字段
    # =========================

    add_column_if_missing(
        cur,
        "clone_tasks",
        "remove_contact_lines",
        "ALTER TABLE clone_tasks ADD COLUMN remove_contact_lines BOOLEAN DEFAULT 1",
    )

    add_column_if_missing(
        cur,
        "clone_tasks",
        "enable_listener",
        "ALTER TABLE clone_tasks ADD COLUMN enable_listener BOOLEAN DEFAULT 0",
    )

    add_column_if_missing(
        cur,
        "clone_tasks",
        "start_message_url",
        "ALTER TABLE clone_tasks ADD COLUMN start_message_url TEXT DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "clone_tasks",
        "end_message_url",
        "ALTER TABLE clone_tasks ADD COLUMN end_message_url TEXT DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "channel_rules",
        "keywords",
        "ALTER TABLE channel_rules ADD COLUMN keywords TEXT DEFAULT '[]'",
    )

    add_column_if_missing(
        cur,
        "channel_rules",
        "clone_task_id",
        "ALTER TABLE channel_rules ADD COLUMN clone_task_id INTEGER",
    )

    add_column_if_missing(
        cur,
        "channel_rules",
        "remove_contact_lines",
        "ALTER TABLE channel_rules ADD COLUMN remove_contact_lines BOOLEAN DEFAULT 1",
    )

    add_column_if_missing(
        cur,
        "listener_tasks",
        "last_received_at",
        "ALTER TABLE listener_tasks ADD COLUMN last_received_at DATETIME",
    )

    add_column_if_missing(
        cur,
        "clone_tasks",
        "selected_link_template_group_id",
        "ALTER TABLE clone_tasks ADD COLUMN selected_link_template_group_id INTEGER",
    )

    add_column_if_missing(
        cur,
        "listener_tasks",
        "selected_link_template_group_id",
        "ALTER TABLE listener_tasks ADD COLUMN selected_link_template_group_id INTEGER",
    )

    add_column_if_missing(
        cur,
        "support_bots",
        "welcome_text_type",
        "ALTER TABLE support_bots ADD COLUMN welcome_text_type VARCHAR DEFAULT 'plain'",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "clone_status",
        "ALTER TABLE my_channels ADD COLUMN clone_status VARCHAR DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "delivery_status",
        "ALTER TABLE my_channels ADD COLUMN delivery_status VARCHAR DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "collection_status",
        "ALTER TABLE my_channels ADD COLUMN collection_status VARCHAR DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "member_count",
        "ALTER TABLE my_channels ADD COLUMN member_count INTEGER",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "can_view_member_count",
        "ALTER TABLE my_channels ADD COLUMN can_view_member_count BOOLEAN DEFAULT 0",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "creator_user_id",
        "ALTER TABLE my_channels ADD COLUMN creator_user_id VARCHAR DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "creator_username",
        "ALTER TABLE my_channels ADD COLUMN creator_username VARCHAR DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "creator_name",
        "ALTER TABLE my_channels ADD COLUMN creator_name VARCHAR DEFAULT ''",
    )

    add_column_if_missing(
        cur,
        "my_channels",
        "can_view_creator",
        "ALTER TABLE my_channels ADD COLUMN can_view_creator BOOLEAN DEFAULT 0",
    )

    # =========================
    # 新系统：Bot 分发端
    # =========================

    create_table_if_missing(
        cur,
        "bot_accounts",
        """
        CREATE TABLE bot_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            token TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            remark TEXT DEFAULT '',
            last_error TEXT DEFAULT '',
            created_at DATETIME,
            updated_at DATETIME
        )
        """,
    )

    create_table_if_missing(
        cur,
        "target_bot_bindings",
        """
        CREATE TABLE target_bot_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_channel VARCHAR NOT NULL,
            bot_id INTEGER NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            remark TEXT DEFAULT '',
            created_at DATETIME
        )
        """,
    )

    create_table_if_missing(
        cur,
        "system_settings",
        """
        CREATE TABLE system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key VARCHAR NOT NULL UNIQUE,
            value TEXT DEFAULT '',
            remark TEXT DEFAULT '',
            updated_at DATETIME
        )
        """,
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_system_settings_key
        ON system_settings(key)
        """
    )

    send_defaults = {
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

    for key, (value, remark) in send_defaults.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO system_settings (key, value, remark, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (key, value, remark),
        )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_target_bot_bindings_target_channel
        ON target_bot_bindings(target_channel)
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_target_bot_bindings_bot_id
        ON target_bot_bindings(bot_id)
        """
    )

    conn.commit()
    conn.close()

    print("数据库升级完成")


if __name__ == "__main__":
    main()
