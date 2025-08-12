# bot.py — VIP Bot (your copy + Mini Apps, multilingual, reminders, admin, coupons, referrals)
# Ready for Render. Paste & deploy with:
#   gunicorn bot:app --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, Response
from fastapi.responses import JSONResponse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

# =====================
# Config (env overrides)
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7709257840:AAHHDafzkhvwMcHMfQuNd1XJTFlTAAd14As")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://gpttest-xrfu.onrender.com/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "CHANGE_ME_TO_A_LONG_RANDOM_STRING")
UPTIME_MONITOR_URL = os.getenv("UPTIME_MONITOR_URL", "https://gpttest-xrfu.onrender.com/uptime")

SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Sebvip")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID", "7914196017")
ADMIN_CHAT_ID: Optional[int] = int(ADMIN_CHAT_ID_ENV) if ADMIN_CHAT_ID_ENV.isdigit() else None
ENV_NAME = os.getenv("ENV_NAME", "production")

# Reminder cadence (minutes) — 1h and 24h only (as requested)
REMINDERS_MINUTES = os.getenv("REMINDERS", "60,1440")  # 60 min, 1440 min
REMINDER_STEPS = [int(x) for x in REMINDERS_MINUTES.split(",") if x.strip().isdigit()]

# Coupons (format: "SPRING10=10,VIP5=5") — optional
COUPONS_RAW = os.getenv("COUPONS", "")
COUPONS: Dict[str, int] = {}
for part in COUPONS_RAW.split(","):
    if "=" in part:
        k, v = part.split("=", 1)
        if v.strip().isdigit():
            COUPONS[k.strip().upper()] = int(v.strip())

# Payment Information
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

# Media Apps (Mini Apps) – optional
MEDIA_LINKS = [
    ("VIP Portal", os.getenv("MEDIA_VIP_PORTAL", "")),
    ("Telegram Hub", os.getenv("MEDIA_TELEGRAM_HUB", "")),
    ("Discord", os.getenv("MEDIA_DISCORD", "")),
    ("Website", os.getenv("MEDIA_WEBSITE", "")),
]
HAS_MEDIA = any(url.strip() for _, url in MEDIA_LINKS)

# Multi-language (labels/UI; long sales copy stays as your English text for consistency)
SUPPORTED_LANGS = ["en", "es", "fr", "de", "it", "pt", "ar", "ru", "tr", "zh-Hans", "hi"]
L = {
    "en": {
        "menu_plans": "View Plans",
        "menu_media": "Media Apps",
        "menu_support": "Support",
        "back": "🔙 Go Back",
        "ive_paid": "✅ I've Paid",
        "open_crypto": "Open Crypto Link",
        "apple_google": "💳 Apple Pay/Google Pay 🚀 (Instant Access)",
        "crypto": "⚡ Crypto ⏳ (30 - 60 min wait time)",
        "paypal": "📧 PayPal 💌 (30 - 60 min wait time)",
        "reminder_resume": "Resume checkout",
        "reminder_snooze": "Not now",
        "media_title": "🎬 Media Apps\n\nOpen inside Telegram.",
        "lang_changed": "🌐 Language updated.",
        "choose_language": "🌐 Choose your language:",
        "coupon_ok": "🎟️ Coupon applied: {code} (-{pct}%).",
        "coupon_bad": "❌ Unknown coupon. Try another.",
        "enter_coupon": "Send your coupon code now (or /skip).",
        "status_title": "*Status*",
        "stats_title": "*Stats*",
        "pending_title": "*Pending checkouts*",
    },
    "es": {
        "menu_plans": "Ver planes",
        "menu_media": "Apps de medios",
        "menu_support": "Soporte",
        "back": "🔙 Volver",
        "ive_paid": "✅ Ya pagué",
        "open_crypto": "Abrir enlace de cripto",
        "apple_google": "💳 Apple/Google Pay 🚀 (Acceso instantáneo)",
        "crypto": "⚡ Cripto ⏳ (30–60 min)",
        "paypal": "📧 PayPal 💌 (30–60 min)",
        "reminder_resume": "Reanudar compra",
        "reminder_snooze": "Ahora no",
        "media_title": "🎬 Apps de medios\n\nAbrir dentro de Telegram.",
        "lang_changed": "🌐 Idioma actualizado.",
        "choose_language": "🌐 Elige tu idioma:",
        "coupon_ok": "🎟️ Cupón aplicado: {code} (-{pct}%).",
        "coupon_bad": "❌ Cupón no válido.",
        "enter_coupon": "Envía tu cupón ahora (o /skip).",
        "status_title": "*Estado*",
        "stats_title": "*Estadísticas*",
        "pending_title": "*Carritos pendientes*",
    },
}
def tr(lang: str, key: str, **kwargs) -> str:
    base = L.get(lang, L["en"]).get(key) or L["en"].get(key, key)
    return base.format(**kwargs) if kwargs else base

# =====================
# Logging
# =====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vip-bot")

# =====================
# Persistence (JSON)
# =====================
DATA_PATH = os.getenv("DATA_PATH", "data_store.json")
STORE: Dict[str, Any] = {
    "users": {},   # {user_id: {lang, last_plan, last_method, email, coupon, ref, awaiting_proof:bool}}
    "leads": {},   # {user_id: {plan, method, started_at, reminded:[idx...], active:bool, snoozed_until}}
    "events": [],  # list of dicts (ts, user_id, type, meta)
}
def load_store():
    global STORE
    try:
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                STORE = json.load(f)
            STORE.setdefault("users", {})
            STORE.setdefault("leads", {})
            STORE.setdefault("events", [])
        else:
            save_store()
    except Exception as e:
        logger.warning("Failed to load store: %s", e)
def save_store():
    try:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(STORE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save store: %s", e)
def user_lang(user_id: int, fallback: str = "en") -> str:
    return STORE["users"].get(str(user_id), {}).get("lang", fallback)
def set_user_lang(user_id: int, lang: str):
    u = STORE["users"].setdefault(str(user_id), {})
    u["lang"] = lang
    save_store()
def set_user_field(user_id: int, key: str, value: Any):
    u = STORE["users"].setdefault(str(user_id), {})
    u[key] = value
    save_store()
def start_lead(user_id: int, plan: str, method: Optional[str] = None):
    lead = STORE["leads"].setdefault(str(user_id), {})
    lead.update({
        "plan": plan, "method": method,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reminded": [], "active": True,
        "snoozed_until": None,
    })
    save_store()
def close_lead(user_id: int):
    lead = STORE["leads"].get(str(user_id))
    if lead:
        lead["active"] = False
        lead["snoozed_until"] = None
        save_store()
def log_event(user_id: int, etype: str, meta: Dict[str, Any]):
    STORE["events"].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "type": etype,
        "meta": meta,
    })
    if len(STORE["events"]) > 5000:
        STORE["events"] = STORE["events"][-3000:]
    save_store()

# =====================
# Helpers: URLs & buttons
# =====================
def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return u
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u.lstrip("/")
    return u

def safe_button(label: str, url: str = "", as_webapp: bool = False) -> InlineKeyboardButton:
    url = _normalize_url(url)
    if not url:
        return InlineKeyboardButton(label, callback_data="support")
    # WebApps cannot be t.me/telegram links; must be https and embeddable
    is_webapp_ok = url.startswith("https://") and ("t.me" not in url and "telegram.org" not in url)
    if as_webapp and is_webapp_ok:
        return InlineKeyboardButton(label, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(label, url=url)

# =====================
# FastAPI + Telegram
# =====================
app = FastAPI()
telegram_app: Optional[Application] = None
START_TIME = datetime.now(timezone.utc)

# Rate limit buckets (anti double-tap)
RL_BUCKET: Dict[int, float] = {}
def ratelimited(user_id: int, seconds: int = 1) -> bool:
    last = RL_BUCKET.get(user_id, 0.0)
    now = datetime.now().timestamp()
    if now - last < seconds:
        return True
    RL_BUCKET[user_id] = now
    return False

# =====================
# Your exact copy (kept)
# =====================
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
    "🔗 Open the crypto payment mini‑app below inside Telegram.\n\n"
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
PAID_THANKS_TEXT = (
    "✅ **Payment Received! Thank You!** 🎉\n\n"
    "📸 Please send a **screenshot** or **transaction ID** to our support team for verification.\n"
    f"👉 {SUPPORT_CONTACT}\n\n"
    "⚡ **Important Notice:**\n"
    "🔗 If you paid via Apple Pay/Google Pay, check your email inbox for the VIP link.\n"
    "🔗 If you paid via PayPal or Crypto, your VIP link will be sent manually."
)
SUPPORT_PAGE_TEXT = (
    "💬 **Need Assistance? We're Here to Help!**\n\n"
    "🕒 **Working Hours:** 8:00 AM - 12:00 AM BST\n"
    f"📨 For support, contact us directly at:\n"
    f"👉 {SUPPORT_CONTACT}\n\n"
    "⚡ Our team is ready to assist you as quickly as possible. "
    "Thank you for choosing VIP Bot! 💎"
)

# =====================
# Keyboards
# =====================
def main_menu(lang="en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
        [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
        [InlineKeyboardButton(tr(lang, "menu_support"), callback_data="support")],
    ]
    if HAS_MEDIA:
        rows.insert(2, [InlineKeyboardButton(tr(lang, "menu_media"), callback_data="media")])
    return InlineKeyboardMarkup(rows)

def payment_selector(plan: str, lang="en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "apple_google"), callback_data=f"payment_shopify_{plan}")],
        [InlineKeyboardButton(tr(lang, "crypto"), callback_data=f"payment_crypto_{plan}")],
        [InlineKeyboardButton(tr(lang, "paypal"), callback_data=f"payment_paypal_{plan}")],
        [InlineKeyboardButton(tr(lang, "menu_support"), callback_data="support")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back")],
    ])

def add_coupon_to_url(url: str, code: Optional[str]) -> str:
    if not code: return url
    code = code.strip()
    if not code: return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}discount={code}"

def shopify_menu_webapp(lang="en", coupon: Optional[str] = None) -> InlineKeyboardMarkup:
    lt = add_coupon_to_url(PAYMENT_INFO["shopify"]["lifetime"], coupon)
    m1 = add_coupon_to_url(PAYMENT_INFO["shopify"]["1_month"], coupon)
    return InlineKeyboardMarkup([
        [safe_button("💎 Lifetime (£20.00)", lt, as_webapp=True)],
        [safe_button("⏳ 1 Month (£10.00)", m1, as_webapp=True)],
        [InlineKeyboardButton(tr(lang, "ive_paid"), callback_data="paid")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back")],
    ])

def crypto_menu(lang="en") -> InlineKeyboardMarkup:
    link = PAYMENT_INFO["crypto"]["link"]
    return InlineKeyboardMarkup([
        [safe_button(tr(lang, "open_crypto"), link, as_webapp=True)],  # auto-fallback if link is t.me
        [InlineKeyboardButton(tr(lang, "ive_paid"), callback_data="paid")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back")],
    ])

def paypal_menu(lang="en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "ive_paid"), callback_data="paid")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back")],
    ])

def media_menu_webapps(lang="en") -> InlineKeyboardMarkup:
    rows = []
    for label, url in MEDIA_LINKS:
        if url.strip():
            rows.append([safe_button(label, url, as_webapp=True)])
    rows.append([InlineKeyboardButton(tr(lang, "back"), callback_data="back")])
    return InlineKeyboardMarkup(rows)

def language_menu() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(code, callback_data=f"lang_{code}")] for code in SUPPORTED_LANGS]
    rows.append([InlineKeyboardButton("Close", callback_data="back")])
    return InlineKeyboardMarkup(rows)

def normalize_coupon(text: str) -> Optional[str]:
    if not text: return None
    t = text.strip().upper()
    return t if t in COUPONS else None

