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
        f"clonebot.db.bak_content_templates_migration_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def add_column_if_missing(conn, table, column, ddl):
    columns = {item["name"] for item in inspect(conn).get_columns(table)}

    if column not in columns:
        conn.execute(text(ddl))
        print(f"已添加字段：{table}.{column}")


def main():
    backup_path = backup_db()
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        add_column_if_missing(
            conn,
            "clone_tasks",
            "use_random_head",
            "ALTER TABLE clone_tasks ADD COLUMN use_random_head BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "use_random_body",
            "ALTER TABLE clone_tasks ADD COLUMN use_random_body BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "use_random_footer",
            "ALTER TABLE clone_tasks ADD COLUMN use_random_footer BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "selected_head_template_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_head_template_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "selected_body_template_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_body_template_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "clone_tasks",
            "selected_footer_template_id",
            "ALTER TABLE clone_tasks ADD COLUMN selected_footer_template_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "use_random_head",
            "ALTER TABLE listener_tasks ADD COLUMN use_random_head BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "use_random_body",
            "ALTER TABLE listener_tasks ADD COLUMN use_random_body BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "use_random_footer",
            "ALTER TABLE listener_tasks ADD COLUMN use_random_footer BOOLEAN DEFAULT 0",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "selected_head_template_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_head_template_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "selected_body_template_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_body_template_id INTEGER",
        )
        add_column_if_missing(
            conn,
            "listener_tasks",
            "selected_footer_template_id",
            "ALTER TABLE listener_tasks ADD COLUMN selected_footer_template_id INTEGER",
        )

    if backup_path:
        print(f"数据库已备份：{backup_path}")

    print("内容模板表迁移完成")


if __name__ == "__main__":
    main()
