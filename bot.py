import json
import os
import time
import logging
import threading
import re
import random
import asyncio
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ====================== CONFIGURATION ======================
TELEGRAM_BOT_TOKEN = '8693146137:AAH62XxM1QQ_NXyFH-NTibvWaujow8ExdAg'
ADMIN_ID = 8571870755  # <-- Replace with your Telegram user ID
SEEN_FILE = 'seen_comments.json'
CONFIG_FILE = 'config.json'
PAYMENT_QR_PATH = 'payment_qr.jpg'  # Optional: path to a QR code image

# ====================== GLOBAL REFERENCES ======================
# These will be set in main()
main_loop = None
bot_app = None

# ====================== MULTIPLE GOOGLE PROJECTS ======================
def get_all_credentials():
    creds_list = []
    if os.path.exists("credentials.json"):
        creds_list.append("credentials.json")
    i = 1
    while True:
        filename = f"credentials{i}.json"
        if os.path.exists(filename):
            creds_list.append(filename)
            i += 1
        else:
            break
    return creds_list

CREDENTIALS_LIST = get_all_credentials()
print(f"\n✅ {len(CREDENTIALS_LIST)} Google Projects Loaded!")
for i, file in enumerate(CREDENTIALS_LIST, 1):
    print(f"   → {file}")

