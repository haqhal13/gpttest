# bot.py
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, Response
from fastapi.responses import JSONResponse

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# Config + URL sanitizing
# =========================
def clean_base_url(url: str) -> str:
    """Force https, trim whitespace, drop trailing slash."""
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    return url.rstrip("/")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it in Render → Environment.")

BASE_URL = clean_base_url(os.getenv("BASE_URL", ""))
if not BASE_URL or "your-service.onrender.com" in BASE_URL:
    raise RuntimeError(
        "BASE_URL is missing or still the placeholder. "
        "Set BASE_URL to your public Render URL (e.g., https://your-app.onrender.com)."
    )

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "CHANGE_ME_TO_A_LONG_RANDOM_STRING")
ALLOWED_UPDATES = ["message", "callback_query"]

SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Sebvip")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID", "")
ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_ENV) if ADMIN_CHAT_ID_ENV.isdigit() else None

# Optional settings
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "0") == "1"
WORKING_HOURS = os.getenv("WORKING_HOURS", "08:00-00:00")
TZ_OFFSET = int(os.getenv("TZ_OFFSET_MINUTES", "0"))
UPTIME_MONITOR_URL = os.getenv("UPTIME_MONITOR_URL", "")
ENV_NAME = os.getenv("ENV_NAME", "production")

# Payment links
PAYMENT_INFO = {
    "shopify": {
        "1_month": "https://nt9qev-td.myshopify.com/cart/55619895394678:1",
        "lifetime": "https://nt9qev-td.myshopify.com/cart/55619898737014:1",
    },
    "crypto": {"link": "https://t.me/+318ocdUDrbA4ODk0"},
    "paypal": "@Aieducation ON PAYPAL F&F only; we can’t process if not F&F",
}

# ==========
# Logging
# ==========
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vip-bot")

logger.info("Loaded BASE_URL = %r", BASE_URL)
logger.info("Webhook will be set to %r", WEBHOOK_URL)

# Preflight reachability check (best-effort)
try:
    with httpx.Client(timeout=5.0, verify=True) as client:
        r = client.get(BASE_URL)
        logger.info("Preflight check to BASE_URL returned: %s", r.status_code)
except Exception as e:
    logger.warning("Preflight check failed: %s", e)

# ===============================
# FastAPI + Telegram integration
# ===============================
app = FastAPI()
telegram_app: Optional[Application] = None
START_TIME = datetime.now(timezone.utc)

# Simple in-memory rate limit + user state
RATE_LIMIT_BUCKET: Dict[int, float] = {}
USER_STATE: Dict[int, Dict[str, bool]] = {}

def now_local() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=TZ_OFFSET)

def human_uptime() -> str:
    delta = datetime.now(timezone.utc) - START_TIME
    d = delta.days
    s = delta.seconds
    h = s // 3600
    m = (s % 3600) // 60
    return f"{d}d {h}h {m}m"

def ratelimited(user_id: int, seconds: int = 2) -> bool:
    last = RATE_LIMIT_BUCKET.get(user_id, 0.0)
    now = datetime.now().timestamp()
    if now - last < seconds:
        return True
    RATE_LIMIT_BUCKET[user_id] = now
    return False

def banner() -> str:
    return "🛠 *Maintenance Mode:* Some features may be limited.\n\n" if MAINTENANCE_MODE else ""

# --------------
# Startup/Stop
# --------------
@app.on_event("startup")
async def startup_event():
    global telegram_app
    logger.info("Starting VIP Bot (%s)…", ENV_NAME)

    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_cmd))
    telegram_app.add_handler(CommandHandler("plans", plans_cmd))
    telegram_app.add_handler(CommandHandler("support", support_cmd))
    telegram_app.add_handler(CommandHandler("terms", terms_cmd))
    telegram_app.add_handler(CommandHandler("status", status_cmd))
    telegram_app.add_handler(CommandHandler("broadcast", admin_broadcast))

    # Callback flows
    telegram_app.add_handler(CallbackQueryHandler(handle_subscription, pattern=r"^select_"))
    telegram_app.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_"))
    telegram_app.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^paid$"))
    telegram_app.add_handler(CallbackQueryHandler(handle_back, pattern=r"^back$"))
    telegram_app.add_handler(CallbackQueryHandler(handle_support_cb, pattern=r"^support$"))
    telegram_app.add_handler(CallbackQueryHandler(show_plans_cb, pattern=r"^plans$"))

    # Payment proof handlers
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_possible_proof))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_fallback))

    # Global error handler
    telegram_app.add_error_handler(on_error)

    await telegram_app.initialize()

    # Optional: ping uptime monitor
    if UPTIME_MONITOR_URL:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(UPTIME_MONITOR_URL)
                logger.info("Uptime monitor responded: %s", r.status_code)
        except Exception as e:
            logger.warning("Uptime monitor ping failed: %s", e)

    # Webhook
    await telegram_app.bot.delete_webhook()
    await telegram_app.bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=ALLOWED_UPDATES,
    )
    logger.info("Webhook set: %s", WEBHOOK_URL)

    await telegram_app.start()
    logger.info("Telegram bot started.")

