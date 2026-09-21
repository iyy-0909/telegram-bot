import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable

from accounts.session_storage import (
    SessionPathError,
    generate_owner_session_path,
    normalize_session_path,
    resolve_legacy_session_path,
    resolve_owner_session_path,
    session_file_path,
    session_journal_path,
    session_path_key,
    stored_owner_session_path,
)
from auth.access import PLAN_PAID, dump_feature_keys_json, plan_feature_keys
from auth.security import hash_password
from bot.support_media import (
    is_uploaded_media_ref,
    migrate_legacy_uploaded_media_ref,
    validate_uploaded_media_ref,
)
from db.database import SessionLocal, engine
from db.models import Base, UserAccount
from init_db import ensure_defaults_for_owner, get_sqlite_db_path, init_db


CONFIRMATION = "SINGLE_ADMIN_OWNERSHIP"
OWNED_UNIQUE_TABLES = tuple(
    table.name
    for table in Base.metadata.sorted_tables
    if "owner_user_id" in table.c
)
REFERENCE_RULES = (
    ("channel_rules", "account_id", "accounts"),
    ("channel_rules", "clone_task_id", "clone_tasks"),
    ("account_auto_reply_states", "account_id", "accounts"),
    ("notification_account_settings", "account_id", "accounts"),
    ("clone_tasks", "account_id", "accounts"),
    ("clone_tasks", "bot_id", "bot_accounts"),
    ("clone_tasks", "ai_prompt_template_id", "ai_prompt_templates"),
    ("clone_tasks", "selected_head_template_group_id", "content_templates"),
    ("clone_tasks", "selected_body_template_group_id", "content_templates"),
    ("clone_tasks", "selected_footer_template_group_id", "content_templates"),
    ("clone_tasks", "selected_filter_template_group_id", "content_templates"),
    ("clone_tasks", "selected_link_template_group_id", "content_templates"),
    ("clone_tasks", "selected_contact_template_group_id", "content_templates"),
    ("clone_tasks", "selected_head_template_id", "content_templates"),
    ("clone_tasks", "selected_body_template_id", "content_templates"),
    ("clone_tasks", "selected_footer_template_id", "content_templates"),
    ("listener_tasks", "account_id", "accounts"),
    ("listener_tasks", "clone_task_id", "clone_tasks"),
    ("listener_tasks", "bot_id", "bot_accounts"),
    ("listener_tasks", "ai_prompt_template_id", "ai_prompt_templates"),
    ("listener_tasks", "selected_head_template_group_id", "content_templates"),
    ("listener_tasks", "selected_body_template_group_id", "content_templates"),
    ("listener_tasks", "selected_footer_template_group_id", "content_templates"),
    ("listener_tasks", "selected_filter_template_group_id", "content_templates"),
    ("listener_tasks", "selected_link_template_group_id", "content_templates"),
    ("listener_tasks", "selected_contact_template_group_id", "content_templates"),
    ("listener_tasks", "selected_head_template_id", "content_templates"),
    ("listener_tasks", "selected_body_template_id", "content_templates"),
    ("listener_tasks", "selected_footer_template_id", "content_templates"),
    ("sent_messages", "task_id", "clone_tasks"),
    ("listener_sent_messages", "listener_task_id", "listener_tasks"),
    ("clone_send_events", "task_id", "clone_tasks"),
    ("clone_send_events", "bot_id", "bot_accounts"),
    ("listener_send_events", "task_id", "listener_tasks"),
    ("listener_send_events", "account_id", "accounts"),
    ("listener_send_events", "bot_id", "bot_accounts"),
    ("bulk_replace_job_items", "job_id", "bulk_replace_jobs"),
    ("target_bot_bindings", "bot_id", "bot_accounts"),
    ("my_channels", "bot_id", "bot_accounts"),
    ("search_bots", "account_id", "accounts"),
    ("search_bot_channel_submissions", "search_bot_id", "search_bots"),
    ("search_bot_channel_submissions", "my_channel_id", "my_channels"),
    ("search_bot_channel_submissions", "account_id", "accounts"),
    ("support_bots", "bot_id", "bot_accounts"),
    ("support_customers", "support_bot_id", "support_bots"),
    ("support_conversations", "support_bot_id", "support_bots"),
    ("support_conversations", "customer_id", "support_customers"),
    ("support_messages", "support_bot_id", "support_bots"),
    ("support_messages", "conversation_id", "support_conversations"),
    ("support_messages", "customer_id", "support_customers"),
    ("support_customer_tags", "customer_id", "support_customers"),
    ("support_customer_tags", "tag_id", "support_tags"),
    ("control_ack_alerts", "support_bot_id", "support_bots"),
    ("control_ack_alerts", "customer_id", "support_customers"),
    ("control_ack_alerts", "conversation_id", "support_conversations"),
)


