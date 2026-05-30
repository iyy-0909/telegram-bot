from types import SimpleNamespace

from db.crud_clone_channels import clone_channel_to_dict
from db.crud_clone_channels import normalize_clone_channel_data


def test_normalize_clone_channel_requires_link():
    try:
        normalize_clone_channel_data({"title": "上海源频道"})
    except ValueError as exc:
        assert "频道链接不能为空" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_normalize_clone_channel_data_trims_fields():
    data = normalize_clone_channel_data(
        {
            "title": " 上海源频道 ",
            "channel_link": " https://t.me/source_sh ",
            "group_name": " 上海 ",
            "channel_type": " channel ",
            "remark": " 重点源 ",
        }
    )

    assert data == {
        "title": "上海源频道",
        "channel_link": "https://t.me/source_sh",
        "group_name": "上海",
        "channel_type": "channel",
        "remark": "重点源",
    }


def test_clone_channel_to_dict_outputs_table_fields():
    channel = SimpleNamespace(
        id=3,
        title="上海源频道",
        channel_link="https://t.me/source_sh",
        group_name="上海",
        channel_type="channel",
        remark="重点源",
        created_at=None,
        updated_at=None,
    )

    assert clone_channel_to_dict(channel) == {
        "id": 3,
        "title": "上海源频道",
        "channel_link": "https://t.me/source_sh",
        "group_name": "上海",
        "channel_type": "channel",
        "remark": "重点源",
        "created_at": "",
        "updated_at": "",
    }


if __name__ == "__main__":
    test_normalize_clone_channel_requires_link()
    test_normalize_clone_channel_data_trims_fields()
    test_clone_channel_to_dict_outputs_table_fields()
    print("ok")
