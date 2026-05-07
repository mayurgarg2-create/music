"""
Telegram Stars Payment System
/buy → user premium
/buygroup → group premium
Auto activation on successful payment
"""
import uuid
import time
from aiogram import Bot
from aiogram.types import (
    Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import (
    USER_PREMIUM_STARS_MONTHLY, USER_PREMIUM_STARS_YEARLY,
    GROUP_PREMIUM_STARS_MONTHLY, GROUP_PREMIUM_STARS_YEARLY
)
from database import (
    create_payment, complete_payment, get_payment,
    set_user_premium, set_group_premium,
    get_user_premium, get_group_premium, get_revenue_stats
)

GOLD = "👑"
NOTE = "🎵"

# ── Plan configs ─────────────────────────────
USER_PLANS = {
    "user_monthly": {
        "label":       "👤 User Premium — 1 Month",
        "stars":       USER_PREMIUM_STARS_MONTHLY,
        "days":        30,
        "description": "Full AI features, 320kbps, downloads, playlists & more for 30 days",
        "plan":        "monthly"
    },
    "user_yearly": {
        "label":       "👤 User Premium — 1 Year",
        "stars":       USER_PREMIUM_STARS_YEARLY,
        "days":        365,
        "description": "Full AI features, 320kbps, downloads, playlists & more for 365 days",
        "plan":        "yearly"
    },
}

GROUP_PLANS = {
    "group_monthly": {
        "label":       "👥 Group Premium — 1 Month",
        "stars":       GROUP_PREMIUM_STARS_MONTHLY,
        "days":        30,
        "description": "AI DJ, unlimited queue, 320kbps for ALL group members for 30 days",
        "plan":        "monthly"
    },
    "group_yearly": {
        "label":       "👥 Group Premium — 1 Year",
        "stars":       GROUP_PREMIUM_STARS_YEARLY,
        "days":        365,
        "description": "AI DJ, unlimited queue, 320kbps for ALL group members for 365 days",
        "plan":        "yearly"
    },
}

ALL_PLANS = {**USER_PLANS, **GROUP_PLANS}

def buy_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"👤 Personal — {USER_PREMIUM_STARS_MONTHLY}⭐/mo",
                                 callback_data="buy:user_monthly"),
            InlineKeyboardButton(text=f"👤 Personal — {USER_PREMIUM_STARS_YEARLY}⭐/yr",
                                 callback_data="buy:user_yearly"),
        ],
        [
            InlineKeyboardButton(text=f"👥 Group — {GROUP_PREMIUM_STARS_MONTHLY}⭐/mo",
                                 callback_data="buy:group_monthly"),
            InlineKeyboardButton(text=f"👥 Group — {GROUP_PREMIUM_STARS_YEARLY}⭐/yr",
                                 callback_data="buy:group_yearly"),
        ],
        [InlineKeyboardButton(text="💎 What's included?", callback_data="premium_info")],
    ])

def premium_info_text():
    return (
        f"╔══「 💎 <b>PREMIUM FEATURES</b> 」══╗\n\n"
        f"  <b>👤 User Premium:</b>\n"
        f"  ✅ AI DJ personality & recommendations\n"
        f"  ✅ Mood detection & smart playlists\n"
        f"  ✅ Song download (320kbps MP3)\n"
        f"  ✅ 20 saved playlists\n"
        f"  ✅ Priority queue (songs play faster)\n"
        f"  ✅ Listening history & weekly report\n"
        f"  ✅ Private mode (hide activity)\n"
        f"  ✅ Reduced cooldown (1 sec vs 5 sec)\n\n"
        f"  <b>👥 Group Premium:</b>\n"
        f"  ✅ Everything above for ALL members\n"
        f"  ✅ AI DJ talks in your group\n"
        f"  ✅ 320kbps for entire group\n"
        f"  ✅ Unlimited queue (200 songs)\n"
        f"  ✅ 💎 Sponsor badge in player UI\n"
        f"  ✅ No restrictions for anyone\n\n"
        f"  <b>💰 Payment:</b> Telegram Stars ⭐\n"
        f"  Safe · Instant · No card needed\n\n"
        f"╚{'═'*32}╝"
    )

async def send_invoice(bot: Bot, chat_id: int, user_id: int, plan_key: str, group_chat_id: int = 0):
    plan = ALL_PLANS.get(plan_key)
    if not plan:
        return

    payment_id = f"{plan_key}_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    target_chat = group_chat_id if group_chat_id else 0
    create_payment(payment_id, user_id, target_chat, plan_key, plan["plan"], plan["stars"])

    await bot.send_invoice(
        chat_id=chat_id,
        title=plan["label"],
        description=plan["description"],
        payload=payment_id,
        currency="XTR",           # Telegram Stars
        prices=[LabeledPrice(label=plan["label"], amount=plan["stars"])],
        # No provider_token for Stars
    )

async def handle_pre_checkout(query: PreCheckoutQuery):
    """Always approve pre-checkout for Stars."""
    await query.answer(ok=True)

async def handle_successful_payment(message: Message, bot: Bot):
    """Activate premium after successful Stars payment."""
    payment = message.successful_payment
    payload = payment.invoice_payload

    db_payment = get_payment(payload)
    if not db_payment:
        return

    complete_payment(payload)

    plan_key   = db_payment["plan_type"]
    user_id    = db_payment["user_id"]
    chat_id    = db_payment["chat_id"]
    plan_conf  = ALL_PLANS.get(plan_key, {})
    days       = plan_conf.get("days", 30)

    if plan_key.startswith("user_"):
        set_user_premium(user_id, True, days=days, plan=plan_conf.get("plan", "monthly"))
        exp = time.strftime("%d %b %Y", time.localtime(time.time() + days * 86400))
        await message.reply(
            f"╔══「 💎 <b>PREMIUM ACTIVATED!</b> 」══╗\n\n"
            f"  {GOLD} <b>User Premium</b> is now active!\n\n"
            f"  📅 Expires: <b>{exp}</b>\n"
            f"  ⭐ Stars paid: <b>{payment.total_amount}</b>\n\n"
            f"  Enjoy AI DJ, downloads, 320kbps & more!\n"
            f"  Use /premium to check your status.\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )

    elif plan_key.startswith("group_"):
        target = chat_id if chat_id else message.chat.id
        set_group_premium(target, True, days=days,
                          sponsor_id=user_id,
                          sponsor_name=message.from_user.first_name,
                          plan=plan_conf.get("plan", "monthly"),
                          activated_by=user_id)
        exp = time.strftime("%d %b %Y", time.localtime(time.time() + days * 86400))
        await message.reply(
            f"╔══「 💎 <b>GROUP PREMIUM ACTIVATED!</b> 」══╗\n\n"
            f"  {GOLD} <b>Group Premium</b> is now active!\n"
            f"  Sponsored by: <b>{message.from_user.first_name}</b>\n\n"
            f"  📅 Expires: <b>{exp}</b>\n"
            f"  ⭐ Stars paid: <b>{payment.total_amount}</b>\n\n"
            f"  All members now enjoy AI DJ, 320kbps & more!\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )
        # Notify the group too
        if chat_id and chat_id != message.chat.id:
            try:
                await bot.send_message(
                    chat_id,
                    f"╔══「 💎 <b>GROUP PREMIUM UNLOCKED!</b> 」══╗\n\n"
                    f"  {GOLD} Sponsored by <b>{message.from_user.first_name}</b>!\n"
                    f"  All members now have full premium access!\n\n"
                    f"╚{'═'*32}╝",
                    parse_mode="HTML"
                )
            except Exception:
                pass
