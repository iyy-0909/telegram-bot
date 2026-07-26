import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class NotificationConfig:
    enabled: bool
    server: str
    topic: str
    only_unmuted: bool
    request_timeout: float = 10.0
    sync_interval: float = 5.0

    @classmethod
    def from_env(cls):
        return cls(
            enabled=_env_bool("NTFY_ENABLE", False),
            server=os.getenv("NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/"),
            topic=os.getenv("NTFY_TOPIC", "").strip(),
            only_unmuted=_env_bool("NTFY_ONLY_UNMUTED", True),
        )

    @property
    def is_ready(self) -> bool:
        return self.enabled and bool(self.server) and bool(self.topic)
