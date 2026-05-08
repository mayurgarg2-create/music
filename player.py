"""
Audio Engine — yt-dlp + PyTgCalls + FFmpeg
320kbps premium quality streaming
"""
import asyncio
import os
import base64
import time
import random
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality
from pytgcalls.exceptions import NoActiveGroupCall
from aiogram import Bot
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
#  COOKIES SETUP
# ══════════════════════════════════════════════
COOKIES_PATH  = os.environ.get("COOKIES_PATH", "cookies.txt")
_cookies_b64  = os.environ.get("COOKIES_B64", "")

if _cookies_b64:
    try:
        with open(COOKIES_PATH, "w") as _f:
            _f.write(base64.b64decode(_cookies_b64).decode())
        print("✅ cookies.txt written from COOKIES_B64 env var")
    except Exception as _ex:
        print(f"⚠️  Failed to decode COOKIES_B64: {_ex}")

_COOKIES_EXIST = os.path.isfile(COOKIES_PATH)

if _COOKIES_EXIST:
    print(f"✅ cookies.txt ready → {os.path.abspath(COOKIES_PATH)}")
else:
    print(
        "⚠️  cookies.txt NOT found — YouTube will block requests!\n"
        "   Railway: add COOKIES_B64 variable in Railway → Variables tab\n"
        "   VPS: place cookies.txt next to player.py"
    )


def _ydl_opts(extra: dict = None) -> dict:
    opts = {
        "quiet":          True,
        "no_warnings":    True,
        "source_address": "0.0.0.0",
        "geo_bypass":     True,
        **({"cookiefile": COOKIES_PATH} if _COOKIES_EXIST else {}),
    }
    if extra:
        opts.update(extra)
    return opts


# ══════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════
queues       = {}
now_playing  = {}
play_history = {}
stream_start = {}
vote_skips   = {}
search_cache = {}
game_audio   = {}
np_messages  = {}
loop_status  = {}
volume_cache = {}


# ══════════════════════════════════════════════
#  NOW-PLAYING CARD
# ══════════════════════════════════════════════
def player_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸ Pause",    callback_data="player_pause"),
            InlineKeyboardButton(text="▶️ Resume",   callback_data="player_resume"),
            InlineKeyboardButton(text="⏭ Skip",     callback_data="player_skip"),
        ],
        [
            InlineKeyboardButton(text="🔁 Loop",    callback_data="player_loop"),
            InlineKeyboardButton(text="🔀 Shuffle",  callback_data="player_shuffle"),
            InlineKeyboardButton(text="⏹ Stop",     callback_data="player_stop"),
        ],
        [
            InlineKeyboardButton(text="🔉 Vol -10", callback_data="player_vol_down"),
            InlineKeyboardButton(text="📋 Queue",   callback_data="player_queue"),
            InlineKeyboardButton(text="🔊 Vol +10", callback_data="player_vol_up"),
        ],
    ])


async def send_now_playing_card(bot: Bot, chat_id: int, track: dict, elapsed: int = 0) -> None:
    total   = track.get("duration", 0)
    bar     = progress_bar(elapsed, total)
    title   = track.get("title", "Unknown")
    artist  = track.get("artist", "Unknown")
    source  = track.get("source", "YouTube")
    thumb   = track.get("thumb", "")
    loop_on = loop_status.get(chat_id, False)
    q_count = len(queues.get(chat_id, []))

    caption = (
        f"╔══「 👑 <b>NOW PLAYING</b> 」══╗\n\n"
        f"  🎵 <b>{title}</b>\n"
        f"  👤 {artist}\n"
        f"  📡 Source: {source}\n"
        f"  🔁 Loop: {'✅ ON' if loop_on else '❌ OFF'} | 📋 Queue: {q_count}\n\n"
        f"  {bar}\n"
        f"  ⏱ {duration_str(elapsed)} / {duration_str(total)}\n\n"
        f"╚{'═' * 30}╝"
    )
    kb = player_keyboard()

    try:
        if chat_id in np_messages:
            stored_bot, msg_id = np_messages[chat_id]
            try:
                await stored_bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=msg_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                return
            except Exception:
                pass

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
                vid_id      = e.get("id", "")
                webpage_url = (
                    e.get("webpage_url")
                    or (f"https://www.youtube.com/watch?v={vid_id}" if vid_id else "")
                )
                if not webpage_url:
                    continue

                thumb = ""
                raw   = e.get("thumbnail") or e.get("thumbnails")
                if isinstance(raw, list) and raw:
                    thumb = raw[-1].get("url", "")
                elif isinstance(raw, str):
                    thumb = raw

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
#  STREAM URL RESOLVER
# ══════════════════════════════════════════════
async def get_fresh_url(webpage_url: str) -> str | None:
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
#  VOICE CHAT JOIN HELPER
# ══════════════════════════════════════════════
async def _join_and_play(chat_id: int, stream) -> bool:
    """Play in VC. If no active call exists, create one then retry."""
    try:
        await calls.play(chat_id, stream)
        return True
    except NoActiveGroupCall:
        print(f"[JOIN_VC] No active group call in {chat_id}, creating one...")
        try:
            from pyrogram.raw.functions.phone import CreateGroupCall
            await pyro.invoke(
                CreateGroupCall(
                    peer=await pyro.resolve_peer(chat_id),
                    random_id=random.randint(10000, 99999),
                )
            )
            await asyncio.sleep(3)
            await calls.play(chat_id, stream)
            print(f"[JOIN_VC] Successfully joined VC in {chat_id}")
            return True
        except Exception as ex:
            print(f"[JOIN_VC CreateGroupCall ERROR] {ex}")
            # Final retry
            try:
                await calls.play(chat_id, stream)
                return True
            except Exception as ex2:
                print(f"[JOIN_VC FINAL RETRY ERROR] {ex2}")
                return False
    except Exception as ex:
        print(f"[STREAM ERROR] {ex}")
        return False


