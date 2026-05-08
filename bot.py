"""
╔══════════════════════════════════════════╗
║    👑 ROYAL MUSIC BOT — MAIN ENTRY      ║
║    Full Premium Telegram Music Bot       ║
╚══════════════════════════════════════════╝
"""

# ── Cookie setup (must run before yt-dlp is used anywhere) ───────────
import os, base64

_cookie_b64 = os.environ.get("COOKIES_B64", "")
if _cookie_b64:
    try:
        with open("cookies.txt", "w") as _f:
            _f.write(base64.b64decode(_cookie_b64).decode("utf-8"))
        print("✅ cookies.txt written from COOKIES_B64")
    except Exception as _e:
        print(f"⚠️  Failed to write cookies.txt: {_e}")
else:
    print("⚠️  COOKIES_B64 not set — YouTube may block requests")
# ─────────────────────────────────────────────────────────────────────

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN, OWNER_ID
from database import register_group
from player import pyro, calls, now_playing, play_next

# Import all handler modules
from handlers import music, premium, admin, ai_cmds, download, games, lyrics
from handlers import player_callbacks   # ← inline button handler

GOLD = "👑"

# ── Init bot & dispatcher ─────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# ── Register all handlers ─────────────────────
music.register(dp, bot, OWNER_ID)
premium.register(dp, bot, OWNER_ID)
admin.register(dp, bot, OWNER_ID)
ai_cmds.register(dp, bot, OWNER_ID)
download.register(dp, bot, OWNER_ID)
games.register(dp, bot, OWNER_ID)
lyrics.register(dp, bot, OWNER_ID)
player_callbacks.register(dp, bot, OWNER_ID)   # ← register inline buttons


