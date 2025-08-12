# bot.py — VIP Bot (your text + mini-app links, hardened)
import os
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, Response
from fastapi.responses import JSONResponse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# =====================
# Config (env overrides)
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7709257840:AAHHDafzkhvwMcHMfQuNd1XJTFlTAAd14As")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://bot-1-f2wh.onrender.com/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "CHANGE_ME_TO_A_LONG_RANDOM_STRING")
UPTIME_MONITOR_URL = os.getenv("UPTIME_MONITOR_URL", "https://bot-1-f2wh.onrender.com/uptime")
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Sebvip")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID", "7914196017")
ADMIN_CHAT_ID: Optional[int] = int(ADMIN_CHAT_ID_ENV) if ADMIN_CHAT_ID_ENV.isdigit() else None

# Payment Information (kept as you wrote; links open via Mini Apps)
PAYMENT_INFO = {
    "shopify": {
        "1_month": os.getenv("PAY_1M", "https://nt9qev-td.myshopify.com/cart/55619895394678:1"),
        "lifetime": os.getenv("PAY_LT", "https://nt9qev-td.myshopify.com/cart/55619898737014:1"),
    },
    "crypto": {"link": os.getenv("PAY_CRYPTO", "https://t.me/+318ocdUDrbA4ODk0")},
    "paypal": os.getenv(
        "PAY_PAYPAL",
        "@Aieducation ON PAYPAL F&F only we cant process order if it isnt F&F",
    ),
}

# =====================
# Logging
# =====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vip-bot")

# =====================
# FastAPI + Telegram
# =====================
app = FastAPI()
telegram_app: Optional[Application] = None
START_TIME = datetime.now()


@app.on_event("startup")
async def startup_event():
    """Initialize Telegram app, set webhook, and start the bot."""
    global telegram_app
    try:
        if not BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is missing")

        telegram_app = Application.builder().token(BOT_TOKEN).build()

        # Handlers (patterns anchored for safety)
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CallbackQueryHandler(handle_subscription, pattern=r"^select_"))
        telegram_app.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_"))
        telegram_app.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^paid$"))
        telegram_app.add_handler(CallbackQueryHandler(handle_back, pattern=r"^back$"))
        telegram_app.add_handler(CallbackQueryHandler(handle_support, pattern=r"^support$"))

        await telegram_app.initialize()
        logger.info("Telegram App initialized.")

        # Optional: uptime monitor ping
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(UPTIME_MONITOR_URL)
                logger.info("Uptime monitor status: %s", r.status_code)
        except Exception as e:
            logger.warning("Uptime monitor ping failed: %s", e)

        # Webhook (with secret + drop old updates)
        await telegram_app.bot.delete_webhook()
        await telegram_app.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        logger.info("Webhook set to %s", WEBHOOK_URL)

        await telegram_app.start()
        logger.info("Telegram bot started.")
    except Exception as e:
        logger.exception("Error during startup: %s", e)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    global telegram_app
    if telegram_app:
        try:
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Telegram app stopped.")
        except Exception as e:
            logger.exception("Error during shutdown: %s", e)


