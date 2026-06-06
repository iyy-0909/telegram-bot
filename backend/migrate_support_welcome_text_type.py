import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from db.database import engine


def get_db_path():
    url = str(engine.url)
    if not url.startswith("sqlite:///"):
        raise RuntimeError(f"当前数据库不是 SQLite：{url}")

    db_path = url.replace("sqlite:///", "", 1)
    if db_path.startswith("./"):
        db_path = db_path[2:]
    return Path(db_path).resolve()


def column_exists(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    return column_name in [row[1] for row in cur.fetchall()]


def main():
    db_path = get_db_path()
    if not db_path.exists():
        print(f"database not found: {db_path}")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(
        f"{db_path.name}.bak_support_welcome_text_type_migration_{stamp}"
    )
    shutil.copy2(db_path, backup_path)
    print(f"backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if not column_exists(cur, "support_bots", "welcome_text_type"):
            cur.execute(
                "ALTER TABLE support_bots ADD COLUMN welcome_text_type VARCHAR DEFAULT 'plain'"
            )
            print("support_bots.welcome_text_type added")
        else:
            print("support_bots.welcome_text_type already exists")
        conn.commit()
    finally:
        conn.close()

    print("support welcome text type migration complete")


if __name__ == "__main__":
    main()
