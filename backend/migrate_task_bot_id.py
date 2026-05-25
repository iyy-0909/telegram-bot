import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.crud_bot import build_target_lookup_keys, normalize_target_channel
from db.database import engine
from db.models import Base


DB_PATH = Path("data/clonebot.db")


def backup_db():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_task_bot_id_migration_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def add_column_if_missing(conn, table, column, ddl):
    columns = {item["name"] for item in inspect(conn).get_columns(table)}

    if column not in columns:
        conn.execute(text(ddl))
        print(f"已添加字段：{table}.{column}")


def parse_targets(value):
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    return [
        normalize_target_channel(item)
        for item in parsed
        if normalize_target_channel(item)
    ]


def load_bindings(conn):
    rows = conn.execute(
        text(
            """
            SELECT target_channel, bot_id
            FROM target_bot_bindings
            WHERE enabled = 1
            """
        )
    ).mappings().all()

    bindings = {}

    for row in rows:
        for key in build_target_lookup_keys(row["target_channel"]):
            bindings[key.lower()] = row["bot_id"]

    return bindings


def infer_bot_id(target_channels, bindings):
    targets = parse_targets(target_channels)

    if not targets:
        return None

    bot_ids = set()

    for target in targets:
        target_keys = [key.lower() for key in build_target_lookup_keys(target)]
        bot_id = next(
            (bindings[key] for key in target_keys if key in bindings),
            None,
        )

        if not bot_id:
            return None

        bot_ids.add(bot_id)

    if len(bot_ids) != 1:
        return None

    return bot_ids.pop()


def migrate_task_table(conn, table, id_column="id"):
    bindings = load_bindings(conn)
    rows = conn.execute(
        text(
            f"""
            SELECT {id_column} AS id, target_channels, bot_id
            FROM {table}
            """
        )
    ).mappings().all()

    updated = 0

    for row in rows:
        if row["bot_id"]:
            continue

        bot_id = infer_bot_id(row["target_channels"], bindings)

        if not bot_id:
            continue

        conn.execute(
            text(f"UPDATE {table} SET bot_id = :bot_id WHERE {id_column} = :id"),
            {
                "bot_id": bot_id,
                "id": row["id"],
            },
        )
        updated += 1

    print(f"{table} 已迁移 bot_id：{updated}")


def main():
    backup_path = backup_db()
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        add_column_if_missing(
            conn,
            "clone_tasks",
            "bot_id",
            "ALTER TABLE clone_tasks ADD COLUMN bot_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "bot_id",
            "ALTER TABLE listener_tasks ADD COLUMN bot_id INTEGER",
        )

        migrate_task_table(conn, "clone_tasks")
        migrate_task_table(conn, "listener_tasks")

    if backup_path:
        print(f"数据库已备份：{backup_path}")

    print("任务级分发 Bot 字段迁移完成")


if __name__ == "__main__":
    main()
