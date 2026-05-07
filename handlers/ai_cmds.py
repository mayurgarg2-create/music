"""AI command handlers — /dj /mood /vibe /recommend /explain /aiplaylist /ask"""
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from database import (
    is_premium, is_group_premium, get_ai_history,
    add_ai_message, clear_ai_history, get_user_history
)
from ai import (
    ai_chat, ai_detect_mood, ai_recommend,
    ai_explain_lyrics, ai_name_playlist,
    ai_generate_playlist, ai_voice_command, DJ_SYSTEM_PROMPT
)
from player import now_playing, queues, yt_search, add_to_queue

GOLD = "👑"

# Store recent chat messages per group for mood detection
chat_buffer: dict[int, list[str]] = {}

def register(dp: Dispatcher, bot: Bot, owner_id: int):

    # ── Track messages for mood detection ─────────────────────
    @dp.message(F.text & ~F.text.startswith("/"))
    async def track_messages(message: Message):
        if message.chat.type not in ("group", "supergroup"): return
        chat_id = message.chat.id
        buf = chat_buffer.setdefault(chat_id, [])
        buf.append(f"{message.from_user.first_name}: {message.text}")
        if len(buf) > 50: buf.pop(0)

    # ── /dj — Talk to the AI DJ ───────────────────────────────
    @dp.message(Command("dj"))
    async def dj_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)

        parts = message.text.split(maxsplit=1)
        text  = parts[1].strip() if len(parts) > 1 else ""
        if not text:
            await message.reply(
                f"╔══「 🎙 <b>AI DJ</b> 」══╗\n\n"
                f"  Talk to your AI DJ!\n\n"
                f"  Usage: /dj [your message]\n\n"
                f"  Examples:\n"
                f"  /dj play something chill\n"
                f"  /dj what song should I play for a party?\n"
                f"  /dj tell me about hip-hop\n\n"
                + ("  💎 Premium: Full AI memory & personality\n" if not prem else "  💎 You have full AI access!\n") +
                f"\n╚{'═'*32}╝",
                parse_mode="HTML"
            ); return

        msg = await message.reply("🎙 <i>DJ is thinking...</i>", parse_mode="HTML")

        # Build conversation history (premium gets memory)
        if prem:
            history = get_ai_history(chat_id)
            add_ai_message(chat_id, "user", f"{message.from_user.first_name} says: {text}")
        else:
            history = []

        messages_list = history + [{"role": "user", "content": f"{message.from_user.first_name} says: {text}"}]
        response      = await ai_chat(messages_list, system=DJ_SYSTEM_PROMPT)

        if prem:
            add_ai_message(chat_id, "assistant", response)

        await msg.edit_text(
            f"🎙 <b>Royal DJ:</b>\n\n{response}",
            parse_mode="HTML"
        )

    # ── /ask — Natural language music command ─────────────────
    @dp.message(Command("ask"))
    async def ask_cmd(message: Message):
        parts = message.text.split(maxsplit=1)
        text  = parts[1].strip() if len(parts) > 1 else ""
        if not text:
            await message.reply("Usage: /ask play something chill"); return

        msg = await message.reply("🤖 <i>Processing...</i>", parse_mode="HTML")
        command = await ai_voice_command(text)
        command = command.strip()

        await msg.edit_text(
            f"╔══「 🤖 <b>AI COMMAND</b> 」══╗\n\n"
            f"  You said: <i>{text}</i>\n"
            f"  Parsed: <code>{command}</code>\n\n"
            f"  <i>Executing...</i>\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

        # Auto-execute the command by faking a message
        if command.startswith("/play "):
            song = command[6:].strip()
            results = await yt_search(song, 3)
            if results:
                from database import mention
                track = results[0]
                track["requester"] = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
                track["source"]    = "YouTube"
                status = await add_to_queue(message.chat.id, track, message.from_user.id)
                await msg.edit_text(
                    f"╔══「 🎵 <b>AI PLAYING</b> 」══╗\n\n  {GOLD} {track['title']}\n\n╚{'═'*32}╝",
                    parse_mode="HTML"
                )
            else:
                await msg.edit_text("❌ Couldn't find a song for that request.")
        elif command == "/skip":
            await bot.send_message(message.chat.id, "⏭ AI requested skip — use /skip")
        elif command == "/pause":
            await bot.send_message(message.chat.id, "⏸ AI requested pause — use /pause")
        elif command == "/shuffle":
            await bot.send_message(message.chat.id, "🔀 AI requested shuffle — use /shuffle")

    # ── /mood — Detect group mood & suggest music ─────────────
    @dp.message(Command("mood"))
    async def mood_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)

        msgs = chat_buffer.get(chat_id, [])
        if len(msgs) < 3:
            await message.reply("💬 Need more chat activity for mood detection. Keep chatting!"); return

        msg = await message.reply("🔍 <i>Analyzing group mood...</i>", parse_mode="HTML")
        mood_data = await ai_detect_mood(msgs)

        mood       = mood_data.get("mood", "chill")
        confidence = int(mood_data.get("confidence", 0.5) * 100)
        genre      = mood_data.get("genre_suggestion", "Pop")
        pl_name    = mood_data.get("playlist_name", "Royal Vibes")

        mood_icons = {
            "happy": "😊", "sad": "😢", "energetic": "⚡", "chill": "😌",
            "romantic": "💕", "party": "🎉", "angry": "🔥", "focused": "🎯"
        }
        icon = mood_icons.get(mood, "🎵")

        result_text = (
            f"╔══「 🎭 <b>MOOD DETECTED</b> 」══╗\n\n"
            f"  {icon} Mood: <b>{mood.upper()}</b> ({confidence}% confidence)\n"
            f"  🎵 Genre: <b>{genre}</b>\n"
            f"  📋 Playlist name: <i>{pl_name}</i>\n\n"
            f"  Use /vibe to auto-play a {mood} playlist!\n\n"
            f"╚{'═'*32}╝"
        )
        await msg.edit_text(result_text, parse_mode="HTML")

    # ── /vibe — Play AI-generated mood playlist ───────────────
    @dp.message(Command("vibe"))
    async def vibe_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)

        if not prem:
            await message.reply(
                f"╔══「 🎵 <b>PLAY MY VIBE</b> 」══╗\n\n"
                f"  💎 This is a <b>Premium Feature</b>!\n\n"
                f"  AI generates a custom playlist based on\n"
                f"  your group's mood and vibe.\n\n"
                f"  Use /buy to unlock!\n\n╚{'═'*32}╝",
                parse_mode="HTML"
            ); return

        parts    = message.text.split(maxsplit=1)
        vibe_req = parts[1].strip() if len(parts) > 1 else ""

        if not vibe_req:
            # Auto-detect from chat
            msgs = chat_buffer.get(chat_id, [])
            if msgs:
                mood_data = await ai_detect_mood(msgs)
                vibe_req  = f"{mood_data.get('mood','chill')} {mood_data.get('genre_suggestion','pop')} music"
            else:
                vibe_req = "chill popular music"

        msg = await message.reply(
            f"╔══「 🎵 <b>GENERATING VIBE</b> 」══╗\n\n"
            f"  🤖 <i>Creating playlist for: {vibe_req}</i>\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

        songs = await ai_generate_playlist(vibe_req)
        if not songs:
            await msg.edit_text("❌ AI couldn't generate a playlist. Try again!"); return

        requester = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
        added     = 0
        for song_line in songs:
            # Strip numbering like "1. Song - Artist"
            clean = song_line.split(".", 1)[-1].strip() if "." in song_line[:3] else song_line
            results = await yt_search(clean, 2)
            if results:
                track = results[0]
                track.update({"requester": requester, "source": "AI Vibe"})
                await add_to_queue(chat_id, track, user_id)
                queues.setdefault(chat_id, []).append(track)
                added += 1
            await asyncio.sleep(0.5)

        pl_name = await ai_name_playlist([s.split(".",1)[-1].strip() for s in songs[:5]])
        await msg.edit_text(
            f"╔══「 🎵 <b>VIBE PLAYLIST READY</b> 」══╗\n\n"
            f"  {GOLD} <b>{pl_name}</b>\n\n"
            f"  ✅ {added} songs added to queue\n"
            f"  🎭 Vibe: <i>{vibe_req}</i>\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /recommend — AI song recommendations ──────────────────
    @dp.message(Command("recommend"))
    async def recommend_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)

        if not prem:
            await message.reply(
                f"💎 <b>Premium Feature!</b>\n\n/recommend gives AI-powered song suggestions.\nUse /buy to unlock!",
                parse_mode="HTML"
            ); return

        parts  = message.text.split(maxsplit=1)
        query  = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            np = now_playing.get(chat_id)
            if np:
                query = np["title"]
            else:
                await message.reply("Usage: /recommend [song or artist name]"); return

        msg  = await message.reply(f"🤖 <i>Finding songs like {query}...</i>", parse_mode="HTML")
        recs = await ai_recommend(query)

        if not recs:
            await msg.edit_text("❌ No recommendations found. Try a different song."); return

        text = f"╔══「 🎵 <b>AI RECOMMENDATIONS</b> 」══╗\n\n"
        text += f"  <i>Because you like: {query[:30]}</i>\n\n"
        for i, r in enumerate(recs[:5], 1):
            text += f"  {GOLD} {i}. <b>{r.get('title','?')}</b> — {r.get('artist','?')}\n"
            text += f"       <i>{r.get('reason','')[:50]}</i>\n\n"
        text += f"╚{'═'*32}╝\n<i>Use /play [song name] to play any!</i>"
        await msg.edit_text(text, parse_mode="HTML")

    # ── /explain — AI song meaning ─────────────────────────────
    @dp.message(Command("explain"))
    async def explain_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)

        if not prem:
            await message.reply("💎 Premium only! Use /buy to unlock AI song explanations."); return

        parts = message.text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            np = now_playing.get(chat_id)
            query = np["title"] if np else ""
        if not query:
            await message.reply("Usage: /explain [song name]"); return

        msg  = await message.reply(f"🤖 <i>Analyzing: {query}...</i>", parse_mode="HTML")
        text = await ai_explain_lyrics(query)
        await msg.edit_text(
            f"╔══「 🎤 <b>SONG MEANING</b> 」══╗\n\n"
            f"  {GOLD} <b>{query}</b>\n\n"
            f"{text}\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /aiplaylist — generate playlist for event/mood ────────
    @dp.message(Command("aiplaylist"))
    async def aiplaylist_cmd(message: Message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        prem    = is_premium(user_id, chat_id)

        if not prem:
            await message.reply("💎 Premium feature! /buy to unlock AI playlist generation."); return

        parts  = message.text.split(maxsplit=1)
        prompt = parts[1].strip() if len(parts) > 1 else ""
        if not prompt:
            await message.reply(
                "Usage: /aiplaylist [mood or event]\n\n"
                "Examples:\n"
                "• /aiplaylist birthday party\n"
                "• /aiplaylist sad breakup\n"
                "• /aiplaylist gym workout\n"
                "• /aiplaylist late night drive"
            ); return

        msg   = await message.reply(f"🤖 <i>Creating playlist for: {prompt}...</i>", parse_mode="HTML")
        songs = await ai_generate_playlist(prompt)
        if not songs:
            await msg.edit_text("❌ Couldn't generate playlist. Try again."); return

        pl_name = await ai_name_playlist(songs)
        text    = f"╔══「 🎵 <b>AI PLAYLIST</b> 」══╗\n\n"
        text   += f"  {GOLD} <b>{pl_name}</b>\n"
        text   += f"  <i>For: {prompt}</i>\n\n"
        for i, song in enumerate(songs, 1):
            clean = song.split(".", 1)[-1].strip() if "." in song[:3] else song
            text += f"  {i}. {clean}\n"
        text += f"\n  Use /play [song name] to play any!\n\n╚{'═'*32}╝"
        await msg.edit_text(text, parse_mode="HTML")

    # ── /djreset — clear AI DJ memory ─────────────────────────
    @dp.message(Command("djreset"))
    async def djreset_cmd(message: Message):
        chat_id = message.chat.id
        clear_ai_history(chat_id)
        await message.reply(
            f"╔══「 🔄 <b>DJ MEMORY CLEARED</b> 」══╗\n\n"
            f"  {GOLD} AI DJ is starting fresh!\n\n╚{'═'*32}╝",
            parse_mode="HTML"
        )
