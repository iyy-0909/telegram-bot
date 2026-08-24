import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.database import engine


DB_PATH = Path("data/clonebot.db")


def backup_db():
    if not DB_PATH.exists():
        return None
    target = DB_PATH.with_name(f"clonebot.db.bak_grok_rewrite_{datetime.now():%Y%m%d_%H%M%S}")
    shutil.copy2(DB_PATH, target)
    return target


def add_column(conn, table, column, ddl):
    if column not in {item["name"] for item in inspect(conn).get_columns(table)}:
        conn.execute(text(ddl))


def main():
    backup = backup_db()
    fields = [
        ("ai_rewrite_enabled", "BOOLEAN DEFAULT 0"),
        ("ai_rewrite_prompt", "TEXT DEFAULT ''"),
        ("ai_rewrite_max_chars", "INTEGER DEFAULT 800"),
        ("ai_rewrite_failure_mode", "VARCHAR DEFAULT 'fallback'"),
    ]
    with engine.begin() as conn:
        for table in ("clone_tasks", "listener_tasks"):
            for column, ddl in fields:
                add_column(conn, table, column, f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    if backup:
        print(f"数据库已备份：{backup}")
    print("Grok 改写配置迁移完成")


if __name__ == "__main__":
    main()
