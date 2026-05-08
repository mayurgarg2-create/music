"""
handlers/music.py
─────────────────
All music playback commands:
/play /search /now /queue /skip /pause /resume /stop
/back /shuffle /seek /volume /loop /247
"""
import random
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from player import (
    add_to_queue, yt_search, resolve_spotify,
    search_cache, queues, now_playing, play_history,
    play_next, seek_track, stream_track, calls,
    loop_status, volume_cache, np_messages,
    send_now_playing_card, get_elapsed,
    duration_str, progress_bar,
)
from database import get_settings, update_settings, is_group_premium

router = Router()


def register(dp, bot: Bot, owner_id: int):
    dp.include_router(router)


# ══════════════════════════════════════════════
#  /play
# ══════════════════════════════════════════════
@router.message(Command("play"))
async def play_cmd(message: Message, bot: Bot):
    chat_id = message.chat.id
    query   = (message.text or "").partition(" ")[2].strip()

    if not query:
        await message.reply(
            "🎵 <b>Usage:</b> /play &lt;song name or URL&gt;\n\n"
            "Examples:\n"
            "  /play Shape of You\n"
            "  /play https://youtu.be/xxx\n"
            "  /play https://open.spotify.com/track/xxx",
            parse_mode="HTML"
        )
        return

    status_msg = await message.reply("🔍 Searching…")

    # ── Spotify ───────────────────────────────────────────────────────────────
    if "spotify.com" in query:
        resolved, err = await resolve_spotify(query)
        if err:
            await status_msg.edit_text(f"❌ Spotify error: {err}")
            return

        if isinstance(resolved, list):
            # Playlist / album → queue all tracks
            added = 0
            await status_msg.edit_text(f"⏳ Loading {len(resolved)} Spotify tracks…")
            for q_str in resolved:
                results = await yt_search(q_str, max_results=1)
                if results:
                    r = await add_to_queue(
                        chat_id, results[0],
                        user_id=message.from_user.id,
                        bot=bot,
                    )
                    if r in ("playing", "queued"):
                        added += 1
            await status_msg.edit_text(
                f"✅ Added <b>{added}</b> tracks from Spotify to queue.",
                parse_mode="HTML"
            )
            return
        else:
            query = resolved  # single track → fall through to YT search

    # ── YouTube URL or search ─────────────────────────────────────────────────
    results = await yt_search(query, max_results=1)
    if not results:
        await status_msg.edit_text(
            "❌ No results found.\n"
            "Tip: Make sure cookies.txt exists — YouTube blocks unauthenticated requests."
        )
        return

    track  = results[0]
    result = await add_to_queue(
        chat_id, track,
        user_id=message.from_user.id,
        bot=bot,
    )

    msgs = {
        "playing":   f"✅ Now playing: <b>{track['title']}</b>",
        "queued":    f"📋 Added to queue: <b>{track['title']}</b>",
        "full":      "❌ Queue is full. Use /skip to make room.",
        "duplicate": f"⚠️ Already in queue: <b>{track['title']}</b>",
        "error": (
            "❌ Failed to stream. Possible causes:\n"
            "• Missing/expired cookies.txt\n"
            "• YouTube region block\n"
            "• FFmpeg not installed"
        ),
    }
    await status_msg.edit_text(msgs.get(result, "❌ Unknown error."), parse_mode="HTML")


# ══════════════════════════════════════════════
#  /search
# ══════════════════════════════════════════════
@router.message(Command("search"))
async def search_cmd(message: Message):
    chat_id = message.chat.id
    query   = (message.text or "").partition(" ")[2].strip()

    if not query:
        await message.reply("🔍 Usage: /search &lt;song name&gt;", parse_mode="HTML")
        return

    status_msg = await message.reply("🔍 Searching for 5 results…")
    results    = await yt_search(query, max_results=5)

    if not results:
        await status_msg.edit_text("❌ No results found.")
        return

    search_cache[chat_id] = results

    lines = "\n".join(
        f"<b>{i + 1}.</b> {r['title'][:60]} <i>({duration_str(r.get('duration', 0))})</i>"
        for i, r in enumerate(results)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{i + 1}. {r['title'][:35]}",
            callback_data=f"search_pick_{i}"
        )]
        for i, r in enumerate(results)
    ])
    await status_msg.edit_text(
        f"🎵 <b>Search results for:</b> {query}\n\n{lines}",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("search_pick_"))
