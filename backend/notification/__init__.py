__all__ = ["NotificationService", "start_notification_service"]


def start_notification_service(*args, **kwargs):
    from notification.service import start_notification_service as start
    return start(*args, **kwargs)


def __getattr__(name):
    if name == "NotificationService":
        from notification.service import NotificationService
        return NotificationService
    raise AttributeError(name)
