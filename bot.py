# bot.py — VIP Bot (your copy kept, links as Mini Apps)
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException, Response
from fastapi.responses import JSONResponse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==========
# Config
# ==========
def _clean_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith("http"):
        u = "https://" + u.lstrip("/")
    return u.rstrip("/")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

BASE_URL = _clean_url(os.getenv("BASE_URL"))
if not BASE_URL:
    raise RuntimeError("BASE_URL missing")

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "CHANGE_ME")
ALLOWED_UPDATES = ["message", "callback_query"]

# Your support/admin
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Sebvip")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0")) or None
ENV_NAME = os.getenv("ENV_NAME", "production")

# Payment links (we’ll open as Telegram WebApps)
PAYMENT_INFO = {
    "shopify": {
        "1_month": _clean_url(os.getenv("PAY_1M", "https://nt9qev-td.myshopify.com/cart/55619895394678:1")),
        "lifetime": _clean_url(os.getenv("PAY_LT", "https://nt9qev-td.myshopify.com/cart/55619898737014:1")),
    },
    "crypto": {"link": _clean_url(os.getenv("PAY_CRYPTO", "https://t.me/+318ocdUDrbA4ODk0"))},
    "paypal": os.getenv("PAY_PAYPAL", "@Aieducation ON PAYPAL F&F only we cant process order if it isnt F&F"),
}

# Optional Media Apps hub (mini-app buttons)
MEDIA_LINKS = [
    ("VIP Portal", _clean_url(os.getenv("MEDIA_VIP_PORTAL", ""))),
    ("Telegram Hub", _clean_url(os.getenv("MEDIA_TELEGRAM_HUB", ""))),
    ("Discord", _clean_url(os.getenv("MEDIA_DISCORD", ""))),
    ("Website", _clean_url(os.getenv("MEDIA_WEBSITE", ""))),
]
HAS_MEDIA = any(url for _, url in MEDIA_LINKS)

# ==========
# Logging
# ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vip-bot")

# ==========
# App
# ==========
app = FastAPI()
tg_app: Optional[Application] = None
START = datetime.now(timezone.utc)

# ==========
# UI (YOUR TEXTS)
# ==========
WELCOME_TEXT = (
    "💎 **Welcome to the VIP Bot!**\n\n"
    "💎 *Get access to thousands of creators every month!*\n"
    "⚡ *Instant access to the VIP link sent directly to your email!*\n"
    "⭐ *Don’t see the model you’re looking for? We’ll add them within 24–72 hours!*\n\n"
    "📌 Got questions ? VIP link not working ? Contact support 🔍👀"
)

SELECT_PLAN_TEXT = lambda plan_text: (
    f"⭐ You have chosen the **{plan_text}** plan.\n\n"
    "💳 **Apple Pay/Google Pay:** 🚀 Instant VIP access (link emailed immediately).\n"
    "⚡ **Crypto:** (30 - 60 min wait time), VIP link sent manually.\n"
    "📧 **PayPal:**(30 - 60 min wait time), VIP link sent manually.\n\n"
    "🎉 Choose your preferred payment method below and get access today!"
)

SHOPIFY_TEXT = (
    "🚀 **Instant Access with Apple Pay/Google Pay!**\n\n"
    "🎁 **Choose Your VIP Plan:**\n"
    "💎 Lifetime Access: **£20.00 GBP** 🎉\n"
    "⏳ 1 Month Access: **£10.00 GBP** 🌟\n\n"
    "🛒 Click below to pay securely and get **INSTANT VIP access** delivered to your email! 📧\n\n"
    "✅ After payment, click 'I've Paid' to confirm."
)

CRYPTO_TEXT = (
    "⚡ **Pay Securely with Crypto!**\n\n"
    f"[Crypto Payment Link]({PAYMENT_INFO['crypto']['link']})\n\n"
    "💎 **Choose Your Plan:**\n"
    "⏳ 1 Month Access: **$13.00 USD** 🌟\n"
    "💎 Lifetime Access: **$27 USD** 🎉\n\n"
    "✅ Once you've sent the payment, click 'I've Paid' to confirm."
)

PAYPAL_TEXT = (
    "💸 **Easy Payment with PayPal!**\n\n"
    f"`{PAYMENT_INFO['paypal']}`\n\n"
    "💎 **Choose Your Plan:**\n"
    "⏳ 1 Month Access: **£10.00 GBP** 🌟\n"
    "💎 Lifetime Access: **£20.00 GBP** 🎉\n\n"
    "✅ Once payment is complete, click 'I've Paid' to confirm."
)

SUPPORT_PAGE_TEXT = (
    "💬 **Need Assistance? We're Here to Help!**\n\n"
    "🕒 **Working Hours:** 8:00 AM - 12:00 AM BST\n"
    f"📨 For support, contact us directly at:\n"
    f"👉 {SUPPORT_CONTACT}\n\n"
    "⚡ Our team is ready to assist you as quickly as possible. "
    "Thank you for choosing VIP Bot! 💎"
)

PAID_THANKS_TEXT = (
    "✅ **Payment Received! Thank You!** 🎉\n\n"
    "📸 Please send a **screenshot** or **transaction ID** to our support team for verification.\n"
    f"👉 {SUPPORT_CONTACT}\n\n"
    "⚡ **Important Notice:**\n"
    "🔗 If you paid via Apple Pay/Google Pay, check your email inbox for the VIP link.\n"
    "🔗 If you paid via PayPal or Crypto, your VIP link will be sent manually."
)

# ==========
# Keyboards
# ==========
def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
        [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
        [InlineKeyboardButton("Support", callback_data="support")],
    ]
    if HAS_MEDIA:
        rows.insert(2, [InlineKeyboardButton("Media Apps", callback_data="media")])
    return InlineKeyboardMarkup(rows)

