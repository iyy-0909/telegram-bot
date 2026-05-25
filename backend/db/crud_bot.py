from db.database import SessionLocal
from db.models import BotAccount, TargetBotBinding
from sqlalchemy import func


def normalize_target_channel(target_channel: str) -> str:
    """
    Normalize target channel keys used for Bot binding lookup.

    Supported:
    @channel
    https://t.me/channel
    http://t.me/channel
    t.me/channel
    -100xxxxxxxxxx
    """
    value = (target_channel or "").strip()

    if not value:
        return ""

    for prefix in [
        "https://t.me/",
        "http://t.me/",
        "t.me/",
    ]:
        if value.startswith(prefix):
            name = value.replace(prefix, "", 1).strip("/")
            name = name.split("?", 1)[0].split("#", 1)[0].strip("/")

            if "/" in name:
                name = name.split("/", 1)[0]

            if not name:
                return ""

            if name.startswith("+") or name in ["c", "joinchat"]:
                return value

            return f"@{name.lower()}"

    if value.startswith("@"):
        return f"@{value[1:].strip().lower()}"

    return value


def build_target_lookup_keys(target_channel: str):
    raw_target = str(target_channel or "").strip()
    normalized_target = normalize_target_channel(raw_target)

    keys = {
        raw_target.lower(),
        raw_target.rstrip("/").lower(),
        normalized_target.lower(),
    }

    if normalized_target.startswith("@"):
        username = normalized_target[1:]

        keys.update(
            {
                f"https://t.me/{username}",
                f"http://t.me/{username}",
                f"t.me/{username}",
                f"https://t.me/{username}/",
                f"http://t.me/{username}/",
                f"t.me/{username}/",
            }
        )

    return [
        key
        for key in keys
        if key
    ]


# =========================
# Bot 账号管理
# =========================

def get_all_bots():
    db = SessionLocal()

    try:
        return db.query(BotAccount).all()
    finally:
        db.close()


def get_enabled_bots():
    db = SessionLocal()

    try:
        return (
            db.query(BotAccount)
            .filter(BotAccount.enabled == True)
            .all()
        )
    finally:
        db.close()


def get_bot(bot_id: int):
    db = SessionLocal()

    try:
        return (
            db.query(BotAccount)
            .filter(BotAccount.id == bot_id)
            .first()
        )
    finally:
        db.close()


def create_bot(data: dict):
    db = SessionLocal()

    try:
        bot = BotAccount(
            name=data.get("name", ""),
            token=(data.get("token", "") or "").strip(),
            enabled=data.get("enabled", True),
            remark=data.get("remark", ""),
            last_error="",
        )

        db.add(bot)
        db.commit()
        db.refresh(bot)

        return bot

    finally:
        db.close()


def update_bot(bot_id: int, data: dict):
    db = SessionLocal()

    try:
        bot = (
            db.query(BotAccount)
            .filter(BotAccount.id == bot_id)
            .first()
        )

        if not bot:
            return None

        for key, value in data.items():
            if key == "token":
                value = (value or "").strip()

            if hasattr(bot, key):
                setattr(bot, key, value)

        db.commit()
        db.refresh(bot)

        return bot

    finally:
        db.close()


def delete_bot(bot_id: int):
    db = SessionLocal()

    try:
        bot = (
            db.query(BotAccount)
            .filter(BotAccount.id == bot_id)
            .first()
        )

        if not bot:
            return False

        # 删除 Bot 时，同时删除目标频道绑定
        db.query(TargetBotBinding).filter(
            TargetBotBinding.bot_id == bot_id
        ).delete()

        db.delete(bot)
        db.commit()

        return True

    finally:
        db.close()


def update_bot_error(bot_id: int, error: str):
    db = SessionLocal()

    try:
        bot = (
            db.query(BotAccount)
            .filter(BotAccount.id == bot_id)
            .first()
        )

        if not bot:
            return False

        bot.last_error = error or ""
        db.commit()

        return True

    finally:
        db.close()


# =========================
# 目标频道绑定 Bot
# =========================

def get_all_bindings():
    db = SessionLocal()

    try:
        return db.query(TargetBotBinding).all()
    finally:
        db.close()


def get_binding(binding_id: int):
    db = SessionLocal()

    try:
        return (
            db.query(TargetBotBinding)
            .filter(TargetBotBinding.id == binding_id)
            .first()
        )
    finally:
        db.close()


def get_binding_by_target(target_channel: str):
    db = SessionLocal()

    try:
        lookup_keys = build_target_lookup_keys(target_channel)

        return (
            db.query(TargetBotBinding)
            .filter(
                func.lower(func.trim(TargetBotBinding.target_channel)).in_(
                    lookup_keys
                ),
                TargetBotBinding.enabled == True,
            )
            .first()
        )
    finally:
        db.close()


def create_binding(data: dict):
    db = SessionLocal()

    try:
        binding = TargetBotBinding(
            target_channel=normalize_target_channel(
                data.get("target_channel", "")
            ),
            bot_id=data.get("bot_id"),
            enabled=data.get("enabled", True),
            remark=data.get("remark", ""),
        )

        db.add(binding)
        db.commit()
        db.refresh(binding)

        return binding

    finally:
        db.close()


def update_binding(binding_id: int, data: dict):
    db = SessionLocal()

    try:
        binding = (
            db.query(TargetBotBinding)
            .filter(TargetBotBinding.id == binding_id)
            .first()
        )

        if not binding:
            return None

        for key, value in data.items():
            if key == "target_channel":
                value = normalize_target_channel(value)

            if hasattr(binding, key):
                setattr(binding, key, value)

        db.commit()
        db.refresh(binding)

        return binding

    finally:
        db.close()


def delete_binding(binding_id: int):
    db = SessionLocal()

    try:
        binding = (
            db.query(TargetBotBinding)
            .filter(TargetBotBinding.id == binding_id)
            .first()
        )

        if not binding:
            return False

        db.delete(binding)
        db.commit()

        return True

    finally:
        db.close()


# =========================
# 分发时查询 Bot
# =========================

def get_bot_for_target(target_channel: str):
    """
    根据目标频道查绑定的 Bot。

    第一版逻辑：
    1. 优先使用 target_bot_bindings 绑定的 Bot
    2. 如果没绑定，返回第一个 enabled Bot
    """
    db = SessionLocal()

    try:
        lookup_keys = build_target_lookup_keys(target_channel)

        binding = (
            db.query(TargetBotBinding)
            .filter(
                func.lower(func.trim(TargetBotBinding.target_channel)).in_(
                    lookup_keys
                ),
                TargetBotBinding.enabled == True,
            )
            .first()
        )

        if binding:
            bot = (
                db.query(BotAccount)
                .filter(
                    BotAccount.id == binding.bot_id,
                    BotAccount.enabled == True,
                )
                .first()
            )

            if bot:
                return bot

        return (
            db.query(BotAccount)
            .filter(BotAccount.enabled == True)
            .first()
        )

    finally:
        db.close()
