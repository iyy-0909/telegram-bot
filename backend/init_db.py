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


def has_support_customer_telegram_unique_index():
    inspector = inspect(engine)
    if "support_customers" not in set(inspector.get_table_names()):
        return False

    with engine.connect() as conn:
        indexes = conn.execute(text("PRAGMA index_list('support_customers')")).fetchall()

        for index in indexes:
            index_name = index[1]
            is_unique = bool(index[2])

            if not is_unique:
                continue

            columns = conn.execute(
                text(f"PRAGMA index_info({quote_name(index_name)})")
            ).fetchall()
            column_names = [column[2] for column in columns]

            if column_names == ["telegram_user_id"]:
                return True

    return False


def schema_needs_migration():
    existing_tables, existing_columns = get_existing_schema()

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            return True

        current_columns = existing_columns.get(table.name, set())
        for column in table.columns:
            if column.name not in current_columns:
                return True

    if has_support_customer_telegram_unique_index():
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


def drop_support_customer_telegram_unique_index():
    inspector = inspect(engine)
    if "support_customers" not in set(inspector.get_table_names()):
        return

    with engine.begin() as conn:
        indexes = conn.execute(text("PRAGMA index_list('support_customers')")).fetchall()

        for index in indexes:
            index_name = index[1]
            is_unique = bool(index[2])

            if not is_unique:
                continue

            columns = conn.execute(
                text(f"PRAGMA index_info({quote_name(index_name)})")
            ).fetchall()
            column_names = [column[2] for column in columns]

            if column_names == ["telegram_user_id"]:
                try:
                    conn.execute(text(f"DROP INDEX {quote_name(index_name)}"))
                    print(f"dropped unique index: support_customers.{index_name}")
                except Exception:
                    rebuild_support_customers_without_unique_index(conn)
                    print("rebuilt table: support_customers without telegram_user_id unique index")
                    return


def rebuild_support_customers_without_unique_index(conn):
    conn.execute(text("DROP TABLE IF EXISTS support_customers_new"))
    conn.execute(text("""
        CREATE TABLE support_customers_new (
            id INTEGER NOT NULL PRIMARY KEY,
            support_bot_id INTEGER,
            telegram_user_id VARCHAR NOT NULL,
            telegram_chat_id VARCHAR NOT NULL,
            username VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            language_code VARCHAR,
            source VARCHAR,
            status VARCHAR,
            blocked BOOLEAN,
            created_at DATETIME,
            last_message_at DATETIME,
            updated_at DATETIME
        )
    """))
    conn.execute(text("""
        INSERT INTO support_customers_new (
            id,
            support_bot_id,
            telegram_user_id,
            telegram_chat_id,
            username,
            first_name,
            last_name,
            language_code,
            source,
            status,
            blocked,
            created_at,
            last_message_at,
            updated_at
        )
        SELECT
            id,
            support_bot_id,
            telegram_user_id,
            telegram_chat_id,
            username,
            first_name,
            last_name,
            language_code,
            source,
            status,
            blocked,
            created_at,
            last_message_at,
            updated_at
        FROM support_customers
    """))
    conn.execute(text("DROP TABLE support_customers"))
    conn.execute(text("ALTER TABLE support_customers_new RENAME TO support_customers"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_support_bot_id ON support_customers (support_bot_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_telegram_user_id ON support_customers (telegram_user_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_telegram_chat_id ON support_customers (telegram_chat_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_username ON support_customers (username)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_source ON support_customers (source)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_status ON support_customers (status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_blocked ON support_customers (blocked)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_last_message_at ON support_customers (last_message_at)"))


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
    drop_support_customer_telegram_unique_index()
    ensure_defaults()

    if backup_path:
        print(f"database backup: {backup_path}")

    print("database initialized")


def main():
    init_db()


if __name__ == "__main__":
    main()
