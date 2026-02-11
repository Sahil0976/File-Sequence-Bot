# SahilxCodes
# Telegram: @iSahilx

import asyncio
import html
import logging
import re

from aiogram import F, Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN
from db import get_custom_caption, get_user_mode, increment_files_sequenced
from plugins import router as plugins_router

#================================================================#

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
user_file_sequences = {}

#================================================================#

QUALITY_PATTERNS = [
    re.compile(r"\b(\d{3,4}p)\b", re.IGNORECASE),
    re.compile(r"[([<{]?\s*(4k)\s*[)\]>}]?", re.IGNORECASE),
    re.compile(r"[([<{]?\s*(2k)\s*[)\]>}]?", re.IGNORECASE),
    re.compile(r"\bhd[-\s]?rip\b", re.IGNORECASE),
    re.compile(r"[([<{]?\s*(4kX264)\s*[)\]>}]?", re.IGNORECASE),
    re.compile(r"[([<{]?\s*(4kx265)\s*[)\]>}]?", re.IGNORECASE),
    re.compile(r"[_-]?\b(\d{3,4}p|hdrip|4k|2160p)\b", re.IGNORECASE),
]

#================================================================#

def natural_sort_key(message):
    filename = None
    if message.document:
        filename = message.document.file_name
    elif message.video:
        filename = message.video.file_name

    if not filename:
        filename = "zzz"

    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", filename)]

#================================================================#

def get_filename(message: Message) -> str:
    if message.document and message.document.file_name:
        return message.document.file_name
    if message.video and message.video.file_name:
        return message.video.file_name
    return "File"

#================================================================#

def quality_rank(filename: str) -> int:
    detected_tokens = set()
    for pattern in QUALITY_PATTERNS:
        for match in pattern.findall(filename):
            if isinstance(match, tuple):
                for part in match:
                    if part:
                        detected_tokens.add(part.lower())
            elif match:
                detected_tokens.add(match.lower())

    normalized = set()
    for token in detected_tokens:
        compact = token.replace(" ", "").replace("-", "")
        if compact in {"4kx264", "4kx265", "4k"}:
            normalized.add("4k")
        elif compact == "2160p":
            normalized.add("2160p")
        elif compact == "hdrip":
            normalized.add("hdrip")
        elif compact in {"480p", "720p", "1080p"}:
            normalized.add(compact)
        elif compact == "2k":
            normalized.add("2k")

    if "480p" in normalized:
        return 0
    if "720p" in normalized:
        return 1
    if "1080p" in normalized:
        return 2
    if "2k" in normalized:
        return 3
    if "hdrip" in normalized:
        return 4
    if "2160p" in normalized or "4k" in normalized:
        return 5
    return 6


def quality_sort_key(message: Message):
    filename = get_filename(message)
    return (quality_rank(filename), natural_sort_key(message))


async def cleanup_inactive_sequences():
    while True:
        try:
            current_time = asyncio.get_event_loop().time()
            for user_id in list(user_file_sequences.keys()):
                if current_time - user_file_sequences[user_id]["started_at"] > 3600:
                    del user_file_sequences[user_id]
            await asyncio.sleep(300)
        except Exception as err:
            logging.error("Cleanup error: %s", err)
            await asyncio.sleep(300)

#================================================================#

@router.message(Command("startsequence"))
async def start_sequence(message: Message):
    user_id = message.chat.id

    if user_id in user_file_sequences:
        await message.reply(
            "You are already in a file sequence process.\nUse <code>/endsequence</code> to complete it.",
            parse_mode=ParseMode.HTML,
        )
        return

    user_file_sequences[user_id] = {
        "files": [],
        "sorted_files": [],
        "completed": False,
        "started_at": asyncio.get_event_loop().time(),
    }

    await message.reply(
        "File sequence process started.\n\n"
        "Now send files you want to sequence.\n\n"
        "When done, use <code>/endsequence</code>.\n"
        "Maximum 100 files per sequence.",
        parse_mode=ParseMode.HTML,
    )

