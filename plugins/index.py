'''# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging, re, asyncio
from utils import temp
from info import ADMINS
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been decliened by our moderators.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):
    vj = await bot.ask(message.chat.id, "**Now Send Me Your Channel Last Post Link Or Forward A Last Message From Your Index Channel.\n\nAnd You Can Set Skip Number By - /setskip yourskipnumber**")
    if vj.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = vj.forward_from_message_id
        chat_id = vj.forward_from_chat.username or vj.forward_from_chat.id
    elif vj.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(vj.text)
        if not match:
            return await vj.reply('Invalid link\n\nTry again by /index')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await vj.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await vj.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await vj.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [
                InlineKeyboardButton('Yes',
                                     callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('close', callback_data='close_data'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure iam an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [
            InlineKeyboardButton('Accept Index',
                                 callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('Reject Index',
                                 callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    await msg.edit(f"Successfully Cancelled!!\n\nSaved <code>{total_files}</code> files to dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>")
                    break
                current += 1
                if current % 50 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    reply = InlineKeyboardMarkup(can)
                    await msg.edit_text(
                        text=f"Total messages fetched: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>",
                        reply_markup=reply)
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                media.file_type = message.media.value
                media.caption = message.caption
                aynav, vnay = await save_file(media)
                if aynav:
                    total_files += 1
                elif vnay == 0:
                    duplicate += 1
                elif vnay == 2:
                    errors += 1
        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            await msg.edit(f'Succesfully saved <code>{total_files}</code> to dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>')
'''
import logging
import re
import asyncio
from utils import temp
from info import ADMINS, INDEX_REQ_CHANNEL  # Ensure these are correctly imported
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid,
    ChatAdminRequired,
    UsernameInvalid,
    UsernameNotModified,
    MessageNotModified,
)
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize Lock for Concurrency Control
lock = asyncio.Lock()

# Initialize Pyrogram Client (Replace 'my_account' with your session name or configuration)
app = Client("my_account")


