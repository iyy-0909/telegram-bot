from datetime import datetime, timezone

from telethon import functions, types


def is_muted_until(mute_until, now: datetime | None = None) -> bool:
    if not mute_until:
        return False

    now = now or datetime.now(timezone.utc)
    if isinstance(mute_until, (int, float)):
        mute_until = datetime.fromtimestamp(mute_until, tz=timezone.utc)
    elif mute_until.tzinfo is None:
        mute_until = mute_until.replace(tzinfo=timezone.utc)

    return mute_until > now


async def is_chat_muted(client, chat) -> bool:
    input_peer = await client.get_input_entity(chat)
    settings = await client(
        functions.account.GetNotifySettingsRequest(
            peer=types.InputNotifyPeer(input_peer),
        )
    )
    return is_muted_until(getattr(settings, "mute_until", None))
