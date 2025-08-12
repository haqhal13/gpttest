yes can u just complete this script ;Here’s your complete, production‑ready bot.py — keeps your original texts/buttons exactly as you like them, adds full multilingual support (🇬🇧🇪🇸🇫🇷🇩🇪🇮🇹🇵🇹🇷🇺🇹🇷🇸🇦🇺🇸🇮🇳🇮🇱 / en, es, fr, de, it, pt, ru, tr, ar, ur, hi, he, zh‑Hans), auto‑detect, one‑tap flags, RTL support, 1h & 24h abandoned‑checkout reminders, and 28‑day membership expiry notifications to the user and admin. Mini‑app buttons for Shopify/media, safe crypto link handling, error‑hardened.

Just copy–paste and deploy:

# bot.py — VIP Bot (multilingual + flags + reminders + expiry + mini-app links; preserves your original texts/buttons)
# Run (Render): gunicorn bot:app --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker

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

# Reminder cadence (minutes) — 1h and 24h
REMINDERS_MINUTES = os.getenv("REMINDERS", "60,1440")
REMINDER_STEPS = [int(x) for x in REMINDERS_MINUTES.split(",") if x.strip().isdigit()]

# Coupons (format: "SPRING10=10,VIP5=5") — optional
COUPONS_RAW = os.getenv("COUPONS", "")
COUPONS: Dict[str, int] = {}
for part in COUPONS_RAW.split(","):
    if "=" in part:
        k, v = part.split("=", 1)
        if v.strip().isdigit():
            COUPONS[k.strip().upper()] = int(v.strip())

# Payment Information (your links)
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

# =====================
# Multi-language
# =====================
SUPPORTED_LANGS = ["en", "es", "fr", "de", "it", "pt", "ru", "tr", "ar", "ur", "hi", "he", "zh-Hans"]
FLAGS = {
    "en": "🇬🇧", "es": "🇪🇸", "fr": "🇫🇷", "de": "🇩🇪", "it": "🇮🇹",
    "pt": "🇵🇹", "ru": "🇷🇺", "tr": "🇹🇷", "ar": "🇸🇦", "ur": "🇵🇰",
    "hi": "🇮🇳", "he": "🇮🇱", "zh-Hans": "🇨🇳"
}

