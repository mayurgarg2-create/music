"""
handlers/player_callbacks.py
─────────────────────────────
Handles all inline button presses on the now-playing card.
Registered in main.py via: player_callbacks.register(dp, bot, OWNER_ID)
"""
import random
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery

from player import (
    calls, queues, now_playing, np_messages,
    loop_status, volume_cache,
    send_now_playing_card, play_next,
    duration_str, get_elapsed,
)

router = Router()


def register(dp, bot: Bot, owner_id: int):
    dp.include_router(router)


# ── PAUSE ─────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_pause")
async def cb_pause(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    try:
        await calls.pause(chat_id)
        await cb.answer("⏸ Paused")
    except Exception as ex:
        await cb.answer(f"❌ {ex}", show_alert=True)


# ── RESUME ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_resume")
async def cb_resume(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    try:
        await calls.resume(chat_id)
        await cb.answer("▶️ Resumed")
    except Exception as ex:
        await cb.answer(f"❌ {ex}", show_alert=True)


# ── SKIP ──────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_skip")
async def cb_skip(cb: CallbackQuery, bot: Bot):
    chat_id = cb.message.chat.id
    now_playing.pop(chat_id, None)
    track = await play_next(chat_id, bot=bot)
    if track:
        await cb.answer(f"⏭ Skipped → {track['title'][:40]}")
    else:
        await cb.answer("⏭ Queue empty — stopped")


# ── STOP ──────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_stop")
async def cb_stop(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    now_playing.pop(chat_id, None)
    queues.pop(chat_id, None)
    np_messages.pop(chat_id, None)
    try:
        await calls.leave_group_call(chat_id)
    except Exception:
        pass
    await cb.answer("⏹ Stopped")
    try:
        await cb.message.delete()
    except Exception:
        pass


# ── LOOP ──────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_loop")
async def cb_loop(cb: CallbackQuery, bot: Bot):
    chat_id  = cb.message.chat.id
    new_val  = not loop_status.get(chat_id, False)
    loop_status[chat_id] = new_val
    await cb.answer(f"🔁 Loop {'ON' if new_val else 'OFF'}")
    # Refresh card to show updated loop status
    track = now_playing.get(chat_id)
    if track:
        elapsed = get_elapsed(chat_id)
        await send_now_playing_card(bot, chat_id, track, elapsed=elapsed)


# ── SHUFFLE ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_shuffle")
async def cb_shuffle(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    q = queues.get(chat_id, [])
    if q:
        random.shuffle(q)
        await cb.answer(f"🔀 Shuffled {len(q)} tracks!")
    else:
        await cb.answer("Queue is empty")


# ── VOLUME DOWN ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_vol_down")
async def cb_vol_down(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    current = volume_cache.get(chat_id, 100)
    new_vol = max(1, current - 10)
    volume_cache[chat_id] = new_vol
    try:
        await calls.change_volume_call(chat_id, new_vol)
        await cb.answer(f"🔉 Volume: {new_vol}%")
    except Exception as ex:
        await cb.answer(f"❌ {ex}", show_alert=True)


# ── VOLUME UP ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_vol_up")
async def cb_vol_up(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    current = volume_cache.get(chat_id, 100)
    new_vol = min(200, current + 10)
    volume_cache[chat_id] = new_vol
    try:
        await calls.change_volume_call(chat_id, new_vol)
        await cb.answer(f"🔊 Volume: {new_vol}%")
    except Exception as ex:
        await cb.answer(f"❌ {ex}", show_alert=True)


# ── QUEUE PREVIEW ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "player_queue")
async def cb_queue(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    q = queues.get(chat_id, [])
    if not q:
        await cb.answer("📋 Queue is empty", show_alert=True)
        return
    lines = [f"{i + 1}. {t['title'][:50]}" for i, t in enumerate(q[:10])]
    text  = "📋 Up next:\n\n" + "\n".join(lines)
    if len(q) > 10:
        text += f"\n\n... and {len(q) - 10} more"
    await cb.answer(text, show_alert=True)
