"""Admin command handlers — /adminpanel /blacklist /dj /lang /settings /broadcast /stats"""
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberAdministrator, ChatMemberOwner
)
from database import (
    get_settings, update_setting,
    add_blacklist, remove_blacklist, get_blacklist,
    add_dj, remove_dj, is_dj,
    get_lang, set_lang,
    get_all_groups, get_global_stats,
    remove_group, register_group,
    is_group_premium
)

GOLD = "👑"

async def is_admin(bot: Bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return isinstance(m, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False

def admin_panel_kb(chat_id):
    s = get_settings(chat_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🔒 Admin Only: {'ON' if s['admin_only'] else 'OFF'}", callback_data=f"ap:admin_only:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text=f"🗳 Vote Skip: {'ON' if s['vote_skip'] else 'OFF'}", callback_data=f"ap:vote_skip:{chat_id}"),
            InlineKeyboardButton(text=f"▶️ Auto Play: {'ON' if s['auto_play'] else 'OFF'}", callback_data=f"ap:auto_play:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text=f"🎭 DJ Role: {'ON' if s['dj_role'] else 'OFF'}", callback_data=f"ap:dj_role:{chat_id}"),
            InlineKeyboardButton(text=f"🎉 Party Mode: {'ON' if s['party_mode'] else 'OFF'}", callback_data=f"ap:party_mode:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text=f"🔁 Dup Check: {'ON' if s['duplicate_check'] else 'OFF'}", callback_data=f"ap:duplicate_check:{chat_id}"),
            InlineKeyboardButton(text=f"📋 Max Queue: {s['max_queue']}", callback_data=f"ap:max_queue:{chat_id}"),
        ],
        [InlineKeyboardButton(text="🚫 Blacklist", callback_data=f"ap:show_blacklist:{chat_id}")],
        [InlineKeyboardButton(text="❌ Close", callback_data=f"ap:close:{chat_id}")],
    ])

def admin_panel_text(chat_id):
    s    = get_settings(chat_id)
    prem = is_group_premium(chat_id)
    return (
        f"╔══「 ⚙️ <b>ADMIN PANEL</b> 」══╗\n\n"
        f"  💎 Premium: {'✅ Active' if prem else '❌ Free'}\n\n"
        f"  🔒 Admin Only Mode: {'ON' if s['admin_only'] else 'OFF'}\n"
        f"  🗳 Vote Skip: {'ON' if s['vote_skip'] else 'OFF'}\n"
        f"  ▶️ Auto Play: {'ON' if s['auto_play'] else 'OFF'}\n"
        f"  🎭 DJ Role System: {'ON' if s['dj_role'] else 'OFF'}\n"
        f"  🎉 Party Mode: {'ON' if s['party_mode'] else 'OFF'}\n"
        f"  🔁 Duplicate Check: {'ON' if s['duplicate_check'] else 'OFF'}\n"
        f"  📋 Max Queue Size: {s['max_queue']}\n\n"
        f"  Tap buttons to toggle settings 👇\n\n"
        f"╚{'═'*32}╝"
    )

def register(dp: Dispatcher, bot: Bot, owner_id: int):

    # ── /adminpanel ───────────────────────────────────────────
    @dp.message(Command("adminpanel"))
    async def adminpanel_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        if not (user_id == owner_id or await is_admin(bot, chat_id, user_id)):
            await message.reply("🚫 Admins only!"); return
        await message.reply(
            admin_panel_text(chat_id),
            reply_markup=admin_panel_kb(chat_id),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("ap:"))
    async def cb_admin_panel(call: CallbackQuery):
        parts   = call.data.split(":")
        action  = parts[1]
        chat_id = int(parts[2])

        if not (call.from_user.id == owner_id or await is_admin(bot, chat_id, call.from_user.id)):
            await call.answer("🚫 Admins only!", show_alert=True); return

        if action == "close":
            await call.message.delete(); return
        if action == "show_blacklist":
            bl = get_blacklist(chat_id)
            text = "🚫 <b>Blacklisted words:</b>\n\n" + ("\n".join(f"• {k}" for k in bl) if bl else "None")
            await call.answer()
            await call.message.edit_text(text, reply_markup=admin_panel_kb(chat_id), parse_mode="HTML")
            return
        if action == "max_queue":
            s   = get_settings(chat_id)
            mq  = s["max_queue"]
            new = 50 if mq == 20 else (100 if mq == 50 else (200 if mq == 100 else 20))
            update_setting(chat_id, "max_queue", new)
            await call.answer(f"Max queue: {new}")
        else:
            s   = get_settings(chat_id)
            nv  = 0 if s.get(action, 0) else 1
            update_setting(chat_id, action, nv)
            await call.answer(f"{action.replace('_',' ').title()}: {'ON' if nv else 'OFF'}")

        await call.message.edit_text(
            admin_panel_text(chat_id),
            reply_markup=admin_panel_kb(chat_id),
            parse_mode="HTML"
        )

    # ── /blacklist ────────────────────────────────────────────
    @dp.message(Command("blacklist"))
    async def blacklist_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        if not (user_id == owner_id or await is_admin(bot, chat_id, user_id)):
            await message.reply("🚫 Admins only!"); return

        parts = message.text.split(maxsplit=2)
        sub   = parts[1].lower() if len(parts) > 1 else ""
        word  = parts[2].strip() if len(parts) > 2 else ""

        if sub == "add" and word:
            add_blacklist(chat_id, word)
            await message.reply(f"🚫 <b>{word}</b> blacklisted.", parse_mode="HTML")
        elif sub == "remove" and word:
            remove_blacklist(chat_id, word)
            await message.reply(f"✅ <b>{word}</b> removed.", parse_mode="HTML")
        elif sub == "list":
            bl = get_blacklist(chat_id)
            text = f"╔══「 🚫 <b>BLACKLIST</b> 」══╗\n\n"
            text += "\n".join(f"  • {k}" for k in bl) if bl else "  No blacklisted words."
            text += f"\n\n╚{'═'*32}╝"
            await message.reply(text, parse_mode="HTML")
        else:
            await message.reply(
                "/blacklist add [word] — Block songs with this word\n"
                "/blacklist remove [word] — Unblock\n"
                "/blacklist list — Show blocked words"
            )

    # ── /dj ───────────────────────────────────────────────────
    @dp.message(Command("dj"))
    async def dj_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        if not (user_id == owner_id or await is_admin(bot, chat_id, user_id)):
            await message.reply("🚫 Admins only!"); return

        parts = message.text.split(maxsplit=2)
        sub   = parts[1].lower() if len(parts) > 1 else ""
        s     = get_settings(chat_id)

        if sub == "on":
            update_setting(chat_id, "dj_role", 1)
            await message.reply(f"🎭 DJ Role system <b>ENABLED</b>.\nUse /dj add (reply to user) to assign.", parse_mode="HTML")
        elif sub == "off":
            update_setting(chat_id, "dj_role", 0)
            await message.reply("🎭 DJ Role system <b>DISABLED</b>.", parse_mode="HTML")
        elif sub == "add":
            if not message.reply_to_message:
                await message.reply("⚠️ Reply to someone's message."); return
            target = message.reply_to_message.from_user
            add_dj(chat_id, target.id)
            await message.reply(f"🎭 <b>{target.first_name}</b> is now a DJ!", parse_mode="HTML")
        elif sub == "remove":
            if not message.reply_to_message:
                await message.reply("⚠️ Reply to someone's message."); return
            target = message.reply_to_message.from_user
            remove_dj(chat_id, target.id)
            await message.reply(f"🎭 DJ role removed from <b>{target.first_name}</b>.", parse_mode="HTML")
        else:
            state = "ON ✅" if s["dj_role"] else "OFF ❌"
            await message.reply(
                f"╔══「 🎭 <b>DJ ROLE</b> 」══╗\n\n"
                f"  Status: <b>{state}</b>\n\n"
                f"  /dj on — Enable\n"
                f"  /dj off — Disable\n"
                f"  /dj add — Reply to user\n"
                f"  /dj remove — Reply to user\n\n"
                f"  DJs can: play, skip, pause, shuffle, volume\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )

    # ── /lang ─────────────────────────────────────────────────
    @dp.message(Command("lang"))
    async def lang_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        if not (user_id == owner_id or await is_admin(bot, chat_id, user_id)):
            await message.reply("🚫 Admins only!"); return
        parts = message.text.split()
        if len(parts) < 2 or parts[1] not in ("en", "hi"):
            cur = get_lang(chat_id)
            await message.reply(f"🌐 Current language: <b>{'English 🇬🇧' if cur == 'en' else 'Hindi 🇮🇳'}</b>\n\nUsage: /lang en  or  /lang hi", parse_mode="HTML")
            return
        set_lang(chat_id, parts[1])
        names = {"en": "English 🇬🇧", "hi": "Hindi 🇮🇳"}
        await message.reply(f"🌐 Language set to <b>{names[parts[1]]}</b>", parse_mode="HTML")

    # ── /broadcast (owner only) ───────────────────────────────
    @dp.message(Command("broadcast"))
    async def broadcast_cmd(message: Message):
        if message.from_user.id != owner_id: return

        if message.reply_to_message:
            bc_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        else:
            parts   = message.text.split(maxsplit=1)
            bc_text = parts[1] if len(parts) > 1 else ""

        if not bc_text:
            await message.reply("⚠️ Reply to a message or: /broadcast your text"); return

        groups  = get_all_groups()
        success = failed = 0
        status  = await message.reply(f"📡 Broadcasting to <b>{len(groups)}</b> groups...", parse_mode="HTML")

        for chat_id in groups:
            try:
                await bot.send_message(
                    chat_id,
                    f"╔══「 {GOLD} <b>BROADCAST</b> {GOLD} 」══╗\n\n{bc_text}\n\n╚{'═'*32}╝",
                    parse_mode="HTML"
                )
                success += 1
            except Exception as e:
                failed += 1
                err = str(e).lower()
                if any(x in err for x in ["kicked", "not found", "deactivated", "blocked"]):
                    remove_group(chat_id)
            await asyncio.sleep(0.3)

        await status.edit_text(
            f"✅ <b>Broadcast done!</b>\n\n📨 Sent: {success}  ❌ Failed: {failed}",
            parse_mode="HTML"
        )

    # ── /stats (owner only) ───────────────────────────────────
    @dp.message(Command("stats"))
    async def stats_cmd(message: Message):
        if message.from_user.id != owner_id:
            await message.reply("🚫 Owner only!"); return
        s    = get_global_stats()
        top  = s.get("top")
        top_text = f"{top[0][:30]} ({top[1]} plays)" if top else "N/A"
        await message.reply(
            f"╔══「 📈 <b>BOT STATISTICS</b> 」══╗\n\n"
            f"  {GOLD} Groups: <b>{s['groups']}</b>\n"
            f"  🎵 Total plays: <b>{s['plays']}</b>\n"
            f"  👤 Premium users: <b>{s['prem_users']}</b>\n"
            f"  👥 Premium groups: <b>{s['prem_groups']}</b>\n"
            f"  🏆 Most played: <i>{top_text}</i>\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /playlist ─────────────────────────────────────────────
    @dp.message(Command("playlist"))
    async def playlist_cmd(message: Message):
        import json
        from database import (
            save_playlist, load_playlist,
            list_playlists, delete_playlist, count_playlists,
            is_premium
        )
        from config import MAX_PLAYLIST_FREE, MAX_PLAYLIST_PREM
        from player import queues, now_playing, add_to_queue

        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)
        max_pl  = MAX_PLAYLIST_PREM if prem else MAX_PLAYLIST_FREE

        parts   = message.text.split(maxsplit=2)
        sub     = parts[1].lower() if len(parts) > 1 else ""
        name    = parts[2].strip() if len(parts) > 2 else ""

        if sub == "save":
            if not name:
                await message.reply("⚠️ /playlist save [name]"); return
            q    = list(queues.get(chat_id, []))
            np   = now_playing.get(chat_id)
            songs = ([np] if np else []) + q
            if not songs:
                await message.reply("❌ Queue is empty!"); return
            if count_playlists(user_id) >= max_pl and load_playlist(user_id, name) is None:
                await message.reply(f"❌ Max {max_pl} playlists. Delete one first."); return
            save_playlist(user_id, name, songs)
            await message.reply(
                f"╔══「 💾 <b>SAVED</b> 」══╗\n\n  {GOLD} <b>{name}</b> — {len(songs)} songs\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )
        elif sub == "load":
            if not name:
                await message.reply("⚠️ /playlist load [name]"); return
            songs = load_playlist(user_id, name)
            if not songs:
                await message.reply(f"❌ Playlist '{name}' not found."); return
            req = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
            for s_ in songs: s_["requester"] = req
            await add_to_queue(chat_id, songs[0], user_id)
            for s_ in songs[1:]: queues.setdefault(chat_id, []).append(s_)
            await message.reply(
                f"╔══「 ▶️ <b>PLAYLIST LOADED</b> 」══╗\n\n  {GOLD} <b>{name}</b> — {len(songs)} songs\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )
        elif sub == "list":
            pls = list_playlists(user_id)
            if not pls:
                await message.reply("😶 No saved playlists."); return
            text = f"╔══「 💾 <b>YOUR PLAYLISTS</b> 」══╗\n\n"
            for p in pls:
                s_ = load_playlist(user_id, p) or []
                text += f"  {GOLD} <b>{p}</b> — {len(s_)} songs\n"
            text += f"\n  {max_pl - len(pls)} slots remaining\n\n╚{'═'*32}╝"
            await message.reply(text, parse_mode="HTML")
        elif sub == "delete":
            if not name:
                await message.reply("⚠️ /playlist delete [name]"); return
            if load_playlist(user_id, name) is None:
                await message.reply(f"❌ Not found."); return
            delete_playlist(user_id, name)
            await message.reply(f"🗑 <b>{name}</b> deleted.", parse_mode="HTML")
        else:
            await message.reply(
                f"╔══「 💾 <b>PLAYLISTS</b> 」══╗\n\n"
                f"  /playlist save [name]\n"
                f"  /playlist load [name]\n"
                f"  /playlist list\n"
                f"  /playlist delete [name]\n\n"
                f"  Max: <b>{max_pl}</b> playlists {'(💎 Premium)' if prem else '(/buy for more)'}\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            )

    # ── /history ──────────────────────────────────────────────
    @dp.message(Command("history"))
    async def history_cmd(message: Message):
        from database import get_user_history, is_premium
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not is_premium(user_id, chat_id):
            await message.reply("💎 Premium feature! Use /buy to unlock listening history."); return
        rows = get_user_history(user_id, 15)
        if not rows:
            await message.reply("😶 No listening history yet."); return
        import time
        text = f"╔══「 📜 <b>YOUR HISTORY</b> 」══╗\n\n"
        for title, duration, played_at in rows:
            dt   = time.strftime("%d %b %H:%M", time.localtime(played_at))
            text += f"  {GOLD} {title[:35]}\n     <code>{dt}</code>\n\n"
        text += f"╚{'═'*32}╝"
        await message.reply(text, parse_mode="HTML")

    # ── /privacy ──────────────────────────────────────────────
    @dp.message(Command("privacy"))
    async def privacy_cmd(message: Message):
        from database import is_premium, toggle_private, is_private_mode
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not is_premium(user_id, chat_id):
            await message.reply("💎 Private mode is a premium feature. Use /buy!"); return
        toggle_private(user_id)
        priv = is_private_mode(user_id)
        await message.reply(
            f"╔══「 🔒 <b>PRIVATE MODE</b> 」══╗\n\n"
            f"  {GOLD} Private mode: <b>{'ON 🔒' if priv else 'OFF 🔓'}</b>\n\n"
            f"  {'Your activity is now hidden.' if priv else 'Your activity is now visible.'}\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )
