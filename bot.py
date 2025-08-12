# bot.py  — VIP Bot (Pro Lite)
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

# =========================
# FAST, MINIMAL CONFIG
# =========================
def _clean_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith("http"):
        u = "https://" + u.lstrip("/")
    return u.rstrip("/")

BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

BASE_URL = _clean_url(os.getenv("BASE_URL"))
if not BASE_URL:
    raise RuntimeError("BASE_URL missing (e.g., https://your-app.onrender.com)")

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "CHANGE_ME")
ALLOWED_UPDATES = ["message", "callback_query"]

# Brand & copy (polished, consistent)
BRAND = "VIP"
EMO = {
    "spark": "✨",
    "vip": "💎",
    "flash": "⚡",
    "star": "⭐",
    "check": "✅",
    "back": "🔙",
    "help": "💬",
    "play": "🎬",
    "card": "💳",
    "crypto": "🪙",
    "paypal": "📧",
    "link": "🔗",
}

SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Sebvip")
ENV_NAME = os.getenv("ENV_NAME", "production")

# Media Hub links (configure what you actually use)
MEDIA_VIP_PORTAL = _clean_url(os.getenv("MEDIA_VIP_PORTAL", ""))         # e.g., https://yourportal.com
MEDIA_TELEGRAM_GROUP = _clean_url(os.getenv("MEDIA_TELEGRAM_GROUP", "")) # e.g., https://t.me/yourgroup
MEDIA_DISCORD = _clean_url(os.getenv("MEDIA_DISCORD", ""))               # e.g., https://discord.gg/xxx
MEDIA_WEBSITE = _clean_url(os.getenv("MEDIA_WEBSITE", ""))               # e.g., https://example.com
MEDIA_TWITTER = _clean_url(os.getenv("MEDIA_TWITTER", ""))               # optional
MEDIA_INSTAGRAM = _clean_url(os.getenv("MEDIA_INSTAGRAM", ""))           # optional

# Payment (fast + simple). If you want WebApp overlay for Shopify, set SHOPIFY_USE_WEBAPP=1
SHOPIFY_USE_WEBAPP = os.getenv("SHOPIFY_USE_WEBAPP", "0") == "1"
PAYMENT = {
    "shopify": {
        "1_month": _clean_url(os.getenv("PAY_1M", "https://nt9qev-td.myshopify.com/cart/55619895394678:1")),
        "lifetime": _clean_url(os.getenv("PAY_LT", "https://nt9qev-td.myshopify.com/cart/55619898737014:1")),
    },
    "crypto": _clean_url(os.getenv("PAY_CRYPTO", "https://t.me/+318ocdUDrbA4ODk0")),
    "paypal": os.getenv("PAY_PAYPAL", "@Aieducation (PayPal F&F only)"),
}

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0")) or None

# ==============
# LOGGING (fast)
# ==============
logging.basicConfig(
    level=logging.INFO,  # keep prod lean; switch to DEBUG only for debugging
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("vip-bot")

# ==============
# FASTAPI + PTB
# ==============
app = FastAPI()
tg_app: Optional[Application] = None
START = datetime.now(timezone.utc)

# =======
# UI TEXT
# =======
WELCOME = (
    f"{EMO['vip']} *Welcome to {BRAND}!* \n\n"
    f"{EMO['flash']} Instant email access on Apple/Google Pay\n"
    f"{EMO['star']} Don’t see a model? We add them within *24–72h*\n"
)

PLANS_TEXT = (
    "*Choose a plan:*\n"
    "• 1 Month – £10.00\n"
    "• Lifetime – £20.00\n\n"
    "_Apple/Google Pay = instant delivery_"
)

SUPPORT_TEXT = (
    f"{EMO['help']} *Need help?* \n\n"
    f"Contact: {SUPPORT_CONTACT}\n"
    "We usually reply within minutes."
)

# ===========
# MAIN MENUS
# ===========
def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{EMO['spark']} View Plans", callback_data="plans")],
        [InlineKeyboardButton(f"{EMO['play']} Media Hub", callback_data="media")],
        [InlineKeyboardButton(f"{EMO['help']} Support", callback_data="support")],
    ]
    return InlineKeyboardMarkup(rows)

def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{EMO['back']} Back", callback_data="back")]])

def plans_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
        [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
        [InlineKeyboardButton(f"{EMO['back']} Back", callback_data="back")],
    ]
    return InlineKeyboardMarkup(rows)

def pay_menu_shopify() -> InlineKeyboardMarkup:
    # WebApp overlay for a slick in‑Telegram checkout if enabled; otherwise URLs.
    if SHOPIFY_USE_WEBAPP:
        rows = [
            [InlineKeyboardButton("💎 Lifetime (£20)", web_app=WebAppInfo(url=PAYMENT["shopify"]["lifetime"]))],
            [InlineKeyboardButton("⏳ 1 Month (£10)", web_app=WebAppInfo(url=PAYMENT["shopify"]["1_month"]))],
        ]
    else:
        rows = [
            [InlineKeyboardButton("💎 Lifetime (£20)", url=PAYMENT["shopify"]["lifetime"])],
            [InlineKeyboardButton("⏳ 1 Month (£10)", url=PAYMENT["shopify"]["1_month"])],
        ]
    rows += [
        [InlineKeyboardButton(f"{EMO['check']} I've Paid", callback_data="paid")],
        [InlineKeyboardButton(f"{EMO['back']} Back", callback_data="back")],
    ]
    return InlineKeyboardMarkup(rows)

def pay_menu_crypto() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Open Crypto Link", url=PAYMENT["crypto"])],
        [InlineKeyboardButton(f"{EMO['check']} I've Paid", callback_data="paid")],
        [InlineKeyboardButton(f"{EMO['back']} Back", callback_data="back")],
    ])

def pay_menu_paypal() -> InlineKeyboardMarkup:
    # Show PayPal handle in text; button confirms
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{EMO['check']} I've Paid", callback_data="paid")],
        [InlineKeyboardButton(f"{EMO['back']} Back", callback_data="back")],
    ])

def media_menu() -> InlineKeyboardMarkup:
    rows = []
    if MEDIA_VIP_PORTAL:
        rows.append([InlineKeyboardButton(f"{EMO['vip']} VIP Portal", url=MEDIA_VIP_PORTAL)])
    if MEDIA_TELEGRAM_GROUP:
        rows.append([InlineKeyboardButton(f"Telegram", url=MEDIA_TELEGRAM_GROUP)])
    if MEDIA_DISCORD:
        rows.append([InlineKeyboardButton(f"Discord", url=MEDIA_DISCORD)])
    if MEDIA_WEBSITE:
        rows.append([InlineKeyboardButton(f"Website", url=MEDIA_WEBSITE)])
    if MEDIA_TWITTER:
        rows.append([InlineKeyboardButton(f"Twitter/X", url=MEDIA_TWITTER)])
    if MEDIA_INSTAGRAM:
        rows.append([InlineKeyboardButton(f"Instagram", url=MEDIA_INSTAGRAM)])
    rows.append([InlineKeyboardButton(f"{EMO['back']} Back", callback_data="back")])
    return InlineKeyboardMarkup(rows)

# =========================
# STARTUP / SHUTDOWN (FAST)
# =========================
@app.on_event("startup")
async def on_start():
    global tg_app
    log.info("Starting %s…", BRAND)

    tg_app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("help", cmd_help))
    tg_app.add_handler(CommandHandler("plans", cmd_plans))
    tg_app.add_handler(CommandHandler("support", cmd_support))
    tg_app.add_handler(CommandHandler("status", cmd_status))

    # Callback flows (anchor patterns to keep updates tiny)
    tg_app.add_handler(CallbackQueryHandler(cb_show_plans, pattern=r"^plans$"))
    tg_app.add_handler(CallbackQueryHandler(cb_media, pattern=r"^media$"))
    tg_app.add_handler(CallbackQueryHandler(cb_support, pattern=r"^support$"))
    tg_app.add_handler(CallbackQueryHandler(cb_back, pattern=r"^back$"))
    tg_app.add_handler(CallbackQueryHandler(cb_select_plan, pattern=r"^select_"))
    tg_app.add_handler(CallbackQueryHandler(cb_payment, pattern=r"^payment_"))
    tg_app.add_handler(CallbackQueryHandler(cb_paid, pattern=r"^paid$"))

    await tg_app.initialize()

    # Fast webhook set (no preflight, no pings)
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

