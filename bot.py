# bot.py
import os
import logging
from datetime import datetime
from typing import Optional

import httpx
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

# -----------------------------
# Configuration (ENV first!)
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # <-- set in Render env; rotate your token!
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to your environment.")

BASE_URL = os.getenv("BASE_URL", "https://gpttest-xrfu.onrender.com")  # your public Render URL
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "please-change-me-to-a-long-random-string")
ALLOWED_UPDATES = ["message", "callback_query"]

UPTIME_MONITOR_URL = os.getenv("UPTIME_MONITOR_URL", "https://bot-1-f2wh.onrender.com/uptime")
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Sebvip")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # set to a chat ID string; optional

# Payment Info (static links provided)
PAYMENT_INFO = {
    "shopify": {
        "1_month": "https://nt9qev-td.myshopify.com/cart/55619895394678:1",
        "lifetime": "https://nt9qev-td.myshopify.com/cart/55619898737014:1",
    },
    "crypto": {"link": "https://t.me/+318ocdUDrbA4ODk0"},
    "paypal": "@Aieducation ON PAYPAL F&F only we cant process order if it isnt F&F",
}

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vip-bot")

# -----------------------------
# FastAPI + Telegram App
# -----------------------------
app = FastAPI()
telegram_app: Optional[Application] = None
START_TIME = datetime.now()