def quote_name(value):
    return '"' + str(value).replace('"', '""') + '"'


def sqlite_path():
    path = get_sqlite_db_path()
    if path is None:
        raise RuntimeError("当前迁移程序仅支持 SQLite")
    return Path(path)


def existing_usernames(path):
    if not path.exists():
        return []
    connection = sqlite3.connect(path)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_accounts'"
        ).fetchone()
        if not exists:
            return []
        return [row[0] for row in connection.execute(
            "SELECT username FROM user_accounts ORDER BY id"
        ).fetchall()]
    finally:
        connection.close()


def backup_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = path.with_name(
        f"{path.name}.bak_single_admin_{datetime.now():%Y%m%d_%H%M%S}"
    )
    source = sqlite3.connect(path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def table_counts(path):
    if not path.exists():
        return {}
    connection = sqlite3.connect(path)
    try:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        return {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {quote_name(table)}"
            ).fetchone()[0]
            for table in tables
        }
    finally:
        connection.close()


def ensure_single_admin(username, password):
    db = SessionLocal()
    try:
        users = db.query(UserAccount).order_by(UserAccount.id.asc()).all()
        if len(users) > 1:
            raise RuntimeError("数据库存在多个后台账号，拒绝统一迁移")
        if users:
            admin = users[0]
            admin.username = username
        else:
            admin = UserAccount(username=username)
            db.add(admin)
        admin.password_hash = hash_password(password)
        admin.role = "admin"
        admin.status = "active"
        admin.plan_tier = PLAN_PAID
        admin.feature_keys_json = dump_feature_keys_json(plan_feature_keys(PLAN_PAID))
        admin.access_expires_at = None
        admin.failed_login_count = 0
        admin.locked_until = None
        admin.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(admin)
        return int(admin.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def revoke_existing_sessions(path):
    connection = sqlite3.connect(path)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_sessions'"
        ).fetchone()
        if not table_exists:
            return 0
        cursor = connection.execute("DELETE FROM user_sessions")
        connection.commit()
        return int(cursor.rowcount or 0)
    finally:
        connection.close()


def backfill_all_owners(path, admin_id, username):
    connection = sqlite3.connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        updated = {}
        for table in tables:
            columns = {
                row[1] for row in connection.execute(
                    f"PRAGMA table_info({quote_name(table)})"
                )
            }
            if "owner_user_id" not in columns:
                continue
            cursor = connection.execute(
                f"UPDATE {quote_name(table)} SET owner_user_id = ?",
                (admin_id,),
            )
            updated[table] = int(cursor.rowcount or 0)
        if "daily_advertisement_deliveries" in tables:
            connection.execute(
                "UPDATE daily_advertisement_deliveries SET user_id = ?",
                (admin_id,),
            )
        if "support_conversations" in tables:
            connection.execute(
                "UPDATE support_conversations SET assigned_admin_id = ? WHERE assigned_admin_id IS NOT NULL",
                (admin_id,),
            )
        if "bulk_replace_jobs" in tables:
            connection.execute(
                "UPDATE bulk_replace_jobs SET created_by = ?",
                (username,),
            )
        connection.commit()
        return updated
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def account_session_rows(path):
    connection = sqlite3.connect(path)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'"
        ).fetchone()
        if not table_exists:
            return []
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info('accounts')")
        }
        if "session_path" not in columns:
            return []
        return connection.execute(
            "SELECT id, session_path FROM accounts ORDER BY id"
        ).fetchall()
    finally:
        connection.close()