# =====================
# Reminder scheduler (1h & 24h DM nudges; persuasive copy)
# =====================
async def reminder_loop(app: Application):
    while True:
        try:
            now = datetime.now(timezone.utc)
            for uid, lead in list(STORE["leads"].items()):
                if not lead.get("active"):
                    continue
                # snooze check
                snoozed_until = lead.get("snoozed_until")
                if snoozed_until:
                    try:
                        if now < datetime.fromisoformat(snoozed_until):
                            continue
                    except Exception:
                        lead["snoozed_until"] = None
                        save_store()

                started = datetime.fromisoformat(lead["started_at"])
                reminded = lead.get("reminded", [])
                for idx, mins in enumerate(REMINDER_STEPS):
                    if idx in reminded:
                        continue
                    if now - started >= timedelta(minutes=mins):
                        await send_reminder(int(uid), idx, lead)
                        lead["reminded"].append(idx)
                        save_store()
            await asyncio.sleep(30)
        except Exception as e:
            logger.warning("Reminder loop error: %s", e)
            await asyncio.sleep(5)

def _reminder_text(lang: str, step_idx: int, plan: str, method: Optional[str]) -> str:
    # Persuasive, friendly, short. Step 0 = 1h, Step 1 = 24h
    if step_idx == 0:
        return (
            "⏰ **Quick reminder**\n\n"
            "Your VIP access is waiting — complete your checkout in one tap to secure today’s price. "
            "Need help? Tap Support anytime."
        )
    else:
        return (
            "⛳ **Last chance today**\n\n"
            "Spots are nearly gone and prices can change. Finish your payment now to lock in your VIP access. "
            "If you need assistance, we're here."
        )

async def send_reminder(user_id: int, step_idx: int, lead: Dict[str, Any]):
    lang = user_lang(user_id)
    try:
        plan = lead.get("plan", "1_month")
        method = lead.get("method")
        text = _reminder_text(lang, step_idx, plan, method)
        # Build a single Resume button back to the plan's payment selector (keeps it simple & fast)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tr(lang, "reminder_resume"), callback_data="resume_checkout")],
            [InlineKeyboardButton(tr(lang, "reminder_snooze"), callback_data="snooze")],
        ])
        await telegram_app.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        log_event(user_id, "reminder", {"step": step_idx})
    except Exception as e:
        logger.warning("Failed to send reminder to %s: %s", user_id, e)

# =====================
# Lifecycle
# =====================
@app.on_event("startup")
async def startup_event():
    global telegram_app
    load_store()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    telegram_app.add_handler(CommandHandler("start", start, block=False))
    telegram_app.add_handler(CommandHandler("help", help_cmd, block=False))
    telegram_app.add_handler(CommandHandler("status", status_cmd, block=False))
    telegram_app.add_handler(CommandHandler("terms", terms_cmd, block=False))
    telegram_app.add_handler(CommandHandler("id", id_cmd, block=False))
    telegram_app.add_handler(CommandHandler("broadcast", admin_broadcast, block=False))
    telegram_app.add_handler(CommandHandler("stats", admin_stats, block=False))
    telegram_app.add_handler(CommandHandler("find", admin_find, block=False))
    telegram_app.add_handler(CommandHandler("pending", admin_pending, block=False))

    # Callbacks
    telegram_app.add_handler(CallbackQueryHandler(handle_subscription, pattern=r"^select_", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_", block=False))
    telegram_app.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^paid$", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_back, pattern=r"^back$", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_support, pattern=r"^support$", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_media, pattern=r"^media$", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_lang_change, pattern=r"^(lang_menu|lang_)", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_resume_or_snooze, pattern=r"^(resume_checkout|snooze)$", block=False))
    telegram_app.add_handler(CallbackQueryHandler(handle_admin_approval, pattern=r"^(approve|needmore|reject)_.+$", block=False))

    # Proof intake (photos/docs/text) — auto-forward to admin
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_possible_proof))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    # Error handler
    telegram_app.add_error_handler(on_error)

    await telegram_app.initialize()

    # Optional: uptime monitor ping
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(UPTIME_MONITOR_URL)
            logger.info("Uptime monitor status: %s", r.status_code)
    except Exception as e:
        logger.warning("Uptime ping failed: %s", e)

    # Webhook with secret
    await telegram_app.bot.delete_webhook()
    await telegram_app.bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Webhook set to %s", WEBHOOK_URL)

    # Start app + reminder loop
    await telegram_app.start()
    logger.info("Telegram bot started.")
    asyncio.create_task(reminder_loop(telegram_app))

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
# HTTP routes
# ==============
@app.get("/")
async def root():
    return {"ok": True, "env": ENV_NAME, "webhook": WEBHOOK_URL}