# ============
# HTTP ROUTES
# ============
@app.get("/")
async def root():
    return {"ok": True, "env": ENV_NAME, "webhook": WEBHOOK_URL}

@app.get("/health")
async def health():
    up = (datetime.now(timezone.utc) - START).total_seconds()
    return {"status": "healthy", "uptime_seconds": int(up)}

@app.head("/webhook")
async def head_wb():
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

# ==================
# COMMAND HANDLERS
# ==================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        WELCOME,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu(),
        disable_web_page_preview=True,
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "*Commands*\n"
        "/start – Main menu\n"
        "/plans – Show plans\n"
        "/support – Contact support\n"
        "/status – Bot status\n"
    )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(PLANS_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=plans_menu())

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(SUPPORT_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    up = int((datetime.now(timezone.utc) - START).total_seconds())
    txt = (
        f"*{BRAND} Status*\n"
        f"Env: `{ENV_NAME}`\n"
        f"Uptime: `{up}s`\n"
        f"Webhook: `{WEBHOOK_URL}`\n"
    )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

# ==================
# CALLBACK HANDLERS
# ==================
async def cb_show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(PLANS_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=plans_menu())

async def cb_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"{EMO['play']} *Media Hub*\n\nOpen your links below."
    await q.edit_message_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=media_menu(), disable_web_page_preview=True)

async def cb_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(SUPPORT_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())

async def cb_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(WELCOME, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu(), disable_web_page_preview=True)

async def cb_select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plan = q.data.split("_", 1)[1]  # 1_month | lifetime

    rows = [
        [InlineKeyboardButton(f"{EMO['card']} Apple/Google Pay (Instant)", callback_data=f"payment_shopify_{plan}")],
        [InlineKeyboardButton(f"{EMO['crypto']} Crypto (30–60m)", callback_data=f"payment_crypto_{plan}")],
        [InlineKeyboardButton(f"{EMO['paypal']} PayPal F&F (30–60m)", callback_data=f"payment_paypal_{plan}")],
        [InlineKeyboardButton(f"{EMO['back']} Back", callback_data="plans")],
    ]
    msg = f"{EMO['star']} *Plan selected:* `{plan.replace('_', ' ').title()}`\nChoose a payment method:"
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(rows))

async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, method, plan = q.data.split("_", 2)

    if method == "shopify":
        msg = (
            f"{EMO['flash']} *Instant Access – Apple/Google Pay*\n\n"
            "Complete checkout and your VIP link is emailed immediately.\n\n"
            f"{EMO['check']} Tap *I've Paid* after completing."
        )
        kb = pay_menu_shopify()
    elif method == "crypto":
        msg = (
            f"{EMO['crypto']} *Crypto Payment*\n"
            f"[Open Payment Link]({PAYMENT['crypto']})\n\n"
            "Verification typically within 30–60 minutes.\n"
            f"{EMO['check']} Tap *I've Paid* after sending."
        )
        kb = pay_menu_crypto()
    else:  # paypal
        msg = (
            f"{EMO['paypal']} *PayPal (Friends & Family only)*\n"
            f"`{PAYMENT['paypal']}`\n\n"
            "Verification typically within 30–60 minutes.\n"
            f"{EMO['check']} Tap *I've Paid* after paying."
        )
        kb = pay_menu_paypal()

    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb, disable_web_page_preview=True)

async def cb_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"{EMO['check']} *Payment Marked as Paid*\n"
                    f"User: @{user.username or user.id}\n"
                    f"Time: {ts}"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    msg = (
        f"{EMO['check']} *Thanks!*\n\n"
        "If instant email didn’t arrive (Apple/Google Pay), reply here with your *email*.\n"
        "For Crypto/PayPal, we’ll verify and send manually."
    )
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())

# ==========================
# GUNICORN START COMMAND
# ==========================
# gunicorn bot:app --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker
