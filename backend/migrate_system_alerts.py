import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from db.database import engine


def database_path():
    url = str(engine.url)
    if not url.startswith("sqlite:///"):
        raise RuntimeError(f"当前数据库不是 SQLite：{url}")
    return Path(url.replace("sqlite:///", "", 1)).resolve()


def main():
    path = database_path()
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在：{path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak_system_alerts_{stamp}")
    shutil.copy2(path, backup)
    print(f"数据库已备份：{backup}")

    columns = {
        "level": "ALTER TABLE control_ack_alerts ADD COLUMN level VARCHAR DEFAULT 'warning'",
        "task_id": "ALTER TABLE control_ack_alerts ADD COLUMN task_id INTEGER",
        "channel": "ALTER TABLE control_ack_alerts ADD COLUMN channel VARCHAR DEFAULT ''",
        "target": "ALTER TABLE control_ack_alerts ADD COLUMN target VARCHAR DEFAULT ''",
        "bot_name": "ALTER TABLE control_ack_alerts ADD COLUMN bot_name VARCHAR DEFAULT ''",
        "context_json": "ALTER TABLE control_ack_alerts ADD COLUMN context_json TEXT DEFAULT '{}'",
    }

    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(control_ack_alerts)")
        existing = {row[1] for row in cursor.fetchall()}
        for name, sql in columns.items():
            if name in existing:
                print(f"control_ack_alerts.{name} already exists")
                continue
            cursor.execute(sql)
            print(f"added control_ack_alerts.{name}")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_control_ack_alerts_level ON control_ack_alerts (level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_control_ack_alerts_task_id ON control_ack_alerts (task_id)")
        connection.commit()
    finally:
        connection.close()

    print("system alerts migration complete")


if __name__ == "__main__":
    main()
