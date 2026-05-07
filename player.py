"""
Audio Engine — yt-dlp + PyTgCalls + FFmpeg
320kbps premium quality streaming

FIXES APPLIED:
  1. YouTube bot-detection bypass via cookies file (cookies.txt)
  2. NoActiveGroupCall → properly joins VC before retrying stream
  3. Now-playing card sent with inline control buttons
"""
import asyncio
import os
import time
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality
from pytgcalls.exceptions import NoActiveGroupCall
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    API_ID, API_HASH, STRING_SESSION,
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
)
from database import (
    get_settings, record_play, is_group_premium,
    update_listening_time, add_history
)

# ══════════════════════════════════════════════
#  CLIENTS
# ══════════════════════════════════════════════
pyro  = Client("RoyalMusic", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
calls = PyTgCalls(pyro)

sp = (
    spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
    )) if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET else None
)

# ══════════════════════════════════════════════
#  COOKIES PATH  (FIX 1 — YouTube bot detection)
# ══════════════════════════════════════════════
# Export cookies from your browser after signing into YouTube:
#   yt-dlp --cookies-from-browser chrome --skip-download "https://youtube.com"
#   → saves cookies.txt  (or export manually via browser extension)
# Place cookies.txt next to this file OR set COOKIES_PATH in your env.
COOKIES_PATH = os.environ.get("COOKIES_PATH", "cookies.txt")
_COOKIES_EXIST = os.path.isfile(COOKIES_PATH)

if not _COOKIES_EXIST:
    print(
        "⚠️  cookies.txt not found — YouTube may block requests.\n"
        "   Export via:  yt-dlp --cookies-from-browser chrome --skip-download https://youtube.com\n"
        f"   Then place at: {os.path.abspath(COOKIES_PATH)}"
    )


def _ydl_opts(extra: dict = None) -> dict:
    """Base yt-dlp options, always injecting cookies when available."""
    opts = {
        "quiet":          True,
        "no_warnings":    True,
        "source_address": "0.0.0.0",
        "geo_bypass":     True,
        # ── FIX 1: pass cookies file when it exists ──────────────────────
        **({"cookiefile": COOKIES_PATH} if _COOKIES_EXIST else {}),
    }
    if extra:
        opts.update(extra)
    return opts


# ══════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════
queues       = {}   # chat_id -> [track, ...]
now_playing  = {}   # chat_id -> track dict
play_history = {}   # chat_id -> [track, ...]
stream_start = {}   # chat_id -> timestamp
vote_skips   = {}   # chat_id -> set(user_ids)
search_cache = {}   # chat_id -> [results]
game_audio   = {}   # chat_id -> audio_url for guess game

# Stores (bot, message_id) of now-playing cards so we can edit them
np_messages  = {}   # chat_id -> (bot_instance, message_id)