# Short UI labels
L = {
    # EN
    "en": {
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
        "change_language": "🌐 Change language",
        "resume": "🧾 Resume checkout",
    },
    # ES
    "es": {
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
        "change_language": "🌐 Cambiar idioma",
        "resume": "🧾 Reanudar",
    },
    # FR
    "fr": {
        "menu_media": "Apps média",
        "menu_support": "Support",
        "back": "🔙 Retour",
        "ive_paid": "✅ J'ai payé",
        "open_crypto": "Ouvrir le lien crypto",
        "apple_google": "💳 Apple/Google Pay 🚀 (Accès instantané)",
        "crypto": "⚡ Crypto ⏳ (30–60 min)",
        "paypal": "📧 PayPal 💌 (30–60 min)",
        "reminder_resume": "Reprendre le paiement",
        "reminder_snooze": "Plus tard",
        "media_title": "🎬 Apps média\n\nOuvrir dans Telegram.",
        "lang_changed": "🌐 Langue mise à jour.",
        "choose_language": "🌐 Choisissez votre langue :",
        "coupon_ok": "🎟️ Code appliqué : {code} (-{pct}%).",
        "coupon_bad": "❌ Code invalide.",
        "enter_coupon": "Envoyez votre code maintenant (ou /skip).",
        "status_title": "*Statut*",
        "stats_title": "*Stats*",
        "pending_title": "*Paniers en attente*",
        "change_language": "🌐 Changer de langue",
        "resume": "🧾 Reprendre",
    },
    # DE
    "de": {
        "menu_media": "Media-Apps",
        "menu_support": "Support",
        "back": "🔙 Zurück",
        "ive_paid": "✅ Ich habe bezahlt",
        "open_crypto": "Krypto-Link öffnen",
        "apple_google": "💳 Apple/Google Pay 🚀 (Sofortzugang)",
        "crypto": "⚡ Krypto ⏳ (30–60 Min.)",
        "paypal": "📧 PayPal 💌 (30–60 Min.)",
        "reminder_resume": "Kauf fortsetzen",
        "reminder_snooze": "Nicht jetzt",
        "media_title": "🎬 Media-Apps\n\nIn Telegram öffnen.",
        "lang_changed": "🌐 Sprache aktualisiert.",
        "choose_language": "🌐 Sprache wählen:",
        "coupon_ok": "🎟️ Gutschein angewandt: {code} (-{pct}%).",
        "coupon_bad": "❌ Ungültiger Gutschein.",
        "enter_coupon": "Gutscheincode senden (oder /skip).",
        "status_title": "*Status*",
        "stats_title": "*Statistiken*",
        "pending_title": "*Offene Warenkörbe*",
        "change_language": "🌐 Sprache ändern",
        "resume": "🧾 Fortsetzen",
    },
    # IT
    "it": {
        "menu_media": "App media",
        "menu_support": "Supporto",
        "back": "🔙 Indietro",
        "ive_paid": "✅ Ho pagato",
        "open_crypto": "Apri link crypto",
        "apple_google": "💳 Apple/Google Pay 🚀 (Accesso immediato)",
        "crypto": "⚡ Cripto ⏳ (30–60 min)",
        "paypal": "📧 PayPal 💌 (30–60 min)",
        "reminder_resume": "Riprendi pagamento",
        "reminder_snooze": "Non ora",
        "media_title": "🎬 App media\n\nApri in Telegram.",
        "lang_changed": "🌐 Lingua aggiornata.",
        "choose_language": "🌐 Scegli la lingua:",
        "coupon_ok": "🎟️ Coupon applicato: {code} (-{pct}%).",
        "coupon_bad": "❌ Coupon non valido.",
        "enter_coupon": "Invia il coupon ora (o /skip).",
        "status_title": "*Stato*",
        "stats_title": "*Statistiche*",
        "pending_title": "*Carrelli in sospeso*",
        "change_language": "🌐 Cambia lingua",
        "resume": "🧾 Riprendi",
    },
    # PT
    "pt": {
        "menu_media": "Apps de mídia",
        "menu_support": "Suporte",
        "back": "🔙 Voltar",
        "ive_paid": "✅ Paguei",
        "open_crypto": "Abrir link de cripto",
        "apple_google": "💳 Apple/Google Pay 🚀 (Acesso instantâneo)",
        "crypto": "⚡ Cripto ⏳ (30–60 min)",
        "paypal": "📧 PayPal 💌 (30–60 min)",
        "reminder_resume": "Retomar pagamento",
        "reminder_snooze": "Agora não",
        "media_title": "🎬 Apps de mídia\n\nAbrir no Telegram.",
        "lang_changed": "🌐 Idioma atualizado.",
        "choose_language": "🌐 Escolha seu idioma:",
        "coupon_ok": "🎟️ Cupom aplicado: {code} (-{pct}%).",
        "coupon_bad": "❌ Cupom inválido.",
        "enter_coupon": "Envie seu cupom agora (ou /skip).",
        "status_title": "*Status*",
        "stats_title": "*Estatísticas*",
        "pending_title": "*Carrinhos pendentes*",
        "change_language": "🌐 Alterar idioma",
        "resume": "🧾 Retomar",
    },
    # RU
    "ru": {
        "menu_media": "Медиа‑приложения",
        "menu_support": "Поддержка",
        "back": "🔙 Назад",
        "ive_paid": "✅ Я оплатил",
        "open_crypto": "Открыть крипто‑ссылку",
        "apple_google": "💳 Apple/Google Pay 🚀 (Мгновенный доступ)",
        "crypto": "⚡ Крипто ⏳ (30–60 мин.)",
        "paypal": "📧 PayPal 💌 (30–60 мин.)",
        "reminder_resume": "Продолжить оплату",
        "reminder_snooze": "Не сейчас",
        "media_title": "🎬 Медиа‑приложения\n\nОткрывается в Telegram.",
        "lang_changed": "🌐 Язык обновлён.",
        "choose_language": "🌐 Выберите язык:",
        "coupon_ok": "🎟️ Купон применён: {code} (-{pct}%).",
        "coupon_bad": "❌ Неверный купон.",
        "enter_coupon": "Отправьте купон (или /skip).",
        "status_title": "*Статус*",
        "stats_title": "*Статистика*",
        "pending_title": "*Брошенные корзины*",
        "change_language": "🌐 Сменить язык",
        "resume": "🧾 Продолжить",
    },
    # TR
    "tr": {
        "menu_media": "Medya Uygulamaları",
        "menu_support": "Destek",
        "back": "🔙 Geri",
        "ive_paid": "✅ Ödeme yaptım",
        "open_crypto": "Kripto bağlantısını aç",
        "apple_google": "💳 Apple/Google Pay 🚀 (Anında erişim)",
        "crypto": "⚡ Kripto ⏳ (30–60 dk)",
        "paypal": "📧 PayPal 💌 (30–60 dk)",
        "reminder_resume": "Ödemeye devam et",
        "reminder_snooze": "Şimdi değil",
        "media_title": "🎬 Medya Uygulamaları\n\nTelegram içinde açın.",
        "lang_changed": "🌐 Dil güncellendi.",
        "choose_language": "🌐 Dil seçin:",
        "coupon_ok": "🎟️ Kupon uygulandı: {code} (-{pct}%).",
        "coupon_bad": "❌ Geçersiz kupon.",
        "enter_coupon": "Kuponunuzu gönderin (veya /skip).",
        "status_title": "*Durum*",
        "stats_title": "*İstatistikler*",
        "pending_title": "*Bekleyen sepetler*",
        "change_language": "🌐 Dili değiştir",
        "resume": "🧾 Devam et",
    },
    # AR (RTL)
    "ar": {
        "menu_media": "تطبيقات الوسائط",
        "menu_support": "الدعم",
        "back": "🔙 رجوع",
        "ive_paid": "✅ دفعت",
        "open_crypto": "فتح رابط العملات",
        "apple_google": "💳 Apple/Google Pay 🚀 (وصول فوري)",
        "crypto": "⚡ عملات رقمية ⏳ (30–60 دقيقة)",
        "paypal": "📧 باي بال 💌 (30–60 دقيقة)",
        "reminder_resume": "متابعة الدفع",
        "reminder_snooze": "لاحقاً",
        "media_title": "🎬 تطبيقات الوسائط\n\nتفتح داخل تيليجرام.",
        "lang_changed": "🌐 تم تحديث اللغة.",
        "choose_language": "🌐 اختر لغتك:",
        "coupon_ok": "🎟️ تم تطبيق القسيمة: {code} (-{pct}%).",
        "coupon_bad": "❌ قسيمة غير صالحة.",
        "enter_coupon": "أرسل القسيمة الآن (أو /skip).",
        "status_title": "*الحالة*",
        "stats_title": "*إحصائيات*",
        "pending_title": "*سلال معلّقة*",
        "change_language": "🌐 تغيير اللغة",
        "resume": "🧾 متابعة",
    },
    # UR (RTL)
    "ur": {
        "menu_media": "میڈیا ایپس",
        "menu_support": "سپورٹ",
        "back": "🔙 واپس",
        "ive_paid": "✅ میں نے ادائیگی کر دی",
        "open_crypto": "کرپٹو لنک کھولیں",
        "apple_google": "💳 Apple/Google Pay 🚀 (فوری رسائی)",
        "crypto": "⚡ کرپٹو ⏳ (30–60 منٹ)",
        "paypal": "📧 پے پال 💌 (30–60 منٹ)",
        "reminder_resume": "چیک آؤٹ مکمل کریں",
        "reminder_snooze": "بعد میں",
        "media_title": "🎬 میڈیا ایپس\n\nٹیلیگرام میں کھلتی ہیں۔",
        "lang_changed": "🌐 زبان تبدیل ہو گئی۔",
        "choose_language": "🌐 اپنی زبان منتخب کریں:",
        "coupon_ok": "🎟️ کوپن لاگو: {code} (-{pct}%).",
        "coupon_bad": "❌ غلط کوپن۔",
        "enter_coupon": "کوپن بھیجیں (یا /skip).",
        "status_title": "*اسٹیٹس*",
        "stats_title": "*اعدادوشمار*",
        "pending_title": "*نامکمل چیک آؤٹ*",
        "change_language": "🌐 زبان تبدیل کریں",
        "resume": "🧾 جاری رکھیں",
    },
    # HI
    "hi": {
        "menu_media": "मीडिया ऐप्स",
        "menu_support": "सपोर्ट",
        "back": "🔙 वापस",
        "ive_paid": "✅ मैंने भुगतान किया",
        "open_crypto": "क्रिप्टो लिंक खोलें",
        "apple_google": "💳 Apple/Google Pay 🚀 (तुरंत एक्सेस)",
        "crypto": "⚡ क्रिप्टो ⏳ (30–60 मिनट)",
        "paypal": "📧 पेपाल 💌 (30–60 मिनट)",
        "reminder_resume": "पेमेंट जारी रखें",
        "reminder_snooze": "अभी नहीं",
        "media_title": "🎬 मीडिया ऐप्स\n\nटेलीग्राम में खोलें।",
        "lang_changed": "🌐 भाषा अपडेट हुई।",
        "choose_language": "🌐 अपनी भाषा चुनें:",
        "coupon_ok": "🎟️ कूपन लागू: {code} (-{pct}%).",
        "coupon_bad": "❌ अमान्य कूपन।",
        "enter_coupon": "कूपन अभी भेजें (या /skip).",
        "status_title": "*स्थिति*",
        "stats_title": "*आंकड़े*",
        "pending_title": "*लंबित चेकआउट*",
        "change_language": "🌐 भाषा बदलें",
        "resume": "🧾 जारी रखें",
    },
    # HE (RTL)
    "he": {
        "menu_media": "אפליקציות מדיה",
        "menu_support": "תמיכה",
        "back": "🔙 חזרה",
        "ive_paid": "✅ שילמתי",
        "open_crypto": "פתח קישור קריפטו",
        "apple_google": "💳 Apple/Google Pay 🚀 (גישה מיידית)",
        "crypto": "⚡ קריפטו ⏳ (30–60 דק׳)",
        "paypal": "📧 פייפאל 💌 (30–60 דק׳)",
        "reminder_resume": "המשך תשלום",
        "reminder_snooze": "לא עכשיו",
        "media_title": "🎬 אפליקציות מדיה\n\nנפתח בתוך טלגרם.",
        "lang_changed": "🌐 השפה עודכנה.",
        "choose_language": "🌐 בחר שפה:",
        "coupon_ok": "🎟️ קופון שויך: {code} (-{pct}%).",
        "coupon_bad": "❌ קופון לא תקין.",
        "enter_coupon": "שלח קופון עכשיו (או /skip).",
        "status_title": "*סטטוס*",
        "stats_title": "*סטטיסטיקות*",
        "pending_title": "*תשלומים שלא הושלמו*",
        "change_language": "🌐 החלפת שפה",
        "resume": "🧾 המשך",
    },
    # ZH-HANS
    "zh-Hans": {
        "menu_media": "媒体应用",
        "menu_support": "客服",
        "back": "🔙 返回",
        "ive_paid": "✅ 我已付款",
        "open_crypto": "打开加密货币链接",
        "apple_google": "💳 Apple/Google Pay 🚀（即时访问）",
        "crypto": "⚡ 加密货币 ⏳（30–60 分钟）",
        "paypal": "📧 PayPal 💌（30–60 分钟）",
        "reminder_resume": "继续结账",
        "reminder_snooze": "稍后",
        "media_title": "🎬 媒体应用\n\n在 Telegram 内打开。",
        "lang_changed": "🌐 语言已更新。",
        "choose_language": "🌐 选择语言：",
        "coupon_ok": "🎟️ 已应用优惠码：{code}（-{pct}%）。",
        "coupon_bad": "❌ 优惠码无效。",
        "enter_coupon": "现在发送优惠码（或 /skip）。",
        "status_title": "*状态*",
        "stats_title": "*统计*",
        "pending_title": "*未完成结账*",
        "change_language": "🌐 更改语言",
        "resume": "🧾 继续",
    },
}

