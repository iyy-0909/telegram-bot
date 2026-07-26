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
        f"{db_path.name}.bak_default_account_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    with engine.connect() as connection:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("accounts")
        }

    with engine.begin() as connection:
        if "is_default" in columns:
            print("accounts.is_default already exists")
        else:
            backup_path = backup_database()
            if backup_path:
                print(f"database backed up: {backup_path}")
            connection.execute(text(
                "ALTER TABLE accounts "
                "ADD COLUMN is_default BOOLEAN DEFAULT 0"
            ))
            print("accounts.is_default added")

        current_default = connection.execute(text(
            "SELECT id FROM accounts "
            "WHERE enabled = 1 AND is_default = 1 "
            "ORDER BY id LIMIT 1"
        )).first()
        if not current_default:
            first_enabled = connection.execute(text(
                "SELECT id FROM accounts "
                "WHERE enabled = 1 ORDER BY id LIMIT 1"
            )).first()
            if first_enabled:
                connection.execute(
                    text("UPDATE accounts SET is_default = 1 WHERE id = :id"),
                    {"id": first_enabled[0]},
                )
                print(f"default account initialized: {first_enabled[0]}")

    print("default account migration complete")


if __name__ == "__main__":
    main()
