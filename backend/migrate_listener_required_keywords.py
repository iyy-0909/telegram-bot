from datetime import datetime
from pathlib import Path
import shutil
from urllib.parse import unquote

from sqlalchemy import inspect, text

from db.database import DATABASE_URL, engine


def get_sqlite_db_path():
    if not DATABASE_URL.startswith("sqlite:///"):
        return None

    db_path = DATABASE_URL.replace("sqlite:///", "", 1)

    if db_path in {":memory:", ""}:
        return None

    return Path(unquote(db_path))


def backup_database():
    db_path = get_sqlite_db_path()

    if not db_path or not db_path.exists():
        return None

    backup_path = db_path.with_name(
        f"{db_path.name}.bak_listener_required_keywords_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(db_path, backup_path)
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
            "listener_tasks",
            "listen_required_keywords",
            "ALTER TABLE listener_tasks ADD COLUMN listen_required_keywords TEXT DEFAULT '[]'",
        )

    print("listener required keywords migration complete")


if __name__ == "__main__":
    main()