# ══════════════════════════════════════════════
#  STREAM ENGINE
# ══════════════════════════════════════════════
async def stream_track(chat_id: int, track: dict, seek: int = 0) -> bool:
    """Resolve stream URL and start/change playback in the voice chat."""
    audio_url = await get_fresh_url(track.get("webpage_url") or track.get("url", ""))
    if not audio_url:
        print(f"[STREAM_TRACK] No audio URL for: {track.get('title')}")
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
        stream = MediaStream(audio_url, audio_parameters=quality)

    ok = await _join_and_play(chat_id, stream)
    if ok:
        stream_start[chat_id] = time.time() - seek
    return ok


async def play_next(chat_id: int, bot: Bot = None) -> dict | None:
    """Play the next track in queue."""
    s = get_settings(chat_id)

    if loop_status.get(chat_id, False) and chat_id in now_playing:
        track = now_playing[chat_id]

    elif s.get("loop_queue") and not queues.get(chat_id) and play_history.get(chat_id):
        queues[chat_id] = list(play_history[chat_id])
        track = queues[chat_id].pop(0)
        _save_history(chat_id)
        now_playing[chat_id] = track

    else:
        if not queues.get(chat_id):
            if not s.get("mode_247"):
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

    if bot is None and chat_id in np_messages:
        bot, _ = np_messages[chat_id]
    if bot:
        await send_now_playing_card(bot, chat_id, track)

    return track


def _save_history(chat_id: int):
    if chat_id in now_playing:
        hist = play_history.setdefault(chat_id, [])
        hist.append(now_playing[chat_id])
        if len(hist) > 15:
            hist.pop(0)


# ══════════════════════════════════════════════
#  ADD TO QUEUE  ← MAIN FIX HERE
# ══════════════════════════════════════════════
async def add_to_queue(chat_id: int, track: dict, user_id: int = 0, bot: Bot = None) -> str:
    """
    Add track to queue or start playing immediately.
    Returns: 'playing' | 'queued' | 'full' | 'duplicate' | 'error'

    FIX: If chat_id is in now_playing but stream is dead/stale,
         clear it and restart instead of queueing.
    """
    s  = get_settings(chat_id)
    q  = queues.setdefault(chat_id, [])
    mx = s.get("max_queue", 50)

    # ── Duplicate check ───────────────────────────────────────────────────────
    if s.get("duplicate_check"):
        all_titles = (
            [now_playing[chat_id]["title"]] if chat_id in now_playing else []
        ) + [t["title"] for t in q]
        if track["title"] in all_titles:
            return "duplicate"

    # ── Queue full ────────────────────────────────────────────────────────────
    if len(q) >= mx:
        return "full"

    # ── Check if already "playing" but VC is actually dead ───────────────────
    if chat_id in now_playing:
        try:
            # Check if bot is actually in a call
            active = await calls.get_call(chat_id)
            if active is None:
                raise Exception("No active call")
            # VC is alive → queue the track
            q.append(track)
            return "queued"
        except Exception:
            # VC is dead/stale → clear state and play fresh
            print(f"[ADD_TO_QUEUE] Stale VC state detected for {chat_id}, clearing and replaying...")
            now_playing.pop(chat_id, None)
            queues[chat_id] = []
            np_messages.pop(chat_id, None)
            stream_start.pop(chat_id, None)

    # ── Play immediately ──────────────────────────────────────────────────────
    now_playing[chat_id] = track
    record_play(chat_id, track["title"])
    ok = await stream_track(chat_id, track)

    if ok:
        if bot:
            await send_now_playing_card(bot, chat_id, track)
        return "playing"
    else:
        # Stream failed — clean up so next /play doesn't get stuck
        now_playing.pop(chat_id, None)
        return "error"


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
