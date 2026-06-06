from datetime import datetime
from pathlib import Path
import shutil

from sqlalchemy import inspect, text

from db.database import engine


DB_PATH = Path("data/clonebot.db")


def backup_database():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_link_rules_migration_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def add_column_if_missing(connection, table_name, column_name, sql):
    columns = {
        column["name"]
        for column in inspect(connection).get_columns(table_name)
    }

    if column_name in columns:
        print(f"{table_name}.{column_name} already exists")
        return False

    connection.execute(text(sql))
    print(f"added {table_name}.{column_name}")
    return True


def main():
    backup_path = backup_database()
    if backup_path:
        print(f"database backed up: {backup_path}")

    with engine.begin() as connection:
        add_column_if_missing(
            connection,
            "clone_tasks",
            "selected_link_template_group_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_link_template_group_id INTEGER",
        )
        add_column_if_missing(
            connection,
            "listener_tasks",
            "selected_link_template_group_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_link_template_group_id INTEGER",
        )

    print("link rules migration complete")


if __name__ == "__main__":
    main()
