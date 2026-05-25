import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.database import engine
from db.models import Base


DB_PATH = Path("data/clonebot.db")


def backup_db():
    if not DB_PATH.exists():
        return None

    backup_path = DB_PATH.with_name(
        f"clonebot.db.bak_template_groups_migration_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def table_columns(conn, table):
    return {item["name"] for item in inspect(conn).get_columns(table)}


def add_column_if_missing(conn, table, column, ddl):
    if column not in table_columns(conn, table):
        conn.execute(text(ddl))
        print(f"added column: {table}.{column}")


def migrate_legacy_flat_templates(conn):
    columns = table_columns(conn, "content_templates")
    if "parent_id" not in columns:
        return

    rows = conn.execute(
        text(
            """
            SELECT id, name, type, content, enabled, weight
            FROM content_templates
            WHERE parent_id IS NULL
              AND TRIM(COALESCE(content, '')) != ''
            ORDER BY id ASC
            """
        )
    ).mappings().all()

    migrated = 0
    for row in rows:
        group_name = row["name"] or f"规则 {row['id']}"
        result = conn.execute(
            text(
                """
                INSERT INTO content_templates
                    (parent_id, name, type, content, enabled, weight, created_at, updated_at)
                VALUES
                    (NULL, :name, :type, '', :enabled, :weight, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "name": group_name,
                "type": row["type"],
                "enabled": row["enabled"],
                "weight": row["weight"] or 1,
            },
        )
        group_id = result.lastrowid
        conn.execute(
            text(
                """
                UPDATE content_templates
                SET parent_id = :group_id,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :item_id
                """
            ),
            {
                "group_id": group_id,
                "item_id": row["id"],
            },
        )
        migrated += 1

    print(f"migrated legacy template items: {migrated}")


def main():
    backup_path = backup_db()
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        add_column_if_missing(
            conn,
            "content_templates",
            "parent_id",
            "ALTER TABLE content_templates ADD COLUMN parent_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "selected_head_template_group_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_head_template_group_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "selected_body_template_group_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_body_template_group_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "selected_footer_template_group_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_footer_template_group_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "selected_head_template_group_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_head_template_group_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "selected_body_template_group_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_body_template_group_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "selected_footer_template_group_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_footer_template_group_id INTEGER",
        )
        migrate_legacy_flat_templates(conn)

    if backup_path:
        print(f"database backup: {backup_path}")

    print("template group migration done")


if __name__ == "__main__":
    main()
