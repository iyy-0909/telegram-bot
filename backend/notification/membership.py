from telethon import errors, functions, types


async def is_chat_member(client, chat) -> bool:
    if isinstance(chat, types.Channel):
        if getattr(chat, "left", False):
            return False

        input_channel = await client.get_input_entity(chat)
        try:
            await client(
                functions.channels.GetParticipantRequest(
                    channel=input_channel,
                    participant="me",
                )
            )
        except (errors.UserNotParticipantError, errors.ChannelPrivateError):
            return False
        return True

    if isinstance(chat, types.Chat):
        return not (
            getattr(chat, "left", False)
            or getattr(chat, "deactivated", False)
        )

    return True
