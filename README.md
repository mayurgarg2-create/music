# 👑 Royal Music Bot

> A full-featured, production-grade Telegram music bot with AI DJ, premium system, Telegram Stars payments, and 320kbps streaming.

---

## ✨ Features

### 🎵 Core Music
- Play from YouTube, Spotify, Gaana
- 320kbps premium audio quality
- Equalizer (Bass / Mid / Treble)
- Queue, shuffle, loop, 24/7 mode
- Seek, volume control, back/previous
- Vote skip system (3 votes)
- Duplicate song prevention
- Beautiful now-playing image card

### 🤖 AI Features (Free AI APIs)
- **AI DJ** — talks & responds like a real DJ
- **Mood Detection** — reads group chat mood
- **Vibe Playlist** — auto-generates mood-based playlists
- **Song Recommendations** — AI suggests similar songs
- **Song Meaning** — AI explains lyrics and story
- **AI Playlist Generator** — for events (party, gym, sad, etc.)
- **Natural Language Commands** — /ask play something chill
- Fallback chain: Gemini → Groq → OpenRouter (all free!)

### 💎 Premium System
- User Premium (personal AI + download + history)
- Group Premium (AI DJ for all + unlimited queue)
- **Telegram Stars ⭐ payment** (built-in, no external gateway)
- Auto-activation after payment
- Sponsor badge in player UI
- Owner can grant/revoke premium manually

### 📥 Downloads
- MP3 download with metadata
- 128kbps (free) / 320kbps (premium)
- Clean filenames, auto-cleanup

### 🎮 Games
- Guess the Song game with timer
- Flexible answer matching

### 🛡 Anti-Spam & Security
- Per-user cooldown system
- Auto-mute on spam
- Per-group isolation
- Duplicate song check
- Blacklist system

### ⚙️ Admin Panel
- Toggle: admin-only mode, vote skip, auto-play, DJ role, party mode, duplicate check
- Blacklist management
- DJ role assignment
- Language settings (English / Hindi)
- Broadcast to all groups

---

## 📁 Project Structure

```
royal_music_bot/
├── bot.py              ← Main entry point
├── config.py           ← All settings & constants
├── database.py         ← SQLite database (all tables)
├── ai.py               ← AI fallback chain (Gemini→Groq→OpenRouter)
├── player.py           ← Audio engine (yt-dlp + PyTgCalls)
├── card.py             ← Now-playing image card generator
├── payments.py         ← Telegram Stars payment system
├── handlers/
│   ├── music.py        ← /play /skip /queue /seek ...
│   ├── premium.py      ← /premium /unpremium /buy
│   ├── admin.py        ← /adminpanel /blacklist /dj /broadcast
│   ├── ai_cmds.py      ← /dj /mood /vibe /recommend /explain
│   ├── download.py     ← /download
│   ├── games.py        ← /guesssong
│   └── lyrics.py       ← /lyrics
├── requirements.txt
├── generate_session.py ← Run once to get Pyrogram string
├── .env.example        ← Copy to .env and fill in
└── .gitignore
```

---

## 🚀 Setup Guide

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/royal-music-bot
cd royal-music-bot
pip install -r requirements.txt
```

### 2. Install FFmpeg

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg -y

# macOS
brew install ffmpeg

# Windows — download from https://ffmpeg.org/download.html
```

### 3. Get Your Credentials

| Credential | Where to Get |
|-----------|-------------|
| `API_ID` & `API_HASH` | https://my.telegram.org |
| `BOT_TOKEN` | @BotFather on Telegram |
| `OWNER_ID` | Message @userinfobot |
| `PYROGRAM_STRING` | Run `generate_session.py` |
| `SPOTIFY_CLIENT_ID/SECRET` | https://developer.spotify.com/dashboard |
| `GENIUS_TOKEN` | https://genius.com/api-clients |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `GROQ_API_KEY` | https://console.groq.com |
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys |

> All AI APIs have **free tiers** — no payment needed!

### 4. Generate Pyrogram String

```bash
# Fill in API_ID and API_HASH in generate_session.py first
python generate_session.py
```

### 5. Configure .env

```bash
cp .env.example .env
# Fill in all values in .env
```

### 6. Configure Bot on Telegram

1. Go to @BotFather → `/mybots` → your bot → **Bot Settings → Group Privacy → Turn OFF**
2. Add bot to your group and make it **Admin**
3. Add your **spare account** to the group and make it **Admin** with "Manage Voice Chats" permission

### 7. Run the Bot

```bash
python bot.py
```

---

## 👑 Owner Commands

| Command | Description |
|---------|-------------|
| `/premium [days]` | Grant group premium (free, unlimited days) |
| `/unpremium` | Remove group premium |
| `/premiumuser [days]` | Reply to user — grant user premium |
| `/unpremiumuser` | Reply to user — remove user premium |
| `/broadcast [text]` | Send to all groups |
| `/stats` | Bot-wide statistics |
| `/revenue` | Payment earnings |

---

## 💰 Monetization

- Users buy with **Telegram Stars ⭐** (built into Telegram, no payment gateway needed)
- Plans: User Monthly / Yearly, Group Monthly / Yearly
- Revenue tracking built-in with `/revenue` command
- Sponsor badge shown in player UI when group buys premium

---

## 🤖 AI Setup (All Free)

The bot uses a **fallback chain** — tries each AI in order until one responds:

1. **Gemini 1.5 Flash** (Google) — generous free tier
2. **Llama 3 via Groq** — ultra fast, very generous free tier
3. **Mistral 7B via OpenRouter** — free model available

You only need ONE key for AI to work, but having all 3 means maximum reliability.

---

## ⭐ Telegram Stars Payment Setup

1. Go to @BotFather → `/mybots` → your bot → **Payments**
2. Enable "Telegram Stars" as payment provider
3. No additional setup needed — Stars work automatically!

---

## 📝 License

MIT License — Free to use, modify, and distribute.

---

Made with ❤️ and 👑 by Royal Music Bot
