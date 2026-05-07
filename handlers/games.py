"""Games handler — /guesssong game"""
import asyncio
import random
import time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from pytgcalls.types import MediaStream, AudioQuality
from database import start_game, get_game, end_game
from player import calls, yt_search, get_fresh_url
from config import GAME_TIMEOUT

GOLD = "👑"

SONG_POOL = [
    "Shape of You Ed Sheeran",
    "Blinding Lights The Weeknd",
    "Dance Monkey Tones and I",
    "Tum Hi Ho Arijit Singh",
    "Kesariya Brahmastra",
    "Sunflower Post Malone",
    "Levitating Dua Lipa",
    "Stay Kid Laroi Justin Bieber",
    "Dynamite BTS",
    "Believer Imagine Dragons",
    "Senorita Shawn Mendes Camila Cabello",
    "Tera Ban Jaunga Kabir Singh",
    "Ae Dil Hai Mushkil",
    "Despacito Luis Fonsi",
    "Perfect Ed Sheeran",
    "Havana Camila Cabello",
    "Closer Chainsmokers",
    "Something Just Like This Coldplay",
    "Photograph Ed Sheeran",
    "Let Her Go Passenger",
    "Counting Stars OneRepublic",
    "Thunder Imagine Dragons",
    "Radioactive Imagine Dragons",
    "Stressed Out Twenty One Pilots",
    "Chandelier Sia",
    "Cheap Thrills Sia",
    "Sorry Justin Bieber",
    "Love Yourself Justin Bieber",
    "Aayat Bajirao Mastani",
    "Raabta Agent Sai",
    "Pal Arijit Singh",
    "Bekhayali Kabir Singh",
]

# Track timeout tasks per chat to allow cancellation
_timeout_tasks: dict[int, asyncio.Task] = {}


def mask_title(title: str) -> str:
    """Show first letter of each word, rest as underscores."""
    words = title.split()
    masked = []
    for word in words:
        if len(word) == 1:
            masked.append(word)
        else:
            masked.append(word[0] + "_ " * (len(word) - 1))
    return " | ".join(m.rstrip() for m in masked)


def _cancel_timeout(chat_id: int):
    task = _timeout_tasks.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


def register(dp: Dispatcher, bot: Bot, owner_id: int):

    async def _auto_reveal(chat_id: int, title: str):
        """Background task — reveals answer after timeout."""
        await asyncio.sleep(GAME_TIMEOUT)
        game = get_game(chat_id)
        if game and game["title"] == title:
            end_game(chat_id)
            try:
                await calls.leave_group_call(chat_id)
            except Exception:
                pass
            await bot.send_message(
                chat_id,
                f"╔══「 ⏰ <b>TIME'S UP!</b> 」══╗\n\n"
                f"  The song was:\n  {GOLD} <b>{title}</b>\n\n"
                f"  Better luck next time! 🎵\n\n╚{'═' * 32}╝",
                parse_mode="HTML",
            )
        _timeout_tasks.pop(chat_id, None)

    @dp.message(Command("guesssong"))
    async def guesssong_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id

        # Check for active game
        existing = get_game(chat_id)
        if existing:
            elapsed = int(time.time()) - existing["started_at"]
            remaining = GAME_TIMEOUT - elapsed
            if remaining > 0:
                await message.reply(
                    f"🎮 A game is already running!\n"
                    f"⏳ <b>{remaining}s</b> remaining.\n\n"
                    f"Hint: <code>{mask_title(existing['title'])}</code>",
                    parse_mode="HTML",
                )
                return
            else:
                end_game(chat_id)
                _cancel_timeout(chat_id)

        # Pick random song
        song_query = random.choice(SONG_POOL)
        results = await yt_search(song_query, 2)

        if not results:
            await message.reply("❌ Couldn't load song. Try again!")
            return

        track = results[0]
        title = track["title"]
        audio_url = await get_fresh_url(track.get("webpage_url", track["url"]))

        if not audio_url:
            await message.reply("❌ Couldn't load audio. Try again!")
            return

        # Clean title for answer matching
        answer = title.lower().split("(")[0].split("|")[0].split("-")[0].strip()

        start_game(chat_id, title, answer, user_id)

        # Stream the mystery clip using new pytgcalls API
        stream = MediaStream(
            audio_url,
            audio_flags=AudioQuality.HIGH,
            ffmpeg_parameters="-t 10",   # 10-second clip
        )

        try:
            await calls.join_group_call(chat_id, stream)
        except Exception:
            try:
                await calls.change_stream(chat_id, stream)
            except Exception as e:
                end_game(chat_id)
                await message.reply(f"❌ Couldn't start game: {e}")
                return

        masked = mask_title(title)
        await message.reply(
            f"╔══「 🎮 <b>GUESS THE SONG!</b> 」══╗\n\n"
            f"  🎵 Listen carefully...\n\n"
            f"  Hint: <code>{masked}</code>\n\n"
            f"  ⏳ You have <b>{GAME_TIMEOUT} seconds</b>!\n"
            f"  Type your answer in chat!\n\n"
            f"  Use /giveup to reveal the answer.\n\n╚{'═' * 32}╝",
            parse_mode="HTML",
        )

        # Start cancellable background timeout
        _cancel_timeout(chat_id)  # cancel any stale task
        _timeout_tasks[chat_id] = asyncio.create_task(_auto_reveal(chat_id, title))

    @dp.message(Command("giveup"))
    async def giveup_cmd(message: Message):
        chat_id = message.chat.id
        game = get_game(chat_id)
        if not game:
            await message.reply("❌ No active game!")
            return

        _cancel_timeout(chat_id)
        end_game(chat_id)

        try:
            await calls.leave_group_call(chat_id)
        except Exception:
            pass

        await message.reply(
            f"╔══「 🏳 <b>GAVE UP</b> 」══╗\n\n"
            f"  The song was:\n  {GOLD} <b>{game['title']}</b>\n\n╚{'═' * 32}╝",
            parse_mode="HTML",
        )

    @dp.message(F.text & ~F.text.startswith("/"))
    async def check_guess(message: Message):
        chat_id = message.chat.id
        game = get_game(chat_id)
        if not game:
            return

        user_answer = message.text.lower().strip()
        answer = game["answer"].lower().strip()

        answer_words = set(answer.split())
        guess_words = set(user_answer.split())
        common = answer_words & guess_words
        match_ratio = len(common) / max(len(answer_words), 1)

        if match_ratio >= 0.6 or answer in user_answer or user_answer in answer:
            _cancel_timeout(chat_id)
            end_game(chat_id)

            try:
                await calls.leave_group_call(chat_id)
            except Exception:
                pass

            user = message.from_user
            await message.reply(
                f"╔══「 🏆 <b>CORRECT!</b> 」══╗\n\n"
                f"  🎉 <b>{user.first_name}</b> got it!\n\n"
                f"  {GOLD} <b>{game['title']}</b>\n\n"
                f"  Amazing ears! 🎵\n\n╚{'═' * 32}╝",
                parse_mode="HTML",
            )