async def search_pick(cb: CallbackQuery, bot: Bot):
    chat_id = cb.message.chat.id
    idx     = int(cb.data.split("_")[-1])
    results = search_cache.get(chat_id, [])

    if idx >= len(results):
        await cb.answer("❌ Result expired. Search again.", show_alert=True)
        return

    track  = results[idx]
    result = await add_to_queue(chat_id, track, user_id=cb.from_user.id, bot=bot)

    msgs = {
        "playing":   f"✅ Now playing: {track['title']}",
        "queued":    f"📋 Added: {track['title']}",
        "full":      "❌ Queue is full.",
        "duplicate": "⚠️ Already in queue.",
        "error":     "❌ Stream failed. Check cookies.txt.",
    }
    await cb.answer(msgs.get(result, "❌ Error"), show_alert=False)
    # Remove buttons after selection
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ══════════════════════════════════════════════
#  /now  — show now-playing card
# ══════════════════════════════════════════════
@router.message(Command("now"))
async def now_cmd(message: Message, bot: Bot):
    chat_id = message.chat.id
    track   = now_playing.get(chat_id)
    if not track:
        await message.reply("❌ Nothing is playing right now.")
        return
    # Remove old card reference so a fresh one is sent
    np_messages.pop(chat_id, None)
    elapsed = get_elapsed(chat_id)
    await send_now_playing_card(bot, chat_id, track, elapsed=elapsed)


