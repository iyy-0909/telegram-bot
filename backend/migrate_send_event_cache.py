from datetime import datetime
from pathlib import Path
import shutil

from db.database import Base, engine
from db.models import CloneSendEvent, ListenerSendEvent


DB_PATH = Path("data/clonebot.db")


def backup_database():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_send_event_cache_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main():
    backup_path = backup_database()
    if backup_path:
        print(f"数据库已备份：{backup_path}")

    Base.metadata.create_all(bind=engine)
    print(
        "发送缓存表迁移完成："
        f"{CloneSendEvent.__tablename__}, {ListenerSendEvent.__tablename__}"
    )


if __name__ == "__main__":
    main()