@app.get("/uptime")
async def get_uptime():
    uptime_duration = datetime.now(timezone.utc) - START_TIME
    return JSONResponse(
        content={
            "status": "online",
            "uptime": str(uptime_duration),
            "start_time": START_TIME.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
    )

@app.head("/uptime")
async def head_uptime():
    return Response(status_code=200)

@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
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

# =====================
# Telegram Handlers
# =====================
def detect_lang(update: Update) -> str:
    code = (update.effective_user.language_code or "en").split("-")[0]
    return code if code in L else "en"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if ratelimited(user.id): return

    # Referral tracking from /start args
    ref = None
    if context.args:
        ref = context.args[0][:32]
        set_user_field(user.id, "ref", ref)

    # Set / remember language
    lang = detect_lang(update)
    set_user_lang(user.id, lang)

    # Sticky cart hint: if lead active, show resume button
    lead = STORE["leads"].get(str(user.id))
    if lead and lead.get("active"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
            [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
            [InlineKeyboardButton("🧾 Resume checkout", callback_data="resume_checkout")],
            [InlineKeyboardButton(tr(lang, "menu_support"), callback_data="support")],
        ])
    else:
        kb = main_menu(lang)

    await update.effective_message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
        disable_web_page_preview=True,
    )
    log_event(user.id, "start", {"ref": ref, "lang": lang})

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "*Commands*\n"
        "/start – Main menu\n"
        "/status – Bot status\n"
        "/terms – Terms & notes\n"
        "/id – Show my ID\n"
        "/lang – Change language\n"
    )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    up = datetime.now(timezone.utc) - START_TIME
    txt = (
        f"*Status*: Online\n"
        f"*Env*: `{ENV_NAME}`\n"
        f"*Uptime*: `{str(up)}`\n"
        f"*Webhook*: `{WEBHOOK_URL}`\n"
    )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def terms_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "*Terms & Notes*\n"
        "• Access is for personal use only; redistribution may lead to a ban\n"
        "• Refunds assessed case‑by‑case if access was not delivered\n"
        "• By purchasing, you accept these terms\n"
    )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"Your ID: `{update.effective_user.id}`", parse_mode=ParseMode.MARKDOWN)