# Long sales/flow texts (full translations)
TEXTS = {
    # EN (original content preserved)
    "en": {
        "welcome": (
            "💎 **Welcome to the VIP Bot!**\n\n"
            "💎 *Get access to thousands of creators every month!*\n"
            "⚡ *Instant access to the VIP link sent directly to your email!*\n"
            "⭐ *Don’t see the model you’re looking for? We’ll add them within 24–72 hours!*\n\n"
            "📌 Got questions ? VIP link not working ? Contact support 🔍👀"
        ),
        "select_plan": (
            "⭐ You have chosen the **{plan_text}** plan.\n\n"
            "💳 **Apple Pay/Google Pay:** 🚀 Instant VIP access (link emailed immediately).\n"
            "⚡ **Crypto:** (30 - 60 min wait time), VIP link sent manually.\n"
            "📧 **PayPal:**(30 - 60 min wait time), VIP link sent manually.\n\n"
            "🎉 Choose your preferred payment method below and get access today!"
        ),
        "shopify": (
            "🚀 **Instant Access with Apple Pay/Google Pay!**\n\n"
            "🎁 **Choose Your VIP Plan:**\n"
            "💎 Lifetime Access: **£20.00 GBP** 🎉\n"
            "⏳ 1 Month Access: **£10.00 GBP** 🌟\n\n"
            "🛒 Click below to pay securely and get **INSTANT VIP access** delivered to your email! 📧\n\n"
            "✅ After payment, click 'I've Paid' to confirm."
        ),
        "crypto": (
            "⚡ **Pay Securely with Crypto!**\n\n"
            "🔗 Open the crypto payment mini‑app below inside Telegram.\n\n"
            "💎 **Choose Your Plan:**\n"
            "⏳ 1 Month Access: **$13.00 USD** 🌟\n"
            "💎 Lifetime Access: **$27 USD** 🎉\n\n"
            "✅ Once you've sent the payment, click 'I've Paid' to confirm."
        ),
        "paypal": (
            "💸 **Easy Payment with PayPal!**\n\n"
            f"`{PAYMENT_INFO['paypal']}`\n\n"
            "💎 **Choose Your Plan:**\n"
            "⏳ 1 Month Access: **£10.00 GBP** 🌟\n"
            "💎 Lifetime Access: **£20.00 GBP** 🎉\n\n"
            "✅ Once payment is complete, click 'I've Paid' to confirm."
        ),
        "paid_thanks": (
            "✅ **Payment Received! Thank You!** 🎉\n\n"
            "📸 Please send a **screenshot** or **transaction ID** to our support team for verification.\n"
            f"👉 {SUPPORT_CONTACT}\n\n"
            "⚡ **Important Notice:**\n"
            "🔗 If you paid via Apple Pay/Google Pay, check your email inbox for the VIP link.\n"
            "🔗 If you paid via PayPal or Crypto, your VIP link will be sent manually."
        ),
        "support_page": (
            "💬 **Need Assistance? We're Here to Help!**\n\n"
            "🕒 **Working Hours:** 8:00 AM - 12:00 AM BST\n"
            f"📨 For support, contact us directly at:\n"
            f"👉 {SUPPORT_CONTACT}\n\n"
            "⚡ Our team is ready to assist you as quickly as possible. "
            "Thank you for choosing VIP Bot! 💎"
        ),
        "reminder0": (
            "⏰ **Quick reminder**\n\n"
            "Your VIP access is waiting — complete your checkout in one tap to secure today’s price. "
            "Need help? Tap Support anytime."
        ),
        "reminder1": (
            "⛳ **Last chance today**\n\n"
            "Spots are nearly gone and prices can change. Finish your payment now to lock in your VIP access. "
            "If you need assistance, we're here."
        ),
        "membership_notice": (
            "⏳ *Membership notice*\n\n"
            "Your *1‑Month VIP access* is reaching *28 days*. To avoid interruption, "
            "renew now in one tap."
        ),
    },
    # ES
    "es": {
        "welcome": "💎 **¡Bienvenido al VIP Bot!**\n\n💎 *Acceso a miles de creadores cada mes.*\n⚡ *Enlace VIP enviado al correo al instante.*\n⭐ *¿No ves el modelo que buscas? Lo añadimos en 24–72h.*\n\n📌 ¿Dudas? ¿Enlace no funciona? Soporte 🔍👀",
        "select_plan": "⭐ Has elegido el plan **{plan_text}**.\n\n💳 **Apple/Google Pay:** 🚀 Acceso instantáneo (enlace por email).\n⚡ **Cripto:** (30–60 min) enlace manual.\n📧 **PayPal:** (30–60 min) enlace manual.\n\n🎉 ¡Elige un método y accede hoy!",
        "shopify": "🚀 **Acceso instantáneo con Apple/Google Pay**\n\n🎁 **Elige tu plan:**\n💎 Lifetime: **£20.00** 🎉\n⏳ 1 mes: **£10.00** 🌟\n\n🛒 Paga seguro y recibe **acceso INSTANTÁNEO** por email.\n\n✅ Luego toca 'Ya pagué'.",
        "crypto": "⚡ **Paga con Cripto**\n\n🔗 Abre la mini‑app de pago abajo.\n\n💎 **Planes:** 1 mes **$13**, Lifetime **$27**.\n\n✅ Tras enviar, toca 'Ya pagué'.",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 mes: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ Tras pagar, toca 'Ya pagué'.",
        "paid_thanks": f"✅ **¡Pago recibido!** 🎉\n\n📸 Envía **captura** o **ID de transacción** a soporte.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Aviso:** Apple/Google Pay → revisa tu email. PayPal/Cripto → enlace manual.",
        "support_page": f"💬 **¿Necesitas ayuda?**\n\n🕒 *Horario:* 8:00–24:00 BST\n📨 Contacto:\n👉 {SUPPORT_CONTACT}\n\n⚡ ¡Respondemos rápido! Gracias por elegir VIP Bot. 💎",
        "reminder0": "⏰ **Recordatorio rápido**\n\nTu acceso VIP te espera. Finaliza el pago en un toque. ¿Dudas? Soporte.",
        "reminder1": "⛳ **Última oportunidad hoy**\n\nQuedan pocas plazas. Termina el pago y asegura tu acceso.",
        "membership_notice": "⏳ *Aviso de membresía*\n\nTu *VIP 1 mes* llega a *28 días*. Renueva ahora para evitar cortes.",
    },
    # FR
    "fr": {
        "welcome": "💎 **Bienvenue sur le VIP Bot !**\n\n💎 *Accédez à des milliers de créateurs chaque mois.*\n⚡ *Lien VIP envoyé par email instantanément.*\n⭐ *Modèle manquant ? Ajout sous 24–72h.*\n\n📌 Questions ? Lien KO ? Support 🔍👀",
        "select_plan": "⭐ Vous avez choisi **{plan_text}**.\n\n💳 **Apple/Google Pay :** 🚀 Accès instantané (email).\n⚡ **Crypto :** (30–60 min) envoi manuel.\n📧 **PayPal :** (30–60 min) envoi manuel.\n\n🎉 Choisissez un moyen de paiement ci‑dessous !",
        "shopify": "🚀 **Accès instantané avec Apple/Google Pay !**\n\n🎁 **Choisissez votre plan :**\n💎 Lifetime : **£20.00** 🎉\n⏳ 1 mois : **£10.00** 🌟\n\n🛒 Payez en toute sécurité et recevez **l’accès INSTANTANÉ** par email.\n\n✅ Ensuite, touchez « J’ai payé ».",
        "crypto": "⚡ **Payer en Crypto**\n\n🔗 Ouvrez la mini‑app ci‑dessous.\n\n💎 **Plans :** 1 mois **$13**, Lifetime **$27**.\n\n✅ Après envoi, touchez « J’ai payé ».",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 mois: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ Après paiement, touchez « J’ai payé ».",
        "paid_thanks": f"✅ **Paiement reçu !** 🎉\n\n📸 Envoyez une **capture** ou **ID de transaction** au support.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Note :** Apple/Google Pay → email. PayPal/Crypto → envoi manuel.",
        "support_page": f"💬 **Besoin d’aide ?**\n\n🕒 8:00–24:00 BST\n📨 Contact : {SUPPORT_CONTACT}\n\n⚡ Réponse rapide. Merci d’utiliser VIP Bot ! 💎",
        "reminder0": "⏰ **Petit rappel**\n\nVotre accès VIP vous attend. Finalisez en un clic. Support dispo.",
        "reminder1": "⛳ **Dernière chance aujourd’hui**\n\nPeu de places. Validez pour verrouiller votre accès.",
        "membership_notice": "⏳ *Alerte abonnement*\n\nVotre *VIP 1 mois* atteint *28 jours*. Renouvelez maintenant.",
    },
    # DE
    "de": {
        "welcome": "💎 **Willkommen beim VIP Bot!**\n\n💎 *Jeden Monat Zugang zu tausenden Creators.*\n⚡ *VIP‑Link sofort per E‑Mail.*\n⭐ *Wunsch‑Model fehlt? Wir fügen es in 24–72h hinzu.*\n\n📌 Fragen? Link kaputt? Support 🔍👀",
        "select_plan": "⭐ Du hast **{plan_text}** gewählt.\n\n💳 **Apple/Google Pay:** 🚀 Sofortzugang (Link per E‑Mail).\n⚡ **Krypto:** (30–60 Min.) manueller Versand.\n📧 **PayPal:** (30–60 Min.) manueller Versand.\n\n🎉 Wähle unten deine Zahlungsmethode!",
        "shopify": "🚀 **Sofortzugang mit Apple/Google Pay!**\n\n🎁 **Wähle deinen Plan:**\n💎 Lifetime: **£20.00** 🎉\n⏳ 1 Monat: **£10.00** 🌟\n\n🛒 Sicher bezahlen und **SOFORTIGEN** Zugang per E‑Mail erhalten.\n\n✅ Danach auf „Ich habe bezahlt” tippen.",
        "crypto": "⚡ **Mit Krypto zahlen**\n\n🔗 Öffne die Mini‑App unten.\n\n💎 **Pläne:** 1 Monat **$13**, Lifetime **$27**.\n\n✅ Nach dem Senden auf „Ich habe bezahlt” tippen.",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 Monat: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ Nach Zahlung „Ich habe bezahlt” tippen.",
        "paid_thanks": f"✅ **Zahlung erhalten!** 🎉\n\n📸 Sende **Screenshot** oder **Transaktions‑ID** an den Support.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Hinweis:** Apple/Google Pay → E‑Mail. PayPal/Krypto → manueller Versand.",
        "support_page": f"💬 **Brauchst du Hilfe?**\n\n🕒 8:00–24:00 BST\n📨 Kontakt: {SUPPORT_CONTACT}\n\n⚡ Danke, dass du VIP Bot nutzt! 💎",
        "reminder0": "⏰ **Kurze Erinnerung**\n\nDein VIP‑Zugang wartet. Beende die Zahlung mit einem Tipp.",
        "reminder1": "⛳ **Letzte Chance heute**\n\nSichere dir jetzt den Zugang – Plätze sind begrenzt.",
        "membership_notice": "⏳ *Mitgliedschaftshinweis*\n\nDein *1‑Monat VIP* erreicht *28 Tage*. Bitte jetzt verlängern.",
    },
    # IT
    "it": {
        "welcome": "💎 **Benvenuto nel VIP Bot!**\n\n💎 *Accesso a migliaia di creator ogni mese.*\n⚡ *Link VIP inviato subito via email.*\n⭐ *Modello mancante? Lo aggiungiamo in 24–72h.*\n\n📌 Domande? Link non funziona? Supporto 🔍👀",
        "select_plan": "⭐ Hai scelto il piano **{plan_text}**.\n\n💳 **Apple/Google Pay:** 🚀 Accesso istantaneo (link via email).\n⚡ **Cripto:** (30–60 min) invio manuale.\n📧 **PayPal:** (30–60 min) invio manuale.\n\n🎉 Scegli un metodo e accedi oggi!",
        "shopify": "🚀 **Accesso istantaneo con Apple/Google Pay!**\n\n🎁 **Scegli il tuo piano:**\n💎 Lifetime: **£20.00** 🎉\n⏳ 1 mese: **£10.00** 🌟\n\n🛒 Paga in sicurezza e ricevi **ACCESSO ISTANTANEO** via email.\n\n✅ Poi tocca 'Ho pagato'.",
        "crypto": "⚡ **Paga in Cripto**\n\n🔗 Apri la mini‑app qui sotto.\n\n💎 **Piani:** 1 mese **$13**, Lifetime **$27**.\n\n✅ Dopo il pagamento, tocca 'Ho pagato'.",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 mese: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ Dopo il pagamento, tocca 'Ho pagato'.",
        "paid_thanks": f"✅ **Pagamento ricevuto!** 🎉\n\n📸 Invia **screenshot** o **ID transazione** al supporto.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Nota:** Apple/Google Pay → email. PayPal/Cripto → invio manuale.",
        "support_page": f"💬 **Serve aiuto?**\n\n🕒 8:00–24:00 BST\n📨 Contatto: {SUPPORT_CONTACT}\n\n⚡ Rispondiamo rapidamente. Grazie per aver scelto VIP Bot! 💎",
        "reminder0": "⏰ **Promemoria veloce**\n\nIl tuo accesso VIP ti aspetta. Completa il pagamento con un tocco.",
        "reminder1": "⛳ **Ultima occasione oggi**\n\nPochi posti rimasti. Completa il pagamento ora.",
        "membership_notice": "⏳ *Avviso abbonamento*\n\nIl tuo *VIP 1 mese* è a *28 giorni*. Rinnova ora.",
    },
    # PT
    "pt": {
        "welcome": "💎 **Bem‑vindo ao VIP Bot!**\n\n💎 *Acesso a milhares de criadores todos os meses.*\n⚡ *Link VIP enviado instantaneamente por e‑mail.*\n⭐ *Não encontra o modelo? Adicionamos em 24–72h.*\n\n📌 Dúvidas? Link com problema? Suporte 🔍👀",
        "select_plan": "⭐ Você escolheu **{plan_text}**.\n\n💳 **Apple/Google Pay:** 🚀 Acesso imediato (link por e‑mail).\n⚡ **Cripto:** (30–60 min) envio manual.\n📧 **PayPal:** (30–60 min) envio manual.\n\n🎉 Escolha abaixo e acesse hoje!",
        "shopify": "🚀 **Acesso imediato com Apple/Google Pay!**\n\n🎁 **Escolha seu plano:**\n💎 Lifetime: **£20.00** 🎉\n⏳ 1 mês: **£10.00** 🌟\n\n🛒 Pague com segurança e receba **ACESSO INSTANTÂNEO** por e‑mail.\n\n✅ Depois toque 'Paguei'.",
        "crypto": "⚡ **Pague com Cripto**\n\n🔗 Abra a mini‑app abaixo.\n\n💎 **Planos:** 1 mês **$13**, Lifetime **$27**.\n\n✅ Após enviar, toque 'Paguei'.",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 mês: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ Após o pagamento, toque 'Paguei'.",
        "paid_thanks": f"✅ **Pagamento recebido!** 🎉\n\n📸 Envie **captura** ou **ID da transação** ao suporte.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Nota:** Apple/Google Pay → e‑mail. PayPal/Cripto → envio manual.",
        "support_page": f"💬 **Precisa de ajuda?**\n\n🕒 8:00–24:00 BST\n📨 Contato: {SUPPORT_CONTACT}\n\n⚡ Obrigado por escolher o VIP Bot! 💎",
        "reminder0": "⏰ **Lembrete rápido**\n\nSeu acesso VIP está te esperando. Conclua o pagamento.",
        "reminder1": "⛳ **Última chance hoje**\n\nGaranta seu acesso agora. Vagas limitadas.",
        "membership_notice": "⏳ *Aviso de assinatura*\n\nSeu *VIP 1 mês* chegou a *28 dias*. Renove agora.",
    },
    # RU
    "ru": {
        "welcome": "💎 **Добро пожаловать в VIP Bot!**\n\n💎 *Доступ к тысячам создателей каждый месяц.*\n⚡ *VIP‑ссылка приходит на email мгновенно.*\n⭐ *Нет нужной модели? Добавим за 24–72ч.*\n\n📌 Вопросы? Ссылка не работает? Поддержка 🔍👀",
        "select_plan": "⭐ Вы выбрали план **{plan_text}**.\n\n💳 **Apple/Google Pay:** 🚀 Мгновенный доступ (ссылка на почту).\n⚡ **Крипто:** (30–60 мин) вручную.\n📧 **PayPal:** (30–60 мин) вручную.\n\n🎉 Выберите способ оплаты ниже!",
        "shopify": "🚀 **Мгновенный доступ через Apple/Google Pay!**\n\n🎁 **Выберите план:**\n💎 Lifetime: **£20.00** 🎉\n⏳ 1 месяц: **£10.00** 🌟\n\n🛒 Оплатите безопасно и получите **МГНОВЕННЫЙ** доступ на email.\n\n✅ Затем нажмите «Я оплатил».",
        "crypto": "⚡ **Оплата криптовалютой**\n\n🔗 Откройте мини‑приложение ниже.\n\n💎 **Планы:** 1 месяц **$13**, Lifetime **$27**.\n\n✅ После перевода нажмите «Я оплатил».",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 месяц: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ После оплаты нажмите «Я оплатил».",
        "paid_thanks": f"✅ **Оплата получена!** 🎉\n\n📸 Пришлите **скрин** или **ID транзакции** в поддержку.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Замечание:** Apple/Google Pay → email. PayPal/Крипто → вручную.",
        "support_page": f"💬 **Нужна помощь?**\n\n🕒 8:00–24:00 BST\n📨 Контакт: {SUPPORT_CONTACT}\n\n⚡ Спасибо, что выбираете VIP Bot! 💎",
        "reminder0": "⏰ **Напоминание**\n\nВаш VIP-доступ ждёт. Завершите оплату в один клик.",
        "reminder1": "⛳ **Последний шанс сегодня**\n\nМест мало. Завершите платеж сейчас.",
        "membership_notice": "⏳ *Оповещение о подписке*\n\nВаш *VIP на 1 месяц* достиг *28 дней*. Продлите сейчас.",
    },
    # TR
    "tr": {
        "welcome": "💎 **VIP Bot'a hoş geldiniz!**\n\n💎 *Her ay binlerce içerik üreticisine erişim.*\n⚡ *VIP bağlantısı anında e‑postanıza gelir.*\n⭐ *Aradığınız model yok mu? 24–72 saatte ekleriz.*\n\n📌 Sorular mı var? Link çalışmıyor mu? Destek 🔍👀",
        "select_plan": "⭐ **{plan_text}** planını seçtiniz.\n\n💳 **Apple/Google Pay:** 🚀 Anında erişim (e‑posta).\n⚡ **Kripto:** (30–60 dk) manuel gönderim.\n📧 **PayPal:** (30–60 dk) manuel gönderim.\n\n🎉 Aşağıdan yöntemi seçip bugün erişin!",
        "shopify": "🚀 **Apple/Google Pay ile anında erişim!**\n\n🎁 **Planınızı seçin:**\n💎 Lifetime: **£20.00** 🎉\n⏳ 1 Ay: **£10.00** 🌟\n\n🛒 Güvenle ödeyin ve **ANINDA** e‑posta ile alın.\n\n✅ Sonra 'Ödeme yaptım' deyin.",
        "crypto": "⚡ **Kripto ile öde**\n\n🔗 Aşağıdaki mini‑uygulamayı açın.\n\n💎 **Planlar:** 1 Ay **$13**, Lifetime **$27**.\n\n✅ Gönderdikten sonra 'Ödeme yaptım' tuşuna basın.",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 Ay: **£10.00** 🌟\n💎 Lifetime: **£20.00** 🎉\n\n✅ Ödeme sonrası 'Ödeme yaptım' tuşuna basın.",
        "paid_thanks": f"✅ **Ödeme alındı!** 🎉\n\n📸 Lütfen **ekran görüntüsü** veya **işlem kimliği** gönderin.\n👉 {SUPPORT_CONTACT}\n\n⚡ **Not:** Apple/Google Pay → e‑posta. PayPal/Kripto → manuel.",
        "support_page": f"💬 **Yardım mı lazım?**\n\n🕒 8:00–24:00 BST\n📨 İletişim: {SUPPORT_CONTACT}\n\n⚡ VIP Bot'u tercih ettiğiniz için teşekkürler! 💎",
        "reminder0": "⏰ **Kısa hatırlatma**\n\nVIP erişiminiz hazır. Ödemeyi tamamlayın.",
        "reminder1": "⛳ **Bugün son fırsat**\n\nSayı az. Şimdi tamamlayın.",
        "membership_notice": "⏳ *Üyelik bildirimi*\n\n*1 Aylık VIP* *28. gün*e ulaştı. Şimdi yenileyin.",
    },
    # AR (RTL)
    "ar": {
        "welcome": "💎 **مرحبًا بك في VIP Bot!**\n\n💎 *وصول إلى آلاف الصنّاع كل شهر.*\n⚡ *رابط VIP يصل لبريدك فورًا.*\n⭐ *لا تجد الموديل؟ نضيفه خلال 24–72 ساعة.*\n\n📌 أسئلة؟ الرابط لا يعمل؟ الدعم 🔍👀",
        "select_plan": "⭐ لقد اخترت باقة **{plan_text}**.\n\n💳 **Apple/Google Pay:** 🚀 وصول فوري (رابط عبر البريد).\n⚡ **العملات الرقمية:** (30–60 دقيقة) إرسال يدوي.\n📧 **باي بال:** (30–60 دقيقة) إرسال يدوي.\n\n🎉 اختر طريقة الدفع أدناه واحصل على الوصول اليوم!",
        "shopify": "🚀 **وصول فوري عبر Apple/Google Pay!**\n\n🎁 **اختر خطتك:**\n💎 مدى الحياة: **£20.00** 🎉\n⏳ شهر واحد: **£10.00** 🌟\n\n🛒 ادفع بأمان واحصل على **وصول فوري** عبر البريد.\n\n✅ بعد الدفع اضغط «دفعت».",
        "crypto": "⚡ **ادفع بالعملات الرقمية**\n\n🔗 افتح تطبيق الدفع المصغّر بالأسفل.\n\n💎 **الخطط:** شهر **$13**، مدى الحياة **$27**.\n\n✅ بعد الإرسال اضغط «دفعت».",
        "paypal": f"💸 **باي بال**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 شهر: **£10.00** 🌟\n💎 مدى الحياة: **£20.00** 🎉\n\n✅ بعد الدفع اضغط «دفعت».",
        "paid_thanks": f"✅ **تم استلام الدفع!** 🎉\n\n📸 أرسل **لقطة شاشة** أو **معرّف العملية** للدعم.\n👉 {SUPPORT_CONTACT}\n\n⚡ **هام:** Apple/Google Pay → البريد. باي بال/العملات → إرسال يدوي.",
        "support_page": f"💬 **بحاجة لمساعدة؟**\n\n🕒 8:00–24:00 BST\n📨 تواصل: {SUPPORT_CONTACT}\n\n⚡ شكرًا لاختيارك VIP Bot! 💎",
        "reminder0": "⏰ **تذكير سريع**\n\nوصولك VIP بانتظارك — أكمل الدفع الآن.",
        "reminder1": "⛳ **الفرصة الأخيرة اليوم**\n\nالأماكن محدودة. أكمل الدفع الآن.",
        "membership_notice": "⏳ *تنبيه العضوية*\n\nوصول *VIP لشهر* بلغ *28 يومًا*. جدّد الآن.",
    },
    # UR (RTL)
    "ur": {
        "welcome": "💎 **VIP Bot میں خوش آمدید!**\n\n💎 *ہر ماہ ہزاروں کری ایٹرز تک رسائی.*\n⚡ *VIP لنک فوراً ای میل میں ملتا ہے.*\n⭐ *پسندیدہ ماڈل نہیں؟ 24–72 گھنٹے میں شامل کریں گے.*\n\n📌 سوالات؟ لنک مسئلہ؟ سپورٹ 🔍👀",
        "select_plan": "⭐ آپ نے **{plan_text}** پلان منتخب کیا ہے۔\n\n💳 **Apple/Google Pay:** 🚀 فوری رسائی (لنک بذریعہ ای میل).\n⚡ **کرپٹو:** (30–60 منٹ) دستی بھیجاؤ.\n📧 **پے پال:** (30–60 منٹ) دستی بھیجاؤ.\n\n🎉 ادائیگی کا طریقہ منتخب کریں!",
        "shopify": "🚀 **Apple/Google Pay کے ساتھ فوری رسائی!**\n\n🎁 **اپنا پلان منتخب کریں:**\n💎 لائف ٹائم: **£20.00** 🎉\n⏳ 1 مہینہ: **£10.00** 🌟\n\n🛒 محفوظ ادائیگی کریں اور **فوری رسائی** ای میل میں پائیں۔\n\n✅ ادائیگی کے بعد 'میں نے ادائیگی کر دی' دبائیں۔",
        "crypto": "⚡ **کرپٹو کے ذریعے ادائیگی**\n\n🔗 نیچے منی ایپ کھولیں۔\n\n💎 **پلان:** 1 مہینہ **$13**، لائف ٹائم **$27**۔\n\n✅ ادائیگی کے بعد 'میں نے ادائیگی کر دی' دبائیں۔",
        "paypal": f"💸 **پے پال**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 مہینہ: **£10.00** 🌟\n💎 لائف ٹائم: **£20.00** 🎉\n\n✅ ادائیگی کے بعد 'میں نے ادائیگی کر دی' دبائیں۔",
        "paid_thanks": f"✅ **ادائیگی موصول!** 🎉\n\n📸 براہ کرم **اسکرین شاٹ** یا **ٹرانزیکشن آئی ڈی** بھیجیں۔\n👉 {SUPPORT_CONTACT}\n\n⚡ **نوٹ:** Apple/Google Pay → ای میل۔ PayPal/کرپٹو → دستی بھیجاؤ.",
        "support_page": f"💬 **مدد درکار ہے؟**\n\n🕒 8:00–24:00 BST\n📨 رابطہ: {SUPPORT_CONTACT}\n\n⚡ VIP Bot منتخب کرنے کا شکریہ! 💎",
        "reminder0": "⏰ **مختصر یاددہانی**\n\nآپ کا VIP ایکسیس تیار ہے — ادائیگی مکمل کریں۔",
        "reminder1": "⛳ **آج آخری موقع**\n\nجگہیں محدود ہیں۔ ابھی ادائیگی مکمل کریں۔",
        "membership_notice": "⏳ *ممبرشپ نوٹس*\n\nآپ کا *1 ماہ VIP* *28 دن* کو پہنچ گیا ہے۔ ابھی تجدید کریں۔",
    },
    # HI
    "hi": {
        "welcome": "💎 **VIP Bot में आपका स्वागत है!**\n\n💎 *हर महीने हजारों क्रिएटर्स तक पहुँच।*\n⚡ *VIP लिंक तुरंत ईमेल पर।*\n⭐ *चाहा मॉडल नहीं? 24–72 घंटों में जोड़ देंगे।*\n\n📌 सवाल? लिंक काम नहीं कर रहा? सपोर्ट 🔍👀",
        "select_plan": "⭐ आपने **{plan_text}** प्लान चुना है।\n\n💳 **Apple/Google Pay:** 🚀 तुरंत एक्सेस (ईमेल)।\n⚡ **क्रिप्टो:** (30–60 मिनट) मैनुअल।\n📧 **पेपल:** (30–60 मिनट) मैनुअल।\n\n🎉 नीचे से भुगतान विधि चुनें!",
        "shopify": "🚀 **Apple/Google Pay से तुरंत एक्सेस!**\n\n🎁 **अपना प्लान चुनें:**\n💎 लाइफटाइम: **£20.00** 🎉\n⏳ 1 महीना: **£10.00** 🌟\n\n🛒 सुरक्षित भुगतान करें और **तुरंत** ईमेल पर पाएँ।\n\n✅ फिर 'मैंने भुगतान किया' दबाएँ।",
        "crypto": "⚡ **क्रिप्टो से भुगतान**\n\n🔗 नीचे मिनी‑ऐप खोलें।\n\n💎 **प्लान:** 1 महीना **$13**, लाइफटाइम **$27**।\n\n✅ भुगतान के बाद 'मैंने भुगतान किया' दबाएँ।",
        "paypal": f"💸 **पेपल**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 महीना: **£10.00** 🌟\n💎 लाइफटाइम: **£20.00** 🎉\n\n✅ भुगतान के बाद 'मैंने भुगतान किया' दबाएँ।",
        "paid_thanks": f"✅ **भुगतान प्राप्त!** 🎉\n\n📸 कृपया **स्क्रीनशॉट** या **ट्रांज़ैक्शन आईडी** भेजें।\n👉 {SUPPORT_CONTACT}\n\n⚡ **नोट:** Apple/Google Pay → ईमेल। PayPal/क्रिप्टो → मैनुअल।",
        "support_page": f"💬 **मदद चाहिए?**\n\n🕒 8:00–24:00 BST\n📨 संपर्क: {SUPPORT_CONTACT}\n\n⚡ VIP Bot चुनने के लिए धन्यवाद! 💎",
        "reminder0": "⏰ **त्वरित याद दिलाना**\n\nआपकी VIP एक्सेस तैयार है — भुगतान पूरा करें।",
        "reminder1": "⛳ **आज आख़िरी मौका**\n\nसीटें सीमित हैं। अभी भुगतान करें।",
        "membership_notice": "⏳ *मेंबरशिप सूचना*\n\nआपका *1‑महीना VIP* *28 दिन* पर है। अभी रिन्यू करें।",
    },
    # HE (RTL)
    "he": {
        "welcome": "💎 **ברוך הבא ל‑VIP Bot!**\n\n💎 *גישה לאלפי יוצרים בכל חודש.*\n⚡ *קישור VIP נשלח מיידית למייל.*\n⭐ *לא מוצא מודל? נוסיף תוך 24–72 שעות.*\n\n📌 שאלות? קישור לא עובד? תמיכה 🔍👀",
        "select_plan": "⭐ בחרת בתוכנית **{plan_text}**.\n\n💳 **Apple/Google Pay:** 🚀 גישה מיידית (קישור במייל).\n⚡ **קריפטו:** (30–60 דק׳) שליחה ידנית.\n📧 **PayPal:** (30–60 דק׳) שליחה ידנית.\n\n🎉 בחר אמצעי תשלום והתחל היום!",
        "shopify": "🚀 **גישה מיידית עם Apple/Google Pay!**\n\n🎁 **בחר תוכנית:**\n💎 לכל החיים: **£20.00** 🎉\n⏳ חודש: **£10.00** 🌟\n\n🛒 שלם בבטחה וקבל **גישה מיידית** למייל.\n\n✅ לאחר התשלום לחץ 'שילמתי'.",
        "crypto": "⚡ **תשלום בקריפטו**\n\n🔗 פתח את המיני‑אפליקציה למטה.\n\n💎 **תוכניות:** חודש **$13**, לכל החיים **$27**.\n\n✅ לאחר השליחה לחץ 'שילמתי'.",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 חודש: **£10.00** 🌟\n💎 לכל החיים: **£20.00** 🎉\n\n✅ לאחר התשלום לחץ 'שילמתי'.",
        "paid_thanks": f"✅ **התשלום התקבל!** 🎉\n\n📸 שלח **צילום מסך** או **מזהה עסקה** לתמיכה.\n👉 {SUPPORT_CONTACT}\n\n⚡ **שימו לב:** Apple/Google Pay → מייל. PayPal/קריפטו → שליחה ידנית.",
        "support_page": f"💬 **צריך עזרה?**\n\n🕒 8:00–24:00 BST\n📨 יצירת קשר: {SUPPORT_CONTACT}\n\n⚡ תודה שבחרת ב‑VIP Bot! 💎",
        "reminder0": "⏰ **תזכורת מהירה**\n\nהגישה ל‑VIP ממתינה — השלם תשלום.",
        "reminder1": "⛳ **הזדמנות אחרונה להיום**\n\nהמלאי מוגבל. השלם עכשיו.",
        "membership_notice": "⏳ *הודעת מנוי*\n\n*VIP לחודש* הגיע ל‑*28 ימים*. חדש עכשיו.",
    },
    # ZH-HANS
    "zh-Hans": {
        "welcome": "💎 **欢迎来到 VIP Bot！**\n\n💎 *每月畅享数千位创作者内容。*\n⚡ *VIP 链接将立即发送到您的邮箱。*\n⭐ *没有看到想要的？我们会在 24–72 小时内添加。*\n\n📌 有问题？链接无法使用？联系客服 🔍👀",
        "select_plan": "⭐ 您已选择 **{plan_text}** 套餐。\n\n💳 **Apple/Google Pay：** 🚀 即时访问（邮件发送链接）。\n⚡ **加密货币：**（30–60 分钟）人工发送。\n📧 **PayPal：**（30–60 分钟）人工发送。\n\n🎉 选择下方支付方式，今天即可开通！",
        "shopify": "🚀 **使用 Apple/Google Pay 即时访问！**\n\n🎁 **选择您的套餐：**\n💎 终身：**£20.00** 🎉\n⏳ 1 个月：**£10.00** 🌟\n\n🛒 安全支付，**即时**收取邮箱链接。\n\n✅ 支付完成后，点击“我已付款”。",
        "crypto": "⚡ **加密货币支付**\n\n🔗 在 Telegram 内打开下方小程序。\n\n💎 **套餐：** 1 个月 **$13**，终身 **$27**。\n\n✅ 支付后点击“我已付款”。",
        "paypal": f"💸 **PayPal**\n\n`{PAYMENT_INFO['paypal']}`\n\n💎 1 个月：**£10.00** 🌟\n💎 终身：**£20.00** 🎉\n\n✅ 支付后点击“我已付款”。",
        "paid_thanks": f"✅ **已收到付款！** 🎉\n\n📸 请发送**截图**或**交易号**给客服。\n👉 {SUPPORT_CONTACT}\n\n⚡ **提示：** Apple/Google Pay → 邮箱查收；PayPal/加密货币 → 人工发送。",
        "support_page": f"💬 **需要帮助？**\n\n🕒 8:00–24:00（BST）\n📨 联系方式：{SUPPORT_CONTACT}\n\n⚡ 感谢选择 VIP Bot！💎",
        "reminder0": "⏰ **小提醒**\n\n您的 VIP 访问已就绪—现在完成付款即可开通。",
        "reminder1": "⛳ **今天最后机会**\n\n名额有限，尽快完成付款锁定资格。",
        "membership_notice": "⏳ *会员提醒*\n\n您的 *1 个月 VIP* 已到 *第 28 天*。请立即续费避免中断。",
    },
}

