import os
from dotenv import load_dotenv
load_dotenv()

# ── Telegram ──────────────────────────────────
API_ID            = int(os.getenv("API_ID", 0))
API_HASH          = os.getenv("API_HASH", "")
BOT_TOKEN         = os.getenv("BOT_TOKEN", "")
OWNER_ID          = int(os.getenv("OWNER_ID", 0))
STRING_SESSION    = os.getenv("PYROGRAM_STRING", "")

# ── Music sources ─────────────────────────────
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
GENIUS_TOKEN          = os.getenv("GENIUS_TOKEN", "")

# ── AI (free fallback chain) ──────────────────
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY= os.getenv("OPENROUTER_API_KEY", "")

# ── Bot settings ──────────────────────────────
VOTE_SKIP_COUNT   = 3
MAX_QUEUE_FREE    = 20
MAX_QUEUE_PREMIUM = 200
MAX_PLAYLIST_FREE = 3
MAX_PLAYLIST_PREM = 20
COOLDOWN_FREE     = 5    # seconds between /play for free users
COOLDOWN_PREMIUM  = 1
MAX_QUEUE_PER_USER_FREE = 3   # songs one user can add at a time

# ── Premium pricing (Telegram Stars) ──────────
USER_PREMIUM_STARS_MONTHLY  = 150
USER_PREMIUM_STARS_YEARLY   = 1200
GROUP_PREMIUM_STARS_MONTHLY = 500
GROUP_PREMIUM_STARS_YEARLY  = 4000

# ── Sponsor display ───────────────────────────
SPONSOR_TAG = "💎 Powered by Royal Music Bot"

# ── Download quality ──────────────────────────
DOWNLOAD_QUALITY_FREE    = "128"
DOWNLOAD_QUALITY_PREMIUM = "320"

# ── Game settings ─────────────────────────────
GAME_TIMEOUT = 30  # seconds to guess
