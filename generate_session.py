"""
Run this ONCE to generate your Pyrogram string session for the spare account.

Steps:
1. Fill in API_ID and API_HASH below (from https://my.telegram.org)
2. Run: python generate_session.py
3. Enter your spare number + OTP when prompted
4. Copy the printed string into your .env as PYROGRAM_STRING
"""
from pyrogram import Client

API_ID   = 0       # ← paste your API_ID here
API_HASH = ""      # ← paste your API_HASH here

with Client("music_session", api_id=API_ID, api_hash=API_HASH) as app:
    session_string = app.export_session_string()
    print("\n" + "=" * 60)
    print("YOUR PYROGRAM STRING SESSION:")
    print("=" * 60)
    print(session_string)
    print("=" * 60)
    print("\nCopy the string above into your .env as PYROGRAM_STRING")