# --- Inline callbacks
async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = update.callback_query
    await q.answer()
    user = q.from_user
    plan = q.data.split("_", 1)[1]  # "1_month" | "lifetime"
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"
    lang = user_lang(user.id)

    # Start/refresh lead
    start_lead(user.id, plan)
    set_user_field(user.id, "last_plan", plan)

    message = SELECT_PLAN_TEXT(plan_text)
    await q.edit_message_text(
        text=message,
        reply_markup=payment_selector(plan, lang),
        parse_mode=ParseMode.MARKDOWN,
    )
    log_event(user.id, "plan_selected", {"plan": plan})

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    lang = user_lang(user.id)

    _, method, plan = q.data.split("_", 2)
    plan_text = "LIFETIME" if plan == "lifetime" else "1 MONTH"

    set_user_field(user.id, "last_plan", plan)
    set_user_field(user.id, "last_method", method)
    lead = STORE["leads"].setdefault(str(user.id), {"active": True})
    lead["method"] = method
    save_store()

    context.user_data["plan_text"] = plan_text
    context.user_data["method"] = method

    coupon = STORE["users"].get(str(user.id), {}).get("coupon")

    if method == "shopify":
        msg = SHOPIFY_TEXT
        kb = shopify_menu_webapp(lang, coupon=coupon)
    elif method == "crypto":
        msg = CRYPTO_TEXT
        kb = crypto_menu(lang)  # SAFE: falls back for t.me links
    elif method == "paypal":
        msg = PAYPAL_TEXT
        kb = paypal_menu(lang)
    else:
        msg = "Unknown payment method."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "back"), callback_data="back")]])

    await q.edit_message_text(
        text=msg,
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )
    log_event(user.id, "payment_method", {"plan": plan, "method": method})

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    plan_text = context.user_data.get("plan_text", "N/A")
    method = context.user_data.get("method", "N/A")
    username = q.from_user.username or "No Username"
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Close the lead (stop reminders)
    close_lead(user.id)

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "📝 **Payment Notification**\n"
                    f"👤 **User:** @{username}\n"
                    f"📋 **Plan:** {plan_text}\n"
                    f"💳 **Method:** {method.capitalize()}\n"
                    f"🕒 **Time:** {current_time}\n\n"
                    f"Approve? / Need more? / Reject?\n"
                    f"(Automated ping — user will also be DM’d for proof.)"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Admin notification failed: %s", e)

    await q.edit_message_text(PAID_THANKS_TEXT, parse_mode=ParseMode.MARKDOWN)
    set_user_field(user.id, "awaiting_proof", True)
    log_event(user.id, "paid_clicked", {"method": method})

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = user_lang(q.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Change language", callback_data="lang_menu")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back")],
    ])
    await q.edit_message_text(SUPPORT_PAGE_TEXT, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = user_lang(q.from_user.id)
    if not HAS_MEDIA:
        await q.edit_message_text("No media apps configured.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "back"), callback_data="back")]]))
        return
    await q.edit_message_text(
        tr(lang, "media_title"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=media_menu_webapps(lang),
        disable_web_page_preview=True,
    )

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    await start(update, context)

# ---- Language switching
async def handle_lang_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "lang_menu":
        await q.edit_message_text(tr("en", "choose_language"), reply_markup=language_menu())
        return
    _, code = data.split("_", 1)
    if code not in SUPPORTED_LANGS:
        code = "en"
    set_user_lang(q.from_user.id, code)
    await q.edit_message_text(tr(code, "lang_changed"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(code, "back"), callback_data="back")]]))

# ---- Reminders: resume / snooze
async def handle_resume_or_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    lang = user_lang(uid)
    lead = STORE["leads"].get(str(uid))
    if q.data == "snooze":
        # Snooze next reminders for 6 hours
        until = datetime.now(timezone.utc) + timedelta(hours=6)
        if lead:
            lead["snoozed_until"] = until.isoformat()
            save_store()
        await q.edit_message_text("👌 Got it — I’ll remind you later. Come back anytime with /start.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "back"), callback_data="back")]]))
        log_event(uid, "snoozed", {"until": until.isoformat()})
        return

    plan = (lead or {}).get("plan") or STORE["users"].get(str(uid), {}).get("last_plan", "1_month")
    await q.edit_message_text(
        SELECT_PLAN_TEXT("LIFETIME" if plan == "lifetime" else "1 MONTH"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=payment_selector(plan, lang)
    )
    log_event(uid, "resume_clicked", {"plan": plan})

# ===========================
# Proof intake + Admin review
# ===========================
def admin_approval_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❓ Need more", callback_data=f"needmore_{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"),
        ]
    ])

