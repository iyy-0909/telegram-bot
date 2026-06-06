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


def main():
    db_path = get_db_path()
    if not db_path.exists():
        print(f"database not found: {db_path}")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak_control_ack_alerts_{stamp}")
    shutil.copy2(db_path, backup_path)
    print(f"backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS control_ack_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_key VARCHAR NOT NULL UNIQUE,
                module VARCHAR DEFAULT '',
                title VARCHAR DEFAULT '',
                detail TEXT DEFAULT '',
                status VARCHAR DEFAULT 'pending',
                support_bot_id INTEGER,
                customer_id INTEGER,
                conversation_id INTEGER,
                last_message_chat_id VARCHAR DEFAULT '',
                last_message_id INTEGER,
                repeat_count INTEGER DEFAULT 0,
                first_sent_at DATETIME,
                last_sent_at DATETIME,
                acknowledged_by VARCHAR DEFAULT '',
                acknowledged_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_control_ack_alerts_alert_key ON control_ack_alerts (alert_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_control_ack_alerts_status ON control_ack_alerts (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_control_ack_alerts_support_bot_id ON control_ack_alerts (support_bot_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_control_ack_alerts_last_sent_at ON control_ack_alerts (last_sent_at)")
        conn.commit()
    finally:
        conn.close()

    print("control ack alerts migration complete")


if __name__ == "__main__":
    main()