@app.on_event("startup")
async def startup_event():
    """Initialize Telegram app, set webhook, and start the bot."""
    global telegram_app
    try:
        logger.info("Starting up…")
        telegram_app = Application.builder().token(BOT_TOKEN).build()

        # Handlers
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CallbackQueryHandler(handle_subscription, pattern=r"^select_"))
        telegram_app.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_"))
        telegram_app.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^paid$"))
        telegram_app.add_handler(CallbackQueryHandler(handle_back, pattern=r"^back$"))
        telegram_app.add_handler(CallbackQueryHandler(handle_support, pattern=r"^support$"))

        await telegram_app.initialize()
        logger.info("Telegram application initialized.")

        # Optional: ping uptime monitor
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(UPTIME_MONITOR_URL)
                logger.info("Uptime monitor status: %s", r.status_code)
        except Exception as e:
            logger.warning("Uptime monitoring failed: %s", e)

        # Configure webhook
        await telegram_app.bot.delete_webhook()
        await telegram_app.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=ALLOWED_UPDATES,
        )
        logger.info("Webhook set to %s", WEBHOOK_URL)

        await telegram_app.start()
        logger.info("Telegram bot started.")
    except Exception as e:
        logger.exception("Error during startup: %s", e)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully stop Telegram app on shutdown."""
    global telegram_app
    if telegram_app:
        try:
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Telegram app stopped.")
        except Exception as e:
            logger.exception("Error during shutdown: %s", e)


# ---------------
# Health Endpoints
# ---------------
@app.get("/")
async def root():
    return {"ok": True, "webhook": WEBHOOK_URL}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.head("/uptime")
async def head_uptime():
    return Response(status_code=200)

@app.get("/uptime")
async def get_uptime():
    current_time = datetime.now()
    uptime_duration = current_time - START_TIME
    return JSONResponse(
        content={
            "status": "online",
            "uptime": str(uptime_duration),
            "start_time": START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


# ---------------
# Webhook endpoint
# ---------------
@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    # Verify Telegram's secret header
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        logger.warning("Invalid webhook secret token.")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    global telegram_app
    if telegram_app is None:
        logger.error("Telegram application not initialized.")
        raise HTTPException(status_code=503, detail="Bot not ready")

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        logger.debug("Received update: %s", data)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Error processing webhook: %s", e)
        return {"status": "error", "message": str(e)}


# -----------------------------
# Telegram Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
        [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
        [InlineKeyboardButton("Support", callback_data="support")],
    ]
    text = (
        "💎 *Welcome to the VIP Bot!*\n\n"
        "💎 *Get access to thousands of creators every month!*\n"
        "⚡ *Instant access to the VIP link sent directly to your email!*\n"
        "⭐ *Don’t see the model you’re looking for? We’ll add them within 24–72 hours!*\n\n"
        "📌 Got questions? VIP link not working? Contact support 🔍👀"
    )
    await update.effective_message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan = query.data.split("_", 1)[1]
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"
    keyboard = [
        [InlineKeyboardButton("💳 Apple Pay/Google Pay 🚀 (Instant Access)", callback_data=f"payment_shopify_{plan}")],
        [InlineKeyboardButton("⚡ Crypto ⏳ (30 - 60 min wait time)", callback_data=f"payment_crypto_{plan}")],
        [InlineKeyboardButton("📧 PayPal 💌 (30 - 60 min wait time)", callback_data=f"payment_paypal_{plan}")],
        [InlineKeyboardButton("💬 Support", callback_data="support")],
        [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
    ]

    message = (
        f"⭐ You have chosen the *{plan_text}* plan.\n\n"
        "💳 *Apple Pay/Google Pay:* 🚀 Instant VIP access (link emailed immediately).\n"
        "⚡ *Crypto:* (30 - 60 min wait time), VIP link sent manually.\n"
        "📧 *PayPal:* (30 - 60 min wait time), VIP link sent manually.\n\n"
        "🎉 Choose your preferred payment method below and get access today!"
    )
    await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, method, plan = query.data.split("_", 2)
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"

    context.user_data["plan_text"] = plan_text
    context.user_data["method"] = method

    if method == "shopify":
        message = (
            "🚀 *Instant Access with Apple Pay/Google Pay!*\n\n"
            "🎁 *Choose Your VIP Plan:*\n"
            "💎 Lifetime Access: *£20.00 GBP* 🎉\n"
            "⏳ 1 Month Access: *£10.00 GBP* 🌟\n\n"
            "🛒 Tap a button to pay securely and get *INSTANT VIP access* delivered to your email! 📧\n\n"
            "✅ After payment, tap *I've Paid* to confirm."
        )
        # URL buttons are simpler & more reliable than WebApp for plain links
        keyboard = [
            [InlineKeyboardButton("💎 Lifetime (£20.00)", url=PAYMENT_INFO["shopify"]["lifetime"])],
            [InlineKeyboardButton("⏳ 1 Month (£10.00)", url=PAYMENT_INFO["shopify"]["1_month"])],
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
        ]
    elif method == "crypto":
        message = (
            "⚡ *Pay Securely with Crypto!*\n\n"
            f"[Crypto Payment Link]({PAYMENT_INFO['crypto']['link']})\n\n"
            "💎 *Choose Your Plan:*\n"
            "⏳ 1 Month Access: *$13.00 USD* 🌟\n"
            "💎 Lifetime Access: *$27 USD* 🎉\n\n"
            "✅ Once you've sent the payment, tap *I've Paid* to confirm."
        )
        keyboard = [
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
        ]
    elif method == "paypal":
        message = (
            "💸 *Easy Payment with PayPal!*\n\n"
            f"`{PAYMENT_INFO['paypal']}`\n\n"
            "💎 *Choose Your Plan:*\n"
            "⏳ 1 Month Access: *£10.00 GBP* 🌟\n"
            "💎 Lifetime Access: *£20.00 GBP* 🎉\n\n"
            "✅ Once payment is complete, tap *I've Paid* to confirm."
        )
        keyboard = [
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
        ]
    else:
        message = "Unknown payment method."
        keyboard = [[InlineKeyboardButton("🔙 Go Back", callback_data="back")]]

    await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_text = context.user_data.get("plan_text", "N/A")
    method = context.user_data.get("method", "N/A")
    username = query.from_user.username or "No Username"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Notify admin if configured
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=(
                    "📝 *Payment Notification*\n"
                    f"👤 *User:* @{username}\n"
                    f"📋 *Plan:* {plan_text}\n"
                    f"💳 *Method:* {method.capitalize()}\n"
                    f"🕒 *Time:* {current_time}"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Failed to notify admin: %s", e)

    await query.edit_message_text(
        text=(
            "✅ *Payment Received! Thank You!* 🎉\n\n"
            "📸 Please send a *screenshot* or *transaction ID* to our support team for verification.\n"
            f"👉 {SUPPORT_CONTACT}\n\n"
            "⚡ *Important Notice:*\n"
            "🔗 If you paid via Apple Pay/Google Pay, check your email inbox for the VIP link.\n"
            "🔗 If you paid via PayPal or Crypto, your VIP link will be sent manually."
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "💬 *Need Assistance? We're Here to Help!*\n\n"
            "🕒 *Working Hours:* 8:00 AM - 12:00 AM BST\n"
            "📨 For support, contact us directly at:\n"
            f"👉 {SUPPORT_CONTACT}\n\n"
            "⚡ Our team is ready to assist you as quickly as possible.\n"
            "Thank you for choosing VIP Bot! 💎"
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Go Back", callback_data="back")]]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Re-render the start menu safely (works for both messages and callbacks)
    if update.callback_query:
        await update.callback_query.answer()
    await start(update, context)
