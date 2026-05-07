"""Premium handler — /premium /unpremium /buy /buygroup /mystatus"""
import time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from database import (
    set_group_premium, set_user_premium,
    get_group_premium, get_user_premium,
    is_group_premium, is_user_premium,
    get_global_stats, get_revenue_stats
)
from payments import (
    buy_kb, premium_info_text, send_invoice,
    handle_pre_checkout, handle_successful_payment, ALL_PLANS
)

GOLD = "👑"

def register(dp: Dispatcher, bot: Bot, owner_id: int):

    # ── /premium (owner only — activate group premium free) ──
    @dp.message(Command("premium"))
    async def premium_cmd(message: Message):
        if message.from_user.id != owner_id:
            await message.reply("🚫 Owner only command!"); return

        chat_id = message.chat.id
        parts   = message.text.split()

        # Usage: /premium [days] [sponsor_name]
        days         = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
        sponsor_name = " ".join(parts[2:]) if len(parts) > 2 else "Royal Bot Owner"

        set_group_premium(
            chat_id, enabled=True, days=days,
            sponsor_id=owner_id, sponsor_name=sponsor_name,
            plan="owner_grant", activated_by=owner_id
        )

        exp = time.strftime("%d %b %Y", time.localtime(time.time() + days * 86400))
        await message.reply(
            f"╔══「 💎 <b>GROUP PREMIUM ACTIVATED</b> 」══╗\n\n"
            f"  {GOLD} Premium is now <b>ON</b> for this group!\n\n"
            f"  📅 Expires: <b>{exp}</b> ({days} days)\n"
            f"  💎 Sponsor: <b>{sponsor_name}</b>\n\n"
            f"  ✅ AI DJ enabled\n"
            f"  ✅ 320kbps streaming\n"
            f"  ✅ Unlimited queue\n"
            f"  ✅ All AI features unlocked\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /unpremium (owner only — remove group premium) ───────
    @dp.message(Command("unpremium"))
    async def unpremium_cmd(message: Message):
        if message.from_user.id != owner_id:
            await message.reply("🚫 Owner only command!"); return

        chat_id = message.chat.id
        set_group_premium(chat_id, enabled=False)
        await message.reply(
            f"╔══「 ❌ <b>GROUP PREMIUM REMOVED</b> 」══╗\n\n"
            f"  {GOLD} Premium features removed from this group.\n"
            f"  Group is back to free tier.\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /premiumuser / /unpremiumuser (owner — grant user premium) ──
    @dp.message(Command("premiumuser"))
    async def premium_user_cmd(message: Message):
        if message.from_user.id != owner_id:
            await message.reply("🚫 Owner only!"); return
        if not message.reply_to_message:
            await message.reply("⚠️ Reply to someone's message to grant them premium."); return

        target = message.reply_to_message.from_user
        parts  = message.text.split()
        days   = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30

        set_user_premium(target.id, True, days=days)
        exp = time.strftime("%d %b %Y", time.localtime(time.time() + days * 86400))

        await message.reply(
            f"╔══「 💎 <b>USER PREMIUM GRANTED</b> 」══╗\n\n"
            f"  {GOLD} <b>{target.first_name}</b> now has premium!\n"
            f"  📅 Expires: <b>{exp}</b> ({days} days)\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )
        try:
            await bot.send_message(
                target.id,
                f"╔══「 💎 <b>PREMIUM ACTIVATED!</b> 」══╗\n\n"
                f"  {GOLD} You have been granted <b>User Premium</b>!\n"
                f"  📅 Expires: <b>{exp}</b>\n\n"
                f"  Enjoy AI DJ, downloads & all premium features!\n\n"
                f"╚{'═'*32}╝",
                parse_mode="HTML"
            )
        except Exception:
            pass

    @dp.message(Command("unpremiumuser"))
    async def unpremium_user_cmd(message: Message):
        if message.from_user.id != owner_id:
            await message.reply("🚫 Owner only!"); return
        if not message.reply_to_message:
            await message.reply("⚠️ Reply to someone's message."); return

        target = message.reply_to_message.from_user
        set_user_premium(target.id, False)
        await message.reply(f"❌ Premium removed from <b>{target.first_name}</b>.", parse_mode="HTML")

    # ── /mystatus — check own premium status ─────────────────
    @dp.message(Command("mystatus"))
    async def mystatus_cmd(message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        up = get_user_premium(user_id)
        gp = get_group_premium(chat_id)

        def exp_str(ts):
            if not ts: return "Never"
            return time.strftime("%d %b %Y %H:%M", time.localtime(ts))

        user_status  = "✅ Active" if up["enabled"] else "❌ Free"
        group_status = "✅ Active" if gp["enabled"] else "❌ Free"
        user_exp     = exp_str(up.get("expires_at", 0)) if up["enabled"] else "—"
        group_exp    = exp_str(gp.get("expires_at", 0)) if gp["enabled"] else "—"
        sponsor      = gp.get("sponsor_name", "") if gp["enabled"] else ""

        await message.reply(
            f"╔══「 💎 <b>YOUR PREMIUM STATUS</b> 」══╗\n\n"
            f"  👤 <b>User Premium:</b> {user_status}\n"
            f"  📅 Expires: {user_exp}\n\n"
            f"  👥 <b>Group Premium:</b> {group_status}\n"
            f"  📅 Expires: {group_exp}\n"
            + (f"  💎 Sponsored by: {sponsor}\n" if sponsor else "") +
            f"\n  Use /buy to upgrade anytime!\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )

    # ── /buy — show purchase menu ─────────────────────────────
    @dp.message(Command("buy"))
    async def buy_cmd(message: Message):
        await message.reply(
            f"╔══「 💎 <b>GET PREMIUM</b> 」══╗\n\n"
            f"  {GOLD} Upgrade for the ultimate music experience!\n\n"
            f"  💰 Paid with <b>Telegram Stars ⭐</b>\n"
            f"  ⚡ Instant activation\n"
            f"  🔒 100% safe via Telegram\n\n"
            f"  Choose your plan below 👇\n\n"
            f"╚{'═'*32}╝",
            reply_markup=buy_kb(),
            parse_mode="HTML"
        )

    # ── /buygroup — helper ────────────────────────────────────
    @dp.message(Command("buygroup"))
    async def buygroup_cmd(message: Message):
        if message.chat.type == "private":
            await message.reply(
                f"╔══「 👥 <b>GROUP PREMIUM</b> 」══╗\n\n"
                f"  To buy group premium, use /buy in your group chat!\n"
                f"  The bot needs to be a member of that group.\n\n"
                f"╚{'═'*32}╝",
                parse_mode="HTML"
            ); return
        await message.reply(
            f"╔══「 👥 <b>GROUP PREMIUM</b> 」══╗\n\n"
            f"  {GOLD} Unlock premium for <b>ALL members</b> of this group!\n\n"
            f"  ✅ AI DJ for everyone\n"
            f"  ✅ 320kbps streaming\n"
            f"  ✅ Unlimited queue\n"
            f"  ✅ Your name shown as Sponsor 💎\n\n"
            f"  Choose plan 👇\n\n"
            f"╚{'═'*32}╝",
            reply_markup=buy_kb(),
            parse_mode="HTML"
        )

    # ── Buy callbacks ─────────────────────────────────────────
    @dp.callback_query(F.data.startswith("buy:"))
    async def cb_buy(call: CallbackQuery):
        plan_key = call.data.split(":", 1)[1]
        if plan_key not in ALL_PLANS:
            await call.answer("Unknown plan.", show_alert=True); return
        await call.answer()
        group_chat_id = call.message.chat.id if call.message.chat.type in ("group", "supergroup") else 0
        await send_invoice(bot, call.message.chat.id, call.from_user.id, plan_key, group_chat_id)

    @dp.callback_query(F.data == "premium_info")
    async def cb_prem_info(call: CallbackQuery):
        await call.answer()
        await call.message.edit_text(
            premium_info_text(),
            reply_markup=buy_kb(),
            parse_mode="HTML"
        )

    # ── Payment handlers ──────────────────────────────────────
    @dp.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery):
        await handle_pre_checkout(query)

    @dp.message(F.successful_payment)
    async def successful_payment(message: Message):
        await handle_successful_payment(message, bot)

    # ── /revenue (owner only) ─────────────────────────────────
    @dp.message(Command("revenue"))
    async def revenue_cmd(message: Message):
        if message.from_user.id != owner_id:
            await message.reply("🚫 Owner only!"); return
        total_stars, count = get_revenue_stats()
        stats = get_global_stats()
        await message.reply(
            f"╔══「 💰 <b>REVENUE STATS</b> 」══╗\n\n"
            f"  ⭐ Total Stars earned: <b>{total_stars}</b>\n"
            f"  📦 Total transactions: <b>{count}</b>\n"
            f"  👤 Premium users: <b>{stats['prem_users']}</b>\n"
            f"  👥 Premium groups: <b>{stats['prem_groups']}</b>\n\n"
            f"╚{'═'*32}╝",
            parse_mode="HTML"
        )