#================================================================#

@router.message(F.document | F.video)
async def process_file_sequence(message: Message):
    user_id = message.chat.id

    if user_id not in user_file_sequences or user_file_sequences[user_id]["completed"]:
        return

    if len(user_file_sequences[user_id]["files"]) >= 100:
        await message.reply(
            "Maximum 100 files allowed per sequence. Use <code>/endsequence</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    user_file_sequences[user_id]["files"].append(message)
    file_count = len(user_file_sequences[user_id]["files"])
    await message.reply(f"File {file_count} added to sequence.")

#================================================================#

@router.message(Command("endsequence"))
async def end_sequence(message: Message):
    user_id = message.chat.id

    if user_id not in user_file_sequences:
        await message.reply("No active sequence found. Use <code>/startsequence</code>.", parse_mode=ParseMode.HTML)
        return

    user_data = user_file_sequences[user_id]

    if user_data["completed"]:
        await message.reply("You have already finished the sequence process.")
        del user_file_sequences[user_id]
        return

    if not user_data["files"]:
        await message.reply("No files found in sequence. Please send files first.")
        del user_file_sequences[user_id]
        return

    user_mode = get_user_mode(user_id)
    if user_mode == "quality":
        user_data["sorted_files"] = sorted(user_data["files"], key=quality_sort_key)
    else:
        user_data["sorted_files"] = sorted(user_data["files"], key=natural_sort_key)
    custom_caption = get_custom_caption(user_id)

    total = len(user_data["sorted_files"])
    progress_msg = await message.reply(f"Sending 0/{total} files...")

    for idx, file_message in enumerate(user_data["sorted_files"], 1):
        try:
            filename = get_filename(file_message)

            if custom_caption:
                safe_filename = html.escape(filename)
                caption = custom_caption.replace("{filename}", safe_filename)
                parse_mode = ParseMode.HTML
            else:
                caption = None
                parse_mode = None

            if file_message.document:
                send_kwargs = {
                    "chat_id": user_id,
                    "document": file_message.document.file_id,
                    "disable_notification": True,
                }
                if caption:
                    send_kwargs["caption"] = caption
                    send_kwargs["parse_mode"] = parse_mode
                await message.bot.send_document(
                    **send_kwargs,
                )
            elif file_message.video:
                send_kwargs = {
                    "chat_id": user_id,
                    "video": file_message.video.file_id,
                    "disable_notification": True,
                }
                if caption:
                    send_kwargs["caption"] = caption
                    send_kwargs["parse_mode"] = parse_mode
                await message.bot.send_video(
                    **send_kwargs,
                )

            if idx % 5 == 0 or idx == total:
                await progress_msg.edit_text(f"Sending {idx}/{total} files...")

            await asyncio.sleep(0.4)
        except Exception as err:
            logging.error("Error sending file %s: %s", idx, err)

    await progress_msg.delete()

    increment_files_sequenced(user_id, message.from_user.first_name, total)

    user_data["completed"] = True
    await message.reply(
        f"<b>File sequencing completed.</b>\n<b>You received {total} sequenced files.</b>",
        parse_mode=ParseMode.HTML,
    )

    del user_file_sequences[user_id]

#================================================================#

@router.message(Command("cancelsequence"))
async def cancel_sequence(message: Message):
    user_id = message.chat.id

    if user_id in user_file_sequences:
        file_count = len(user_file_sequences[user_id]["files"])
        del user_file_sequences[user_id]
        await message.reply(
            f"Sequence cancelled.\n{file_count} files discarded.\n\nUse <code>/startsequence</code> for a new sequence.",
            parse_mode=ParseMode.HTML,
        )
        return

    await message.reply("No active sequence to cancel.", parse_mode=ParseMode.HTML)

#================================================================#

async def main():
    logging.info("Bot is starting...")
    dp.include_router(plugins_router)
    dp.include_router(router)
    asyncio.create_task(cleanup_inactive_sequences())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