@app.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    """
    Handle callback queries related to indexing files.
    """
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        await query.answer("Cancelling Indexing")
        return

    try:
        _, action, chat, lst_msg_id, from_user = query.data.split("#")
    except ValueError:
        await query.answer("Invalid callback data.", show_alert=True)
        return

    if action == 'reject':
        await query.message.delete()
        await bot.send_message(
            int(from_user),
            f'Your submission for indexing **{chat}** has been declined by our moderators.',
            reply_to_message_id=int(lst_msg_id)
        )
        return

    if lock.locked():
        await query.answer('Wait until the previous process completes.', show_alert=True)
        return

    msg = query.message
    await query.answer('Processing...⏳', show_alert=True)

    if int(from_user) not in ADMINS:
        await bot.send_message(
            int(from_user),
            f'Your submission for indexing **{chat}** has been accepted by our moderators and will be added soon.',
            reply_to_message_id=int(lst_msg_id)
        )

    await safe_edit_message(
        msg,
        "Starting Indexing...",
        InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )

    try:
        chat = int(chat)
    except ValueError:
        # If chat is not an integer, assume it's a username
        pass

    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@app.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):
    """
    Handle the /index command in private chats.
    """
    vj = await bot.ask(
        message.chat.id,
        "**Now send me your channel's last post link or forward the last message from your index channel.**\n\n"
        "You can set the skip number using `/setskip your_skip_number`."
    )

    if vj.forward_from_chat and vj.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = vj.forward_from_message_id
        chat_id = vj.forward_from_chat.username or vj.forward_from_chat.id
    elif vj.text:
        regex = re.compile(
            r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$"
        )
        match = regex.match(vj.text)
        if not match:
            return await vj.reply('Invalid link.\n\nPlease try again using /index.')

        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id = int(f"-100{chat_id}")
    else:
        return await vj.reply("Invalid input. Please provide a valid channel link or forward a message.")

    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await vj.reply('This may be a private channel or group. Please make me an admin there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await vj.reply('Invalid link specified.')
    except Exception as e:
        logger.exception(e)
        return await vj.reply(f'An error occurred: {e}')

    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except Exception as e:
        logger.exception(e)
        return await message.reply('Ensure that I am an admin in the channel if it is private.')

    if not k or k.empty:
        return await message.reply('This may be a group and I am not an admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [
                InlineKeyboardButton(
                    'Yes',
                    callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}'
                )
            ],
            [
                InlineKeyboardButton('Close', callback_data='close_data'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you want to index this channel/group?\n\n'
            f'**Chat ID/Username:** <code>{chat_id}</code>\n'
            f'**Last Message ID:** <code>{last_msg_id}</code>',
            reply_markup=reply_markup
        )

    if isinstance(chat_id, int):
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Ensure I am an admin in the chat and have permission to create invite links.')
    else:
        link = f"@{vj.forward_from_chat.username}"

    buttons = [
        [
            InlineKeyboardButton(
                'Accept Index',
                callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}'
            )
        ],
        [
            InlineKeyboardButton(
                'Reject Index',
                callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'
            ),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await bot.send_message(
        INDEX_REQ_CHANNEL,
        f'#IndexRequest\n\n'
        f'**By:** {message.from_user.mention} (<code>{message.from_user.id}</code>)\n'
        f'**Chat ID/Username:** <code>{chat_id}</code>\n'
        f'**Last Message ID:** <code>{last_msg_id}</code>\n'
        f'**Invite Link:** {link}',
        reply_markup=reply_markup
    )

    await message.reply('Thank you for your contribution! Please wait for our moderators to verify the files.')


@app.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    """
    Handle the /setskip command for admins to set the skip number.
    """
    parts = message.text.split(" ")
    if len(parts) != 2:
        return await message.reply("Usage: /setskip <number>")

    _, skip = parts
    try:
        skip = int(skip)
    except ValueError:
        return await message.reply("The skip number must be an integer.")

    temp.CURRENT = skip
    await message.reply(f"Successfully set SKIP number to <code>{skip}</code>.")


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    """
    Index files from the specified chat and save them to the database.
    """
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0

    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False

            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    await safe_edit_message(
                        msg,
                        f"**Indexing Cancelled!**\n\n"
                        f"**Saved Files:** <code>{total_files}</code>\n"
                        f"**Duplicate Files Skipped:** <code>{duplicate}</code>\n"
                        f"**Deleted Messages Skipped:** <code>{deleted}</code>\n"
                        f"**Non-Media Messages Skipped:** <code>{no_media + unsupported}</code> "
                        f"(Unsupported Media - `{unsupported}`)\n"
                        f"**Errors Occurred:** <code>{errors}</code>"
                    )
                    return

                current += 1

                if current % 50 == 0:
                    buttons = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    reply_markup = InlineKeyboardMarkup(buttons)
                    status_text = (
                        f"**Total Messages Fetched:** <code>{current}</code>\n"
                        f"**Total Files Saved:** <code>{total_files}</code>\n"
                        f"**Duplicate Files Skipped:** <code>{duplicate}</code>\n"
                        f"**Deleted Messages Skipped:** <code>{deleted}</code>\n"
                        f"**Non-Media Messages Skipped:** <code>{no_media + unsupported}</code> "
                        f"(Unsupported Media - `{unsupported}`)\n"
                        f"**Errors Occurred:** <code>{errors}</code>"
                    )
                    await safe_edit_message(
                        msg,
                        status_text,
                        reply_markup=reply_markup
                    )

                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [
                    enums.MessageMediaType.VIDEO,
                    enums.MessageMediaType.AUDIO,
                    enums.MessageMediaType.DOCUMENT
                ]:
                    unsupported += 1
                    continue

                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue

                media.file_type = message.media.value
                media.caption = message.caption

                try:
                    saved, status = await save_file(media)
                    if saved:
                        total_files += 1
                    elif status == 0:
                        duplicate += 1
                    elif status == 2:
                        errors += 1
                except Exception as e:
                    errors += 1
                    logger.exception(f"Error saving file: {e}")

        except FloodWait as fw:
            logger.warning(f"Flood wait for {fw.x} seconds.")
            await asyncio.sleep(fw.x)
            await index_files_to_db(lst_msg_id, chat, msg, bot)  # Retry after waiting
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            await safe_edit_message(msg, f"**Error:** {e}")
        else:
            await safe_edit_message(
                msg,
                f"**Indexing Completed!**\n\n"
                f"**Saved Files:** <code>{total_files}</code>\n"
                f"**Duplicate Files Skipped:** <code>{duplicate}</code>\n"
                f"**Deleted Messages Skipped:** <code>{deleted}</code>\n"
                f"**Non-Media Messages Skipped:** <code>{no_media + unsupported}</code> "
                f"(Unsupported Media - `{unsupported}`)\n"
                f"**Errors Occurred:** <code>{errors}</code>"
            )


async def safe_edit_message(msg, text, reply_markup=None):
    """
    Safely edit a message by checking if the new text is different from the current text.
    Avoids the MESSAGE_NOT_MODIFIED error.
    """
    try:
        current_text = msg.text or msg.caption or ""
        if current_text != text:
            await msg.edit_text(text, reply_markup=reply_markup)
        else:
            logger.info("Message content is unchanged. No edit performed.")
    except MessageNotModified:
        logger.info("Attempted to edit message with the same content. Skipping edit.")
    except Exception as e:
        logger.exception(f"Failed to edit message: {e}")


if __name__ == "__main__":
    # Start the Pyrogram Client
    app.run()