def payment_selector(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Apple Pay/Google Pay 🚀 (Instant Access)", callback_data=f"payment_shopify_{plan}")],
        [InlineKeyboardButton("⚡ Crypto ⏳ (30 - 60 min wait time)", callback_data=f"payment_crypto_{plan}")],
        [InlineKeyboardButton("📧 PayPal 💌 (30 - 60 min wait time)", callback_data=f"payment_paypal_{plan}")],
        [InlineKeyboardButton("💬 Support", callback_data="support")],
        [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
    ])

def shopify_menu_webapp() -> InlineKeyboardMarkup:
    # Mini‑app buttons for both plans
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Lifetime (£20.00)", web_app=WebAppInfo(url=PAYMENT_INFO["shopify"]["lifetime"]))],
        [InlineKeyboardButton("⏳ 1 Month (£10.00)", web_app=WebAppInfo(url=PAYMENT_INFO["shopify"]["1_month"]))],
        [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
        [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
    ])

def crypto_menu_webapp() -> InlineKeyboardMarkup:
    # Open crypto link in Telegram webview as a mini‑app
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Open Crypto Link", web_app=WebAppInfo(url=PAYMENT_INFO["crypto"]["link"]))],
        [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
        [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
    ])

def paypal_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
        [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
    ])

def media_menu_webapps() -> InlineKeyboardMarkup:
    rows = []
    for label, url in MEDIA_LINKS:
        if url:
            rows.append([InlineKeyboardButton(label, web_app=WebAppInfo(url=url))])
    rows.append([InlineKeyboardButton("🔙 Go Back", callback_data="back")])
    return InlineKeyboardMarkup(rows)

# ==========
# Startup / Shutdown
# ==========
@app.on_event("startup")
async def on_start():
    global tg_app
    log.info("Starting bot…")

    tg_app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("support", support_cmd))
    tg_app.add_handler(CommandHandler("status", status_cmd))

    # Callbacks
    tg_app.add_handler(CallbackQueryHandler(handle_subscription, pattern=r"^select_"))
    tg_app.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_"))
    tg_app.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^paid$"))
    tg_app.add_handler(CallbackQueryHandler(handle_back, pattern=r"^back$"))
    tg_app.add_handler(CallbackQueryHandler(handle_support, pattern=r"^support$"))
    tg_app.add_handler(CallbackQueryHandler(handle_media, pattern=r"^media$"))

    await tg_app.initialize()

    await tg_app.bot.delete_webhook()
    await tg_app.bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=ALLOWED_UPDATES,
    )
    log.info("Webhook set to %s", WEBHOOK_URL)

    await tg_app.start()
    log.info("Bot online.")

@app.on_event("shutdown")
async def on_stop():
    if tg_app:
        await tg_app.stop()
        await tg_app.shutdown()
        log.info("Bot stopped.")

# ==========
# HTTP
# ==========
@app.get("/")
async def root():
    return {"ok": True, "env": ENV_NAME, "webhook": WEBHOOK_URL}

@app.head(WEBHOOK_PATH)
async def head_webhook():
    return Response(status_code=200)

@app.post(WEBHOOK_PATH)
async def webhook(request: Request, x_telegram_bot_api_secret_token: Optional[str] = Header(None)):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")
    if tg_app is None:
        raise HTTPException(status_code=503, detail="Bot not ready")

    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"status": "ok"}

# ==========
# Handlers (YOUR TEXTS)
# ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu(),
    )

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plan = q.data.split("_", 1)[1]  # 1_month | lifetime
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"

    await q.edit_message_text(
        SELECT_PLAN_TEXT(plan_text),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=payment_selector(plan),
    )

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, method, plan = q.data.split("_", 2)
    context.user_data["plan_text"] = "LIFETIME" if plan == "lifetime" else "1 MONTH"
    context.user_data["method"] = method

    if method == "shopify":
        await q.edit_message_text(SHOPIFY_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=shopify_menu_webapp())
    elif method == "crypto":
        await q.edit_message_text(CRYPTO_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=crypto_menu_webapp(), disable_web_page_preview=True)
    elif method == "paypal":
        await q.edit_message_text(PAYPAL_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=paypal_menu())
    else:
        await q.edit_message_text("Unknown payment method.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Go Back", callback_data="back")]]))

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    plan_text = context.user_data.get("plan_text", "N/A")
    method = context.user_data.get("method", "N/A")
    username = q.from_user.username or "No Username"
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "📝 *Payment Notification*\n"
                    f"👤 *User:* @{username}\n"
                    f"📋 *Plan:* {plan_text}\n"
                    f"💳 *Method:* {method.capitalize()}\n"
                    f"🕒 *Time:* {current_time}"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    await q.edit_message_text(PAID_THANKS_TEXT, parse_mode=ParseMode.MARKDOWN)

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        SUPPORT_PAGE_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Go Back", callback_data="back")]]),
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not HAS_MEDIA:
        await q.edit_message_text("No media apps configured.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Go Back", callback_data="back")]]))
        return
    await q.edit_message_text(
        "🎬 **Media Apps**\n\nOpen inside Telegram.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=media_menu_webapps(),
        disable_web_page_preview=True,
    )

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    await start(update, context)

# Simple command mirrors
async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(SUPPORT_PAGE_TEXT, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    up = int((datetime.now(timezone.utc) - START).total_seconds())
    await update.effective_message.reply_text(
        f"*Status*: Online\n*Env*: `{ENV_NAME}`\n*Uptime*: `{up}s`\n*Webhook*: `{WEBHOOK_URL}`",
        parse_mode=ParseMode.MARKDOWN,
    )