# ══════════════════════════════════════════════
#  NOW-PLAYING INLINE KEYBOARD  (FIX 3)
# ══════════════════════════════════════════════
def player_keyboard() -> InlineKeyboardMarkup:
    """Inline control buttons shown on the now-playing card."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸ Pause",   callback_data="player_pause"),
            InlineKeyboardButton(text="▶️ Resume",  callback_data="player_resume"),
            InlineKeyboardButton(text="⏭ Skip",    callback_data="player_skip"),
        ],
        [
            InlineKeyboardButton(text="🔁 Loop",   callback_data="player_loop"),
            InlineKeyboardButton(text="🔀 Shuffle", callback_data="player_shuffle"),
            InlineKeyboardButton(text="⏹ Stop",    callback_data="player_stop"),
        ],
        [
            InlineKeyboardButton(text="🔉 Vol -10", callback_data="player_vol_down"),
            InlineKeyboardButton(text="📋 Queue",   callback_data="player_queue"),
            InlineKeyboardButton(text="🔊 Vol +10", callback_data="player_vol_up"),
        ],
    ])


async def send_now_playing_card(
    bot,
    chat_id: int,
    track: dict,
    elapsed: int = 0,
) -> None:
    """
    Send (or edit) the now-playing card with inline buttons.
    Stores the message reference in np_messages so it can be updated later.
    """
    total   = track.get("duration", 0)
    bar     = progress_bar(elapsed, total)
    elapsed_str = duration_str(elapsed)
    total_str   = duration_str(total)
    thumb   = track.get("thumb", "")
    title   = track.get("title", "Unknown")
    artist  = track.get("artist", "")
    source  = track.get("source", "YouTube")

    caption = (
        f"╔══「 👑 <b>NOW PLAYING</b> 」══╗\n\n"
        f"  🎵 <b>{title}</b>\n"
        f"  👤 {artist or 'Unknown'}\n"
        f"  📡 Source: {source}\n\n"
        f"  {bar}\n"
        f"  ⏱ {elapsed_str} / {total_str}\n\n"
        f"╚{'═'*30}╝"
    )
    kb = player_keyboard()

    try:
        # If we already have a card, try to edit it
        if chat_id in np_messages:
            _, msg_id = np_messages[chat_id]
            try:
                await bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=msg_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                return
            except Exception:
                pass  # Fall through to send a fresh card

        # Send a fresh card (with photo if thumb is available)
        if thumb:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=thumb,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        np_messages[chat_id] = (bot, msg.message_id)
    except Exception as ex:
        print(f"[NOW_PLAYING_CARD ERROR] {ex}")


# ══════════════════════════════════════════════
#  YT-DLP SEARCH
# ══════════════════════════════════════════════
async def yt_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search YouTube and return a list of track metadata dicts.
    Uses extract_flat=True so we only fetch metadata (fast).
    The actual stream URL is resolved later in get_fresh_url().
    """
    opts = _ydl_opts({
        "extract_flat":   True,
        "default_search": "ytsearch",
    })
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            )
            results = []
            for e in (info.get("entries") or []):
                if not e:
                    continue
                vid_id = e.get("id", "")
                webpage_url = (
                    e.get("webpage_url")
                    or (f"https://www.youtube.com/watch?v={vid_id}" if vid_id else "")
                )
                if not webpage_url:
                    continue

                thumb = ""
                raw_thumb = e.get("thumbnail") or e.get("thumbnails")
                if isinstance(raw_thumb, list) and raw_thumb:
                    thumb = raw_thumb[-1].get("url", "")
                elif isinstance(raw_thumb, str):
                    thumb = raw_thumb

                results.append({
                    "title":       e.get("title", "Unknown"),
                    "url":         webpage_url,
                    "webpage_url": webpage_url,
                    "duration":    e.get("duration", 0),
                    "thumb":       thumb,
                    "source":      "YouTube",
                    "artist":      e.get("uploader") or e.get("channel", ""),
                })
            return results
    except Exception as ex:
        print(f"[YT_SEARCH ERROR] {ex}")
        return []


# ══════════════════════════════════════════════
#  STREAM URL RESOLVER  (FIX 1 continued)
# ══════════════════════════════════════════════
async def get_fresh_url(webpage_url: str) -> str | None:
    """
    Given a YouTube watch URL, extract a fresh direct audio stream URL.
    Called right before PyTgCalls starts streaming.
    Cookies are injected automatically via _ydl_opts().
    """
    if not webpage_url:
        return None

    opts = _ydl_opts({"format": "bestaudio/best"})
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(webpage_url, download=False)
            )
            if info.get("entries"):
                info = info["entries"][0]
            url = info.get("url")
            if not url:
                for fmt in reversed(info.get("formats", [])):
                    if fmt.get("acodec") != "none" and fmt.get("url"):
                        url = fmt["url"]
                        break
            return url
    except Exception as ex:
        print(f"[GET_FRESH_URL ERROR] {ex}")
        return None


# ══════════════════════════════════════════════
#  SPOTIFY RESOLVER
# ══════════════════════════════════════════════
async def resolve_spotify(url: str):
    if not sp:
        return None, "Spotify credentials not configured."
    try:
        if "track" in url:
            t = sp.track(url)
            return f"{t['name']} {t['artists'][0]['name']}", None
        elif "playlist" in url:
            items = sp.playlist_tracks(url)["items"][:30]
            return [
                f"{i['track']['name']} {i['track']['artists'][0]['name']}"
                for i in items if i.get("track")
            ], None
        elif "album" in url:
            items = sp.album_tracks(url)["items"][:30]
            return [f"{i['name']} {i['artists'][0]['name']}" for i in items], None
    except Exception as ex:
        return None, str(ex)
    return None, "Unsupported Spotify URL."


# ══════════════════════════════════════════════
#  STREAM ENGINE  (FIX 2 — proper VC join)
# ══════════════════════════════════════════════
async def _join_and_play(chat_id: int, stream: "MediaStream") -> bool:
    """
    Attempt to play in VC. If NoActiveGroupCall, create the call first,
    then retry. Returns True on success.
    """
    try:
        await calls.play(chat_id, stream)
        return True
    except NoActiveGroupCall:
        # ── FIX 2: join the voice chat via Pyrogram, then retry ──────────
        try:
            # Start a group call if none exists (requires Pyrogram)
            await pyro.invoke(
                __import__("pyrogram.raw.functions.phone", fromlist=["CreateGroupCall"])
                .CreateGroupCall(
                    peer=await pyro.resolve_peer(chat_id),
                    random_id=__import__("random").randint(1000, 9999),
                )
            )
            await asyncio.sleep(1)          # let Telegram register the call
            await calls.play(chat_id, stream)
            return True
        except Exception as ex:
            print(f"[JOIN_VC CREATE_CALL ERROR] {ex}")
            # Last resort: just retry play once more (works if call already existed)
            try:
                await calls.play(chat_id, stream)
                return True
            except Exception as ex2:
                print(f"[JOIN_VC FINAL RETRY ERROR] {ex2}")
                return False
    except Exception as ex:
        print(f"[STREAM ERROR] {ex}")
        return False


