"""
AI Module — Gemini → Groq → OpenRouter fallback chain
All free tiers. No payment required.
"""
import asyncio
import json
import aiohttp
from config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

# ══════════════════════════════════════════════
#  AI DJ PERSONALITY SYSTEM PROMPT
# ══════════════════════════════════════════════
DJ_SYSTEM_PROMPT = """You are Royal DJ — the AI DJ personality of a premium Telegram music bot.
You are charismatic, fun, and knowledgeable about music. You speak like a real DJ —
energetic, friendly, sometimes playful. You know about all genres: Bollywood, Pop, Hip-hop,
EDM, Classical, etc. You help users discover music, understand song meanings,
suggest playlists, and create a party vibe.

Keep responses SHORT (2-4 sentences max) unless explaining lyrics or meanings.
Use music emojis naturally 🎵🎶🎧🎸🥁. Never be boring.
When suggesting songs, give 3-5 specific song names with artists.
Always respond in the same language the user writes in."""

MOOD_SYSTEM_PROMPT = """You are a music mood analyzer. Analyze the given chat messages and detect the mood.
Return ONLY a JSON object like:
{"mood": "happy|sad|energetic|chill|romantic|party|angry|focused", "confidence": 0.0-1.0, "genre_suggestion": "genre name", "playlist_name": "creative playlist name"}
Nothing else. No explanation."""

RECOMMEND_SYSTEM_PROMPT = """You are a music recommendation AI. Based on the song/artist given,
suggest 5 similar songs. Return ONLY a JSON array like:
[{"title": "Song Name", "artist": "Artist Name", "reason": "short reason"}]
Nothing else."""

# ══════════════════════════════════════════════
#  GEMINI
# ══════════════════════════════════════════════
async def _gemini(messages: list, system: str = DJ_SYSTEM_PROMPT) -> str | None:
    if not GEMINI_API_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    # Build Gemini-style contents
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.8}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[GEMINI] {e}")
    return None

# ══════════════════════════════════════════════
#  GROQ
# ══════════════════════════════════════════════
async def _groq(messages: list, system: str = DJ_SYSTEM_PROMPT) -> str | None:
    if not GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 512,
        "temperature": 0.8
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[GROQ] {e}")
    return None

# ══════════════════════════════════════════════
#  OPENROUTER
# ══════════════════════════════════════════════
async def _openrouter(messages: list, system: str = DJ_SYSTEM_PROMPT) -> str | None:
    if not OPENROUTER_API_KEY:
        return None
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/royalmusicbot",
        "X-Title": "Royal Music Bot"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct:free",  # free model
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 512,
        "temperature": 0.8
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[OPENROUTER] {e}")
    return None

# ══════════════════════════════════════════════
#  FALLBACK CHAIN — main entry point
# ══════════════════════════════════════════════
async def ai_chat(messages: list, system: str = DJ_SYSTEM_PROMPT) -> str:
    """Try Gemini → Groq → OpenRouter → fallback message."""
    for provider in [_gemini, _groq, _openrouter]:
        result = await provider(messages, system)
        if result:
            return result
    return "🎵 Royal DJ is taking a quick break! Try again in a moment."

async def ai_detect_mood(chat_messages: list[str]) -> dict:
    """Detect mood from recent chat messages."""
    combined = "\n".join(chat_messages[-10:])
    messages = [{"role": "user", "content": f"Analyze these chat messages:\n{combined}"}]
    raw = await ai_chat(messages, system=MOOD_SYSTEM_PROMPT)
    try:
        raw = raw.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return {"mood": "chill", "confidence": 0.5, "genre_suggestion": "Pop", "playlist_name": "Royal Vibes"}

async def ai_recommend(song_or_artist: str) -> list[dict]:
    """Get song recommendations similar to given song/artist."""
    messages = [{"role": "user", "content": f"Recommend 5 songs similar to: {song_or_artist}"}]
    raw = await ai_chat(messages, system=RECOMMEND_SYSTEM_PROMPT)
    try:
        raw = raw.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return []

async def ai_explain_lyrics(song_title: str, artist: str = "") -> str:
    """Explain the meaning of a song."""
    q = f"{song_title}" + (f" by {artist}" if artist else "")
    messages = [{"role": "user", "content": f"Explain the meaning and story behind the song: {q}. Keep it under 200 words."}]
    return await ai_chat(messages)

async def ai_name_playlist(songs: list[str]) -> str:
    """Generate a creative playlist name from song titles."""
    song_list = ", ".join(songs[:10])
    messages = [{"role": "user", "content": f"Create ONE creative, catchy playlist name for these songs: {song_list}. Just the name, nothing else."}]
    result = await ai_chat(messages)
    return result.strip().strip('"').strip("'")

async def ai_generate_playlist(mood_or_event: str) -> list[str]:
    """Generate a playlist for a given mood/event."""
    messages = [{"role": "user", "content": f"Create a playlist of 10 songs for: {mood_or_event}. Return as a simple numbered list, one song per line like: 1. Song Name - Artist"}]
    result = await ai_chat(messages)
    lines = [l.strip() for l in result.split("\n") if l.strip() and any(c.isdigit() for c in l[:3])]
    return lines[:10]

async def ai_dj_intro(track_title: str, requester_name: str) -> str:
    """Generate a DJ-style intro for a song being played."""
    messages = [{"role": "user", "content": f"Give a short DJ-style intro (1-2 sentences, max 20 words) for playing '{track_title}' requested by {requester_name}. Be hype!"}]
    return await ai_chat(messages)

async def ai_voice_command(text: str) -> str:
    """Parse a natural language voice/text command into a bot command."""
    messages = [{"role": "user", "content": f"""Parse this music request into a command.
User said: "{text}"
Return ONLY one of these exact formats:
- /play <song name>
- /skip
- /pause
- /resume
- /stop
- /queue
- /shuffle
Nothing else."""}]
    return await ai_chat(messages)
# ══════════════════════════════════════════════
#  CONVERSATION HISTORY (per chat)
# ══════════════════════════════════════════════
ai_history: dict[int, list[dict]] = {}  # chat_id -> messages

def add_ai_message(chat_id: int, role: str, content: str):
    """Store a message in AI conversation history."""
    if chat_id not in ai_history:
        ai_history[chat_id] = []
    ai_history[chat_id].append({"role": role, "content": content})
    # Keep last 20 messages to avoid token overflow
    if len(ai_history[chat_id]) > 20:
        ai_history[chat_id] = ai_history[chat_id][-20:]

def get_ai_history(chat_id: int) -> list[dict]:
    """Get conversation history for a chat."""
    return ai_history.get(chat_id, [])

def clear_ai_history(chat_id: int):
    """Clear conversation history for a chat."""
    ai_history.pop(chat_id, None)
