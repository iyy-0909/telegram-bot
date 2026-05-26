from datetime import datetime
from pathlib import Path
import shutil

from db.database import Base, engine
from db.crud_support import ensure_support_defaults
from db.models import (
    SupportConversation,
    SupportCustomer,
    SupportCustomerTag,
    SupportMessage,
    SupportQuickReply,
    SupportSetting,
    SupportTag,
)


DB_PATH = Path("data/clonebot.db")


def backup_database():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_support_mvp_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main():
    backup_path = backup_database()
    if backup_path:
        print(f"数据库已备份：{backup_path}")

    Base.metadata.create_all(bind=engine)
    ensure_support_defaults()

    print(
        "客服模块 MVP 迁移完成："
        f"{SupportCustomer.__tablename__}, "
        f"{SupportConversation.__tablename__}, "
        f"{SupportMessage.__tablename__}, "
        f"{SupportQuickReply.__tablename__}, "
        f"{SupportTag.__tablename__}, "
        f"{SupportCustomerTag.__tablename__}, "
        f"{SupportSetting.__tablename__}"
    )


if __name__ == "__main__":
    main()
