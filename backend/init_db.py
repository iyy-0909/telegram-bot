import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import inspect, text

from auth.tenant import tenant_scope
from db.database import Base
from db.database import SessionLocal
from db.database import engine
from db.models import Account
from db.models import AccountAutoReplyState
from db.models import BotAccount
from db.models import ChannelRule
from db.models import CloneChannel
from db.models import CloneSendEvent
from db.models import CloneTask
from db.models import ContentTemplate
from db.models import DailyAdvertisementDelivery
from db.models import ListenerSendEvent
from db.models import ListenerSentMessage
from db.models import ListenerTask
from db.models import MyChannel
from db.models import NotificationAccountSetting
from db.models import SearchBot
from db.models import SearchBotChannelSubmission
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
from db.models import UserAccount
from db.models import UserSession


# Importing the model classes above registers every table on Base.metadata.
_REGISTERED_MODELS = (
    Account,
    AccountAutoReplyState,
    BotAccount,
    ChannelRule,
    CloneChannel,
    CloneSendEvent,
    CloneTask,
    ContentTemplate,
    DailyAdvertisementDelivery,
    ListenerSendEvent,
    ListenerSentMessage,
    ListenerTask,
    MyChannel,
    NotificationAccountSetting,
    SearchBot,
    SearchBotChannelSubmission,
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
    UserAccount,
    UserSession,
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
    inspector = inspect(engine)

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            return True

        current_columns = existing_columns.get(table.name, set())
        for column in table.columns:
            if column.name not in current_columns:
                return True
        if "owner_user_id" in table.c:
            current_owner_column = next(
                (
                    item
                    for item in inspector.get_columns(table.name)
                    if item["name"] == "owner_user_id"
                ),
                None,
            )
            if current_owner_column and current_owner_column.get("nullable", True):
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
            owner_user_id INTEGER,
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
            owner_user_id,
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
            owner_user_id,
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
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_owner_user_id ON support_customers (owner_user_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_support_bot_id ON support_customers (support_bot_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_telegram_user_id ON support_customers (telegram_user_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_telegram_chat_id ON support_customers (telegram_chat_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_username ON support_customers (username)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_source ON support_customers (source)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_status ON support_customers (status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_blocked ON support_customers (blocked)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_support_customers_last_message_at ON support_customers (last_message_at)"))


def ensure_defaults_for_owner(owner_user_id):
    from db.crud import ensure_default_account
    from db.crud_ai_prompts import ensure_default_ai_prompt
    from db.crud_settings import ensure_default_settings
    from db.crud_support import ensure_support_defaults
    from db.crud_templates import ensure_default_contact_rule

    owner_user_id = int(owner_user_id)
    with tenant_scope(owner_user_id, is_admin=False):
        ensure_default_account()
        ensure_default_settings(owner_user_id)
        ensure_default_ai_prompt(owner_user_id=owner_user_id)
        ensure_support_defaults(owner_user_id)
        ensure_default_contact_rule(owner_user_id)


def ensure_defaults():
    """Seed defaults only when every existing resource already has an owner."""
    db = SessionLocal()
    try:
        users = db.query(UserAccount.id).order_by(UserAccount.id.asc()).all()
        if not users:
            return

        for mapper in Base.registry.mappers:
            model = mapper.class_
            if not hasattr(model, "owner_user_id"):
                continue
            if db.query(model.id).filter(model.owner_user_id.is_(None)).first():
                # Legacy databases are backfilled by the explicit ownership
                # migration before any tenant defaults are created.
                return
        owner_ids = [int(row[0]) for row in users]
    finally:
        db.close()

    for owner_user_id in owner_ids:
        ensure_defaults_for_owner(owner_user_id)


def migrate_legacy_user_plans():
    """Map legacy granular grants to the nearest fixed edition once."""
    from auth.access import PLAN_FREE, PLAN_PAID, dump_feature_keys_json, plan_feature_keys

    free_features = set(plan_feature_keys(PLAN_FREE))
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, role, feature_keys_json FROM user_accounts")
        ).mappings().all()
        for row in rows:
            role = str(row.get("role") or "").strip().lower()
            try:
                legacy_features = set(json.loads(row.get("feature_keys_json") or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                legacy_features = set()
            plan_tier = (
                PLAN_PAID
                if role == "admin" or bool(legacy_features - free_features)
                else PLAN_FREE
            )
            conn.execute(
                text(
                    "UPDATE user_accounts "
                    "SET plan_tier = :plan_tier, feature_keys_json = :features "
                    "WHERE id = :user_id"
                ),
                {
                    "plan_tier": plan_tier,
                    "features": dump_feature_keys_json(plan_feature_keys(plan_tier)),
                    "user_id": row["id"],
                },
            )


def find_unowned_resource_counts():
    """Return legacy rows that would bypass tenant isolation."""
    inspector = inspect(engine)
    counts = {}
    with engine.connect() as conn:
        for table_name in inspector.get_table_names():
            columns = {
                item["name"]
                for item in inspector.get_columns(table_name)
            }
            if "owner_user_id" not in columns:
                continue
            count = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {quote_name(table_name)} "
                    "WHERE owner_user_id IS NULL"
                )
            ).scalar_one()
            if count:
                counts[table_name] = int(count)
    return counts


def find_nullable_owner_tables():
    inspector = inspect(engine)
    nullable_tables = []
    for table_name in inspector.get_table_names():
        for column in inspector.get_columns(table_name):
            if column["name"] == "owner_user_id" and column.get("nullable", True):
                nullable_tables.append(table_name)
                break
    return nullable_tables


def init_db(*, allow_legacy_unowned=False):
    from migrate_managed_channels import migrate as migrate_managed_channels
    managed_backup = migrate_managed_channels(engine)
    if managed_backup:
        print(f"Managed channels database backup: {managed_backup}")
    from migrate_channel_activity import migrate as migrate_channel_activity
    activity_backup = migrate_channel_activity(engine)
    if activity_backup:
        print(f"Channel activity database backup: {activity_backup}")
    from migrate_ai_prompt_routing import migrate
    routing_backup = migrate(engine)
    if routing_backup:
        print(f"AI routing database backup: {routing_backup}")
    db_path = get_sqlite_db_path()
    db_existed_before_check = bool(db_path and db_path.exists())
    existing_tables, existing_columns = get_existing_schema()
    migrate_user_plans = (
        "user_accounts" in existing_tables
        and "plan_tier" not in existing_columns.get("user_accounts", set())
    )
    needs_migration = schema_needs_migration()
    backup_path = backup_database_if_needed(
        needs_migration,
        db_existed_before_check,
    )

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    if migrate_user_plans:
        migrate_legacy_user_plans()
    drop_support_customer_telegram_unique_index()

    unowned_counts = find_unowned_resource_counts()
    if unowned_counts and not allow_legacy_unowned:
        tables = ", ".join(sorted(unowned_counts))
        raise RuntimeError(
            "检测到尚未分配归属人的旧数据，服务已拒绝启动；"
            "请先执行单一管理员归属迁移。涉及表：" + tables
        )
    nullable_owner_tables = find_nullable_owner_tables()
    if nullable_owner_tables and not allow_legacy_unowned:
        tables = ", ".join(sorted(nullable_owner_tables))
        raise RuntimeError(
            "检测到归属人字段仍允许为空，服务已拒绝启动；"
            "请先执行单一管理员归属迁移。涉及表：" + tables
        )

    # Validate legacy ownership before querying or creating tenant defaults.
    ensure_defaults()

    if backup_path:
        print(f"database backup: {backup_path}")

    print("database initialized")


def main():
    init_db()


if __name__ == "__main__":
    main()