async def handle_possible_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = STORE["users"].get(str(user.id), {})
    if not st.get("awaiting_proof"):
        return

    caption = (update.effective_message.caption or update.effective_message.text or "").strip()
    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
                reply_markup=admin_approval_kb(user.id),
                reply_to_message_id=fwd.message_id,
            )
        except Exception as e:
            logger.warning("Forward to admin failed: %s", e)

    set_user_field(user.id, "awaiting_proof", False)
    await update.effective_message.reply_text("🙏 Thanks! Our team will verify and send your VIP link shortly.")
    log_event(user.id, "proof_sent", {"caption": caption[:200]})

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.effective_message.text or "").strip()

    coupon = normalize_coupon(text)
    if coupon:
        set_user_field(uid, "coupon", coupon)
        await update.effective_message.reply_text(tr(user_lang(uid), "coupon_ok", code=coupon, pct=COUPONS[coupon]))
        return

    # basic email capture
    if "@" in text and "." in text and len(text) <= 100:
        set_user_field(uid, "email", text)
        await update.effective_message.reply_text(f"📧 Saved: *{text}*", parse_mode=ParseMode.MARKDOWN)
        return

    await update.effective_message.reply_text("Use /start to see options or contact support.")

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if ADMIN_CHAT_ID is None or q.from_user.id != ADMIN_CHAT_ID:
        return
    action, user_id_str = q.data.split("_", 1)
    target_id = int(user_id_str)

    if action == "approve":
        msg = "🎉 Your payment has been verified. Check your email/spam for your VIP link. If not found, contact support."
    elif action == "needmore":
        msg = "❓ We need a bit more information to verify your payment. Please send a clearer screenshot or transaction ID."
    else:
        msg = "❌ We couldn’t verify this payment. If you think this is a mistake, please contact support."

    try:
        await context.bot.send_message(chat_id=target_id, text=msg)
    except Exception as e:
        logger.warning("Admin action: failed to message user %s: %s", target_id, e)

    await q.edit_message_text(f"Action '{action}' sent to user {target_id}.")

# =====================
# Admin tools
# =====================
def is_admin(update: Update) -> bool:
    return ADMIN_CHAT_ID is not None and update.effective_user and update.effective_user.id == ADMIN_CHAT_ID

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.effective_message.reply_text("Usage: /broadcast Your message")
        return
    sent = 0
    for uid in list(STORE["users"].keys()):
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
            sent += 1
        except Exception:
            pass
    await update.effective_message.reply_text(f"Broadcast sent to {sent} users.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    total_users = len(STORE["users"])
    active_leads = sum(1 for v in STORE["leads"].values() if v.get("active"))
    reminders_sent = sum(1 for e in STORE["events"] if e["type"] == "reminder")
    proofs = sum(1 for e in STORE["events"] if e["type"] == "proof_sent")
    txt = (
        f"{tr('en','stats_title')}\n"
        f"Users: *{total_users}*\n"
        f"Active leads: *{active_leads}*\n"
        f"Reminders sent: *{reminders_sent}*\n"
        f"Proofs received: *{proofs}*\n"
    )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def admin_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.effective_message.reply_text("Usage: /find <user_id>")
        return
    key = context.args[0]
    if not key.isdigit():
        await update.effective_message.reply_text("Please provide numeric user_id.")
        return
    u = STORE["users"].get(key)
    l = STORE["leads"].get(key)
    if not u and not l:
        await update.effective_message.reply_text("No data for that user.")
        return
    await update.effective_message.reply_text(
        f"*User* `{key}`\n"
        f"Lang: {u.get('lang') if u else '-'}\n"
        f"Last plan: {u.get('last_plan') if u else '-'}\n"
        f"Last method: {u.get('last_method') if u else '-'}\n"
        f"Email: {u.get('email') if u else '-'}\n"
        f"Coupon: {u.get('coupon') if u else '-'}\n"
        f"Ref: {u.get('ref') if u else '-'}\n"
        f"Lead: {l if l else '-'}",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    lines = []
    for uid, lead in STORE["leads"].items():
        if lead.get("active"):
            since = datetime.now(timezone.utc) - datetime.fromisoformat(lead["started_at"])
            lines.append(f"{uid}: plan={lead.get('plan')} method={lead.get('method')} since={str(since).split('.')[0]}")
    txt = tr("en", "pending_title") + "\n" + ("\n".join(lines) if lines else "None")
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

# =====================
# Error handler
# =====================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Update error: %s", context.error)
    try:
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ Error:\n`{repr(context.error)}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception:
        pass