# ====================== BILINGUAL TEXTS ======================
TEXTS = {
    'en': {
        'welcome': "✅ *Welcome!* Please choose your language:",
        'lang_set': "Language set to English. Now please provide your email address (the one linked to your YouTube channel):",
        'email_received': "📧 Email received. Admin will verify it. You'll be notified once approved.",
        'verification_success': "✅ *Verification successful!* You can now use the bot.\n\n🔑 First, press **Login with YouTube** to connect your account.\n\n{}",
        'verification_failed': "❌ Verification failed. Please contact admin.",
        'not_verified': "⚠️ Your account is not yet verified. Please wait for admin approval or contact support.",
        'already_verified': "✅ You are already verified. Use the buttons below.",
        'login_first': "🔑 First, press **Login with YouTube** to connect your account.",
        'video_added': "✅ Video added!\nReply: {}",
        'no_videos': "📭 No videos added yet.",
        'video_list': "📋 *Your Videos:*\n",
        'delete_prompt': "Reply with the number to delete.",
        'invalid_number': "❌ Invalid number.",
        'deleted': "🗑️ Deleted video: {}",
        'total_replies': "📊 *Lifetime replies sent:* {}",
        'credits_status': "💰 *Today's remaining replies:* {} / {}\n📅 Resets at midnight.",
        'subscription_prompt': "📦 *Choose a plan (valid for 1 month):*\n₹99 → 150 replies/day\n₹199 → 300 replies/day\n₹299 → 500 replies/day\n\nSend the plan name (e.g., `₹99`) to proceed.",
        'invalid_plan': "❌ Invalid plan. Choose ₹99, ₹199, or ₹299.",
        'payment_instruction': "💳 *Plan {} selected.*\nPlease send a screenshot of the payment to this UPI ID: `you@upi` (or scan the QR below).\nAfter payment, send the screenshot here.",
        'payment_waiting': "⏳ Payment screenshot received. Waiting for admin approval.",
        'payment_approved': "✅ *Plan {} activated!*\nDaily replies: {}\nValid until: {}",
        'payment_rejected': "❌ Payment verification failed. Please contact admin.",
        'logout_success': "👋 Logged out. All your data has been removed.\nUse /start to begin again.",
        'unknown': "Please use the buttons below.\nIf you need help, press /start.",
        'start_reply': "✅ **Reply Started!** Now auto-reply will work on new comments only.",
        'stop_reply': "🛑 **Auto Reply stopped!**",
        'youtube_login_prompt': "🔗 Click the link, allow access, then copy the code and paste it here.",
        'youtube_success': "✅ **YouTube connected!** Now you can add videos.",
        'youtube_fail': "❌ Invalid code: {}",
        'add_video_prompt': "📎 Send the YouTube video link:",
        'add_reply_prompt': "✍️ Send the reply message (e.g., 'Thanks for watching ❤️'):",
        'invalid_link': "❌ Invalid link. Send a proper YouTube URL.",
        'no_credits': "⚠️ Your daily reply credits are exhausted. Please upgrade your plan to continue auto-replying.",
        'credits_zero_alert': "⚠️ You have used all your daily reply credits. Auto-reply will pause until tomorrow or until you upgrade.\n\nTo get more replies, press 💳 Subscription.",
        'admin_approve_help': "Use /approve <user_id> <plan> to activate subscription.\nExample: /approve 123456789 ₹99",
        'payment_already_waiting': "Your payment is already being verified. Please wait for admin approval.",
        'pending_verifications': "📋 *Pending verifications:*\n",
        'no_pending': "No pending verifications.",
        'verify_help': "Use /verify <user_id> [optional message] to approve email.",
        'my_plan': "📋 *Your current plan:*\n\nPlan: {}\nDaily replies: {}\nStatus: ✅ Active\nValid until: {}\n\nTo upgrade, use the 💳 Subscription button.",
        'free_plan': "📋 *Your current plan:*\n\nPlan: Free\nDaily replies: 10\nStatus: ✅ Active\nValid until: Unlimited\n\nTo get more replies per day, subscribe using the 💳 Subscription button.",
        'expired_plan': "⚠️ Your subscription has expired. You are now on the Free plan (10 replies/day).\nTo renew, use the 💳 Subscription button.",
        'projects_list': "📁 *Available Google Projects:*\n{}",
        'choose_project': "🔑 Please select the Google project you want to use for YouTube login:",
        'project_selected': "✅ You selected: {}\nNow click the link below to log in with YouTube.",
    },
    'hi': {
        'welcome': "✅ *स्वागत है!* कृपया अपनी भाषा चुनें:",
        'lang_set': "भाषा हिंदी पर सेट हो गई। अब कृपया अपना ईमेल पता दें (जो आपके YouTube चैनल से जुड़ा है):",
        'email_received': "📧 ईमेल प्राप्त हो गया। एडमिन इसे सत्यापित करेंगे। अनुमति मिलने पर आपको सूचित कर दिया जाएगा।",
        'verification_success': "✅ *सत्यापन सफल!* अब आप बॉट का उपयोग कर सकते हैं।\n\n🔑 पहले **Login with YouTube** बटन दबाकर अपना अकाउंट कनेक्ट करें।\n\n{}",
        'verification_failed': "❌ सत्यापन विफल। कृपया एडमिन से संपर्क करें।",
        'not_verified': "⚠️ आपका अकाउंट अभी सत्यापित नहीं है। कृपया एडमिन की अनुमति का इंतजार करें या सहायता लें।",
        'already_verified': "✅ आप पहले से सत्यापित हैं। नीचे दिए गए बटन का उपयोग करें।",
        'login_first': "🔑 पहले **Login with YouTube** बटन दबाकर अपना YouTube अकाउंट कनेक्ट करें।",
        'video_added': "✅ वीडियो जोड़ दी गई!\nजवाब: {}",
        'no_videos': "📭 अभी कोई वीडियो नहीं जोड़ी गई।",
        'video_list': "📋 *आपकी वीडियोस:*\n",
        'delete_prompt': "हटाने के लिए नंबर भेजें।",
        'invalid_number': "❌ गलत नंबर।",
        'deleted': "🗑️ वीडियो हटा दी: {}",
        'total_replies': "📊 *अब तक भेजे गए जवाब:* {}",
        'credits_status': "💰 *आज बचे हुए जवाब:* {} / {}\n📅 आधी रात को रीसेट होगा।",
        'subscription_prompt': "📦 *प्लान चुनें (1 महीने के लिए वैध):*\n₹99 → 150 जवाब/दिन\n₹199 → 300 जवाब/दिन\n₹299 → 500 जवाब/दिन\n\nप्लान का नाम भेजें (जैसे `₹99`)।",
        'invalid_plan': "❌ गलत प्लान। ₹99, ₹199, या ₹299 चुनें।",
        'payment_instruction': "💳 *प्लान {} चुना गया।*\nकृपया इस UPI ID पर भुगतान का स्क्रीनशॉट भेजें: `you@upi` (या नीचे QR स्कैन करें)।\nभुगतान के बाद स्क्रीनशॉट यहाँ भेजें।",
        'payment_waiting': "⏳ भुगतान का स्क्रीनशॉट मिल गया। एडमिन से अनुमति की प्रतीक्षा है।",
        'payment_approved': "✅ *प्लान {} सक्रिय कर दिया गया!*\nदैनिक जवाब: {}\nवैधता: {} तक",
        'payment_rejected': "❌ भुगतान सत्यापन विफल। कृपया एडमिन से संपर्क करें।",
        'logout_success': "👋 लॉगआउट हो गया। आपका सारा डेटा हटा दिया गया है।\nफिर से शुरू करने के लिए /start दबाएँ।",
        'unknown': "कृपया नीचे दिए गए बटन का उपयोग करें।\nसहायता के लिए /start दबाएँ।",
        'start_reply': "✅ **जवाब शुरू हो गया!** अब ऑटो रिप्लाई केवल नए कमेंट्स पर काम करेगा।",
        'stop_reply': "🛑 **ऑटो रिप्लाई बंद हो गया!**",
        'youtube_login_prompt': "🔗 लिंक पर क्लिक करें, अनुमति दें, फिर यहाँ कोड कॉपी करके पेस्ट करें।",
        'youtube_success': "✅ **YouTube कनेक्ट हो गया!** अब आप वीडियो जोड़ सकते हैं।",
        'youtube_fail': "❌ गलत कोड: {}",
        'add_video_prompt': "📎 YouTube वीडियो का लिंक भेजें:",
        'add_reply_prompt': "✍️ जवाब का मैसेज भेजें (जैसे 'देखने के लिए धन्यवाद ❤️'):",
        'invalid_link': "❌ गलत लिंक। सही YouTube URL भेजें।",
        'no_credits': "⚠️ आपके दैनिक रिप्लाई क्रेडिट समाप्त हो गए हैं। जारी रखने के लिए कृपया अपग्रेड करें।",
        'credits_zero_alert': "⚠️ आपने सभी दैनिक रिप्लाई क्रेडिट का उपयोग कर लिया है। ऑटो-रिप्लाई कल तक या अपग्रेड होने तक रुक जाएगा।\n\nअधिक रिप्लाई के लिए 💳 Subscription दबाएँ।",
        'admin_approve_help': "सब्सक्रिप्शन सक्रिय करने के लिए /approve <user_id> <plan> का उपयोग करें।\nउदाहरण: /approve 123456789 ₹99",
        'payment_already_waiting': "आपका भुगतान पहले से ही सत्यापन की प्रक्रिया में है। कृपया एडमिन की अनुमति का इंतजार करें।",
        'pending_verifications': "📋 *लंबित सत्यापन:*\n",
        'no_pending': "कोई लंबित सत्यापन नहीं।",
        'verify_help': "ईमेल स्वीकृत करने के लिए /verify <user_id> [optional message] का उपयोग करें।",
        'my_plan': "📋 *आपकी वर्तमान योजना:*\n\nयोजना: {}\nदैनिक जवाब: {}\nस्थिति: ✅ सक्रिय\nवैधता: {} तक\n\nअपग्रेड करने के लिए 💳 Subscription बटन का उपयोग करें।",
        'free_plan': "📋 *आपकी वर्तमान योजना:*\n\nयोजना: मुफ्त\nदैनिक जवाब: 10\nस्थिति: ✅ सक्रिय\nवैधता: असीमित\n\nअधिक जवाब पाने के लिए 💳 Subscription बटन से सदस्यता लें।",
        'expired_plan': "⚠️ आपकी सदस्यता समाप्त हो गई है। अब आप फ्री प्लान (10 जवाब/दिन) पर हैं।\nनवीनीकरण के लिए 💳 Subscription बटन का उपयोग करें।",
        'projects_list': "📁 *उपलब्ध Google प्रोजेक्ट:*\n{}",
        'choose_project': "🔑 कृपया वह Google प्रोजेक्ट चुनें जिसका उपयोग YouTube लॉगिन के लिए करना चाहते हैं:",
        'project_selected': "✅ आपने चुना: {}\nअब YouTube से लॉगिन करने के लिए नीचे दिए लिंक पर क्लिक करें।",
    }
}

