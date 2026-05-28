import os


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default=0):
    try:
        return int(str(os.getenv(name, default)).strip() or default)
    except (TypeError, ValueError):
        return default


def split_ids(value):
    return {
        item.strip()
        for item in str(value or "").split(",")
        if item.strip()
    }


def control_config():
    token = os.getenv("CONTROL_BOT_TOKEN", "").strip()
    chat_id = (
        os.getenv("CONTROL_CHAT_ID", "").strip()
        or os.getenv("ALERT_CHAT_ID", "").strip()
    )

    return {
        "enabled": env_bool("CONTROL_BOT_ENABLED", True),
        "token": token,
        "chat_id": chat_id,
        "admin_ids": split_ids(os.getenv("CONTROL_ADMIN_IDS", "")),
        "commands_enabled": env_bool("CONTROL_COMMANDS_ENABLED", True),
        "alerts_enabled": env_bool("CONTROL_ALERTS_ENABLED", True),
        "alert_thread_id": os.getenv("CONTROL_ALERT_THREAD_ID", "").strip(),
        "command_thread_id": os.getenv("CONTROL_COMMAND_THREAD_ID", "").strip(),
        "polling_timeout": max(env_int("CONTROL_POLLING_TIMEOUT", 30), 5),
        "notify_level": os.getenv("CONTROL_NOTIFY_LEVEL", "error").strip().lower() or "error",
        "allow_channel_commands": env_bool("CONTROL_ALLOW_CHANNEL_COMMANDS", False),
    }


def control_is_configured_for_alerts():
    config = control_config()
    return bool(
        config["enabled"]
        and config["alerts_enabled"]
        and config["token"]
        and config["chat_id"]
    )


def control_is_configured_for_commands():
    config = control_config()
    return bool(
        config["enabled"]
        and config["commands_enabled"]
        and config["token"]
        and config["chat_id"]
        and config["admin_ids"]
    )