def tr(lang: str, key: str, **kwargs) -> str:
    base = L.get(lang, L["en"]).get(key) or L["en"].get(key, key)
    return base.format(**kwargs) if kwargs else base

def tx(lang: str, key: str, **kwargs) -> str:
    base = TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, ""))
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
    "users": {},        # {user_id: {lang, last_plan, last_method, email, coupon, ref, awaiting_proof, username}}
    "leads": {},        # {user_id: {plan, method, started_at, reminded:[idx...], active:bool, snoozed_until}}
    "events": [],       # list of dicts (ts, user_id, type, meta)
    "memberships": {},  # {user_id: {plan, activated_at, expiry_notified}}
}
def load_store():
    global STORE
    try:
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                STORE = json.load(f)
            for k in ("users", "leads", "events", "memberships"):
                STORE.setdefault(k, {} if k != "events" else [])
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

def activate_membership(user_id: int, plan: str):
    STORE["memberships"][str(user_id)] = {
        "plan": plan,  # "1_month" | "lifetime"
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "expiry_notified": False,
    }
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

# Rate limiting to prevent double-tap spam
RL_BUCKET: Dict[int, float] = {}
def ratelimited(user_id: int, seconds: int = 1) -> bool:
    last = RL_BUCKET.get(user_id, 0.0)
    now = datetime.now().timestamp()
    if now - last < seconds:
        return True
    RL_BUCKET[user_id] = now
    return False

