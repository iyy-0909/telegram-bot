from datetime import datetime, timedelta, timezone


try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


APP_TIMEZONE_NAME = "Asia/Shanghai"
FALLBACK_TIMEZONE = timezone(timedelta(hours=8))


def app_timezone():
    if ZoneInfo:
        try:
            return ZoneInfo(APP_TIMEZONE_NAME)
        except Exception:
            pass

    return FALLBACK_TIMEZONE


def app_now():
    return datetime.now(app_timezone())


def format_app_time(value=None):
    current = value or app_now()

    if current.tzinfo is None:
        current = current.replace(tzinfo=app_timezone())
    else:
        current = current.astimezone(app_timezone())

    return current.strftime("%Y-%m-%d %H:%M:%S")
