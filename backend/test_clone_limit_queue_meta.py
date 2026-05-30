from types import SimpleNamespace

from bot.cloner import build_clone_limit_waiting_meta


def make_message(message_id, grouped_id=None):
    return SimpleNamespace(id=message_id, grouped_id=grouped_id)


def make_task():
    return SimpleNamespace(
        id=7,
        name="上海源频道历史克隆",
        source_channel="@source_sh",
    )


def test_build_clone_limit_waiting_meta_for_single_message():
    item = {
        "type": "single",
        "messages": [make_message(1200)],
    }

    meta = build_clone_limit_waiting_meta(
        make_task(),
        ["@target_sh"],
        item,
        30,
    )

    assert meta["source_type"] == "clone"
    assert meta["task_id"] == 7
    assert meta["task_name"] == "上海源频道历史克隆"
    assert meta["source_channel"] == "@source_sh"
    assert meta["target_channel"] == "@target_sh"
    assert meta["source_message_id"] == 1200
    assert meta["grouped_id"] is None
    assert meta["message_type"] == "single"
    assert meta["reason"] == "克隆任务限流等待中"
    assert meta["estimated_send_remaining_seconds"] == 30


def test_build_clone_limit_waiting_meta_for_album():
    item = {
        "type": "album",
        "grouped_id": "9988",
        "messages": [make_message(1200, "9988"), make_message(1201, "9988")],
    }

    meta = build_clone_limit_waiting_meta(
        make_task(),
        ["@target_a", "@target_b"],
        item,
        45,
    )

    assert meta["target_channel"] == "@target_a, @target_b"
    assert meta["source_message_id"] == 1201
    assert meta["grouped_id"] == "9988"
    assert meta["message_type"] == "album"
    assert meta["estimated_send_remaining_seconds"] == 45


if __name__ == "__main__":
    test_build_clone_limit_waiting_meta_for_single_message()
    test_build_clone_limit_waiting_meta_for_album()
    print("ok")