# =====================
# Keyboards
# =====================
def main_menu(lang="en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],   # keep exact labels
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
        [safe_button(tr(lang, "open_crypto"), link, as_webapp=True)],
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
    rows, row = [], []
    for code in SUPPORTED_LANGS:
        label = f"{FLAGS.get(code,'🏳️')} {code}"
        row.append(InlineKeyboardButton(label, callback_data=f"lang_{code}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("Close", callback_data="back")])
    return InlineKeyboardMarkup(rows)

def detect_lang(update: Update) -> str:
    raw = (update.effective_user.language_code or "en")
    code = raw.split("-")[0]
    if raw.lower().startswith("zh"):
        code = "zh-Hans"
    return code if code in L else "en"

def normalize_coupon(text: str) -> Optional[str]:
    if not text: return None
    t = text.strip().upper()
    return t if t in COUPONS else None

# Reminder scheduler (1h & 24h) + 28-day membership expiry

import asyncio
from datetime import datetime, timedelta

ADMIN_ID = 123456789  # replace with your Telegram user ID

# Store pending payments and active memberships
pending_payments = {}  # user_id: time_of_order
active_memberships = {}  # user_id: expiry_datetime


async def schedule_payment_reminders(context, user_id):
    """Schedules 1h and 24h reminders for pending payments."""
    now = datetime.utcnow()
    pending_payments[user_id] = now
    print(f"[Reminder] Payment tracking started for {user_id}")

    # Wait 1 hour
    await asyncio.sleep(3600)
    if user_id in pending_payments:
        await context.bot.send_message(
            chat_id=user_id,
            text="⏳ Hey! Just a reminder to complete your payment to access VIP 🚀"
        )

    # Wait until 24 hours from start
    await asyncio.sleep(23 * 3600)
    if user_id in pending_payments:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ 24 hours have passed! Complete your payment now before the offer expires."
        )
        # Optional: Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"User {user_id} still hasn’t paid after 24 hours."
        )


async def schedule_membership_expiry(context, user_id):
    """Schedules a 28-day membership expiry notification."""
    expiry_time = datetime.utcnow() + timedelta(days=28)
    active_memberships[user_id] = expiry_time
    print(f"[Expiry] Membership for {user_id} will expire on {expiry_time}")

    # Wait 28 days
    await asyncio.sleep(28 * 24 * 3600)
    if user_id in active_memberships:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Your 1-month VIP access is about to expire. Renew now to keep your benefits!"
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ User {user_id}'s membership is expiring today."
        )
        del active_memberships[user_id]