# ══════════════════════════════════════════════
#  /queue
# ══════════════════════════════════════════════
@router.message(Command("queue"))
async def queue_cmd(message: Message):
    chat_id = message.chat.id
    q       = queues.get(chat_id, [])
    current = now_playing.get(chat_id)

    if not current and not q:
        await message.reply("📋 Queue is empty.")
        return

    lines = []
    if current:
        elapsed = get_elapsed(chat_id)
        lines.append(
            f"▶️ <b>Now:</b> {current['title'][:55]}\n"
            f"   ⏱ {duration_str(elapsed)} / {duration_str(current.get('duration', 0))}"
        )
    for i, t in enumerate(q[:20]):
        lines.append(f"  <b>{i + 1}.</b> {t['title'][:55]}")
    if len(q) > 20:
        lines.append(f"\n  ... and {len(q) - 20} more")

    await message.reply(
        f"╔══「 📋 <b>QUEUE</b> 」══╗\n\n"
        + "\n".join(lines)
        + f"\n\n╚{'═' * 22}╝",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════
#  /skip
# ══════════════════════════════════════════════
@router.message(Command("skip"))
async def skip_cmd(message: Message, bot: Bot):
    chat_id = message.chat.id
    if chat_id not in now_playing:
        await message.reply("❌ Nothing is playing.")
        return
    now_playing.pop(chat_id, None)
    track = await play_next(chat_id, bot=bot)
    if track:
        await message.reply(f"⏭ Skipped! Now playing: <b>{track['title']}</b>", parse_mode="HTML")
    else:
        await message.reply("⏭ Skipped. Queue is now empty.")


# ══════════════════════════════════════════════
#  /pause  /resume
# ══════════════════════════════════════════════
@router.message(Command("pause"))
async def pause_cmd(message: Message):
    try:
        await calls.pause(message.chat.id)
        await message.reply("⏸ Paused.")
    except Exception as ex:
        await message.reply(f"❌ {ex}")


@router.message(Command("resume"))
async def resume_cmd(message: Message):
    try:
        await calls.resume(message.chat.id)
        await message.reply("▶️ Resumed.")
    except Exception as ex:
        await message.reply(f"❌ {ex}")


# ══════════════════════════════════════════════
#  /stop
# ══════════════════════════════════════════════
@router.message(Command("stop"))
async def stop_cmd(message: Message):
    chat_id = message.chat.id
    now_playing.pop(chat_id, None)
    queues.pop(chat_id, None)
    np_messages.pop(chat_id, None)
    try:
        await calls.leave_group_call(chat_id)
    except Exception:
        pass
    await message.reply("⏹ Stopped and left voice chat.")


# ══════════════════════════════════════════════
#  /back  — play previous track
# ══════════════════════════════════════════════
@router.message(Command("back"))
async def back_cmd(message: Message, bot: Bot):
    chat_id = message.chat.id
    hist    = play_history.get(chat_id, [])
    if not hist:
        await message.reply("❌ No previous track.")
        return

    prev = hist.pop()
    # Put current track back at front of queue
    current = now_playing.get(chat_id)
    if current:
        queues.setdefault(chat_id, []).insert(0, current)

    now_playing[chat_id] = prev
    from player import record_play
    record_play(chat_id, prev["title"])
    ok = await stream_track(chat_id, prev)
    if ok:
        np_messages.pop(chat_id, None)
        await send_now_playing_card(bot, chat_id, prev)
        await message.reply(f"⏮ Playing previous: <b>{prev['title']}</b>", parse_mode="HTML")
    else:
        await message.reply("❌ Could not play previous track.")


# ══════════════════════════════════════════════
#  /shuffle
# ══════════════════════════════════════════════
@router.message(Command("shuffle"))
async def shuffle_cmd(message: Message):
    chat_id = message.chat.id
    q = queues.get(chat_id, [])
    if not q:
        await message.reply("📋 Queue is empty.")
        return
    random.shuffle(q)
    await message.reply(f"🔀 Shuffled {len(q)} tracks in queue!")


# ══════════════════════════════════════════════
#  /seek [mm:ss or seconds]
# ══════════════════════════════════════════════
@router.message(Command("seek"))
async def seek_cmd(message: Message):
    chat_id = message.chat.id
    arg     = (message.text or "").partition(" ")[2].strip()

    if not arg:
        await message.reply("⏩ Usage: /seek 1:30  or  /seek 90")
        return

    try:
        if ":" in arg:
            parts   = arg.split(":")
            seconds = int(parts[0]) * 60 + int(parts[1])
        else:
            seconds = int(arg)
    except ValueError:
        await message.reply("❌ Invalid time format. Use mm:ss or seconds.")
        return

    ok = await seek_track(chat_id, seconds)
    if ok:
        await message.reply(f"⏩ Seeked to {duration_str(seconds)}")
    else:
        await message.reply("❌ Nothing is playing or seek failed.")


# ══════════════════════════════════════════════
#  /volume [1-200]
# ══════════════════════════════════════════════
@router.message(Command("volume"))
async def volume_cmd(message: Message):
    chat_id = message.chat.id
    arg     = (message.text or "").partition(" ")[2].strip()

    if not arg:
        current = volume_cache.get(chat_id, 100)
        await message.reply(f"🔊 Current volume: <b>{current}%</b>\nUsage: /volume 1-200", parse_mode="HTML")
        return

    try:
        vol = int(arg)
        if not 1 <= vol <= 200:
            raise ValueError
    except ValueError:
        await message.reply("❌ Volume must be between 1 and 200.")
        return

    try:
        await calls.change_volume_call(chat_id, vol)
        volume_cache[chat_id] = vol
        await message.reply(f"🔊 Volume set to <b>{vol}%</b>", parse_mode="HTML")
    except Exception as ex:
        await message.reply(f"❌ {ex}")


# ══════════════════════════════════════════════
#  /loop
# ══════════════════════════════════════════════
@router.message(Command("loop"))
async def loop_cmd(message: Message, bot: Bot):
    chat_id = message.chat.id
    new_val = not loop_status.get(chat_id, False)
    loop_status[chat_id] = new_val
    await message.reply(f"🔁 Loop is now <b>{'ON' if new_val else 'OFF'}</b>", parse_mode="HTML")
    # Refresh now-playing card
    track = now_playing.get(chat_id)
    if track:
        elapsed = get_elapsed(chat_id)
        await send_now_playing_card(bot, chat_id, track, elapsed=elapsed)


# ══════════════════════════════════════════════
#  /247  — toggle 24/7 mode
# ══════════════════════════════════════════════
@router.message(Command("247"))
async def mode_247_cmd(message: Message):
    chat_id = message.chat.id
    s       = get_settings(chat_id)
    new_val = not s.get("mode_247", False)
    update_settings(chat_id, "mode_247", int(new_val))
    await message.reply(
        f"🕐 24/7 mode is now <b>{'ON' if new_val else 'OFF'}</b>\n"
        f"{'Bot will stay in VC even when queue is empty.' if new_val else 'Bot will leave VC when queue is empty.'}",
        parse_mode="HTML"
    )
