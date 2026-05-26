import json

from db.database import Base, SessionLocal, engine
from db.models import CloneTask, ListenerTask, TargetBotBinding
from db.crud_my_channels import upsert_my_channel_from_target


def parse_targets(value):
    if not value:
        return []

    if isinstance(value, list):
        return value

    text = str(value).strip()

    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    return [
        item.strip()
        for item in text.replace("，", ",").replace("\n", ",").split(",")
        if item.strip()
    ]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    imported = 0

    try:
        for task in db.query(CloneTask).all():
            for target in parse_targets(task.target_channels):
                if upsert_my_channel_from_target(target, bot_id=getattr(task, "bot_id", None)):
                    imported += 1

        for task in db.query(ListenerTask).all():
            for target in parse_targets(task.target_channels):
                if upsert_my_channel_from_target(target, bot_id=getattr(task, "bot_id", None)):
                    imported += 1

        for binding in db.query(TargetBotBinding).all():
            if upsert_my_channel_from_target(binding.target_channel, bot_id=binding.bot_id):
                imported += 1

    finally:
        db.close()

    print(f"my_channels migration done, scanned/imported targets: {imported}")


if __name__ == "__main__":
    main()
