"""Add managed channel snapshots after an online-safe SQLite backup."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect

from db.database import engine
from db.models import AccountChannelSync, AccountManagedChannel


def migrate(bind=engine):
    tables = (AccountChannelSync.__table__, AccountManagedChannel.__table__)
    if all(inspect(bind).has_table(table.name) for table in tables):
        return None
    if bind.dialect.name != "sqlite":
        raise RuntimeError("请先为目标数据库建立备份，此自动迁移仅支持 SQLite")
    backup = None
    if bind.url.database and bind.url.database != ":memory:":
        path = Path(bind.url.database).resolve()
        if path.exists():
            backup = path.with_name(f"{path.name}.bak_managed_channels_{datetime.now():%Y%m%d_%H%M%S_%f}")
            with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(backup))) as target:
                source.backup(target)
    for table in tables:
        table.create(bind, checkfirst=True)
    return backup


if __name__ == "__main__":
    print(f"管理频道关系迁移完成；备份：{migrate() or '无需备份或迁移'}")