# ====================== DATA STORAGE ======================
user_configs = {}
user_states = {}
user_temp = {}
seen_comments = {}
running_users = {}
bot_running = False

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        user_configs = json.load(f)

def load_seen_comments():
    global seen_comments
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            data = json.load(f)
        seen_comments = {uid: {vid: set(comments) for vid, comments in videos.items()} for uid, videos in data.items()}

def save_data():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(user_configs, f, indent=4)
    data_to_save = {uid: {vid: list(comments) for vid, comments in videos.items()} for uid, videos in seen_comments.items()}
    with open(SEEN_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=4)

load_seen_comments()

def extract_video_id(url):
    url = url.split('?')[0]
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/shorts\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/v\/)([\w-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if re.match(r'^[\w-]+$', url):
        return url
    return None

def get_user_lang(uid):
    return user_configs.get(uid, {}).get('lang', 'en')

def get_text(uid, key, *args):
    lang = get_user_lang(uid)
    text = TEXTS[lang].get(key, TEXTS['en'].get(key, ''))
    return text.format(*args) if args else text

# ====================== VERIFICATION ======================
def is_user_verified(uid):
    return user_configs.get(uid, {}).get('verified', False)

# ====================== SUBSCRIPTION & CREDITS ======================
PLANS = {
    "₹99": {"daily_limit": 150, "price": 99},
    "₹199": {"daily_limit": 300, "price": 199},
    "₹299": {"daily_limit": 500, "price": 299},
}
FREE_PLAN = {"daily_limit": 10, "price": 0}

def check_expired_subscription(uid):
    config = user_configs.get(uid)
    if not config:
        return
    sub = config.get('subscription')
    if sub and sub.get('expiry_date'):
        expiry = datetime.fromisoformat(sub['expiry_date'])
        if datetime.now() > expiry:
            del config['subscription']
            config['credits_remaining_today'] = FREE_PLAN['daily_limit']
            save_data()
            return True
    return False

def get_user_plan(uid):
    config = user_configs.get(uid)
    if not config:
        return FREE_PLAN, "Free"
    check_expired_subscription(uid)
    sub = config.get('subscription', {})
    if sub and sub.get('plan') in PLANS:
        return PLANS[sub['plan']], sub['plan']
    return FREE_PLAN, "Free"

def reset_daily_credits_if_needed(uid):
    config = user_configs.get(uid)
    if not config:
        return
    today = datetime.now().strftime('%Y-%m-%d')
    last_reset = config.get('last_reset_date')
    if last_reset != today:
        check_expired_subscription(uid)
        plan, _ = get_user_plan(uid)
        config['credits_remaining_today'] = plan['daily_limit']
        config['last_reset_date'] = today
        # Reset zero‑alert flag for new day
        config['zero_alert_sent'] = False
        save_data()

def can_send_reply(uid):
    reset_daily_credits_if_needed(uid)
    config = user_configs.get(uid, {})
    remaining = config.get('credits_remaining_today', 0)
    return remaining > 0

def deduct_credit(uid):
    config = user_configs.get(uid)
    if not config:
        return False
    reset_daily_credits_if_needed(uid)
    if config.get('credits_remaining_today', 0) > 0:
        config['credits_remaining_today'] -= 1
        config['total_replies_sent'] = config.get('total_replies_sent', 0) + 1
        save_data()
        return True
    return False

# ====================== ZERO-CREDIT ALERT ======================
async def send_zero_credit_alert(uid):
    """Send alert to user that credits are exhausted."""
    lang = get_user_lang(uid)
    text = TEXTS[lang].get('credits_zero_alert', TEXTS['en']['credits_zero_alert'])
    await bot_app.bot.send_message(chat_id=int(uid), text=text, reply_markup=menu_keyboard)

def check_and_alert_zero_credits(uid):
    """Called from loop thread to schedule an alert if needed."""
    config = user_configs.get(uid)
    if not config:
        return
    remaining = config.get('credits_remaining_today', 0)
    if remaining == 0 and not config.get('zero_alert_sent', False):
        config['zero_alert_sent'] = True
        save_data()
        # Schedule the async send in the main event loop
        if main_loop is not None:
            asyncio.run_coroutine_threadsafe(send_zero_credit_alert(uid), main_loop)

# ====================== AUTO-REPLY LOOP ======================
def youtube_comment_loop():
    global bot_running
    while bot_running:
        for uid in list(user_configs.keys()):
            if not running_users.get(uid, False):
                continue
            config = user_configs.get(uid)
            if not config or 'youtube_credentials' not in config or not config.get('videos'):
                continue

            # Start from the project the user selected, or 0
            if 'current_project' not in config:
                config['current_project'] = config.get('selected_project_index', 0)
            idx = config['current_project'] % len(CREDENTIALS_LIST)
            project_file = CREDENTIALS_LIST[idx]

            try:
                creds = Credentials.from_authorized_user_info(config['youtube_credentials'])
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    config['youtube_credentials'] = json.loads(creds.to_json())
                    save_data()

                youtube = build('youtube', 'v3', credentials=creds)

                for video in config.get('videos', [])[:]:
                    video_id = video['video_id']
                    reply_text = video['reply_text']

                    if not can_send_reply(uid):
                        # Possibly alert user about zero credits
                        check_and_alert_zero_credits(uid)
                        continue

                    if uid not in seen_comments:
                        seen_comments[uid] = {}
                    if video_id not in seen_comments[uid]:
                        seen_comments[uid][video_id] = set()

                    try:
                        response = youtube.commentThreads().list(
                            part="snippet",
                            videoId=video_id,
                            maxResults=10,
                            order="time"
                        ).execute()
                    except Exception as e:
                        err_str = str(e).lower()
                        if "video not found" in err_str or "videoidentified" in err_str:
                            print(f"⚠️ Video {video_id} not found or inaccessible. Removing from list for user {uid}.")
                            config['videos'].remove(video)
                            save_data()
                            continue
                        else:
                            raise e

                    for item in response.get('items', []):
                        comment_id = item['id']
                        if comment_id not in seen_comments[uid][video_id]:
                            try:
                                youtube.comments().insert(
                                    part="snippet",
                                    body={"snippet": {"parentId": comment_id, "textOriginal": reply_text}}
                                ).execute()
                                if deduct_credit(uid):
                                    seen_comments[uid][video_id].add(comment_id)
                                    save_data()
                                    print(f"✅ Reply sent (Project {idx+1}: {project_file}) → {reply_text[:50]}")
                                delay = random.randint(30, 60)
                                time.sleep(delay)
                            except Exception as e:
                                err = str(e).lower()
                                if "quota" in err or "403" in err:
                                    print(f"⚠️ QUOTA EXHAUSTED for Project {idx+1} ({project_file}). Switching to next project.")
                                    config['current_project'] += 1
                                    save_data()
                                    break  # break inner loop to move to next project
                                else:
                                    print(f"Reply failed: {e}")
            except Exception as e:
                print(f"User {uid} loop error: {e}")
                time.sleep(10)

        time.sleep(5)  # reduced from 15 to 5 seconds for faster reaction

def start_thread():
    global bot_running
    if bot_running: return
    bot_running = True
    threading.Thread(target=youtube_comment_loop, daemon=True).start()
    print("🚀 Auto-Reply Thread Started (random delay 30-60s, only new comments, cycle 5s)")

# ====================== TELEGRAM HANDLERS ======================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in user_configs and is_user_verified(uid):
        if 'videos' not in user_configs[uid]:
            user_configs[uid]['videos'] = []
        if 'total_replies_sent' not in user_configs[uid]:
            user_configs[uid]['total_replies_sent'] = 0
        if 'credits_remaining_today' not in user_configs[uid]:
            user_configs[uid]['credits_remaining_today'] = FREE_PLAN['daily_limit']
        if 'last_reset_date' not in user_configs[uid]:
            user_configs[uid]['last_reset_date'] = datetime.now().strftime('%Y-%m-%d')
        if 'zero_alert_sent' not in user_configs[uid]:
            user_configs[uid]['zero_alert_sent'] = False
        save_data()
        running_users[uid] = True
        await update.message.reply_text(
            get_text(uid, 'login_first'),
            reply_markup=menu_keyboard
        )
    elif uid in user_configs and not is_user_verified(uid):
        await update.message.reply_text(
            get_text(uid, 'not_verified'),
            reply_markup=ReplyKeyboardMarkup([["📧 Resend Email"]], resize_keyboard=True)
        )
        user_states[uid] = 'waiting_resend_email'
    else:
        lang_keyboard = ReplyKeyboardMarkup([["English", "हिंदी"]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(TEXTS['en']['welcome'] + "\n\n" + TEXTS['hi']['welcome'], reply_markup=lang_keyboard)
        user_states[uid] = 'waiting_lang'

async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    if text.lower() == 'english':
        lang = 'en'
    elif text.lower() == 'हिंदी':
        lang = 'hi'
    else:
        await update.message.reply_text("Please choose either English or हिंदी.")
        return
    user_configs[uid] = {
        'lang': lang,
        'verified': False,
        'videos': [],
        'total_replies_sent': 0,
        'credits_remaining_today': FREE_PLAN['daily_limit'],
        'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
        'zero_alert_sent': False
    }
    save_data()
    await update.message.reply_text(get_text(uid, 'lang_set'), reply_markup=ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True))
    user_states[uid] = 'waiting_email'

async def email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, email: str):
    uid = str(update.effective_user.id)
    user_temp[uid] = {'email': email}
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📧 New verification request from user {uid}:\nEmail: {email}"
    )
    await update.message.reply_text(get_text(uid, 'email_received'), reply_markup=menu_keyboard)
    user_states[uid] = 'waiting_verification'

async def resend_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if user_states.get(uid) == 'waiting_resend_email':
        await update.message.reply_text("Please send your email address again:")
        user_states[uid] = 'waiting_email'
    else:
        await update.message.reply_text("Use /start to begin again.")

# ====================== ADMIN COMMANDS ======================
async def pending_verifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    pending = [uid for uid, data in user_configs.items() if not data.get('verified', False) and data.get('lang')]
    if not pending:
        await update.message.reply_text(get_text(ADMIN_ID, 'no_pending'))
        return
    msg = get_text(ADMIN_ID, 'pending_verifications')
    for uid in pending:
        email = user_temp.get(uid, {}).get('email', 'No email provided')
        msg += f"• {uid} – {email}\n"
    await update.message.reply_text(msg)

async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /verify <user_id> [optional message]")
        return
    uid = args[0]
    optional_msg = " ".join(args[1:]) if len(args) > 1 else ""
    if uid not in user_configs:
        await update.message.reply_text(f"User {uid} not found.")
        return
    user_configs[uid]['verified'] = True
    save_data()
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=get_text(uid, 'verification_success', optional_msg),
            reply_markup=menu_keyboard
        )
    except Exception as e:
        print(f"Could not notify user {uid}: {e}")
    await update.message.reply_text(f"✅ User {uid} verified.\nMessage sent: {optional_msg if optional_msg else 'None'}")
    if uid in user_temp:
        user_temp.pop(uid, None)
    if uid in user_states:
        user_states.pop(uid, None)

