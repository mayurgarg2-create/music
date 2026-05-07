"""Music command handlers — /play /skip /pause /resume /stop /queue /now /seek /shuffle /back"""
import time
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberAdministrator, ChatMemberOwner
)
from config import (
    COOLDOWN_FREE, COOLDOWN_PREMIUM,
    MAX_QUEUE_PER_USER_FREE, VOTE_SKIP_COUNT
)
from database import (
    register_group, register_user, is_premium,
    is_group_premium, get_settings, update_setting,
    get_last_play, update_last_play, is_blacklisted,
    get_lang, get_top_songs, record_play,
    log_spam, get_spam_count, mute_user, reset_spam,
    add_history, is_dj
)
from player import (
    queues, now_playing, vote_skips, play_history,
    stream_start, search_cache,
    yt_search, resolve_spotify, add_to_queue,
    play_next, stream_track, seek_track,
    get_elapsed, duration_str, progress_bar
)
from card import make_card
from ai import ai_dj_intro, add_ai_message

GOLD = "👑"
NOTE = "🎵"

# ── Permission helpers ────────────────────────
def is_owner(uid, owner_id): return uid == owner_id

async def is_admin(bot: Bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return isinstance(m, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False

async def has_permission(bot, chat_id, user_id, owner_id):
    if user_id == owner_id: return True
    if await is_admin(bot, chat_id, user_id): return True
    s = get_settings(chat_id)
    if s.get("dj_role") and is_dj(chat_id, user_id): return True
    return False

def mention(uid, name): return f"<a href='tg://user?id={uid}'>{name}</a>"

def player_kb(chat_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸", callback_data=f"pause:{chat_id}"),
            InlineKeyboardButton(text="▶️", callback_data=f"resume:{chat_id}"),
            InlineKeyboardButton(text="⏭ Skip", callback_data=f"skip:{chat_id}"),
            InlineKeyboardButton(text="⏹ Stop", callback_data=f"stop:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="🔉 Vol−", callback_data=f"vol:down:{chat_id}"),
            InlineKeyboardButton(text="🔊 Vol+", callback_data=f"vol:up:{chat_id}"),
            InlineKeyboardButton(text="⏮ Back", callback_data=f"back:{chat_id}"),
            InlineKeyboardButton(text="🔀 Shuffle", callback_data=f"shuffle:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="🔁 Loop",  callback_data=f"loop:{chat_id}"),
            InlineKeyboardButton(text="🌙 24/7",  callback_data=f"247:{chat_id}"),
            InlineKeyboardButton(text="🎛 EQ",    callback_data=f"eq_menu:{chat_id}"),
            InlineKeyboardButton(text="📋 Queue", callback_data=f"queue_cb:{chat_id}"),
        ],
    ])

def eq_kb(chat_id):
    from database import get_settings
    s = get_settings(chat_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔉 Bass: {s['eq_bass']:+d}dB", callback_data=f"eq_info:{chat_id}")],
        [InlineKeyboardButton(text="Bass −", callback_data=f"eq:bass:-1:{chat_id}"),
         InlineKeyboardButton(text="Bass +", callback_data=f"eq:bass:1:{chat_id}")],
        [InlineKeyboardButton(text=f"🎼 Mid: {s['eq_mid']:+d}dB", callback_data=f"eq_info:{chat_id}")],
        [InlineKeyboardButton(text="Mid −", callback_data=f"eq:mid:-1:{chat_id}"),
         InlineKeyboardButton(text="Mid +",  callback_data=f"eq:mid:1:{chat_id}")],
        [InlineKeyboardButton(text=f"🔊 Treble: {s['eq_treble']:+d}dB", callback_data=f"eq_info:{chat_id}")],
        [InlineKeyboardButton(text="Treble −", callback_data=f"eq:treble:-1:{chat_id}"),
         InlineKeyboardButton(text="Treble +",  callback_data=f"eq:treble:1:{chat_id}")],
        [InlineKeyboardButton(text="🔄 Reset", callback_data=f"eq:reset:0:{chat_id}"),
         InlineKeyboardButton(text="🔙 Back",  callback_data=f"player_back:{chat_id}")],
    ])

def voteskip_kb(chat_id, votes):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🗳 Vote Skip ({votes}/{VOTE_SKIP_COUNT})", callback_data=f"voteskip:{chat_id}")
    ]])

def search_kb(chat_id, results):
    btns = []
    for i, r in enumerate(results[:5]):
        t = r["title"][:42] + "..." if len(r["title"]) > 42 else r["title"]
        btns.append([InlineKeyboardButton(text=f"{i+1}. {t}", callback_data=f"pick:{chat_id}:{i}")])
    btns.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_search:{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

def now_text(chat_id):
    track = now_playing.get(chat_id)
    if not track: return "❌ Nothing playing."
    s       = get_settings(chat_id)
    elapsed = get_elapsed(chat_id)
    bar     = progress_bar(elapsed, track.get("duration", 0))
    prem    = is_group_premium(chat_id)
    return (
        f"╔══「 {NOTE} <b>NOW PLAYING</b> {NOTE} 」══╗\n\n"
        f"  {GOLD} <b>{track['title']}</b>\n\n"
        f"  ⏱ <code>{duration_str(elapsed)} / {duration_str(track.get('duration',0))}</code>\n"
        f"  <code>{bar}</code>\n\n"
        f"  🎤 {track.get('requester','')}\n"
        f"  📡 {track.get('source','YouTube')}  🔊 {s.get('volume',100)}%"
        + (f"  💎 Premium" if prem else "") +
        f"\n╚{'═'*32}╝"
    )

async def send_now_playing(bot: Bot, chat_id: int, track: dict, requester_name: str, reply_msg: Message = None):
    prem = is_group_premium(chat_id)
    elapsed = get_elapsed(chat_id)
    try:
        card  = make_card(track, requester_name, elapsed, prem)
        photo = BufferedInputFile(card, filename="now_playing.jpg")
        caption = now_text(chat_id)
        kb = player_kb(chat_id)

        # Show sponsor if group premium
        gp = get_group_premium(chat_id) if prem else None
        if gp and gp.get("sponsor_name"):
            caption += f"\n\n  💎 <i>Sponsored by {gp['sponsor_name']}</i>"

        if reply_msg:
            await reply_msg.delete()
        await bot.send_photo(chat_id, photo, caption=caption, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await bot.send_message(chat_id, now_text(chat_id), reply_markup=player_kb(chat_id), parse_mode="HTML")

# ── Anti-spam check ───────────────────────────
async def check_cooldown(user_id: int, chat_id: int, is_prem: bool) -> int:
    """Returns seconds remaining on cooldown, 0 if clear."""
    last = get_last_play(user_id)
    cd   = COOLDOWN_PREMIUM if is_prem else COOLDOWN_FREE
    remaining = cd - (int(time.time()) - last)
    return max(0, remaining)

def register(dp: Dispatcher, bot: Bot, owner_id: int):

    # ── /play ─────────────────────────────────
    @dp.message(Command("play"))
    async def play_cmd(message: Message):
        if message.chat.type not in ("group", "supergroup"):
            await message.reply("⚠️ Use me in a group!"); return

        chat_id   = message.chat.id
        user_id   = message.from_user.id
        register_group(chat_id, message.chat.title or "")
        register_user(user_id, message.from_user.username or "", message.from_user.first_name)

        # Spam / mute check
        _, muted_until = get_spam_count(user_id, chat_id)
        if muted_until and muted_until > int(time.time()):
            await message.reply(f"⏳ You are muted until <code>{time.strftime('%H:%M:%S', time.localtime(muted_until))}</code>", parse_mode="HTML"); return

        prem      = is_premium(user_id, chat_id)
        requester = mention(user_id, message.from_user.first_name)

        # Admin-only mode
        s = get_settings(chat_id)
        if s.get("admin_only") and not await has_permission(bot, chat_id, user_id, owner_id):
            await message.reply("🔒 Bot is in admin-only mode."); return

        # Cooldown
        cd = await check_cooldown(user_id, chat_id, prem)
        if cd > 0:
            log_spam(user_id, chat_id)
            cnt, _ = get_spam_count(user_id, chat_id)
            if cnt >= 5:
                mute_user(user_id, chat_id, 60)
                await message.reply("🚫 Too many requests! You've been muted for 60 seconds."); return
            await message.reply(f"⏳ Cooldown: <b>{cd}s</b> remaining.", parse_mode="HTML"); return

        reset_spam(user_id, chat_id)

        parts = message.text.split(maxsplit=1)
        query = (parts[1].strip() if len(parts) > 1 else "").strip()
        if not query and message.reply_to_message:
            query = (message.reply_to_message.text or "").strip()
        if not query:
            await message.reply("⚠️ Usage: <code>/play song name or URL</code>", parse_mode="HTML"); return

        msg = await message.reply(
            f"╔══「 🔍 <b>SEARCHING</b> 」══╗\n\n  {GOLD} Finding <i>{query[:50]}</i>...\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

        tracks = []

        if "spotify.com" in query:
            result, err = await resolve_spotify(query)
            if err: await msg.edit_text(f"❌ Spotify error: {err}"); return
            if isinstance(result, list):
                for q_ in result:
                    found = await yt_search(q_, 2)
                    if found:
                        found[0].update({"requester": requester, "source": "Spotify → YouTube"})
                        tracks.append(found[0])
            else:
                found = await yt_search(result, 5)
                if found:
                    found[0].update({"requester": requester, "source": "Spotify → YouTube"})
                    tracks = [found[0]]
        elif "gaana.com" in query:
            clean = query.rstrip("/").split("/")[-1].replace("-", " ")
            found = await yt_search(clean + " song", 5)
            if found:
                found[0].update({"requester": requester, "source": "Gaana → YouTube"})
                tracks = [found[0]]
        else:
            found = await yt_search(query, 5)
            if found:
                found[0].update({"requester": requester, "source": "YouTube"})
                tracks = [found[0]]

        if not tracks:
            await msg.edit_text(
                f"╔══「 ❌ <b>NOT FOUND</b> 」══╗\n\n  Couldn't find: <i>{query[:50]}</i>\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            ); return

        main = tracks[0]
        if is_blacklisted(chat_id, main["title"]):
            await msg.edit_text("🚫 That song is blacklisted in this group."); return

        update_last_play(user_id)

        # Multiple tracks (Spotify playlist/album)
        if len(tracks) > 1:
            status = await add_to_queue(chat_id, tracks[0], user_id)
            for tr in tracks[1:]:
                queues.setdefault(chat_id, []).append(tr)
            await msg.edit_text(
                f"╔══「 📋 <b>PLAYLIST ADDED</b> 」══╗\n\n  {GOLD} <b>{len(tracks)}</b> songs added\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            ); return

        status = await add_to_queue(chat_id, main, user_id)

        if status == "duplicate":
            await msg.edit_text("⚠️ That song is already in the queue!"); return
        if status == "full":
            mx = get_settings(chat_id).get("max_queue", 20)
            await msg.edit_text(f"❌ Queue is full! ({mx} songs max)"); return
        if status == "error":
            await msg.edit_text("❌ Failed to play. Try again."); return

        if status == "playing":
            # AI DJ intro (premium only)
            if prem:
                intro = await ai_dj_intro(main["title"], message.from_user.first_name)
                if intro:
                    await bot.send_message(chat_id, f"🎙 <i>{intro}</i>", parse_mode="HTML")
            await send_now_playing(bot, chat_id, main, message.from_user.first_name, msg)
        else:
            pos = len(queues.get(chat_id, []))
            await msg.edit_text(
                f"╔══「 📋 <b>ADDED TO QUEUE</b> 」══╗\n\n"
                f"  {GOLD} <b>{main['title']}</b>\n\n"
                f"  ⏱ {duration_str(main.get('duration', 0))}\n"
                f"  📍 Position #{pos}\n"
                f"  🎤 {requester}\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )

    # ── /search ───────────────────────────────
    @dp.message(Command("search"))
    async def search_cmd(message: Message):
        if message.chat.type not in ("group","supergroup"):
            await message.reply("⚠️ Groups only!"); return
        chat_id = message.chat.id
        parts   = message.text.split(maxsplit=1)
        query   = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            await message.reply("⚠️ Usage: /search song name"); return

        msg     = await message.reply(f"🔍 Searching <b>{query}</b>...", parse_mode="HTML")
        results = await yt_search(query, 5)
        if not results:
            await msg.edit_text("❌ Nothing found."); return

        req = mention(message.from_user.id, message.from_user.first_name)
        for r in results:
            r["requester"] = req
        search_cache[chat_id] = results

        text = f"╔══「 🔍 <b>SEARCH RESULTS</b> 」══╗\n\n"
        for i, r in enumerate(results, 1):
            text += f"  {GOLD} {i}. <b>{r['title']}</b>\n     ⏱ {duration_str(r.get('duration',0))}\n\n"
        text += f"╚{'═'*32}╝\n<i>Tap to play 👇</i>"
        await msg.edit_text(text, reply_markup=search_kb(chat_id, results), parse_mode="HTML")

    # ── /skip ─────────────────────────────────
    @dp.message(Command("skip"))
    async def skip_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        if chat_id not in now_playing:
            await message.reply("❌ Nothing is playing!"); return

        if await has_permission(bot, chat_id, user_id, owner_id):
            now_playing.pop(chat_id, None)
            vote_skips.pop(chat_id, None)
            await message.reply(
                f"╔══「 ⏭ <b>SKIPPED</b> 」══╗\n\n  {GOLD} Track skipped.\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )
            await play_next(chat_id)
        else:
            if chat_id not in vote_skips: vote_skips[chat_id] = set()
            if user_id in vote_skips[chat_id]:
                await message.reply("⚠️ Already voted!"); return
            vote_skips[chat_id].add(user_id)
            votes = len(vote_skips[chat_id])
            if votes >= VOTE_SKIP_COUNT:
                vote_skips.pop(chat_id, None)
                np = now_playing.pop(chat_id, None)
                await message.reply(
                    f"╔══「 ⏭ <b>VOTED! SKIPPING</b> 」══╗\n\n  {GOLD} {votes}/{VOTE_SKIP_COUNT} votes!\n\n╚{'═'*32}╝",
                    parse_mode="HTML"
                )
                await play_next(chat_id)
            else:
                await message.reply(
                    f"╔══「 🗳 <b>VOTE SKIP</b> 」══╗\n\n  {GOLD} {votes}/{VOTE_SKIP_COUNT} needed.\n\n╚{'═'*32}╝",
                    parse_mode="HTML", reply_markup=voteskip_kb(chat_id, votes)
                )

    # ── /pause /resume /stop ──────────────────
    @dp.message(Command("pause"))
    async def pause_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        from player import calls
        try:
            await calls.pause_stream(chat_id)
            await message.reply(f"╔══「 ⏸ <b>PAUSED</b> 」══╗\n\n  /resume to continue\n\n╚{'═'*32}╝", parse_mode="HTML")
        except Exception as e:
            await message.reply(f"❌ {e}")

    @dp.message(Command("resume"))
    async def resume_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        from player import calls
        try:
            await calls.resume_stream(chat_id)
            await message.reply(f"╔══「 ▶️ <b>RESUMED</b> 」══╗\n\n  {GOLD} Music is back!\n\n╚{'═'*32}╝", parse_mode="HTML")
        except Exception as e:
            await message.reply(f"❌ {e}")

    @dp.message(Command("stop"))
    async def stop_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        from player import calls
        queues.pop(chat_id, None); now_playing.pop(chat_id, None); vote_skips.pop(chat_id, None)
        try: await calls.leave_group_call(chat_id)
        except Exception: pass
        await message.reply(
            f"╔══「 ⏹ <b>STOPPED</b> 」══╗\n\n  {GOLD} Queue cleared. Left VC.\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /volume ───────────────────────────────
    @dp.message(Command("volume"))
    async def volume_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            s = get_settings(chat_id)
            await message.reply(f"🔊 Volume: <b>{s.get('volume',100)}%</b>\nUsage: /volume [1-200]", parse_mode="HTML"); return
        vol = max(1, min(200, int(parts[1])))
        update_setting(chat_id, "volume", vol)
        await message.reply(f"╔══「 🔊 <b>VOLUME</b> 」══╗\n\n  {GOLD} Set to <b>{vol}%</b>\n\n╚{'═'*32}╝", parse_mode="HTML")

    # ── /seek ─────────────────────────────────
    @dp.message(Command("seek"))
    async def seek_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        if chat_id not in now_playing:
            await message.reply("❌ Nothing playing!"); return
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("⚠️ Usage: /seek 1:30 or /seek 90"); return
        ts = parts[1]
        try:
            secs = sum(int(x) * (60 ** i) for i, x in enumerate(reversed(ts.split(":")))) if ":" in ts else int(ts)
        except Exception:
            await message.reply("⚠️ Invalid time. Use mm:ss or seconds."); return
        ok = await seek_track(chat_id, secs)
        if ok:
            await message.reply(f"╔══「 ⏩ <b>SEEKED</b> 」══╗\n\n  {GOLD} Jumped to <b>{duration_str(secs)}</b>\n\n╚{'═'*32}╝", parse_mode="HTML")
        else:
            await message.reply("❌ Seek failed.")

    # ── /back ─────────────────────────────────
    @dp.message(Command("back"))
    async def back_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        hist = play_history.get(chat_id, [])
        if not hist:
            await message.reply("❌ No previous track."); return
        prev = hist.pop()
        q = queues.setdefault(chat_id, [])
        if chat_id in now_playing: q.insert(0, now_playing[chat_id])
        now_playing[chat_id] = prev
        await message.reply(f"╔══「 ⏮ <b>PREVIOUS</b> 」══╗\n\n  {GOLD} {prev['title']}\n\n╚{'═'*32}╝", parse_mode="HTML")
        await stream_track(chat_id, prev)

    # ── /shuffle ──────────────────────────────
    @dp.message(Command("shuffle"))
    async def shuffle_cmd(message: Message):
        import random
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        q = queues.get(chat_id, [])
        if not q: await message.reply("❌ Queue is empty!"); return
        random.shuffle(q)
        await message.reply(f"╔══「 🔀 <b>SHUFFLED</b> 」══╗\n\n  {GOLD} {len(q)} songs shuffled!\n\n╚{'═'*32}╝", parse_mode="HTML")

    # ── /queue ────────────────────────────────
    @dp.message(Command("queue"))
    async def queue_cmd(message: Message):
        chat_id = message.chat.id
        q  = queues.get(chat_id, [])
        np = now_playing.get(chat_id)
        if not np and not q:
            await message.reply(f"╔══「 📋 <b>QUEUE</b> 」══╗\n\n  😶 Empty.\n\n╚{'═'*32}╝", parse_mode="HTML"); return
        text = f"╔══「 📋 <b>QUEUE</b> ({len(q)} songs) 」══╗\n\n"
        if np: text += f"  {NOTE} <b>Now:</b> {np['title']}\n  <code>{duration_str(np.get('duration',0))}</code>\n\n"
        for i, tr in enumerate(q[:12], 1):
            text += f"  {GOLD} {i}. {tr['title']} <code>[{duration_str(tr.get('duration',0))}]</code>\n"
        if len(q) > 12: text += f"\n  ...and {len(q)-12} more"
        text += f"\n╚{'═'*32}╝"
        await message.reply(text, parse_mode="HTML")

    # ── /now ──────────────────────────────────
    @dp.message(Command("now"))
    async def now_cmd(message: Message):
        chat_id = message.chat.id
        track   = now_playing.get(chat_id)
        if not track:
            await message.reply("❌ Nothing is playing right now."); return
        await send_now_playing(bot, chat_id, track, message.from_user.first_name)

    # ── /loop ─────────────────────────────────
    @dp.message(Command("loop"))
    async def loop_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        s = get_settings(chat_id)
        new_val = 0 if s["loop"] else 1
        update_setting(chat_id, "loop", new_val)
        icon = "🔁 ON" if new_val else "➡️ OFF"
        await message.reply(f"╔══「 🔁 <b>LOOP {icon}</b> 」══╗\n\n╚{'═'*32}╝", parse_mode="HTML")

    # ── /247 ──────────────────────────────────
    @dp.message(Command("247"))
    async def mode247_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        s = get_settings(chat_id)
        new_val = 0 if s["mode_247"] else 1
        update_setting(chat_id, "mode_247", new_val)
        state = "ON 🌙" if new_val else "OFF"
        await message.reply(f"╔══「 🌙 <b>24/7 {state}</b> 」══╗\n\n  {'Stays in VC always.' if new_val else 'Leaves when queue empty.'}\n\n╚{'═'*32}╝", parse_mode="HTML")

    # ── /top ──────────────────────────────────
    @dp.message(Command("top"))
    async def top_cmd(message: Message):
        chat_id = message.chat.id
        rows    = get_top_songs(chat_id, 10)
        if not rows:
            await message.reply("📊 No stats yet. Play some music!"); return
        medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
        text   = f"╔══「 📊 <b>TOP SONGS</b> 」══╗\n\n"
        for i, (title, count) in enumerate(rows):
            short = title[:33] + "..." if len(title) > 33 else title
            text += f"  {medals[i]} <b>{short}</b> — {count} plays\n"
        text += f"\n╚{'═'*32}╝"
        await message.reply(text, parse_mode="HTML")

    # ── /eq ───────────────────────────────────
    @dp.message(Command("eq"))
    async def eq_cmd(message: Message):
        chat_id = message.chat.id
        if not await has_permission(bot, chat_id, message.from_user.id, owner_id):
            await message.reply("🚫 No permission!"); return
        s = get_settings(chat_id)
        await message.reply(
            f"╔══「 🎛 <b>EQUALIZER</b> 」══╗\n\n"
            f"  🔉 Bass:   <b>{s['eq_bass']:+d} dB</b>\n"
            f"  🎼 Mid:    <b>{s['eq_mid']:+d} dB</b>\n"
            f"  🔊 Treble: <b>{s['eq_treble']:+d} dB</b>\n\n"
            f"  Range: −10 to +10\n\n╚{'═'*32}╝",
            reply_markup=eq_kb(chat_id), parse_mode="HTML"
        )

    # ── CALLBACKS ─────────────────────────────
    @dp.callback_query(F.data.startswith("pick:"))
    async def cb_pick(call: CallbackQuery):
        _, chat_id_s, idx_s = call.data.split(":")
        chat_id = int(chat_id_s); idx = int(idx_s)
        results = search_cache.get(chat_id, [])
        if idx >= len(results):
            await call.answer("Expired.", show_alert=True); return
        track  = results[idx]
        status = await add_to_queue(chat_id, track, call.from_user.id)
        await call.answer(f"✅ {track['title'][:30]}")
        if status == "playing":
            await send_now_playing(bot, chat_id, track, call.from_user.first_name, call.message)
        else:
            pos = len(queues.get(chat_id, []))
            await call.message.edit_text(
                f"╔══「 📋 <b>QUEUED</b> 」══╗\n\n  {GOLD} {track['title']}\n  📍 #{pos}\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )

    @dp.callback_query(F.data.startswith("cancel_search:"))
    async def cb_cancel(call: CallbackQuery):
        await call.message.delete(); await call.answer("Cancelled")

    @dp.callback_query(F.data.startswith("pause:"))
    async def cb_pause(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        from player import calls as vc
        try: await vc.pause_stream(chat_id); await call.answer("⏸ Paused")
        except Exception as e: await call.answer(str(e), show_alert=True)

    @dp.callback_query(F.data.startswith("resume:"))
    async def cb_resume(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        from player import calls as vc
        try: await vc.resume_stream(chat_id); await call.answer("▶️ Resumed")
        except Exception as e: await call.answer(str(e), show_alert=True)

    @dp.callback_query(F.data.startswith("skip:"))
    async def cb_skip(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        now_playing.pop(chat_id, None); vote_skips.pop(chat_id, None)
        await call.answer("⏭ Skipped"); await play_next(chat_id)

    @dp.callback_query(F.data.startswith("stop:"))
    async def cb_stop(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        from player import calls as vc
        queues.pop(chat_id, None); now_playing.pop(chat_id, None)
        try: await vc.leave_group_call(chat_id)
        except Exception: pass
        await call.answer("⏹ Stopped")
        try: await call.message.edit_caption(caption=f"╔══「 ⏹ <b>STOPPED</b> 」══╗\n\n  {GOLD} Left VC.\n\n╚{'═'*32}╝", parse_mode="HTML", reply_markup=None)
        except Exception: pass

    @dp.callback_query(F.data.startswith("back:"))
    async def cb_back(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        hist = play_history.get(chat_id, [])
        if not hist: await call.answer("No previous track!", show_alert=True); return
        prev = hist.pop()
        q = queues.setdefault(chat_id, [])
        if chat_id in now_playing: q.insert(0, now_playing[chat_id])
        now_playing[chat_id] = prev
        await call.answer(f"⏮ {prev['title'][:25]}")
        await stream_track(chat_id, prev)

    @dp.callback_query(F.data.startswith("shuffle:"))
    async def cb_shuffle(call: CallbackQuery):
        import random
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        q = queues.get(chat_id, [])
        if not q: await call.answer("Queue is empty!"); return
        random.shuffle(q); await call.answer(f"🔀 {len(q)} songs shuffled!")

    @dp.callback_query(F.data.startswith("vol:"))
    async def cb_vol(call: CallbackQuery):
        parts   = call.data.split(":")
        action  = parts[1]; chat_id = int(parts[2])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        s   = get_settings(chat_id)
        vol = max(1, min(200, s.get("volume", 100) + (10 if action == "up" else -10)))
        update_setting(chat_id, "volume", vol)
        await call.answer(f"🔊 Volume: {vol}%")

    @dp.callback_query(F.data.startswith("loop:"))
    async def cb_loop(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        s = get_settings(chat_id); nv = 0 if s["loop"] else 1
        update_setting(chat_id, "loop", nv); await call.answer(f"🔁 Loop {'ON' if nv else 'OFF'}")

    @dp.callback_query(F.data.startswith("247:"))
    async def cb_247(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        s = get_settings(chat_id); nv = 0 if s["mode_247"] else 1
        update_setting(chat_id, "mode_247", nv); await call.answer(f"🌙 24/7 {'ON' if nv else 'OFF'}")

    @dp.callback_query(F.data.startswith("queue_cb:"))
    async def cb_queue(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        q  = queues.get(chat_id, [])
        np = now_playing.get(chat_id)
        if not np and not q: await call.answer("Queue empty!", show_alert=True); return
        text = f"╔══「 📋 <b>QUEUE</b> 」══╗\n\n"
        if np: text += f"  {NOTE} <b>{np['title']}</b>\n\n"
        for i, tr in enumerate(q[:8], 1): text += f"  {GOLD} {i}. {tr['title']}\n"
        if len(q) > 8: text += f"\n  +{len(q)-8} more"
        text += f"\n\n╚{'═'*32}╝"
        await call.answer()
        try: await call.message.edit_caption(caption=text, reply_markup=player_kb(chat_id), parse_mode="HTML")
        except Exception: await call.message.edit_text(text, reply_markup=player_kb(chat_id), parse_mode="HTML")

    @dp.callback_query(F.data.startswith("eq_menu:"))
    async def cb_eq_menu(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        s = get_settings(chat_id); await call.answer()
        text = (f"╔══「 🎛 <b>EQUALIZER</b> 」══╗\n\n"
                f"  🔉 Bass:   <b>{s['eq_bass']:+d} dB</b>\n"
                f"  🎼 Mid:    <b>{s['eq_mid']:+d} dB</b>\n"
                f"  🔊 Treble: <b>{s['eq_treble']:+d} dB</b>\n\n╚{'═'*32}╝")
        try: await call.message.edit_caption(caption=text, reply_markup=eq_kb(chat_id), parse_mode="HTML")
        except Exception: await call.message.edit_text(text, reply_markup=eq_kb(chat_id), parse_mode="HTML")

    @dp.callback_query(F.data.startswith("eq:"))
    async def cb_eq(call: CallbackQuery):
        parts = call.data.split(":")
        band = parts[1]; change = int(parts[2]); chat_id = int(parts[3])
        if not await has_permission(bot, chat_id, call.from_user.id, owner_id):
            await call.answer("🚫 No permission!", show_alert=True); return
        if band == "reset":
            for k in ("eq_bass","eq_mid","eq_treble"): update_setting(chat_id, k, 0)
            await call.answer("🔄 EQ Reset")
        else:
            s = get_settings(chat_id); key = f"eq_{band}"
            nv = max(-10, min(10, s[key] + change))
            update_setting(chat_id, key, nv); await call.answer(f"{band.title()}: {nv:+d}dB")
        s = get_settings(chat_id)
        text = (f"╔══「 🎛 <b>EQUALIZER</b> 」══╗\n\n"
                f"  🔉 Bass:   <b>{s['eq_bass']:+d} dB</b>\n"
                f"  🎼 Mid:    <b>{s['eq_mid']:+d} dB</b>\n"
                f"  🔊 Treble: <b>{s['eq_treble']:+d} dB</b>\n\n╚{'═'*32}╝")
        try: await call.message.edit_caption(caption=text, reply_markup=eq_kb(chat_id), parse_mode="HTML")
        except Exception: await call.message.edit_text(text, reply_markup=eq_kb(chat_id), parse_mode="HTML")

    @dp.callback_query(F.data.startswith("eq_info:"))
    async def cb_eq_info(call: CallbackQuery):
        await call.answer("Use +/− to adjust. Range: −10 to +10 dB")

    @dp.callback_query(F.data.startswith("player_back:"))
    async def cb_player_back(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1])
        track   = now_playing.get(chat_id)
        if not track: await call.answer("Nothing playing"); return
        await call.answer()
        text = now_text(chat_id)
        try: await call.message.edit_caption(caption=text, reply_markup=player_kb(chat_id), parse_mode="HTML")
        except Exception: await call.message.edit_text(text, reply_markup=player_kb(chat_id), parse_mode="HTML")

    @dp.callback_query(F.data.startswith("voteskip:"))
    async def cb_voteskip(call: CallbackQuery):
        chat_id = int(call.data.split(":")[1]); user_id = call.from_user.id
        if chat_id not in now_playing: await call.answer("Nothing playing!", show_alert=True); return
        if chat_id not in vote_skips: vote_skips[chat_id] = set()
        if user_id in vote_skips[chat_id]: await call.answer("Already voted!", show_alert=True); return
        vote_skips[chat_id].add(user_id)
        votes = len(vote_skips[chat_id])
        await call.answer(f"✅ {votes}/{VOTE_SKIP_COUNT}")
        if votes >= VOTE_SKIP_COUNT:
            vote_skips.pop(chat_id, None); now_playing.pop(chat_id, None)
            await call.message.reply(f"╔══「 ⏭ <b>VOTED! SKIPPING</b> 」══╗\n\n  {GOLD} {votes}/{VOTE_SKIP_COUNT}!\n\n╚{'═'*32}╝", parse_mode="HTML")
            await play_next(chat_id)
        else:
            await call.message.edit_reply_markup(reply_markup=voteskip_kb(chat_id, votes))
