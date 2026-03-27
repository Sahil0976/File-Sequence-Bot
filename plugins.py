# SahilxCodes
# Telegram: @iSahilx

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ABOUT_TXT, HELP_TXT, OWNER_ID, START_MSG, START_PIC
from db import (
    count_users,
    delete_custom_caption,
    get_all_users_sorted,
    get_top_users,
    get_user,
    get_user_mode,
    iter_user_ids,
    set_custom_caption,
    set_user_mode,
    total_files_sequenced,
    upsert_user,
    delete_dump_channel_id,
    set_dump_channel_id,
    get_dump_channel_id
)

#================================================================#

router = Router()
awaiting_dump_channel_input = set()


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="My Developer", url="https://t.me/iSahilx", style="primary")],
            [
                InlineKeyboardButton(text="Help", callback_data="help"),
                InlineKeyboardButton(text="About", callback_data="about"),
            ],
            [InlineKeyboardButton(text="Close", callback_data="close")],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Back", callback_data="start", style='danger'),
                InlineKeyboardButton(text="Close", callback_data="close", style='danger'),
            ]
        ]
    )

#================================================================#

def mode_keyboard(selected_mode: str) -> InlineKeyboardMarkup:
    quality_text = "✅ Quality" if selected_mode == "quality" else "Quality"
    episode_text = "✅ Episode" if selected_mode == "episode" else "Episode"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=quality_text, callback_data="mode:set:quality"),
                InlineKeyboardButton(text=episode_text, callback_data="mode:set:episode"),
            ]
        ]
    )

def dump_setting_keyboard(can_delete: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Set Dump Channel", callback_data="dump:set"),
            InlineKeyboardButton(text="Delete Dump Channel", callback_data="dump:delete") if can_delete else None,
        ],
        [
            InlineKeyboardButton(icon_custom_emoji_id="6296577138615125756", text="Back", callback_data="close", style='danger')
        ]
    ]

    if not can_delete:
        keyboard[0] = [InlineKeyboardButton(text="Set Dump Channel", callback_data="dump:set")]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def dump_setting_text(current_dump_channel_id) -> str:
    dump_text = f"Current Dump Channel ID: <code>{current_dump_channel_id}</code>\n\n" if current_dump_channel_id else "Not Set Yet."
    return (
        "<b> Dump Channel Settings</b>\n\n"
        f"Current Dump Channel ID: <code>{current_dump_channel_id}</code>\n\n"
        "Set Dump Channel: Use the button below and send the channel ID where you want the sequenced files to be dumped.\n\n"
        "Delete Dump Channel: Use the button below to remove the currently set dump channel. This will stop files from being dumped to any channel."
    )
    
#================================================================#