async def reject_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /reject_verify <user_id>")
        return
    uid = args[0]
    if uid not in user_configs:
        await update.message.reply_text(f"User {uid} not found.")
        return
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=get_text(uid, 'verification_failed'),
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
    except Exception as e:
        print(f"Could not notify user {uid}: {e}")
    if uid in user_configs:
        del user_configs[uid]
    if uid in user_temp:
        user_temp.pop(uid, None)
    if uid in user_states:
        user_states.pop(uid, None)
    save_data()
    await update.message.reply_text(f"❌ Rejected verification for user {uid}.")

async def approve_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /approve <user_id> <plan>\nExample: /approve 123456789 ₹99")
        return
    user_id = args[0]
    plan_name = args[1]
    if plan_name not in PLANS:
        await update.message.reply_text("Invalid plan. Choose ₹99, ₹199, or ₹299.")
        return
    if user_id not in user_configs:
        user_configs[user_id] = {
            'videos': [],
            'total_replies_sent': 0,
            'credits_remaining_today': PLANS[plan_name]['daily_limit'],
            'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
            'lang': 'en',
            'zero_alert_sent': False
        }
    expiry_date = (datetime.now() + timedelta(days=30)).isoformat()
    user_configs[user_id]['subscription'] = {
        'plan': plan_name,
        'activated_at': datetime.now().isoformat(),
        'expiry_date': expiry_date
    }
    user_configs[user_id]['credits_remaining_today'] = PLANS[plan_name]['daily_limit']
    user_configs[user_id]['zero_alert_sent'] = False
    save_data()
    try:
        expiry_readable = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        await context.bot.send_message(
            chat_id=int(user_id),
            text=get_text(user_id, 'payment_approved', plan_name, PLANS[plan_name]['daily_limit'], expiry_readable),
            reply_markup=menu_keyboard
        )
    except Exception as e:
        print(f"Could not notify user {user_id}: {e}")
    await update.message.reply_text(f"✅ Subscription approved for user {user_id} with plan {plan_name}.")
    if user_id in user_states:
        user_states.pop(user_id, None)
    if user_id in user_temp:
        user_temp.pop(user_id, None)

