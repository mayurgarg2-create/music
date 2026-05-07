"""Lyrics handler — /lyrics command using Genius API"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from player import now_playing
from config import GENIUS_TOKEN

GOLD = "👑"

try:
    import lyricsgenius
    genius = lyricsgenius.Genius(
        GENIUS_TOKEN,
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)", "(Cover)"],
        remove_section_headers=False
    ) if GENIUS_TOKEN else None

    # Silence lyricsgenius output the proper way
    if genius:
        genius.verbose = False
        logging.getLogger("lyricsgenius").setLevel(logging.WARNING)

except ImportError:
    genius = None


def register(dp: Dispatcher, bot: Bot, owner_id: int):

    @dp.message(Command("lyrics"))
    async def lyrics_cmd(message: Message):
        chat_id = message.chat.id
        parts   = message.text.split(maxsplit=1)
        query   = parts[1].strip() if len(parts) > 1 else ""

        if not query:
            np = now_playing.get(chat_id)
            if np:
                query = np.get("title", "")
            else:
                await message.reply(
                    "⚠️ Usage: <code>/lyrics song name</code>\n"
                    "Or play a song first and use /lyrics",
                    parse_mode="HTML"
                )
                return

        if not genius:
            await message.reply(
                "❌ Genius API not configured.\n"
                "Add <code>GENIUS_TOKEN</code> to your .env file.\n"
                "Get it free at: genius.com/api-clients",
                parse_mode="HTML"
            )
            return

        msg = await message.reply(
            f"╔══「 🎤 <b>FETCHING LYRICS</b> 」══╗\n\n"
            f"  {GOLD} Searching for: <i>{query[:50]}</i>...\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

        try:
            loop = asyncio.get_event_loop()
            song = await loop.run_in_executor(None, lambda: genius.search_song(query))

            if not song:
                await msg.edit_text(
                    f"╔══「 ❌ <b>NOT FOUND</b> 」══╗\n\n"
                    f"  Lyrics not found for: <i>{query}</i>\n"
                    f"  Try the exact song title and artist.\n\n╚{'═'*32}╝",
                    parse_mode="HTML"
                )
                return

            lyrics = song.lyrics or ""
            # Clean up genius artifacts
            lyrics = lyrics.replace("EmbedShare URLCopyEmbedCopy", "").strip()

            MAX_CHUNK = 3500
            header = (
                f"╔══「 🎤 <b>LYRICS</b> 」══╗\n\n"
                f"  {GOLD} <b>{song.title}</b>\n"
                f"  🎤 <b>{song.artist}</b>\n\n"
            )
            footer = f"\n╚{'═'*32}╝"

            if len(lyrics) <= MAX_CHUNK:
                await msg.edit_text(
                    header + f"<code>{lyrics}</code>" + footer,
                    parse_mode="HTML"
                )
            else:
                await msg.edit_text(
                    header + "<i>Sending lyrics in parts...</i>",
                    parse_mode="HTML"
                )
                chunks = [lyrics[i:i + MAX_CHUNK] for i in range(0, len(lyrics), MAX_CHUNK)]
                for i, chunk in enumerate(chunks[:4]):
                    part_label = f"<i>Part {i+1}/{min(len(chunks), 4)}</i>\n\n" if len(chunks) > 1 else ""
                    await message.reply(
                        part_label + f"<code>{chunk}</code>",
                        parse_mode="HTML"
                    )
                if len(chunks) > 4:
                    await message.reply(
                        "<i>...lyrics trimmed. Full lyrics at genius.com</i>",
                        parse_mode="HTML"
                    )

        except Exception as e:
            await msg.edit_text(f"❌ Error fetching lyrics: {e}")