@router.message(CommandStart())
async def start_command(message: Message):
    upsert_user(message.chat.id, message.from_user.first_name)

    await message.answer_photo(
        photo=START_PIC,
        caption=START_MSG.format(first=message.from_user.first_name),
        reply_markup=start_keyboard(),
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.message(Command("leaderboard"))
async def leaderboard(message: Message):
    top_users = get_top_users(limit=10)
    leaderboard_text = "<b>Top 10 Users</b>\n\n"

    users_found = False
    for index, user in enumerate(top_users, start=1):
        users_found = True
        username = user.get("username", "Unknown")
        files = user.get("files_sequenced", 0)
        leaderboard_text += f"<b>{index}. {username}</b> : <code>{files} files</code>\n"

    if not users_found:
        leaderboard_text = "<b>No users on the leaderboard yet.</b>\n\nBe the first to sequence files."

    await message.reply(leaderboard_text, parse_mode=ParseMode.HTML)

#================================================================#

@router.message(Command("stats"))
async def stats_command(message: Message):
    user_id = message.chat.id
    user_data = get_user(user_id)

    if user_data:
        files = user_data.get("files_sequenced", 0)
        username = user_data.get("username", "Unknown")
        all_users = get_all_users_sorted()
        rank = next((i + 1 for i, u in enumerate(all_users) if u["user_id"] == user_id), None)

        await message.reply(
            f"<b>Your Statistics</b>\n\n"
            f"Name: {username}\n"
            f"Files Sequenced: {files}\n"
            f"Rank: #{rank} out of {len(all_users)}",
            parse_mode=ParseMode.HTML,
        )
        return

    await message.reply(
        "<b>No statistics found.</b>\n\nStart sequencing files to see your stats.",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.message(Command("setcaption"))
async def set_caption(message: Message):
    user_id = message.chat.id
    command_parts = message.text.split(" ", 1)

    if len(command_parts) < 2:
        await message.reply(
            "<b>Usage:</b> <code>/setcaption Your custom caption here</code>\n"
            "<b>Tip:</b> Use <code>{filename}</code> to insert current file name.\n\n"
            "This caption will be used for all sequenced files.\n"
            "Use <code>/delcaption</code> to remove caption completely.",
            parse_mode=ParseMode.HTML,
        )
        return

    custom_caption = command_parts[1]
    set_custom_caption(user_id, message.from_user.first_name, custom_caption)

    await message.reply(
        f"<b>Caption saved successfully.</b>\n\n"
        f"<b>Your caption:</b>\n{custom_caption}\n\n"
        f"<b>Note:</b> <code>{{filename}}</code> will be replaced with each file name.",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.message(Command("delcaption"))
async def del_caption(message: Message):
    if not delete_custom_caption(message.chat.id):
        await message.reply("No custom caption found to delete.")
        return

    await message.reply(
        "<b>Custom caption deleted.</b>\n\nFiles will now be sent without any caption.",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.message(Command("mode"))
async def mode_command(message: Message):
    current_mode = get_user_mode(message.chat.id)
    await message.reply(
        "<b>Select Sorting Mode</b>\n\n"
        "Quality: Sequence by quality (480p, 720p, 1080p, HDRip, 2160p/4K)\n"
        "Episode: Sequence by Episode (Ep-01, Ep-02, etc.)\n",
        parse_mode=ParseMode.HTML,
        reply_markup=mode_keyboard(current_mode),
    )

#================================================================#

@router.message(Command("dumpsettings"))
async def dump_settings_command(message: Message):
    current_dump_channel_id = get_dump_channel_id(message.chat.id)
    await message.reply(
        dump_setting_text(current_dump_channel_id),
        parse_mode=ParseMode.HTML,
        reply_markup = dump_setting_keyboard(bool(current_dump_channel_id))
    )

#================================================================#

@router.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    command_parts = message.text.split(" ", 1)
    if len(command_parts) < 2:
        await message.reply(
            "Usage: <code>/broadcast Your message here</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    broadcast_text = command_parts[1]
    users = iter_user_ids()
    success = 0
    failed = 0
    status_msg = await message.reply("Broadcasting message...")

    for user in users:
        try:
            await message.bot.send_message(user["user_id"], broadcast_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as err:
            failed += 1
            logging.error("Broadcast failed for %s: %s", user.get("user_id"), err)

    await status_msg.edit_text(
        f"Broadcast Completed.\n\nSuccessfully sent: {success}\nFailed: {failed}",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.message(Command("users"))
async def users_command(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    user_count = count_users()
    total_files = total_files_sequenced()

    await message.reply(
        f"Bot Statistics\n\nTotal Users: {user_count}\nTotal Files Sequenced: {total_files}",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.callback_query(F.data == "help")
async def help_callback(query: CallbackQuery):
    await query.message.edit_caption(
        caption=HELP_TXT.format(first=query.from_user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "start")
async def start_callback(query: CallbackQuery):
    await query.message.edit_caption(
        caption=START_MSG.format(first=query.from_user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=start_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "about")
async def about_callback(query: CallbackQuery):
    await query.message.edit_caption(
        caption=ABOUT_TXT,
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "close")
async def close_callback(query: CallbackQuery):
    await query.message.delete()
    try:
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete()
    except Exception:
        pass
    await query.answer()


#================================================================#
# Dump callback data

@router.callback_query(F.data == "dump:set")
async def set_dump_callback(query: CallbackQuery):
    awaiting_dump_channel_input.add(query.from_user.id)
    await query.message.reply(
        f"Please send your dump channel ID.\nExample: <code>-1001234567890</code>",
        parse_mode=ParseMode.HTML,
    )
    await query.answer()

@router.callback_query(F.data == "dump:delete")
async def delete_dump_callback(query: CallbackQuery):
    delete = delete_dump_channel_id(query.from_user.id)
    current_dump_channel_id = None

    await query.message.edit_text(
        dump_setting_text(current_dump_channel_id), 
        parse_mode=ParseMode.HTML,
        reply_markup=dump_setting_keyboard(False)
    )
    await query.answer("Dump channel deleted." if delete else "No dump channel was set.")


@router.message(F.text.regexp(r"^-100\d{5,}$"))
async def capture_dump_channel_id(message: Message):
    user_id = message.chat.id
    if user_id not in awaiting_dump_channel_input:
        return
    
    channel_id = int(message.text.strip())
    set_dump_channel_id(user_id, message.from_user.first_name, channel_id)
    awaiting_dump_channel_input.discard(user_id)

    await message.reply(
        f"Dump Channel set successfully to <code>{channel_id}</code>.\n\nFiles will now be dumped to this channel.",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.callback_query(F.data.startswith("mode:set:"))
async def mode_callback(query: CallbackQuery):
    selected_mode = query.data.split(":")[-1]
    if selected_mode not in {"quality", "episode"}:
        await query.answer("Invalid mode", show_alert=True)
        return

    set_user_mode(query.from_user.id, query.from_user.first_name, selected_mode)

    await query.message.edit_text(
        "<b>Select Sorting Mode</b>\n\n"
        "Quality: Sort by quality (480p, 720p, 1080p, HDRip, 2160p/4K)\n"
        "Episode: Default filename-based natural sorting",
        parse_mode=ParseMode.HTML,
        reply_markup=mode_keyboard(selected_mode),
    )
    await query.answer(f"{selected_mode.capitalize()} mode selected")