async def reject_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /reject <user_id>")
        return
    user_id = args[0]
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=get_text(user_id, 'payment_rejected'),
            reply_markup=menu_keyboard
        )
    except Exception as e:
        print(f"Could not notify user {user_id}: {e}")
    if user_id in user_states:
        user_states.pop(user_id, None)
    if user_id in user_temp:
        user_temp.pop(user_id, None)
    await update.message.reply_text(f"❌ Rejected subscription for user {user_id}.")

async def projects_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    if not CREDENTIALS_LIST:
        await update.message.reply_text("No project files found.")
        return
    msg = ""
    for i, file in enumerate(CREDENTIALS_LIST, 1):
        msg += f"📁 *Project {i}:* `{file}`\n"
    await update.message.reply_text(
        get_text(str(update.effective_user.id), 'projects_list', msg),
        parse_mode='Markdown'
    )

# ====================== YOUTUBE LOGIN WITH PROJECT SELECTION ======================
async def youtube_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    if not CREDENTIALS_LIST:
        await update.message.reply_text("❌ No credentials file found!", reply_markup=menu_keyboard)
        return
    keyboard = []
    for i, file in enumerate(CREDENTIALS_LIST, 1):
        keyboard.append([InlineKeyboardButton(f"Project {i} ({file})", callback_data=f"proj_{i-1}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_text(uid, 'choose_project'), reply_markup=reply_markup)
    user_states[uid] = 'waiting_project_selection'

async def project_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data
    if data.startswith("proj_"):
        proj_index = int(data.split("_")[1])
        if proj_index < 0 or proj_index >= len(CREDENTIALS_LIST):
            await query.edit_message_text("Invalid project selection.")
            return
        user_temp[uid] = {'selected_project_index': proj_index}
        try:
            flow = Flow.from_client_secrets_file(
                CREDENTIALS_LIST[proj_index],
                scopes=['https://www.googleapis.com/auth/youtube.force-ssl'],
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            await query.edit_message_text(
                get_text(uid, 'project_selected', CREDENTIALS_LIST[proj_index]) + "\n\n" +
                get_text(uid, 'youtube_login_prompt')
            )
            await context.bot.send_message(chat_id=uid, text=auth_url)
            user_temp[uid]['flow'] = flow
            user_states[uid] = 'waiting_youtube_code'
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading credentials: {e}")
            user_states.pop(uid, None)
            user_temp.pop(uid, None)
    else:
        await query.edit_message_text("Invalid selection.")

async def youtube_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    uid = str(update.effective_user.id)
    try:
        flow = user_temp[uid]['flow']
        flow.fetch_token(code=code)
        creds = flow.credentials
        user_configs[uid]['youtube_credentials'] = json.loads(creds.to_json())
        user_configs[uid]['selected_project_index'] = user_temp[uid]['selected_project_index']
        user_configs[uid]['current_project'] = user_temp[uid]['selected_project_index']
        save_data()
        await update.message.reply_text(get_text(uid, 'youtube_success'), reply_markup=menu_keyboard)
        user_states.pop(uid, None)
        user_temp.pop(uid, None)
    except Exception as e:
        await update.message.reply_text(get_text(uid, 'youtube_fail', str(e)[:100]), reply_markup=menu_keyboard)

# ====================== OTHER HANDLERS ======================
async def start_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    running_users[uid] = True
    await update.message.reply_text(get_text(uid, 'start_reply'), reply_markup=menu_keyboard)
    start_thread()

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    running_users[uid] = False
    await update.message.reply_text(get_text(uid, 'stop_reply'), reply_markup=menu_keyboard)

async def add_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    if 'youtube_credentials' not in user_configs.get(uid, {}):
        await update.message.reply_text(get_text(uid, 'login_first'), reply_markup=menu_keyboard)
        return
    await update.message.reply_text(get_text(uid, 'add_video_prompt'), reply_markup=menu_keyboard)
    user_states[uid] = 'waiting_video_link'

async def video_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str):
    uid = str(update.effective_user.id)
    video_id = extract_video_id(link)
    if not video_id:
        await update.message.reply_text(get_text(uid, 'invalid_link'), reply_markup=menu_keyboard)
        return
    user_temp[uid] = {'video_id': video_id}
    await update.message.reply_text(get_text(uid, 'add_reply_prompt'), reply_markup=menu_keyboard)
    user_states[uid] = 'waiting_video_reply'

async def video_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, reply_text: str):
    uid = str(update.effective_user.id)
    video_id = user_temp[uid]['video_id']
    user_configs[uid]['videos'].append({'video_id': video_id, 'reply_text': reply_text})
    save_data()
    await update.message.reply_text(get_text(uid, 'video_added', reply_text[:50]), reply_markup=menu_keyboard)
    user_states.pop(uid, None)
    user_temp.pop(uid, None)

async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    videos = user_configs.get(uid, {}).get('videos', [])
    if not videos:
        await update.message.reply_text(get_text(uid, 'no_videos'), reply_markup=menu_keyboard)
        return
    msg = get_text(uid, 'video_list')
    for i, v in enumerate(videos, 1):
        msg += f"{i}. {v['video_id']} → {v['reply_text'][:40]}\n"
    await update.message.reply_text(msg, reply_markup=menu_keyboard)

async def delete_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    videos = user_configs.get(uid, {}).get('videos', [])
    if not videos:
        await update.message.reply_text(get_text(uid, 'no_videos'), reply_markup=menu_keyboard)
        return
    msg = get_text(uid, 'video_list')
    for i, v in enumerate(videos, 1):
        msg += f"{i}. {v['video_id']} → {v['reply_text'][:40]}\n"
    msg += "\n" + get_text(uid, 'delete_prompt')
    await update.message.reply_text(msg, reply_markup=menu_keyboard)
    user_states[uid] = 'waiting_delete_video'

async def delete_video_number(update: Update, context: ContextTypes.DEFAULT_TYPE, num_str: str):
    uid = str(update.effective_user.id)
    try:
        idx = int(num_str) - 1
        videos = user_configs.get(uid, {}).get('videos', [])
        if 0 <= idx < len(videos):
            deleted = videos.pop(idx)
            save_data()
            await update.message.reply_text(get_text(uid, 'deleted', deleted['video_id']), reply_markup=menu_keyboard)
        else:
            await update.message.reply_text(get_text(uid, 'invalid_number'), reply_markup=menu_keyboard)
    except ValueError:
        await update.message.reply_text(get_text(uid, 'invalid_number'), reply_markup=menu_keyboard)
    user_states.pop(uid, None)

async def total_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    total = user_configs.get(uid, {}).get('total_replies_sent', 0)
    await update.message.reply_text(get_text(uid, 'total_replies', total), reply_markup=menu_keyboard)

async def show_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    reset_daily_credits_if_needed(uid)
    remaining = user_configs.get(uid, {}).get('credits_remaining_today', 0)
    plan, _ = get_user_plan(uid)
    await update.message.reply_text(
        get_text(uid, 'credits_status', remaining, plan['daily_limit']),
        reply_markup=menu_keyboard
    )

async def subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    await update.message.reply_text(get_text(uid, 'subscription_prompt'), reply_markup=menu_keyboard)
    user_states[uid] = 'waiting_plan_selection'

async def plan_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_name: str):
    uid = str(update.effective_user.id)
    if plan_name not in PLANS:
        await update.message.reply_text(get_text(uid, 'invalid_plan'), reply_markup=menu_keyboard)
        return
    user_temp[uid] = {'selected_plan': plan_name}
    instruction = get_text(uid, 'payment_instruction', plan_name)
    await update.message.reply_text(instruction, reply_markup=menu_keyboard)
    if os.path.exists(PAYMENT_QR_PATH):
        with open(PAYMENT_QR_PATH, 'rb') as f:
            await update.message.reply_photo(photo=f, caption=instruction)
    user_states[uid] = 'waiting_payment_screenshot'

async def payment_screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if user_states.get(uid) == 'awaiting_admin_approval':
        await update.message.reply_text(get_text(uid, 'payment_already_waiting'), reply_markup=menu_keyboard)
        return
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        caption = f"Payment screenshot from user {uid}\nPlan: {user_temp.get(uid, {}).get('selected_plan', 'Unknown')}"
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=file.file_id, caption=caption)
        await update.message.reply_text(get_text(uid, 'payment_waiting'), reply_markup=menu_keyboard)
        user_temp[uid]['awaiting_approval'] = True
        user_states[uid] = 'awaiting_admin_approval'
    else:
        await update.message.reply_text("Please send a photo/screenshot of the payment.", reply_markup=menu_keyboard)