# Example: Call these in your existing payment flow
async def handle_order(update, context):
    user_id = update.effective_user.id
    # Your existing order logic here...
    await schedule_payment_reminders(context, user_id)


async def confirm_payment(update, context):
    user_id = update.effective_user.id
    # Your existing payment confirmation logic here...
    if "1-month" in update.message.text.lower():
        await schedule_membership_expiry(context, user_id)
    if user_id in pending_payments:
        del pending_payments[user_id]
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
    telegram_app.add_handler(CommandHandler("lang", lang_cmd, block=False))
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

    # Optional: uptime ping
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

    # Start bot + reminder loop
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if ratelimited(user.id): return

    # Persist username for admin notifications
    set_user_field(user.id, "username", user.username or "No Username")

    # Referral tracking from /start args
    ref = None
    if context.args:
        ref = context.args[0][:32]
        set_user_field(user.id, "ref", ref)

    # Language auto-detect
    lang = detect_lang(update)
    set_user_lang(user.id, lang)

    # Sticky cart hint: if lead active, show resume button
    lead = STORE["leads"].get(str(user.id))
    if lead and lead.get("active"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 Month (£10.00)", callback_data="select_1_month")],
            [InlineKeyboardButton("Lifetime (£20.00)", callback_data="select_lifetime")],
            [InlineKeyboardButton(tr(lang, "resume"), callback_data="resume_checkout")],
            [InlineKeyboardButton(tr(lang, "menu_support"), callback_data="support")],
        ])
    else:
        kb = main_menu(lang)

    await update.effective_message.reply_text(
        tx(lang, "welcome"),  # translated welcome (fallback to your original)
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
    await update.effective_message.reply_text(
        "*Terms & Notes*\n"
        "• Access is for personal use only; redistribution may lead to a ban\n"
        "• Refunds assessed case‑by‑case if access was not delivered\n"
        "• By purchasing, you accept these terms\n",
        parse_mode=ParseMode.MARKDOWN
    )

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"Your ID: `{update.effective_user.id}`", parse_mode=ParseMode.MARKDOWN)

