import sqlite3
import json
import time
from datetime import datetime

conn   = sqlite3.connect("royal_music.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# ══════════════════════════════════════════════
#  SCHEMA
# ══════════════════════════════════════════════
cursor.executescript("""
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS groups (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT,
    lang        TEXT    DEFAULT 'en',
    registered  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS group_settings (
    chat_id          INTEGER PRIMARY KEY,
    loop             INTEGER DEFAULT 0,
    loop_queue       INTEGER DEFAULT 0,
    mode_247         INTEGER DEFAULT 0,
    eq_bass          INTEGER DEFAULT 0,
    eq_mid           INTEGER DEFAULT 0,
    eq_treble        INTEGER DEFAULT 0,
    volume           INTEGER DEFAULT 100,
    dj_role          INTEGER DEFAULT 0,
    admin_only       INTEGER DEFAULT 0,
    vote_skip        INTEGER DEFAULT 1,
    auto_play        INTEGER DEFAULT 1,
    max_queue        INTEGER DEFAULT 20,
    party_mode       INTEGER DEFAULT 0,
    duplicate_check  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS group_premium (
    chat_id      INTEGER PRIMARY KEY,
    enabled      INTEGER DEFAULT 0,
    expires_at   INTEGER DEFAULT 0,
    sponsor_id   INTEGER DEFAULT 0,
    sponsor_name TEXT    DEFAULT '',
    plan         TEXT    DEFAULT 'monthly',
    activated_by INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_premium (
    user_id     INTEGER PRIMARY KEY,
    enabled     INTEGER DEFAULT 0,
    expires_at  INTEGER DEFAULT 0,
    plan        TEXT    DEFAULT 'monthly'
);

CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    username     TEXT    DEFAULT '',
    first_name   TEXT    DEFAULT '',
    last_play    INTEGER DEFAULT 0,
    total_plays  INTEGER DEFAULT 0,
    streak_days  INTEGER DEFAULT 0,
    last_streak  TEXT    DEFAULT '',
    listening_mins INTEGER DEFAULT 0,
    fav_genre    TEXT    DEFAULT '',
    private_mode INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dj_users (
    chat_id INTEGER,
    user_id INTEGER,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS blacklist (
    chat_id INTEGER,
    keyword TEXT,
    PRIMARY KEY (chat_id, keyword)
);

CREATE TABLE IF NOT EXISTS song_stats (
    chat_id    INTEGER,
    title      TEXT,
    play_count INTEGER DEFAULT 1,
    PRIMARY KEY (chat_id, title)
);

CREATE TABLE IF NOT EXISTS playlists (
    user_id INTEGER,
    name    TEXT,
    songs   TEXT,
    PRIMARY KEY (user_id, name)
);

CREATE TABLE IF NOT EXISTS listening_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER,
    chat_id   INTEGER,
    title     TEXT,
    duration  INTEGER DEFAULT 0,
    played_at INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id  TEXT PRIMARY KEY,
    user_id     INTEGER,
    chat_id     INTEGER DEFAULT 0,
    plan_type   TEXT,
    plan        TEXT,
    stars       INTEGER,
    status      TEXT    DEFAULT 'pending',
    created_at  INTEGER DEFAULT 0,
    completed_at INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_history (
    chat_id     INTEGER,
    role        TEXT,
    content     TEXT,
    created_at  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spam_log (
    user_id     INTEGER,
    chat_id     INTEGER,
    count       INTEGER DEFAULT 1,
    muted_until INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS game_sessions (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT,
    answer      TEXT,
    started_at  INTEGER DEFAULT 0,
    started_by  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    user_id     INTEGER,
    week        TEXT,
    data        TEXT,
    PRIMARY KEY (user_id, week)
);
""")
conn.commit()

# ══════════════════════════════════════════════
#  GROUPS
# ══════════════════════════════════════════════
def register_group(chat_id, title=""):
    cursor.execute("INSERT OR IGNORE INTO groups(chat_id,title,registered) VALUES(?,?,?)",
                   (chat_id, title, int(time.time())))
    cursor.execute("INSERT OR IGNORE INTO group_settings(chat_id) VALUES(?)", (chat_id,))
    cursor.execute("INSERT OR IGNORE INTO group_premium(chat_id) VALUES(?)", (chat_id,))
    conn.commit()

def get_all_groups():
    cursor.execute("SELECT chat_id FROM groups")
    return [r[0] for r in cursor.fetchall()]

def remove_group(chat_id):
    cursor.execute("DELETE FROM groups WHERE chat_id=?", (chat_id,))
    conn.commit()

def get_lang(chat_id):
    cursor.execute("SELECT lang FROM groups WHERE chat_id=?", (chat_id,))
    r = cursor.fetchone()
    return r[0] if r else "en"

def set_lang(chat_id, lang):
    cursor.execute("UPDATE groups SET lang=? WHERE chat_id=?", (lang, chat_id))
    conn.commit()

# ══════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════
def get_settings(chat_id):
    cursor.execute("SELECT * FROM group_settings WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT OR IGNORE INTO group_settings(chat_id) VALUES(?)", (chat_id,))
        conn.commit()
        return get_settings(chat_id)
    return dict(row)

def update_setting(chat_id, key, val):
    cursor.execute(f"UPDATE group_settings SET {key}=? WHERE chat_id=?", (val, chat_id))
    if cursor.rowcount == 0:
        cursor.execute("INSERT OR IGNORE INTO group_settings(chat_id) VALUES(?)", (chat_id,))
        cursor.execute(f"UPDATE group_settings SET {key}=? WHERE chat_id=?", (val, chat_id))
    conn.commit()

# Alias for backward compatibility (some modules import update_settings)
update_settings = update_setting

# ══════════════════════════════════════════════
#  PREMIUM — GROUP
# ══════════════════════════════════════════════
def set_group_premium(chat_id, enabled, days=30, sponsor_id=0, sponsor_name="", plan="monthly", activated_by=0):
    expires = int(time.time()) + days * 86400 if enabled else 0
    cursor.execute("""
        INSERT INTO group_premium(chat_id,enabled,expires_at,sponsor_id,sponsor_name,plan,activated_by)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(chat_id) DO UPDATE SET
            enabled=excluded.enabled, expires_at=excluded.expires_at,
            sponsor_id=excluded.sponsor_id, sponsor_name=excluded.sponsor_name,
            plan=excluded.plan, activated_by=excluded.activated_by
    """, (chat_id, int(enabled), expires, sponsor_id, sponsor_name, plan, activated_by))
    conn.commit()

def get_group_premium(chat_id):
    cursor.execute("SELECT * FROM group_premium WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        return {"enabled": 0, "expires_at": 0, "sponsor_id": 0, "sponsor_name": "", "plan": ""}
    d = dict(row)
    # auto-expire check
    if d["enabled"] and d["expires_at"] > 0 and d["expires_at"] < int(time.time()):
        cursor.execute("UPDATE group_premium SET enabled=0 WHERE chat_id=?", (chat_id,))
        conn.commit()
        d["enabled"] = 0
    return d

def is_group_premium(chat_id):
    return bool(get_group_premium(chat_id)["enabled"])

# ══════════════════════════════════════════════
#  PREMIUM — USER
# ══════════════════════════════════════════════
def set_user_premium(user_id, enabled, days=30, plan="monthly"):
    expires = int(time.time()) + days * 86400 if enabled else 0
    cursor.execute("""
        INSERT INTO user_premium(user_id,enabled,expires_at,plan) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,
            expires_at=excluded.expires_at, plan=excluded.plan
    """, (user_id, int(enabled), expires, plan))
    conn.commit()

def get_user_premium(user_id):
    cursor.execute("SELECT * FROM user_premium WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return {"enabled": 0, "expires_at": 0, "plan": ""}
    d = dict(row)
    if d["enabled"] and d["expires_at"] > 0 and d["expires_at"] < int(time.time()):
        cursor.execute("UPDATE user_premium SET enabled=0 WHERE user_id=?", (user_id,))
        conn.commit()
        d["enabled"] = 0
    return d

def is_user_premium(user_id):
    return bool(get_user_premium(user_id)["enabled"])

def is_premium(user_id, chat_id):
    """User or group premium = premium access."""
    return is_user_premium(user_id) or is_group_premium(chat_id)

# ══════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════
def register_user(user_id, username="", first_name=""):
    cursor.execute("""
        INSERT OR IGNORE INTO users(user_id,username,first_name) VALUES(?,?,?)
    """, (user_id, username, first_name))
    conn.commit()

def update_last_play(user_id):
    now = int(time.time())
    cursor.execute("UPDATE users SET last_play=?, total_plays=total_plays+1 WHERE user_id=?", (now, user_id))
    conn.commit()
    return now

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return dict(row) if row else None

def get_last_play(user_id):
    cursor.execute("SELECT last_play FROM users WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    return r[0] if r else 0

def update_listening_time(user_id, seconds):
    mins = seconds // 60
    cursor.execute("UPDATE users SET listening_mins=listening_mins+? WHERE user_id=?", (mins, user_id))
    conn.commit()

def is_private_mode(user_id):
    cursor.execute("SELECT private_mode FROM users WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    return bool(r[0]) if r else False

def toggle_private(user_id):
    cursor.execute("UPDATE users SET private_mode=1-private_mode WHERE user_id=?", (user_id,))
    conn.commit()

# ══════════════════════════════════════════════
#  DJ / BLACKLIST
# ══════════════════════════════════════════════
def add_dj(chat_id, user_id):
    cursor.execute("INSERT OR IGNORE INTO dj_users VALUES(?,?)", (chat_id, user_id))
    conn.commit()

def remove_dj(chat_id, user_id):
    cursor.execute("DELETE FROM dj_users WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()

def is_dj(chat_id, user_id):
    cursor.execute("SELECT 1 FROM dj_users WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return bool(cursor.fetchone())

def add_blacklist(chat_id, keyword):
    cursor.execute("INSERT OR IGNORE INTO blacklist VALUES(?,?)", (chat_id, keyword.lower()))
    conn.commit()

def remove_blacklist(chat_id, keyword):
    cursor.execute("DELETE FROM blacklist WHERE chat_id=? AND keyword=?", (chat_id, keyword.lower()))
    conn.commit()

def get_blacklist(chat_id):
    cursor.execute("SELECT keyword FROM blacklist WHERE chat_id=?", (chat_id,))
    return [r[0] for r in cursor.fetchall()]

def is_blacklisted(chat_id, title):
    return any(kw in title.lower() for kw in get_blacklist(chat_id))

# ══════════════════════════════════════════════
#  SONG STATS
# ══════════════════════════════════════════════
def record_play(chat_id, title):
    cursor.execute("""
        INSERT INTO song_stats(chat_id,title,play_count) VALUES(?,?,1)
        ON CONFLICT(chat_id,title) DO UPDATE SET play_count=play_count+1
    """, (chat_id, title))
    conn.commit()

def get_top_songs(chat_id, limit=10):
    cursor.execute("SELECT title, play_count FROM song_stats WHERE chat_id=? ORDER BY play_count DESC LIMIT ?",
                   (chat_id, limit))
    return cursor.fetchall()

def get_global_stats():
    cursor.execute("SELECT COUNT(*) FROM groups")
    groups = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(play_count) FROM song_stats")
    plays = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM user_premium WHERE enabled=1")
    prem_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM group_premium WHERE enabled=1")
    prem_groups = cursor.fetchone()[0]
    cursor.execute("SELECT title, SUM(play_count) as t FROM song_stats GROUP BY title ORDER BY t DESC LIMIT 1")
    top = cursor.fetchone()
    return {"groups": groups, "plays": plays, "prem_users": prem_users,
            "prem_groups": prem_groups, "top": top}

# ══════════════════════════════════════════════
#  HISTORY
# ══════════════════════════════════════════════
def add_history(user_id, chat_id, title, duration):
    cursor.execute("""
        INSERT INTO listening_history(user_id,chat_id,title,duration,played_at)
        VALUES(?,?,?,?,?)
    """, (user_id, chat_id, title, duration, int(time.time())))
    conn.commit()

def get_user_history(user_id, limit=20):
    cursor.execute("""
        SELECT title, duration, played_at FROM listening_history
        WHERE user_id=? ORDER BY played_at DESC LIMIT ?
    """, (user_id, limit))
    return cursor.fetchall()

# ══════════════════════════════════════════════
#  PLAYLISTS
# ══════════════════════════════════════════════
def save_playlist(user_id, name, songs):
    cursor.execute("INSERT OR REPLACE INTO playlists VALUES(?,?,?)",
                   (user_id, name, json.dumps(songs)))
    conn.commit()

def load_playlist(user_id, name):
    cursor.execute("SELECT songs FROM playlists WHERE user_id=? AND name=?", (user_id, name))
    r = cursor.fetchone()
    return json.loads(r[0]) if r else None

def list_playlists(user_id):
    cursor.execute("SELECT name FROM playlists WHERE user_id=?", (user_id,))
    return [r[0] for r in cursor.fetchall()]

def delete_playlist(user_id, name):
    cursor.execute("DELETE FROM playlists WHERE user_id=? AND name=?", (user_id, name))
    conn.commit()

def count_playlists(user_id):
    cursor.execute("SELECT COUNT(*) FROM playlists WHERE user_id=?", (user_id,))
    return cursor.fetchone()[0]

# ══════════════════════════════════════════════
#  PAYMENTS
# ══════════════════════════════════════════════
def create_payment(payment_id, user_id, chat_id, plan_type, plan, stars):
    cursor.execute("""
        INSERT OR IGNORE INTO payments(payment_id,user_id,chat_id,plan_type,plan,stars,created_at)
        VALUES(?,?,?,?,?,?,?)
    """, (payment_id, user_id, chat_id, plan_type, plan, stars, int(time.time())))
    conn.commit()

def complete_payment(payment_id):
    cursor.execute("""
        UPDATE payments SET status='completed', completed_at=? WHERE payment_id=?
    """, (int(time.time()), payment_id))
    conn.commit()

def get_payment(payment_id):
    cursor.execute("SELECT * FROM payments WHERE payment_id=?", (payment_id,))
    r = cursor.fetchone()
    return dict(r) if r else None

def get_revenue_stats():
    cursor.execute("SELECT SUM(stars) FROM payments WHERE status='completed'")
    total = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM payments WHERE status='completed'")
    count = cursor.fetchone()[0]
    return total, count

# ══════════════════════════════════════════════
#  AI HISTORY (per-group conversation)
# ══════════════════════════════════════════════
def add_ai_message(chat_id, role, content):
    cursor.execute("INSERT INTO ai_history(chat_id,role,content,created_at) VALUES(?,?,?,?)",
                   (chat_id, role, content, int(time.time())))
    # Keep only last 20 messages per group
    cursor.execute("""
        DELETE FROM ai_history WHERE chat_id=? AND id NOT IN (
            SELECT id FROM ai_history WHERE chat_id=? ORDER BY created_at DESC LIMIT 20
        )
    """, (chat_id, chat_id))
    conn.commit()

def get_ai_history(chat_id):
    cursor.execute("SELECT role, content FROM ai_history WHERE chat_id=? ORDER BY created_at ASC", (chat_id,))
    return [{"role": r[0], "content": r[1]} for r in cursor.fetchall()]

def clear_ai_history(chat_id):
    cursor.execute("DELETE FROM ai_history WHERE chat_id=?", (chat_id,))
    conn.commit()

# ══════════════════════════════════════════════
#  SPAM CONTROL
# ══════════════════════════════════════════════
def log_spam(user_id, chat_id):
    cursor.execute("""
        INSERT INTO spam_log(user_id,chat_id,count) VALUES(?,?,1)
        ON CONFLICT(user_id,chat_id) DO UPDATE SET count=count+1
    """, (user_id, chat_id))
    conn.commit()

def get_spam_count(user_id, chat_id):
    cursor.execute("SELECT count, muted_until FROM spam_log WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    r = cursor.fetchone()
    return (r[0], r[1]) if r else (0, 0)

def mute_user(user_id, chat_id, seconds=60):
    until = int(time.time()) + seconds
    cursor.execute("""
        INSERT INTO spam_log(user_id,chat_id,muted_until) VALUES(?,?,?)
        ON CONFLICT(user_id,chat_id) DO UPDATE SET muted_until=?
    """, (user_id, chat_id, until, until))
    conn.commit()
    return until

def reset_spam(user_id, chat_id):
    cursor.execute("UPDATE spam_log SET count=0 WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    conn.commit()

# ══════════════════════════════════════════════
#  GAME SESSIONS
# ══════════════════════════════════════════════
def start_game(chat_id, title, answer, started_by):
    cursor.execute("""
        INSERT OR REPLACE INTO game_sessions(chat_id,title,answer,started_at,started_by)
        VALUES(?,?,?,?,?)
    """, (chat_id, title, answer, int(time.time()), started_by))
    conn.commit()

def get_game(chat_id):
    cursor.execute("SELECT * FROM game_sessions WHERE chat_id=?", (chat_id,))
    r = cursor.fetchone()
    return dict(r) if r else None

def end_game(chat_id):
    cursor.execute("DELETE FROM game_sessions WHERE chat_id=?", (chat_id,))
    conn.commit()