async def stream_track(chat_id: int, track: dict, seek: int = 0) -> bool:
    """Resolve stream URL and start/change playback in the voice chat."""
    audio_url = await get_fresh_url(track.get("webpage_url") or track.get("url", ""))
    if not audio_url:
        print(f"[STREAM_TRACK] Could not resolve audio URL for: {track.get('title')}")
        return False

    premium = is_group_premium(chat_id)
    quality = AudioQuality.HIGH if premium else AudioQuality.MEDIUM
    ffmpeg_params = f"-ss {seek}" if seek else None

    try:
        stream = MediaStream(
            audio_url,
            audio_parameters=quality,
            ffmpeg_parameters=ffmpeg_params,
        )
    except TypeError:
        # Older py-tgcalls versions don't support ffmpeg_parameters
        stream = MediaStream(audio_url, audio_parameters=quality)

    ok = await _join_and_play(chat_id, stream)
    if ok:
        stream_start[chat_id] = time.time() - seek
    return ok


async def play_next(chat_id: int, bot=None) -> dict | None:
    """
    Play the next track in queue.
    Pass `bot` to send/update the now-playing card automatically.
    Returns the track played or None.
    """
    s = get_settings(chat_id)

    if s["loop"] and chat_id in now_playing:
        track = now_playing[chat_id]

    elif s.get("loop_queue") and not queues.get(chat_id) and play_history.get(chat_id):
        queues[chat_id] = list(play_history.get(chat_id, []))
        track = queues[chat_id].pop(0)
        _save_history(chat_id)
        now_playing[chat_id] = track

    else:
        if not queues.get(chat_id):
            if not s["mode_247"]:
                now_playing.pop(chat_id, None)
                np_messages.pop(chat_id, None)
                try:
                    await calls.leave_group_call(chat_id)
                except Exception:
                    pass
            return None
        track = queues[chat_id].pop(0)
        _save_history(chat_id)
        now_playing[chat_id] = track

    record_play(chat_id, track["title"])
    ok = await stream_track(chat_id, track)
    if not ok:
        now_playing.pop(chat_id, None)
        return await play_next(chat_id, bot=bot)

    # ── FIX 3: send now-playing card with inline buttons ─────────────────
    if bot is None and chat_id in np_messages:
        bot, _ = np_messages[chat_id]   # reuse stored bot instance
    if bot:
        await send_now_playing_card(bot, chat_id, track)

    return track


def _save_history(chat_id: int):
    """Save current now_playing to history before switching."""
    if chat_id in now_playing:
        hist = play_history.setdefault(chat_id, [])
        hist.append(now_playing[chat_id])
        if len(hist) > 15:
            hist.pop(0)


async def add_to_queue(chat_id: int, track: dict, user_id: int = 0, bot=None) -> str:
    """
    Add a track to the queue or start playing immediately.
    Pass `bot` so the now-playing card is sent when playback starts.
    Returns: 'playing' | 'queued' | 'full' | 'duplicate' | 'error'
    """
    s  = get_settings(chat_id)
    q  = queues.setdefault(chat_id, [])
    mx = s.get("max_queue", 20)

    if s.get("duplicate_check"):
        all_titles = (
            [now_playing[chat_id]["title"]] if chat_id in now_playing else []
        ) + [t["title"] for t in q]
        if track["title"] in all_titles:
            return "duplicate"

    if len(q) >= mx:
        return "full"

    if chat_id not in now_playing:
        now_playing[chat_id] = track
        record_play(chat_id, track["title"])
        ok = await stream_track(chat_id, track)
        if ok and bot:
            await send_now_playing_card(bot, chat_id, track)
        return "playing" if ok else "error"
    else:
        q.append(track)
        return "queued"


async def seek_track(chat_id: int, seconds: int) -> bool:
    track = now_playing.get(chat_id)
    if not track:
        return False
    ok = await stream_track(chat_id, track, seek=seconds)
    if ok:
        stream_start[chat_id] = time.time() - seconds
    return ok


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def get_elapsed(chat_id: int) -> int:
    start = stream_start.get(chat_id, time.time())
    return int(time.time() - start)


def duration_str(sec) -> str:
    if not sec:
        return "LIVE"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def progress_bar(elapsed: int, total: int, length: int = 14) -> str:
    if not total:
        return "▓" * length
    pct    = min(elapsed / total, 1.0)
    filled = int(length * pct)
    return "▓" * filled + "░" * (length - filled)