def duplicate_account_session_paths(path):
    seen = {}
    duplicates = {}
    for account_id, raw_path in account_session_rows(path):
        if not normalize_session_path(raw_path):
            duplicates.setdefault("<empty>", []).append(int(account_id))
            continue
        key = session_path_key(raw_path, backend_dir=BACKEND_DIR)
        if key in seen:
            duplicates.setdefault(key, [seen[key]]).append(int(account_id))
        else:
            seen[key] = int(account_id)
    return list(duplicates.values())


def migrate_account_session_files(path, admin_id):
    """Copy legacy session files into one tenant directory and retain originals."""
    rows = account_session_rows(path)
    duplicates = duplicate_account_session_paths(path)
    if duplicates:
        duplicate_ids = ", ".join(
            "/".join(str(account_id) for account_id in group)
            for group in duplicates
        )
        raise RuntimeError(f"检测到重复 Telegram Session 路径，涉及账号: {duplicate_ids}")

    occupied_paths = [raw_path for _account_id, raw_path in rows]
    updates = []
    copied_session_files = 0
    copied_journal_files = 0
    missing_session_files = 0
    already_isolated = 0

    for account_id, raw_path in rows:
        if not normalize_session_path(raw_path):
            raise RuntimeError(f"账号 {account_id} 的 Telegram Session 路径为空")
        try:
            current_path = resolve_owner_session_path(
                admin_id,
                raw_path,
                create_parent=True,
            )
        except SessionPathError:
            current_path = None

        if current_path is not None:
            stored_path = stored_owner_session_path(admin_id, current_path)
            updates.append((stored_path, int(account_id)))
            occupied_paths.append(stored_path)
            already_isolated += 1
            continue

        source_path = resolve_legacy_session_path(raw_path, backend_dir=BACKEND_DIR)
        destination_stored = generate_owner_session_path(
            admin_id,
            occupied_paths=occupied_paths,
        )
        destination_path = resolve_owner_session_path(
            admin_id,
            destination_stored,
            create_parent=True,
        )
        occupied_paths.append(destination_stored)

        source_file = session_file_path(source_path)
        destination_file = session_file_path(destination_path)
        source_journal = session_journal_path(source_path)
        destination_journal = session_journal_path(destination_path)
        if destination_file.exists() or destination_journal.exists():
            raise RuntimeError("新 Telegram Session 路径发生冲突，迁移已停止")

        if source_file.exists():
            shutil.copy2(source_file, destination_file)
            copied_session_files += 1
        else:
            missing_session_files += 1
        if source_journal.exists():
            shutil.copy2(source_journal, destination_journal)
            copied_journal_files += 1
        updates.append((destination_stored, int(account_id)))

    connection = sqlite3.connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "UPDATE accounts SET session_path = ? WHERE id = ?",
            updates,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return {
        "account_count": len(rows),
        "already_isolated": already_isolated,
        "migrated": len(rows) - already_isolated,
        "copied_session_files": copied_session_files,
        "copied_journal_files": copied_journal_files,
        "missing_session_files": missing_session_files,
        "legacy_files_retained": True,
    }


def support_media_rows(path):
    connection = sqlite3.connect(path)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='support_bots'"
        ).fetchone()
        if not table_exists:
            return []
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info('support_bots')")
        }
        if "welcome_media_file_id" not in columns:
            return []
        return connection.execute(
            "SELECT id, welcome_media_file_id FROM support_bots ORDER BY id"
        ).fetchall()
    finally:
        connection.close()


