import time
import uuid
from collections import OrderedDict, deque
from datetime import datetime, timedelta


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def future_text(seconds):
    return (datetime.now() + timedelta(seconds=max(float(seconds or 0), 0))).strftime("%Y-%m-%d %H:%M:%S")


class RuntimeQueueState:
    def __init__(self, max_recent=100):
        self.max_recent = max_recent
        self.waiting = OrderedDict()
        self.current = None
        self.recent = deque(maxlen=max_recent)

    def add_waiting(self, meta=None):
        item_id = uuid.uuid4().hex
        item = {
            "id": item_id,
            "source_type": "",
            "task_id": None,
            "task_name": "",
            "source_channel": "",
            "target_channel": "",
            "source_message_id": None,
            "grouped_id": None,
            "message_type": "",
            "status": "waiting",
            "reason": "等待全局发送队列",
            "queued_at": now_text(),
            "started_at": "",
            "finished_at": "",
            "estimated_send_at": "",
            "estimated_send_remaining_seconds": None,
            "error": "",
            "_queued_monotonic": time.monotonic(),
            "_estimated_send_monotonic": None,
        }
        item.update(meta or {})
        item["id"] = item_id
        item["status"] = "waiting"
        self._apply_estimated_send(item)
        self.waiting[item_id] = item
        return item_id

    def mark_current(self, item_id, reason=""):
        item = self.waiting.pop(item_id, None)
        if item is None and self.current and self.current.get("id") == item_id:
            item = self.current
        if item is None:
            return None

        item["status"] = "rate_limited"
        item["reason"] = reason or "全局发送间隔"
        item["started_at"] = item.get("started_at") or now_text()
        self.current = item
        return item

    def mark_sending(self, item_id):
        if not self.current or self.current.get("id") != item_id:
            return None

        self.current["status"] = "sending"
        self.current["reason"] = "正在调用 Bot API"
        self.current["started_at"] = self.current.get("started_at") or now_text()
        self.current["estimated_send_at"] = ""
        self.current["estimated_send_remaining_seconds"] = None
        self.current["_estimated_send_monotonic"] = None
        return self.current

    def finish(self, item_id, success=False, error=""):
        item = None
        if self.current and self.current.get("id") == item_id:
            item = self.current
            self.current = None
        else:
            item = self.waiting.pop(item_id, None)

        if item is None:
            return None

        item["status"] = "success" if success else "failed"
        item["reason"] = "已完成" if success else "发送失败"
        item["finished_at"] = now_text()
        item["error"] = str(error or "")
        item.pop("_queued_monotonic", None)
        self.recent.appendleft(item)
        return item

    def cancel(self, item_id, reason="已取消"):
        item = self.waiting.pop(item_id, None)
        if item is None and self.current and self.current.get("id") == item_id:
            item = self.current
            self.current = None
        if item is None:
            return None
        item["status"] = "cancelled"
        item["reason"] = reason
        item["finished_at"] = now_text()
        item.pop("_queued_monotonic", None)
        self.recent.appendleft(item)
        return item

    def remove_waiting(self, item_id):
        item = self.waiting.pop(item_id, None)
        if item is None:
            return None

        item.pop("_queued_monotonic", None)
        item.pop("_estimated_send_monotonic", None)
        return item

    def update_current(self, **fields):
        if not self.current:
            return None
        if "estimated_send_remaining_seconds" in fields:
            seconds = fields.get("estimated_send_remaining_seconds")
            self._apply_estimated_send(self.current, seconds)
        self.current.update(fields)
        return self.current

    def _apply_estimated_send(self, item, seconds=None):
        if seconds is None:
            seconds = item.get("estimated_send_remaining_seconds")

        if seconds is None:
            item["_estimated_send_monotonic"] = None
            item["estimated_send_at"] = item.get("estimated_send_at") or ""
            return

        seconds = max(float(seconds or 0), 0)
        item["_estimated_send_monotonic"] = time.monotonic() + seconds
        item["estimated_send_at"] = future_text(seconds)
        item["estimated_send_remaining_seconds"] = seconds

    def snapshot(self):
        waiting = list(self.waiting.values())
        recent = list(self.recent)

        return {
            "current": self._public_item(self.current) if self.current else None,
            "waiting": [self._public_item(item) for item in waiting],
            "recent": [self._public_item(item) for item in recent],
            "stats": {
                "waiting_count": len(waiting),
                "sending_count": 1 if self.current else 0,
                "recent_count": len(recent),
                "failed_count": len([
                    item for item in recent
                    if item.get("status") == "failed"
                ]),
            },
        }

    def _public_item(self, item):
        payload = dict(item)
        payload.pop("_queued_monotonic", None)
        estimated_monotonic = payload.pop("_estimated_send_monotonic", None)
        if estimated_monotonic is not None:
            payload["estimated_send_remaining_seconds"] = max(
                int(round(estimated_monotonic - time.monotonic())),
                0,
            )
        return payload


runtime_queue_state = RuntimeQueueState()