# ── /start ────────────────────────────────────
@dp.message(Command("start"))
async def start_cmd(message: Message):
    if message.chat.type in ("group", "supergroup"):
        register_group(message.chat.id, message.chat.title or "")
    await message.reply(
        f"╔══「 {GOLD} <b>ROYAL MUSIC BOT</b> {GOLD} 」══╗\n\n"
        f"  ♛ Premium • 320kbps • Multi-Source\n"
        f"  🤖 AI DJ • 💎 Sponsor System\n\n"
        f"  <b>🎵 Music:</b>\n"
        f"  /play — YouTube / Spotify / Gaana\n"
        f"  /search — Pick from 5 results\n"
        f"  /now — Now playing card\n"
        f"  /queue — View queue\n"
        f"  /skip /pause /resume /stop\n"
        f"  /back /shuffle /seek /volume\n"
        f"  /loop /247\n\n"
        f"  <b>🤖 AI Features:</b>\n"
        f"  /dj — Talk to AI DJ\n"
        f"  /mood — Detect group mood\n"
        f"  /vibe — AI mood playlist 💎\n"
        f"  /recommend — AI suggestions 💎\n"
        f"  /explain — Song meaning 💎\n"
        f"  /aiplaylist — Custom AI playlist 💎\n"
        f"  /ask — Natural language commands\n\n"
        f"  <b>⚙️ Tools:</b>\n"
        f"  /lyrics [song] — Get lyrics\n"
        f"  /download [song] — MP3 download\n"
        f"  /playlist — Saved playlists\n"
        f"  /top — Top songs chart\n"
        f"  /history — Listening history 💎\n"
        f"  /guesssong — Guess the song game\n\n"
        f"  <b>💎 Premium:</b>\n"
        f"  /buy — Get premium with ⭐ Stars\n"
        f"  /mystatus — Check your status\n\n"
        f"  /help — Full command list\n\n"
        f"╚{'═' * 32}╝",
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.reply(
        f"╔══「 {GOLD} <b>HELP MENU</b> {GOLD} 」══╗\n\n"
        f"<b>🎵 Playback:</b>\n"
        f"/play [name/URL] — YouTube, Spotify, Gaana\n"
        f"/search [name] — Show 5 results to pick\n"
        f"/pause /resume /stop\n"
        f"/volume [1-200]\n"
        f"/seek [mm:ss] — Jump to time\n"
        f"/back — Previous song\n"
        f"/shuffle — Shuffle queue\n"
        f"/loop — Toggle repeat\n"
        f"/247 — Stay in VC always\n\n"
        f"<b>📋 Queue:</b>\n"
        f"/queue /now /top\n\n"
        f"<b>🤖 AI (💎 = Premium):</b>\n"
        f"/dj [message] — Talk to AI DJ\n"
        f"/ask [command] — Natural language\n"
        f"/mood — Detect group mood\n"
        f"/vibe 💎 — AI mood playlist\n"
        f"/recommend 💎 — Song suggestions\n"
        f"/explain 💎 — Song meaning\n"
        f"/aiplaylist 💎 — Event playlist\n"
        f"/djreset — Clear DJ memory\n\n"
        f"<b>🎵 Extras:</b>\n"
        f"/lyrics [song] — Get lyrics\n"
        f"/download [song] — MP3 download\n"
        f"/history 💎 — Listening history\n"
        f"/privacy 💎 — Hide your activity\n"
        f"/guesssong — Music game\n"
        f"/giveup — Give up game\n\n"
        f"<b>💾 Playlists:</b>\n"
        f"/playlist save/load/list/delete [name]\n\n"
        f"<b>⚙️ Admin:</b>\n"
        f"/adminpanel — Settings dashboard\n"
        f"/blacklist add/remove/list [word]\n"
        f"/dj on/off/add/remove\n"
        f"/lang [en/hi]\n\n"
        f"<b>💎 Premium:</b>\n"
        f"/buy — Purchase with Telegram Stars\n"
        f"/mystatus — Your premium status\n\n"
        f"<b>👑 Owner Only:</b>\n"
        f"/premium [days] — Grant group premium\n"
        f"/unpremium — Remove group premium\n"
        f"/premiumuser [days] — Grant user premium\n"
        f"/unpremiumuser — Remove user premium\n"
        f"/broadcast — Message all groups\n"
        f"/stats — Bot statistics\n"
        f"/revenue — Payment stats\n\n"
        f"╚{'═' * 32}╝",
        parse_mode="HTML"
    )


# ── Auto-register group when bot is added ─────
@dp.my_chat_member()
async def on_chat_member(update):
    chat = update.chat
    if chat.type in ("group", "supergroup") and \
       update.new_chat_member.status in ("member", "administrator"):
        register_group(chat.id, chat.title or "")


# ── Stream end → play next ────────────────────
def _find_stream_end_class():
    """Return the stream-ended update class for whatever pytgcalls version is installed."""
    import pytgcalls.types as pt
    for name in ("GroupCallEnded", "StreamEnded", "StreamAudioEnded", "AudioEnded"):
        cls = getattr(pt, name, None)
        if cls is not None:
            return cls
    try:
        import pytgcalls.types.stream as pts
        for name in ("GroupCallEnded", "StreamEnded", "StreamAudioEnded", "AudioEnded"):
            cls = getattr(pts, name, None)
            if cls is not None:
                return cls
    except ImportError:
        pass
    return None


_StreamEndClass = _find_stream_end_class()

if _StreamEndClass is not None:
    @calls.on_update()
    async def on_stream_end(client, update):
        if not isinstance(update, _StreamEndClass):
            return
        chat_id = update.chat_id
        from player import play_history
        if chat_id in now_playing:
            play_history.setdefault(chat_id, []).append(now_playing[chat_id])
            now_playing.pop(chat_id, None)
        await play_next(chat_id, bot=bot)   # bot passed → auto sends now-playing card
else:
    print("⚠️  pytgcalls stream-end event not found — using polling fallback")

    async def _stream_end_poller():
        from player import queues
        while True:
            await asyncio.sleep(5)
            for chat_id in list(now_playing.keys()):
                try:
                    status = await calls.get_call(chat_id)
                    if status is None:
                        from player import play_history
                        if chat_id in now_playing:
                            play_history.setdefault(chat_id, []).append(now_playing[chat_id])
                            now_playing.pop(chat_id, None)
                        await play_next(chat_id, bot=bot)
                except Exception:
                    pass


# ── Main ──────────────────────────────────────
async def main():
    print("╔══════════════════════════════════════════╗")
    print("║     👑 ROYAL MUSIC BOT STARTING...       ║")
    print("╚══════════════════════════════════════════╝")
    await pyro.start()
    print("✅ Pyrogram client started")
    await calls.start()
    print("✅ PyTgCalls started")

    if _StreamEndClass is None:
        asyncio.create_task(_stream_end_poller())
        print("✅ Stream-end poller started (fallback mode)")
    else:
        print(f"✅ Stream-end handler registered via {_StreamEndClass.__name__}")

    print("✅ Bot is running! Press Ctrl+C to stop.\n")
    await dp.start_polling(bot)


if __name__ == "__main__":
    # ── EVENT LOOP FIX: Share the same loop for Pyrogram and Aiogram ──
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped gracefully.")