async def show_my_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_user_verified(uid):
        await update.message.reply_text(get_text(uid, 'not_verified'))
        return
    plan, plan_name = get_user_plan(uid)
    if plan_name == "Free":
        config = user_configs.get(uid, {})
        if 'subscription' not in config:
            text = get_text(uid, 'free_plan')
        else:
            text = get_text(uid, 'expired_plan')
    else:
        sub = user_configs[uid]['subscription']
        expiry_date = datetime.fromisoformat(sub['expiry_date']).strftime('%Y-%m-%d')
        text = get_text(uid, 'my_plan', plan_name, plan['daily_limit'], expiry_date)
    await update.message.reply_text(text, reply_markup=menu_keyboard)

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in user_configs:
        del user_configs[uid]
    if uid in seen_comments:
        del seen_comments[uid]
    if uid in running_users:
        running_users[uid] = False
    if uid in user_states:
        del user_states[uid]
    if uid in user_temp:
        del user_temp[uid]
    save_data()
    await update.message.reply_text(get_text(uid, 'logout_success'), reply_markup=menu_keyboard)

# ====================== MAIN MESSAGE HANDLER ======================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    state = user_states.get(uid)

    if update.message is None:
        return

    if update.message.photo:
        if state == 'waiting_payment_screenshot':
            await payment_screenshot_handler(update, context)
        else:
            await update.message.reply_text(get_text(uid, 'unknown'), reply_markup=menu_keyboard)
        return

    if not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return

    if text == "📧 Resend Email" and state == 'waiting_resend_email':
        await resend_email_handler(update, context)
        return

    if state == 'waiting_lang':
        await handle_language(update, context)
        return

    if state == 'waiting_email':
        if "@" in text and "." in text:
            await email_handler(update, context, text)
        else:
            await update.message.reply_text("Please send a valid email address.")
        return

    if uid in user_configs and not is_user_verified(uid):
        if text == "/start":
            await start_cmd(update, context)
        else:
            await update.message.reply_text(get_text(uid, 'not_verified'), reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True))
        return

    # Main menu buttons
    if text == "🚀 Start Reply":
        await start_reply(update, context)
        return
    elif text == "🛑 Stop Reply":
        await stop_cmd(update, context)
        return
    elif text == "🔑 Login with YouTube":
        await youtube_login(update, context)
        return
    elif text == "➕ Add Video":
        await add_video_start(update, context)
        return
    elif text == "🗑️ Delete Video":
        await delete_video_start(update, context)
        return
    elif text == "📋 Total Videos":
        await list_videos(update, context)
        return
    elif text == "📊 Total Send Reply":
        await total_replies(update, context)
        return
    elif text == "💰 Reply Credits":
        await show_credits(update, context)
        return
    elif text == "💳 Subscription":
        await subscription_start(update, context)
        return
    elif text == "📋 My Plan":
        await show_my_plan(update, context)
        return
    elif text == "":
        await logout(update, context)
        return

    # State flows
    if state == 'waiting_youtube_code':
        await youtube_code_handler(update, context, text)
        return
    elif state == 'waiting_video_link':
        await video_link_handler(update, context, text)
        return
    elif state == 'waiting_video_reply':
        await video_reply_handler(update, context, text)
        return
    elif state == 'waiting_delete_video':
        await delete_video_number(update, context, text)
        return
    elif state == 'waiting_plan_selection':
        await plan_selection(update, context, text)
        return
    elif state == 'awaiting_admin_approval':
        await update.message.reply_text(get_text(uid, 'payment_already_waiting'), reply_markup=menu_keyboard)
        return

    await update.message.reply_text(get_text(uid, 'unknown'), reply_markup=menu_keyboard)

# ====================== ERROR HANDLER ======================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

# ====================== MAIN ======================
menu_keyboard = ReplyKeyboardMarkup([
    ["🚀 Start Reply", "🛑 Stop Reply"],
    ["➕ Add Video", "🗑️ Delete Video"],
    ["📋 Total Videos", "📊 Total Send Reply"],
    ["💰 Reply Credits", "💳 Subscription"],
    ["📋 My Plan", "🚪 Logout"],
    ["🔑 Login with YouTube"]
], resize_keyboard=True)

if __name__ == '__main__':
    # Create a new event loop and set it as the current loop for the main thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_loop = loop
    # Create the bot application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    bot_app = app
    # Add handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("approve", approve_subscription))
    app.add_handler(CommandHandler("reject", reject_subscription))
    app.add_handler(CommandHandler("verify", verify_user))
    app.add_handler(CommandHandler("reject_verify", reject_verification))
    app.add_handler(CommandHandler("pending", pending_verifications))
    app.add_handler(CommandHandler("projects", projects_list))
    app.add_handler(CallbackQueryHandler(project_selection_callback, pattern="^proj_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    print("✅ Bot Started with Project Selection, Random Delay (30-60s), Only New Comments, and Zero-Credit Alert!")
    app.run_polling()