async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(tr(user_lang(update.effective_user.id), "choose_language"), reply_markup=language_menu())

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

    await q.edit_message_text(
        text=tx(lang, "select_plan", plan_text=plan_text),
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
    set_user_field(user.id, "last_plan", plan)
    set_user_field(user.id, "last_method", method)
    lead = STORE["leads"].setdefault(str(user.id), {"active": True})
    lead["method"] = method
    save_store()

    context.user_data["plan_text"] = "LIFETIME" if plan == "lifetime" else "1 MONTH"
    context.user_data["method"] = method

    coupon = STORE["users"].get(str(user.id), {}).get("coupon")

    if method == "shopify":
        msg = tx(lang, "shopify")
        kb = shopify_menu_webapp(lang, coupon=coupon)
    elif method == "crypto":
        msg = tx(lang, "crypto")
        kb = crypto_menu(lang)
    elif method == "paypal":
        msg = tx(lang, "paypal")
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
    lang = user_lang(user.id)
    plan_text = context.user_data.get("plan_text", "N/A")
    method = context.user_data.get("method", "N/A")
    username = q.from_user.username or "No Username"
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Close the lead (stop reminders)
    close_lead(user.id)

    # Activate membership if it's a 1-month plan
    plan_key = STORE["users"].get(str(user.id), {}).get("last_plan")
    if plan_key == "1_month":
        activate_membership(user.id, plan_key)

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

    await q.edit_message_text(tx(lang, "paid_thanks"), parse_mode=ParseMode.MARKDOWN)
    set_user_field(user.id, "awaiting_proof", True)
    log_event(user.id, "paid_clicked", {"method": method})

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = user_lang(q.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "change_language"), callback_data="lang_menu")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back")],
    ])
    await q.edit_message_text(tx(lang, "support_page"), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

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
        tx(lang, "select_plan", plan_text=("LIFETIME" if plan == "lifetime" else "1 MONTH")),
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
        f"Username: {u.get('username') if u else '-'}\n"
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
