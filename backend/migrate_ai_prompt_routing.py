"""Add automatic routing fields; back up SQLite consistently before DDL."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.database import engine


def migrate(bind=engine):
    additions = {"clone_tasks": ("ai_prompt_mode", "fixed"),
                 "listener_tasks": ("ai_prompt_mode", "fixed"),
                 "ai_prompt_templates": ("content_type", "")}
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    pending = [(table, column, default) for table, (column, default) in additions.items()
               if table in tables and column not in {c["name"] for c in inspector.get_columns(table)}]
    if not pending:
        return None
    if bind.dialect.name != "sqlite":
        raise RuntimeError("此迁移仅支持 SQLite，请先为目标数据库建立备份")
    database = bind.url.database
    backup = None
    if database and database != ":memory:":
        path = Path(database).resolve()
        backup = path.with_name(f"{path.name}.bak_ai_routing_{datetime.now():%Y%m%d_%H%M%S_%f}")
        with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(backup))) as target:
            source.backup(target)
    with bind.begin() as conn:
        for table, column, default in pending:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR NOT NULL DEFAULT '{default}'"))
    return backup


if __name__ == "__main__":
    backup = migrate()
    print(f"AI 提示词自动匹配迁移完成；数据库备份：{backup or '无需迁移'}")