@app.on_event("shutdown")
async def shutdown_event():
    global telegram_app
    if telegram_app:
        try:
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Telegram app stopped.")
        except Exception as e:
            logger.exception("Shutdown error: %s", e)

# --------------
# Health/Status
# --------------
@app.get("/")
async def root():
    return {"ok": True, "env": ENV_NAME, "webhook": WEBHOOK_URL}

@app.get("/health")
async def health():
    return {"status": "healthy", "uptime": human_uptime()}

@app.get("/status")
async def http_status():
    return {
        "env": ENV_NAME,
        "maintenance": MAINTENANCE_MODE,
        "uptime": human_uptime(),
        "start_time_utc": START_TIME.isoformat(),
        "webhook": WEBHOOK_URL,
        "allowed_updates": ALLOWED_UPDATES,
    }

@app.head("/uptime")
async def head_uptime():
    return Response(status_code=200)

@app.get("/uptime")
async def get_uptime():
    return JSONResponse(
        content={
            "status": "online",
            "uptime": human_uptime(),
            "start_time_utc": START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

# --------------
# Webhook entry
# --------------
@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        logger.warning("Invalid webhook secret.")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    global telegram_app
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Bot not ready")

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Error processing webhook: %s", e)
        return {"status": "error", "message": str(e)}

# ==================
# Telegram Handlers
# ==================
MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("✨ View Plans", callback_data="plans")],
    [InlineKeyboardButton("💬 Support", callback_data="support")],
])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if ratelimited(user.id, seconds=1):
        return
    text = (
        f"{banner()}"
        "💎 *Welcome to VIP Bot!*\n\n"
        "• *Instant* email delivery on Apple Pay / Google Pay\n"
        "• Don’t see a model? We add them within *24–72h*\n"
        f"• Support hours: `{WORKING_HOURS}`\n"
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_MENU
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ratelimited(update.effective_user.id):
        return
    text = (
        "*Commands*\n"
        "/start – Main menu\n"
        "/plans – Show plans\n"
        "/support – Contact support\n"
        "/terms – Terms & notes\n"
        "/status – Bot status\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def plans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ratelimited(update.effective_user.id):
        return
    await show_plans(update.effective_message, context)

async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ratelimited(update.effective_user.id):
        return
    await render_support(update.effective_message, context)

async def terms_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ratelimited(update.effective_user.id):
        return
    text = (
        "*Terms & Notes*\n"
        "• Access is for personal use only; redistribution may lead to a ban\n"
        "• Refunds assessed case‑by‑case if access was not delivered\n"
        "• By purchasing, you accept these terms\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ratelimited(update.effective_user.id, seconds=3):
        return
    text = (
        f"*Status*: Online\n"
        f"*Env*: `{ENV_NAME}`\n"
        f"*Uptime*: `{human_uptime()}`\n"
        f"*Maintenance*: `{MAINTENANCE_MODE}`\n"
        f"*Webhook*: `{WEBHOOK_URL}`\n"
        f"*Server Time*: `{now_local().strftime('%Y-%m-%d %H:%M:%S')}`\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# --- Inline callbacks
async def show_plans_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await show_plans(update.callback_query, context)

async def show_plans(target, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
        [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ]
    msg = (
        "*Choose a plan:*\n"
        "• 1 Month – £10.00\n"
        "• Lifetime – £20.00\n\n"
        "_Tip: Apple/Google Pay = instant email delivery_"
    )
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await target.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plan = q.data.split("_", 1)[1]
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"

    keyboard = [
        [InlineKeyboardButton("💳 Apple/Google Pay (Instant)", callback_data=f"payment_shopify_{plan}")],
        [InlineKeyboardButton("⚡ Crypto (30–60m manual)", callback_data=f"payment_crypto_{plan}")],
        [InlineKeyboardButton("📧 PayPal F&F (30–60m)", callback_data=f"payment_paypal_{plan}")],
        [InlineKeyboardButton("💬 Support", callback_data="support")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ]
    msg = f"⭐ You chose *{plan_text}*.\n\nPick a payment method below:"
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, method, plan = q.data.split("_", 2)
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"
    context.user_data["plan_text"] = plan_text
    context.user_data["method"] = method

    if method == "shopify":
        msg = (
            "🚀 *Instant Access with Apple/Google Pay*\n\n"
            "Tap a button to pay securely. Your VIP link is emailed instantly.\n\n"
            "✅ After paying, tap *I've Paid* and (optionally) send a screenshot."
        )
        kb = [
            [InlineKeyboardButton("💎 Lifetime (£20)", url=PAYMENT_INFO["shopify"]["lifetime"])],
            [InlineKeyboardButton("⏳ 1 Month (£10)", url=PAYMENT_INFO["shopify"]["1_month"])],
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
    elif method == "crypto":
        msg = (
            "⚡ *Pay with Crypto*\n"
            f"[Open Payment Link]({PAYMENT_INFO['crypto']['link']})\n\n"
            "Manual verification ~30–60m.\n"
            "✅ After paying, tap *I've Paid* and send a screenshot / txn ID."
        )
        kb = [
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
    elif method == "paypal":
        msg = (
            "💸 *PayPal (Friends & Family only)*\n"
            f"`{PAYMENT_INFO['paypal']}`\n\n"
            "Manual verification ~30–60m.\n"
            "✅ After paying, tap *I've Paid* and send a screenshot / txn ID."
        )
        kb = [
            [InlineKeyboardButton("✅ I've Paid", callback_data="paid")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
    else:
        msg = "Unknown method."
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]

    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    plan_text = context.user_data.get("plan_text", "N/A")
    method = context.user_data.get("method", "N/A")
    ts = now_local().strftime("%Y-%m-%d %H:%M:%S")

    st = USER_STATE.setdefault(user.id, {})
    st["awaiting_proof"] = True

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "📝 *Payment Confirmation Clicked*\n"
                    f"👤 *User:* @{user.username or user.id}\n"
                    f"📋 *Plan:* {plan_text}\n"
                    f"💳 *Method:* {method}\n"
                    f"🕒 *Time:* {ts}"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Admin notify failed: %s", e)

    await q.edit_message_text(
        text=(
            "✅ *Thanks!*\n\n"
            "If you didn’t get instant email access yet, please *send a screenshot* or *transaction ID* here now.\n"
            f"Or message support: {SUPPORT_CONTACT}\n\n"
            "_This helps us verify quickly._"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )

async def handle_support_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await render_support(update.callback_query, context)

async def render_support(target, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💬 *Need Assistance?*\n\n"
        f"• Working Hours: `{WORKING_HOURS}`\n"
        f"• Contact support: {SUPPORT_CONTACT}\n"
        "We usually reply within minutes."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]])
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await target.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    await start(update, context)

# --- Proof capture (photos/docs/text) ---
async def handle_possible_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = USER_STATE.get(user.id, {})
    if not st.get("awaiting_proof"):
        return

    caption = (update.effective_message.caption or "").strip()
    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    ts = now_local().strftime("%Y-%m-%d %H:%M:%S")

    if ADMIN_CHAT_ID:
        try:
            fwd = await update.effective_message.forward(chat_id=ADMIN_CHAT_ID)
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "🧾 *Payment Proof Received*\n"
                    f"👤 {username}\n"
                    f"🕒 {ts}\n"
                    f"🗒 Notes: {caption or '—'}"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=fwd.message_id,
            )
        except Exception as e:
            logger.warning("Forward to admin failed: %s", e)

    st["awaiting_proof"] = False
    await update.effective_message.reply_text(
        "🙏 Thanks! Our team will verify and send your VIP link shortly."
    )

async def handle_text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = USER_STATE.get(user.id, {})
    if st.get("awaiting_proof"):
        await handle_possible_proof(update, context)
        return
    await update.effective_message.reply_text(
        "Use /plans to see options or /support to contact us. 👍"
    )

# --- Admin broadcast (demo stub) ---
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_CHAT_ID is None or update.effective_user.id != ADMIN_CHAT_ID:
        return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.effective_message.reply_text("Usage: /broadcast Your message")
        return
    # Here you would iterate over your own user store and send messages.
    await update.effective_message.reply_text("Broadcast queued (demo).")

# --- Global error handler ---
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Update caused error: %s", context.error)
    try:
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ *Error:*\n`{repr(context.error)}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception:
        pass