def migrate_support_media_refs(path, admin_id):
    """Copy legacy support uploads into the admin tenant and retain originals."""
    rows = support_media_rows(path)
    updates = []
    uploaded_refs = 0
    already_isolated = 0
    for support_bot_id, media_ref in rows:
        value = str(media_ref or "").strip()
        if not is_uploaded_media_ref(value):
            continue
        uploaded_refs += 1
        migrated_ref = migrate_legacy_uploaded_media_ref(value, admin_id)
        if migrated_ref == value:
            already_isolated += 1
            continue
        updates.append((migrated_ref, int(support_bot_id)))

    if updates:
        connection = sqlite3.connect(path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                "UPDATE support_bots SET welcome_media_file_id = ? WHERE id = ?",
                updates,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    return {
        "support_bot_count": len(rows),
        "uploaded_reference_count": uploaded_refs,
        "migrated": len(updates),
        "already_isolated": already_isolated,
        "legacy_files_retained": True,
    }


def rebuild_owned_unique_tables(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=OFF")
    rebuilt = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing_tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for table_name in OWNED_UNIQUE_TABLES:
            if table_name not in existing_tables:
                continue
            model_table = Base.metadata.tables[table_name]
            temporary_name = f"__tenant_new_{table_name}"
            connection.execute(f"DROP TABLE IF EXISTS {quote_name(temporary_name)}")
            temporary_table = model_table.to_metadata(MetaData(), name=temporary_name)
            connection.execute(str(CreateTable(temporary_table).compile(engine)))
            existing_columns = {
                row[1] for row in connection.execute(
                    f"PRAGMA table_info({quote_name(table_name)})"
                )
            }
            columns = [column.name for column in model_table.columns if column.name in existing_columns]
            column_sql = ", ".join(quote_name(column) for column in columns)
            connection.execute(
                f"INSERT INTO {quote_name(temporary_name)} ({column_sql}) "
                f"SELECT {column_sql} FROM {quote_name(table_name)}"
            )
            connection.execute(f"DROP TABLE {quote_name(table_name)}")
            connection.execute(
                f"ALTER TABLE {quote_name(temporary_name)} RENAME TO {quote_name(table_name)}"
            )
            for index in model_table.indexes:
                connection.execute(str(CreateIndex(index).compile(engine)))
            rebuilt.append(table_name)
        connection.commit()
        return rebuilt
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()


def ensure_owner_indexes(path):
    connection = sqlite3.connect(path)
    created = []
    try:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        for table in tables:
            columns = {
                row[1] for row in connection.execute(
                    f"PRAGMA table_info({quote_name(table)})"
                )
            }
            if "owner_user_id" not in columns:
                continue
            index_name = f"ix_{table}_owner_user_id"
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {quote_name(index_name)} "
                f"ON {quote_name(table)} (owner_user_id)"
            )
            created.append(index_name)
        connection.commit()
        return created
    finally:
        connection.close()


def collect_reference_errors(path):
    """Count broken owned-resource references without mutating the database."""
    connection = sqlite3.connect(path)
    try:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        table_columns = {
            table: {
                row[1]
                for row in connection.execute(
                    f"PRAGMA table_info({quote_name(table)})"
                )
            }
            for table in tables
        }
        errors = {}
        for child, field, parent in REFERENCE_RULES:
            if child not in table_columns or parent not in table_columns:
                continue
            if field not in table_columns[child]:
                continue

            invalid_conditions = ["p.id IS NULL"]
            if (
                "owner_user_id" in table_columns[child]
                and "owner_user_id" in table_columns[parent]
            ):
                invalid_conditions.append(
                    "c.owner_user_id != p.owner_user_id"
                )
            error_count = connection.execute(
                f"SELECT COUNT(*) FROM {quote_name(child)} c "
                f"LEFT JOIN {quote_name(parent)} p ON p.id = c.{quote_name(field)} "
                f"WHERE c.{quote_name(field)} IS NOT NULL "
                f"AND c.{quote_name(field)} != 0 "
                f"AND ({' OR '.join(invalid_conditions)})"
            ).fetchone()[0]
            if error_count:
                errors[f"{child}.{field}->{parent}"] = int(error_count)
        return errors
    finally:
        connection.close()


def compare_reference_errors(baseline, current):
    """Return only newly introduced or increased reference-error counts."""
    baseline = {
        str(key): int(value or 0)
        for key, value in (baseline or {}).items()
        if int(value or 0) > 0
    }
    current = {
        str(key): int(value or 0)
        for key, value in (current or {}).items()
        if int(value or 0) > 0
    }
    return {
        key: {
            "baseline": int(baseline.get(key, 0)),
            "current": count,
            "increase": count - int(baseline.get(key, 0)),
        }
        for key, count in sorted(current.items())
        if count > int(baseline.get(key, 0))
    }


def verify_database(
    path,
    admin_id,
    expected_counts,
    admin_username=None,
    reference_errors_baseline=None,
):
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        users = connection.execute(
            "SELECT id, username, role, status, plan_tier, access_expires_at FROM user_accounts ORDER BY id"
        ).fetchall()
        owner_mismatches = {}
        owner_nullable_tables = []
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        table_columns = {}
        for table in tables:
            column_rows = connection.execute(
                f"PRAGMA table_info({quote_name(table)})"
            ).fetchall()
            columns = {row[1] for row in column_rows}
            table_columns[table] = columns
            if "owner_user_id" in columns:
                owner_column = next(row for row in column_rows if row[1] == "owner_user_id")
                if not bool(owner_column[3]):
                    owner_nullable_tables.append(table)
                mismatch = connection.execute(
                    f"SELECT COUNT(*) FROM {quote_name(table)} WHERE owner_user_id IS NULL OR owner_user_id != ?",
                    (admin_id,),
                ).fetchone()[0]
                if mismatch:
                    owner_mismatches[table] = mismatch

        reference_errors_baseline = {
            str(key): int(value or 0)
            for key, value in (reference_errors_baseline or {}).items()
            if int(value or 0) > 0
        }
        reference_errors_current = collect_reference_errors(path)
        reference_errors_new_or_increased = compare_reference_errors(
            reference_errors_baseline,
            reference_errors_current,
        )

        session_path_errors = []
        session_keys = set()
        if "accounts" in table_columns and "session_path" in table_columns["accounts"]:
            account_sessions = connection.execute(
                "SELECT id, session_path FROM accounts ORDER BY id"
            ).fetchall()
            for account_id, raw_path in account_sessions:
                try:
                    resolved = resolve_owner_session_path(admin_id, raw_path)
                    key = session_path_key(resolved)
                except SessionPathError:
                    session_path_errors.append(int(account_id))
                    continue
                if key in session_keys:
                    session_path_errors.append(int(account_id))
                session_keys.add(key)

        support_media_errors = []
        if (
            "support_bots" in table_columns
            and "welcome_media_file_id" in table_columns["support_bots"]
        ):
            media_rows = connection.execute(
                "SELECT id, welcome_media_file_id FROM support_bots ORDER BY id"
            ).fetchall()
            for support_bot_id, media_ref in media_rows:
                value = str(media_ref or "").strip()
                if not is_uploaded_media_ref(value):
                    continue
                try:
                    validate_uploaded_media_ref(value, owner_user_id=admin_id)
                except Exception:
                    support_media_errors.append(int(support_bot_id))

        counts_after = table_counts(path)
        changed_counts = {
            table: {"before": count, "after": counts_after.get(table)}
            for table, count in expected_counts.items()
            if table != "user_accounts" and counts_after.get(table) != count
        }
        ok = (
            integrity == "ok"
            and len(users) == 1
            and users[0][0] == admin_id
            and (admin_username is None or users[0][1] == admin_username)
            and users[0][2] == "admin"
            and users[0][3] == "active"
            and users[0][4] == PLAN_PAID
            and users[0][5] is None
            and not owner_mismatches
            and not owner_nullable_tables
            and not reference_errors_new_or_increased
            and not session_path_errors
            and not support_media_errors
            and not changed_counts
        )
        return {
            "ok": ok,
            "integrity": integrity,
            "users": [
                {
                    "id": row[0],
                    "username": row[1],
                    "role": row[2],
                    "status": row[3],
                    "plan_tier": row[4],
                    "access_expires_at": row[5],
                }
                for row in users
            ],
            "owner_mismatches": owner_mismatches,
            "owner_nullable_tables": owner_nullable_tables,
            "reference_errors": {
                "baseline": reference_errors_baseline,
                "current": reference_errors_current,
                "new_or_increased": reference_errors_new_or_increased,
            },
            "session_path_errors": session_path_errors,
            "support_media_errors": support_media_errors,
            "changed_counts": changed_counts,
            "counts": counts_after,
        }
    finally:
        connection.close()


def write_report(path, payload):
    report_path = path.with_name(
        f"single-admin-migration-{datetime.now():%Y%m%d-%H%M%S}.json"
    )
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return report_path


def main():
    parser = argparse.ArgumentParser(description="单一最高管理员资源归属迁移")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--admin-username", required=True)
    parser.add_argument("--password-env", default="MIGRATION_ADMIN_PASSWORD")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--revoke-existing-sessions",
        action="store_true",
        help="显式撤销迁移前已有的后台登录会话；默认全部保留",
    )
    args = parser.parse_args()

    path = sqlite_path()
    before_counts = table_counts(path)
    reference_errors_baseline = collect_reference_errors(path)
    users_before = existing_usernames(path)
    too_many_users = len(users_before) > 1
    duplicate_session_accounts = duplicate_account_session_paths(path)
    preview = {
        "mode": "dry-run" if args.dry_run else "execute",
        "database": str(path),
        "admin_username": args.admin_username,
        "users_before": users_before,
        "existing_user_action": (
            "create" if not users_before
            else "rename_and_upgrade" if len(users_before) == 1
            else "reject"
        ),
        "duplicate_session_account_ids": duplicate_session_accounts,
        "revoke_existing_sessions": bool(args.revoke_existing_sessions),
        "counts_before": before_counts,
        "reference_errors_baseline": reference_errors_baseline,
    }
    if args.dry_run:
        preview["ready"] = not too_many_users and not duplicate_session_accounts
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0 if preview["ready"] else 2

    if args.confirm != CONFIRMATION:
        raise RuntimeError(f"执行迁移必须提供 --confirm {CONFIRMATION}")
    if too_many_users:
        raise RuntimeError("检测到多个后台账号，已拒绝迁移")
    if duplicate_session_accounts:
        raise RuntimeError("检测到重复 Telegram Session 路径，已拒绝迁移")
    password = os.getenv(args.password_env, "")
    if not password:
        raise RuntimeError(f"环境变量 {args.password_env} 未设置")

    backup_path = backup_database(path)
    init_db(allow_legacy_unowned=True)
    admin_id = ensure_single_admin(args.admin_username, password)
    updated = backfill_all_owners(path, admin_id, args.admin_username)
    ensure_defaults_for_owner(admin_id)
    post_schema_counts = table_counts(path)
    session_migration = migrate_account_session_files(path, admin_id)
    support_media_migration = migrate_support_media_refs(path, admin_id)
    revoked_session_count = (
        revoke_existing_sessions(path)
        if args.revoke_existing_sessions
        else 0
    )
    rebuilt = rebuild_owned_unique_tables(path)
    owner_indexes = ensure_owner_indexes(path)
    expected_counts = dict(post_schema_counts)
    if args.revoke_existing_sessions and "user_sessions" in expected_counts:
        expected_counts["user_sessions"] = 0
    verification = verify_database(
        path,
        admin_id,
        expected_counts,
        args.admin_username,
        reference_errors_baseline=reference_errors_baseline,
    )
    verification["preexisting_count_losses"] = {
        table: {"before": count, "after": verification["counts"].get(table)}
        for table, count in before_counts.items()
        if not (args.revoke_existing_sessions and table == "user_sessions")
        if (verification["counts"].get(table) or 0) < count
    }
    verification["ok"] = (
        verification["ok"]
        and not verification["preexisting_count_losses"]
    )
    payload = {
        **preview,
        "backup": str(backup_path),
        "admin_id": admin_id,
        "counts_after_schema_upgrade": post_schema_counts,
        "updated_owner_tables": updated,
        "session_migration": session_migration,
        "support_media_migration": support_media_migration,
        "revoked_session_count": revoked_session_count,
        "rebuilt_unique_tables": rebuilt,
        "owner_indexes": owner_indexes,
        "verification": verification,
    }
    report_path = write_report(path, payload)
    payload["report"] = str(report_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not verification["ok"]:
        raise RuntimeError("迁移校验失败，请保持服务停止并恢复备份")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
