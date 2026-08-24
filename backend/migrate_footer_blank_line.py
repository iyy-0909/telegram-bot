import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.database import engine


DB_PATH = Path("data/clonebot.db")


def main():
    backup = None
    if DB_PATH.exists():
        backup = DB_PATH.with_name(
            f"clonebot.db.bak_footer_blank_line_{datetime.now():%Y%m%d_%H%M%S}"
        )
        shutil.copy2(DB_PATH, backup)

    with engine.begin() as conn:
        for table in ("clone_tasks", "listener_tasks"):
            columns = {item["name"] for item in inspect(conn).get_columns(table)}
            if "footer_leading_blank_line" not in columns:
                conn.execute(
                    text(
                        f"ALTER TABLE {table} "
                        "ADD COLUMN footer_leading_blank_line BOOLEAN DEFAULT 1"
                    )
                )
            conn.execute(
                text(
                    f"UPDATE {table} SET footer_leading_blank_line = 1 "
                    "WHERE footer_leading_blank_line IS NULL"
                )
            )

    if backup:
        print(f"数据库已备份：{backup}")
    print("Footer 空行配置迁移完成")


if __name__ == "__main__":
    main()
