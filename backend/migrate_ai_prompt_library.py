import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db.database import engine, SessionLocal
from db.models import Base, AiPromptTemplate, CloneTask, ListenerTask, SystemSetting
from db.crud_settings import DEFAULT_AI_REWRITE_PROMPT


DB_PATH = Path("data/clonebot.db")


def backup_database():
    if not DB_PATH.exists():
        return None
    backup = DB_PATH.with_name(
        f"clonebot.db.bak_ai_prompt_library_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup)
    return backup


def add_task_columns():
    with engine.begin() as conn:
        for table in ("clone_tasks", "listener_tasks"):
            columns = {item["name"] for item in inspect(conn).get_columns(table)}
            if "ai_prompt_template_id" not in columns:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN ai_prompt_template_id INTEGER"
                ))


def unique_name(db, base):
    name = base
    index = 2
    while db.query(AiPromptTemplate).filter(AiPromptTemplate.name == name).first():
        name = f"{base} {index}"
        index += 1
    return name


def migrate_prompts():
    db = SessionLocal()
    try:
        if not db.query(AiPromptTemplate).filter(
            AiPromptTemplate.is_default == True
        ).first():
            setting = db.query(SystemSetting).filter(
                SystemSetting.key == "ai_default_rewrite_prompt"
            ).first()
            default_content = str(getattr(setting, "value", "") or "").strip()
            prompt = AiPromptTemplate(
                name=unique_name(db, "系统默认提示词"),
                content=default_content or DEFAULT_AI_REWRITE_PROMPT,
                is_default=True,
                enabled=True,
            )
            db.add(prompt)
            db.flush()

        content_to_prompt_id = {
            prompt.content.strip(): prompt.id
            for prompt in db.query(AiPromptTemplate).all()
            if str(prompt.content or "").strip()
        }
        imported_index = 1
        for model, prefix in (
            (CloneTask, "克隆任务迁移提示词"),
            (ListenerTask, "监听任务迁移提示词"),
        ):
            tasks = db.query(model).filter(
                model.ai_rewrite_prompt.isnot(None),
                model.ai_rewrite_prompt != "",
            ).all()
            for task in tasks:
                content = str(task.ai_rewrite_prompt or "").strip()
                if not content:
                    continue
                prompt_id = content_to_prompt_id.get(content)
                if not prompt_id:
                    prompt = AiPromptTemplate(
                        name=unique_name(db, f"{prefix} {imported_index}"),
                        content=content,
                        is_default=False,
                        enabled=True,
                    )
                    imported_index += 1
                    db.add(prompt)
                    db.flush()
                    prompt_id = prompt.id
                    content_to_prompt_id[content] = prompt_id
                task.ai_prompt_template_id = prompt_id
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    backup = backup_database()
    Base.metadata.create_all(bind=engine)
    add_task_columns()
    migrate_prompts()
    if backup:
        print(f"数据库已备份：{backup}")
    print("AI 提示词库迁移完成")


if __name__ == "__main__":
    main()
