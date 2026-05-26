from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

from db.crud_support import ensure_support_defaults


DB_PATH = Path("data/clonebot.db")


def backup_database():
    if not DB_PATH.exists():
        return None
    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_support_group_mode_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def get_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table, column_name, definition):
    columns = get_columns(cursor, table)
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}")
        return True
    return False


def main():
    backup_path = backup_database()
    if backup_path:
        print(f"数据库已备份：{backup_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        added = []
        for column_name, definition in [
            ("support_thread_id", "INTEGER"),
            ("support_topic_name", "VARCHAR DEFAULT ''"),
            ("support_topic_created_at", "DATETIME"),
        ]:
            if add_column_if_missing(cursor, "support_conversations", column_name, definition):
                added.append(f"support_conversations.{column_name}")

        for column_name, definition in [
            ("support_group_message_id", "INTEGER"),
            ("reply_to_support_group_message_id", "INTEGER"),
            ("send_status", "VARCHAR DEFAULT 'success'"),
            ("error_message", "TEXT DEFAULT ''"),
            ("caption", "TEXT DEFAULT ''"),
            ("file_unique_id", "VARCHAR DEFAULT ''"),
            ("file_name", "VARCHAR DEFAULT ''"),
            ("mime_type", "VARCHAR DEFAULT ''"),
            ("file_size", "INTEGER"),
            ("width", "INTEGER"),
            ("height", "INTEGER"),
            ("duration", "INTEGER"),
        ]:
            if add_column_if_missing(cursor, "support_messages", column_name, definition):
                added.append(f"support_messages.{column_name}")

        conn.commit()
    finally:
        conn.close()

    ensure_support_defaults()
    print(f"客服群模式迁移完成，新增字段：{added or '无'}")


if __name__ == "__main__":
    main()
