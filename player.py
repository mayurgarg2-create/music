"""
Audio Engine — yt-dlp + PyTgCalls + FFmpeg
320kbps premium quality streaming
"""
import asyncio
import time
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality
from pytgcalls.exceptions import NoActiveGroupCall
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
#  STATE
# ══════════════════════════════════════════════
queues       = {}   # chat_id -> [track, ...]
now_playing  = {}   # chat_id -> track dict
play_history = {}   # chat_id -> [track, ...]
stream_start = {}   # chat_id -> timestamp
vote_skips   = {}   # chat_id -> set(user_ids)
search_cache = {}   # chat_id -> [results]
game_audio   = {}   # chat_id -> audio_url for guess game

# ══════════════════════════════════════════════
#  YT-DLP
# ══════════════════════════════════════════════
async def yt_search(query: str, max_results: int = 5) -> list[dict]:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "source_address": "0.0.0.0",
        "geo_bypass": True,
    }
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            )
            results = []
            for e in (info.get("entries") or []):
                if e and e.get("url"):
                    results.append({
                        "title":       e.get("title", "Unknown"),
                        "url":         e.get("url"),
                        "duration":    e.get("duration", 0),
                        "thumb":       e.get("thumbnail", ""),
                        "source":      "YouTube",
                        "webpage_url": e.get("webpage_url", ""),
                        "artist":      e.get("uploader", ""),
                    })
            return results
    except Exception as ex:
        print(f"[YT_SEARCH] {ex}")
        return []

async def get_fresh_url(webpage_url: str) -> str | None:
    opts = {"format": "bestaudio/best", "quiet": True, "no_warnings": True}
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(webpage_url, download=False))
            return info.get("url")
    except Exception:
        return None

async def resolve_spotify(url: str):
    if not sp:
        return None, "Spotify credentials not configured."
    try:
        if "track" in url:
            t = sp.track(url)
            return f"{t['name']} {t['artists'][0]['name']}", None
        elif "playlist" in url:
            items = sp.playlist_tracks(url)["items"][:30]
            return [f"{i['track']['name']} {i['track']['artists'][0]['name']}"
                    for i in items if i.get("track")], None
        elif "album" in url:
            items = sp.album_tracks(url)["items"][:30]
            return [f"{i['name']} {i['artists'][0]['name']}" for i in items], None
    except Exception as ex:
        return None, str(ex)
    return None, "Unsupported Spotify URL."

# ══════════════════════════════════════════════
#  STREAM ENGINE
# ══════════════════════════════════════════════
async def stream_track(chat_id: int, track: dict, seek: int = 0) -> bool:
    audio_url = await get_fresh_url(track.get("webpage_url", track.get("url", "")))
    if not audio_url:
        return False

    premium = is_group_premium(chat_id)
    quality = AudioQuality.HIGH if premium else AudioQuality.MEDIUM

    # Build MediaStream — seek via ffmpeg_parameters if needed
    ffmpeg_params = f"-ss {seek}" if seek else ""

    try:
        stream = MediaStream(
            audio_url,
            audio_parameters=quality,
            ffmpeg_parameters=ffmpeg_params if ffmpeg_params else None,
        )
    except TypeError:
        # Some versions don't support ffmpeg_parameters keyword — fall back
        stream = MediaStream(audio_url, audio_parameters=quality)

    try:
        # Try to change existing stream first
        await calls.play(chat_id, stream)
    except NoActiveGroupCall:
        try:
            await calls.play(chat_id, stream)
        except Exception as ex:
            print(f"[JOIN_VC] {ex}")
            return False
    except Exception as ex:
        print(f"[STREAM] {ex}")
        return False

    stream_start[chat_id] = time.time() - seek
    return True

async def play_next(chat_id: int) -> dict | None:
    """Play next track. Returns the track played or None."""
    s = get_settings(chat_id)

    if s["loop"] and chat_id in now_playing:
        track = now_playing[chat_id]
    elif s.get("loop_queue") and queues.get(chat_id) == [] and play_history.get(chat_id):
        queues[chat_id] = list(play_history.get(chat_id, []))
        track = queues[chat_id].pop(0)
        _save_history(chat_id)
        now_playing[chat_id] = track
    else:
        if not queues.get(chat_id):
            if not s["mode_247"]:
                now_playing.pop(chat_id, None)
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
        return await play_next(chat_id)
    return track

def _save_history(chat_id: int):
    """Save current now_playing to history before switching."""
    if chat_id in now_playing:
        hist = play_history.setdefault(chat_id, [])
        hist.append(now_playing[chat_id])
        if len(hist) > 15:
            hist.pop(0)

async def add_to_queue(chat_id: int, track: dict, user_id: int = 0) -> str:
    """Returns: 'playing' | 'queued' | 'full' | 'duplicate' | 'error'"""
    s   = get_settings(chat_id)
    q   = queues.setdefault(chat_id, [])
    mx  = s.get("max_queue", 20)

    if s.get("duplicate_check"):
        all_titles = ([now_playing[chat_id]["title"]] if chat_id in now_playing else []) + [t["title"] for t in q]
        if track["title"] in all_titles:
            return "duplicate"

    if len(q) >= mx:
        return "full"

    if chat_id not in now_playing:
        now_playing[chat_id] = track
        record_play(chat_id, track["title"])
        ok = await stream_track(chat_id, track)
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

def get_elapsed(chat_id: int) -> int:
    start = stream_start.get(chat_id, time.time())
    return int(time.time() - start)

def duration_str(sec) -> str:
    if not sec: return "LIVE"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def progress_bar(elapsed: int, total: int, length: int = 14) -> str:
    if not total: return "▓" * length
    pct    = min(elapsed / total, 1.0)
    filled = int(length * pct)
    return "▓" * filled + "░" * (length - filled)
