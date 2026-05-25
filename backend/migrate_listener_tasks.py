import shutil
from datetime import datetime
from pathlib import Path

from db.database import engine
from db.models import Base


DB_PATH = Path("data/clonebot.db")


def backup_db():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_listener_tasks_migration_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main():
    backup_path = backup_db()
    Base.metadata.create_all(bind=engine)

    if backup_path:
        print(f"数据库已备份：{backup_path}")

    print("监听任务表迁移完成")


if __name__ == "__main__":
    main()
