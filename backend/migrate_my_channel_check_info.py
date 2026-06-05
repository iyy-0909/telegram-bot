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
        f"clonebot.db.bak_my_channel_check_info_migration_{datetime.now():%Y%m%d_%H%M%S}"
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
            "my_channels",
            "delivery_status",
            "ALTER TABLE my_channels ADD COLUMN delivery_status VARCHAR DEFAULT ''",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "collection_status",
            "ALTER TABLE my_channels ADD COLUMN collection_status VARCHAR DEFAULT ''",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "member_count",
            "ALTER TABLE my_channels ADD COLUMN member_count INTEGER",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "can_view_member_count",
            "ALTER TABLE my_channels ADD COLUMN can_view_member_count BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "creator_user_id",
            "ALTER TABLE my_channels ADD COLUMN creator_user_id VARCHAR DEFAULT ''",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "creator_username",
            "ALTER TABLE my_channels ADD COLUMN creator_username VARCHAR DEFAULT ''",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "creator_name",
            "ALTER TABLE my_channels ADD COLUMN creator_name VARCHAR DEFAULT ''",
        )
        add_column_if_missing(
            connection,
            "my_channels",
            "can_view_creator",
            "ALTER TABLE my_channels ADD COLUMN can_view_creator BOOLEAN DEFAULT 0",
        )

    print("my channel check info migration complete")


if __name__ == "__main__":
    main()
