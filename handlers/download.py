"""Download handler — /download command for MP3 downloads"""
import asyncio
import os
import re
import yt_dlp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, BufferedInputFile
from database import is_premium
from player import now_playing, yt_search
from config import DOWNLOAD_QUALITY_FREE, DOWNLOAD_QUALITY_PREMIUM

GOLD     = "👑"
DL_PATH  = "/tmp/royal_downloads"
os.makedirs(DL_PATH, exist_ok=True)

def sanitize(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:80]

async def download_audio(query: str, quality: str, webpage_url: str = "") -> tuple[str, dict] | tuple[None, None]:
    """Download audio file. Returns (filepath, info) or (None, None)."""
    ydl_opts = {
        "format":      "bestaudio/best",
        "quiet":       True,
        "no_warnings": True,
        "outtmpl":     f"{DL_PATH}/%(id)s.%(ext)s",
        "postprocessors": [{
            "key":              "FFmpegExtractAudio",
            "preferredcodec":   "mp3",
            "preferredquality": quality,
        }],
        "postprocessor_args": ["-ar", "44100"],
        "prefer_ffmpeg": True,
    }

    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if webpage_url:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(webpage_url, download=True))
            else:
                info = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(f"ytsearch1:{query}", download=True)
                )
                if "entries" in info:
                    info = info["entries"][0]

            # Find the downloaded file
            video_id = info.get("id", "")
            filepath = f"{DL_PATH}/{video_id}.mp3"
            if os.path.exists(filepath):
                return filepath, info

            # Try alternate extensions
            for ext in ["mp3", "m4a", "webm", "opus"]:
                fp = f"{DL_PATH}/{video_id}.{ext}"
                if os.path.exists(fp):
                    return fp, info

    except Exception as ex:
        print(f"[DOWNLOAD] {ex}")
    return None, None

def register(dp: Dispatcher, bot: Bot, owner_id: int):

    @dp.message(Command("download"))
    async def download_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)
        quality = DOWNLOAD_QUALITY_PREMIUM if prem else DOWNLOAD_QUALITY_FREE

        parts = message.text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""

        # Default to currently playing song
        if not query:
            np = now_playing.get(chat_id)
            if np:
                query       = np.get("title", "")
                webpage_url = np.get("webpage_url", "")
            else:
                await message.reply(
                    "⚠️ Usage: <code>/download song name</code>\n"
                    "Or play a song first and then use /download",
                    parse_mode="HTML"
                )
                return
        else:
            webpage_url = ""

        quality_label = f"{quality}kbps"
        msg = await message.reply(
            f"╔══「 📥 <b>DOWNLOADING</b> 」══╗\n\n"
            f"  {GOLD} <i>{query[:50]}</i>\n"
            f"  🎵 Quality: <b>{quality_label} MP3</b>\n"
            f"  {'💎 Premium quality' if prem else '⬆️ Upgrade to 320kbps with /buy'}\n\n"
            f"  ⏳ Please wait...\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

        filepath, info = await download_audio(query, quality, webpage_url)

        if not filepath or not info:
            await msg.edit_text(
                f"╔══「 ❌ <b>DOWNLOAD FAILED</b> 」══╗\n\n"
                f"  Couldn't download: <i>{query[:40]}</i>\n"
                f"  Try again or use a different name.\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )
            return

        title      = info.get("title", query)
        artist     = info.get("uploader", "Unknown")
        duration   = info.get("duration", 0)
        filesize   = os.path.getsize(filepath)
        size_mb    = filesize / (1024 * 1024)

        # Check file size (Telegram limit = 50MB)
        if size_mb > 49:
            os.remove(filepath)
            await msg.edit_text("❌ File too large (>50MB). Try a shorter song.")
            return

        # Build safe filename
        safe_name = sanitize(f"{title} - {artist} [{quality_label}]") + ".mp3"

        try:
            with open(filepath, "rb") as f:
                audio_bytes = f.read()

            audio_file = BufferedInputFile(audio_bytes, filename=safe_name)

            await msg.delete()
            await bot.send_audio(
                chat_id,
                audio=audio_file,
                title=title,
                performer=artist,
                duration=duration,
                caption=(
                    f"╔══「 📥 <b>DOWNLOADED</b> 」══╗\n\n"
                    f"  {GOLD} <b>{title}</b>\n"
                    f"  🎤 {artist}\n"
                    f"  🎵 {quality_label} MP3  •  {size_mb:.1f} MB\n"
                    + ("  💎 Premium Quality\n" if prem else "") +
                    f"\n  Royal Music Bot\n\n╚{'═'*32}╝"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            await msg.edit_text(f"❌ Upload failed: {e}")
        finally:
            # Clean up
            try:
                os.remove(filepath)
            except Exception:
                pass

    @dp.message(Command("dlquality"))
    async def dlquality_cmd(message: Message):
        """Show download quality info."""
        user_id = message.from_user.id
        chat_id = message.chat.id
        prem    = is_premium(user_id, chat_id)
        current = DOWNLOAD_QUALITY_PREMIUM if prem else DOWNLOAD_QUALITY_FREE

        await message.reply(
            f"╔══「 🎵 <b>DOWNLOAD QUALITY</b> 」══╗\n\n"
            f"  Your current quality: <b>{current}kbps MP3</b>\n\n"
            f"  🆓 Free: 128kbps\n"
            f"  💎 Premium: 320kbps (crystal clear)\n\n"
            + ("  You have Premium — enjoy 320kbps! 🎶\n" if prem else
               "  Upgrade with /buy for 320kbps quality!\n") +
            f"\n╚{'═'*32}╝",
            parse_mode="HTML"
        )
