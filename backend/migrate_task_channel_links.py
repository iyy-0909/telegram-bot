"""Create stable task/channel links after a consistent SQLite backup."""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from db.channel_overview import backfill_task_links
from db.database import engine
from db.models import TaskChannelLink


def migrate(bind=engine, *, backfill=True):
    table_exists = inspect(bind).has_table(TaskChannelLink.__tablename__)
    if not table_exists and bind.dialect.name != "sqlite":
        raise RuntimeError("请先备份数据库；任务频道关联自动迁移仅支持 SQLite")

    backup = None
    if not table_exists and bind.url.database and bind.url.database != ":memory:":
        path = Path(bind.url.database).resolve()
        if path.exists():
            backup = path.with_name(
                f"{path.name}.bak_task_channel_links_{datetime.now():%Y%m%d_%H%M%S_%f}"
            )
            with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(backup))) as target:
                source.backup(target)

    if not table_exists:
        TaskChannelLink.__table__.create(bind, checkfirst=True)
    tables = set(inspect(bind).get_table_names())
    if backfill and {"my_channels", "listener_tasks", "clone_tasks"}.issubset(tables):
        with Session(bind=bind, autoflush=False) as db:
            backfill_task_links(db)
    return backup


if __name__ == "__main__":
    print(f"任务频道关联迁移完成；备份：{migrate() or '无需迁移'}")
