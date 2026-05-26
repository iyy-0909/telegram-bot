import os
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/clonebot.db")


def ensure_sqlite_parent_dir(database_url):
    if not database_url.startswith("sqlite:///"):
        return

    db_path = database_url.replace("sqlite:///", "", 1)

    if db_path in {":memory:", ""}:
        return

    if db_path.startswith("./"):
        db_path = db_path[2:]

    Path(unquote(db_path)).parent.mkdir(parents=True, exist_ok=True)


ensure_sqlite_parent_dir(DATABASE_URL)


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()
