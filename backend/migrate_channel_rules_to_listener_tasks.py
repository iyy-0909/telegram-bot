import json
import shutil
from datetime import datetime
from pathlib import Path

from db.crud_listener import create_listener_task
from db.database import SessionLocal
from db.models import ChannelRule, ListenerTask


DB_PATH = Path("data/clonebot.db")


def backup_db():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_channel_rules_to_listener_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main():
    backup_path = backup_db()
    db = SessionLocal()

    try:
        created = 0
        rules = db.query(ChannelRule).all()

        for rule in rules:
            existing = (
                db.query(ListenerTask)
                .filter(
                    ListenerTask.source_channel == rule.source,
                    ListenerTask.target_channels == json.dumps(
                        [rule.target],
                        ensure_ascii=False,
                    ),
                    ListenerTask.account_id == rule.account_id,
                    ListenerTask.clone_task_id == rule.clone_task_id,
                )
                .first()
            )

            if existing:
                continue

            keywords = getattr(rule, "keywords", None) or "[]"

            create_listener_task({
                "name": f"旧监听规则 {rule.id}",
                "source_channel": rule.source,
                "target_channels": json.dumps([rule.target], ensure_ascii=False),
                "account_id": rule.account_id or 1,
                "enabled": bool(rule.enabled),
                "status": "running" if rule.enabled else "stopped",
                "blocked_keywords": keywords,
                "replace_words": rule.replace_words or "{}",
                "footer": rule.footer or "",
                "remove_contact_lines": getattr(rule, "remove_contact_lines", True),
                "album_wait_seconds": 3,
                "clone_task_id": getattr(rule, "clone_task_id", None),
            })
            created += 1

        if backup_path:
            print(f"数据库已备份：{backup_path}")

        print(f"迁移完成，新增监听任务：{created}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
