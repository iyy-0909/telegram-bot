import asyncio
from types import SimpleNamespace

from bot.sender import prepare_single_message


class FakeMessage:
    id = 95
    media = SimpleNamespace()
    file = None
    document = None
    photo = None

    async def download_media(self, file=None):
        raise AssertionError("non-file media should not be downloaded")


def test_non_file_media_is_prepared_as_text():
    prepared = asyncio.run(prepare_single_message(FakeMessage(), "hello link"))

    assert prepared["ok"] is True
    assert prepared["text"] == "hello link"
    assert prepared["files"] == []


if __name__ == "__main__":
    test_non_file_media_is_prepared_as_text()
    print("test_sender.py passed")
