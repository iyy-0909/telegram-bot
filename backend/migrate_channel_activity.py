"""Add channel content timestamps, backing up SQLite before changing its schema."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.database import engine


def migrate(bind=engine):
    inspector = inspect(bind)
    if not inspector.has_table("my_channels") or "last_content_at" in {
        column["name"] for column in inspector.get_columns("my_channels")
    }:
        return None
    if bind.dialect.name != "sqlite":
        raise RuntimeError("此迁移仅支持 SQLite，请先为目标数据库建立备份")
    backup = None
    if bind.url.database and bind.url.database != ":memory:":
        path = Path(bind.url.database).resolve()
        backup = path.with_name(f"{path.name}.bak_channel_activity_{datetime.now():%Y%m%d_%H%M%S_%f}")
        with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(backup))) as target:
            source.backup(target)
    with bind.begin() as connection:
        connection.execute(text("ALTER TABLE my_channels ADD COLUMN last_content_at DATETIME"))
    return backup


if __name__ == "__main__":
    backup = migrate()
    print(f"频道更新时间迁移完成；数据库备份：{backup or '无需迁移'}")
