import shutil
from datetime import datetime
from pathlib import Path
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
        f"{db_path.name}.bak_search_bot_manual_account_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    backup_path = backup_database()
    if backup_path:
        print(f"database backed up: {backup_path}")

    with engine.begin() as connection:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns(
                "search_bot_channel_submissions"
            )
        }
        if "manual_account_id" in columns:
            print(
                "search_bot_channel_submissions.manual_account_id "
                "already exists"
            )
        else:
            connection.execute(text(
                "ALTER TABLE search_bot_channel_submissions "
                "ADD COLUMN manual_account_id VARCHAR DEFAULT ''"
            ))
            print(
                "search_bot_channel_submissions.manual_account_id added"
            )

    print("search bot manual account migration complete")


if __name__ == "__main__":
    main()