# ==============
# Webhook route
# ==============
@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    # Verify Telegram secret header
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    global telegram_app
    try:
        update = Update.de_json(await request.json(), telegram_app.bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Error processing webhook: %s", e)
        return {"status": "error", "message": str(e)}


# ==============
# Health routes
# ==============
@app.get("/")
async def root():
    return {"ok": True, "webhook": WEBHOOK_URL}

@app.get("/uptime")
async def get_uptime():
    uptime_duration = datetime.now() - START_TIME
    return JSONResponse(
        content={
            "status": "online",
            "uptime": str(uptime_duration),
            "start_time": START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

@app.head("/uptime")
async def head_uptime():
    return Response(status_code=200)


# =====================
# Telegram Handlers
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
        [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
        [InlineKeyboardButton("Support", callback_data="support")],
    ]
    # Use effective_message so it works from both /start command and "Back" callback
    await update.effective_message.reply_text(
        "💎 **Welcome to the VIP Bot!**\n\n"
        "💎 *Get access to thousands of creators every month!*\n"
        "⚡ *Instant access to the VIP link sent directly to your email!*\n"
        "⭐ *Don’t see the model you’re looking for? We’ll add them within 24–72 hours!*\n\n"
        "📌 Got questions ? VIP link not working ? Contact support 🔍👀",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan = query.data.split("_", 1)[1]  # "1_month" | "lifetime"
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"
    keyboard = [
        [InlineKeyboardButton("💳 Apple Pay/Google Pay 🚀 (Instant Access)", callback_data=f"payment_shopify_{plan}")],
        [InlineKeyboardButton("⚡ Crypto ⏳ (30 - 60 min wait time)", callback_data=f"payment_crypto_{plan}")],
        [InlineKeyboardButton("📧 PayPal 💌 (30 - 60 min wait time)", callback_data=f"payment_paypal_{plan}")],
        [InlineKeyboardButton("💬 Support", callback_data="support")],
        [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
    ]

    message = (
        f"⭐ You have chosen the **{plan_text}** plan.\n\n"
        "💳 **Apple Pay/Google Pay:** 🚀 Instant VIP access (link emailed immediately).\n"
        "⚡ **Crypto:** (30 - 60 min wait time), VIP link sent manually.\n"
        "📧 **PayPal:**(30 - 60 min wait time), VIP link sent manually.\n\n"
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
            "🚀 **Instant Access with Apple Pay/Google Pay!**\n\n"
            "🎁 **Choose Your VIP Plan:**\n"
            "💎 Lifetime Access: **£20.00 GBP** 🎉\n"
            "⏳ 1 Month Access: **£10.00 GBP** 🌟\n\n"
            "🛒 Click below to pay securely and get **INSTANT VIP access** delivered to your email! 📧\n\n"
            "✅ After payment, click 'I've Paid' to confirm."
        )
        keyboard = [
            [InlineKeyboardButton("💎 Lifetime (£20.00)", web_app=WebAppInfo(url=PAYMENT_INFO["shopify"]["lifetime"]))],
            [InlineKeyboardButton("⏳ 1 Month (£10.00)", web_app=WebAppInfo(url=PAYMENT_INFO["shopify"]["1_month"]))],
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
        ]
    elif method == "crypto":
        message = (
            "⚡ **Pay Securely with Crypto!**\n\n"
            "🔗 Open the crypto payment mini‑app below inside Telegram.\n\n"
            "💎 **Choose Your Plan:**\n"
            "⏳ 1 Month Access: **$13.00 USD** 🌟\n"
            "💎 Lifetime Access: **$27 USD** 🎉\n\n"
            "✅ Once you've sent the payment, click 'I've Paid' to confirm."
        )
        keyboard = [
            [InlineKeyboardButton("Open Crypto Link", web_app=WebAppInfo(url=PAYMENT_INFO["crypto"]["link"]))],
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Go Back", callback_data="back")],
        ]
    elif method == "paypal":
        message = (
            "💸 **Easy Payment with PayPal!**\n\n"
            f"`{PAYMENT_INFO['paypal']}`\n\n"
            "💎 **Choose Your Plan:**\n"
            "⏳ 1 Month Access: **£10.00 GBP** 🌟\n"
            "💎 Lifetime Access: **£20.00 GBP** 🎉\n\n"
            "✅ Once payment is complete, click 'I've Paid' to confirm."
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

    # Notify admin (if configured)
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "📝 **Payment Notification**\n"
                    f"👤 **User:** @{username}\n"
                    f"📋 **Plan:** {plan_text}\n"
                    f"💳 **Method:** {method.capitalize()}\n"
                    f"🕒 **Time:** {current_time}"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Admin notification failed: %s", e)

    await query.edit_message_text(
        text=(
            "✅ **Payment Received! Thank You!** 🎉\n\n"
            "📸 Please send a **screenshot** or **transaction ID** to our support team for verification.\n"
            f"👉 {SUPPORT_CONTACT}\n\n"
            "⚡ **Important Notice:**\n"
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
            "💬 **Need Assistance? We're Here to Help!**\n\n"
            "🕒 **Working Hours:** 8:00 AM - 12:00 AM BST\n"
            "📨 For support, contact us directly at:\n"
            f"👉 {SUPPORT_CONTACT}\n\n"
            "⚡ Our team is ready to assist you as quickly as possible. "
            "Thank you for choosing VIP Bot! 💎"
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Go Back", callback_data="back")]]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Works whether it's a command or a callback
    if update.callback_query:
        await update.callback_query.answer()
    await start(update, context)
