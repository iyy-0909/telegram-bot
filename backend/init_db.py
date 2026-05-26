import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import inspect, text

from db.database import Base
from db.database import engine
from db.models import Account
from db.models import BotAccount
from db.models import ChannelRule
from db.models import CloneSendEvent
from db.models import CloneTask
from db.models import ContentTemplate
from db.models import ListenerSendEvent
from db.models import ListenerSentMessage
from db.models import ListenerTask
from db.models import MyChannel
from db.models import SentMessage
from db.models import SupportConversation
from db.models import SupportCustomer
from db.models import SupportCustomerTag
from db.models import SupportMessage
from db.models import SupportQuickReply
from db.models import SupportSetting
from db.models import SupportTag
from db.models import SupportBot
from db.models import SystemSetting
from db.models import TargetBotBinding


# Importing the model classes above registers every table on Base.metadata.
_REGISTERED_MODELS = (
    Account,
    BotAccount,
    ChannelRule,
    CloneSendEvent,
    CloneTask,
    ContentTemplate,
    ListenerSendEvent,
    ListenerSentMessage,
    ListenerTask,
    MyChannel,
    SentMessage,
    SupportConversation,
    SupportCustomer,
    SupportCustomerTag,
    SupportMessage,
    SupportQuickReply,
    SupportSetting,
    SupportTag,
    SupportBot,
    SystemSetting,
    TargetBotBinding,
)


def get_sqlite_db_path():
    url = str(engine.url)

    if not url.startswith("sqlite:///"):
        return None

    db_path = url.replace("sqlite:///", "", 1)

    if db_path in {":memory:", ""}:
        return None

    if db_path.startswith("./"):
        db_path = db_path[2:]

    return Path(unquote(db_path)).resolve()


def backup_database_if_needed(needs_migration, db_existed_before_check):
    db_path = get_sqlite_db_path()

    if (
        not needs_migration
        or not db_existed_before_check
        or not db_path
        or not db_path.exists()
    ):
        return None

    backup_path = db_path.with_name(
        f"{db_path.name}.bak_init_db_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(db_path, backup_path)
    return backup_path


def get_existing_schema():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    columns = {}

    for table_name in tables:
        columns[table_name] = {
            item["name"]
            for item in inspector.get_columns(table_name)
        }

    return tables, columns


def schema_needs_migration():
    existing_tables, existing_columns = get_existing_schema()

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            return True

        current_columns = existing_columns.get(table.name, set())
        for column in table.columns:
            if column.name not in current_columns:
                return True

    return False


def quote_name(name):
    return '"' + name.replace('"', '""') + '"'


def render_default(column):
    default = column.default

    if default is None or default.is_callable:
        return ""

    value = default.arg

    if isinstance(value, bool):
        return f" DEFAULT {1 if value else 0}"

    if isinstance(value, int):
        return f" DEFAULT {value}"

    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f" DEFAULT '{escaped}'"

    return ""


def add_missing_columns():
    inspector = inspect(engine)
    dialect = engine.dialect

    with engine.begin() as conn:
        existing_tables = set(inspector.get_table_names())

        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue

            columns = {
                item["name"]
                for item in inspect(conn).get_columns(table.name)
            }

            for column in table.columns:
                if column.name in columns or column.primary_key:
                    continue

                column_type = column.type.compile(dialect=dialect)
                ddl = (
                    f"ALTER TABLE {quote_name(table.name)} "
                    f"ADD COLUMN {quote_name(column.name)} "
                    f"{column_type}{render_default(column)}"
                )
                conn.execute(text(ddl))
                print(f"added column: {table.name}.{column.name}")


def ensure_defaults():
    from db.crud_settings import ensure_default_settings
    from db.crud_support import ensure_support_defaults

    ensure_default_settings()
    ensure_support_defaults()


def init_db():
    db_path = get_sqlite_db_path()
    db_existed_before_check = bool(db_path and db_path.exists())
    needs_migration = schema_needs_migration()
    backup_path = backup_database_if_needed(
        needs_migration,
        db_existed_before_check,
    )

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    ensure_defaults()

    if backup_path:
        print(f"database backup: {backup_path}")

    print("database initialized")


def main():
    init_db()


if __name__ == "__main__":
    main()
