#-----create by siam ---#
#------TG: @SIAMKHANXD--#
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import json
import re
import uuid
import random
import time
import os
import urllib3
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
from curl_cffi import requests as cureq

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ══════════════════════════════════════════════════════════
# SETTINGS (Ekhane tomar token boshao)
# ══════════════════════════════════════════════════════════
BOT_TOKEN = "6983447601:AAH2UIsDejULIvKdmBmg1HGgzXGz26_QOTM" 
ADMIN_ID = "6408202140" # Tomar Telegram ID

bot = telebot.TeleBot(BOT_TOKEN)

# ══════════════════════════════════════════════════════════
# FLASK WEB SERVER (To keep Render awake)
# ══════════════════════════════════════════════════════════
app = Flask('')

@app.route('/')
def home():
    return "FB Login Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ══════════════════════════════════════════════════════════
# CONSTANTS & UTILS
# ══════════════════════════════════════════════════════════
PROXY_FILE = "proxies.txt"
SAVE_FILE = "fb_logged_in.txt"

LANG_MAP = {
    'us': ('en-US,en;q=0.9', 'America/New_York'),
    'gb': ('en-GB,en;q=0.9', 'Europe/London'),
    'de': ('de-DE,de;q=0.9,en;q=0.8', 'Europe/Berlin'),
    'bd': ('bn-BD,bn;q=0.9,en;q=0.8', 'Asia/Dhaka'),
    'id': ('id-ID,id;q=0.9,en;q=0.8', 'Asia/Jakarta'),
    'fr': ('fr-FR,fr;q=0.9,en;q=0.8', 'Europe/Paris'),
}

def load_proxies():
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, 'r') as f:
            return [l.strip() for l in f if l.strip() and ':' in l]
    return []

def get_proxy_dict():
    proxies = load_proxies()
    if not proxies: return None
    p = random.choice(proxies).split(':')
    if len(p) == 4: return {'http': f'http://{p[2]}:{p[3]}@{p[0]}:{p[1]}', 'https': f'http://{p[2]}:{p[3]}@{p[0]}:{p[1]}'}
    elif len(p) == 2: return {'http': f'http://{p[0]}:{p[1]}', 'https': f'http://{p[0]}:{p[1]}'}
    return None

def format_cookies(cookies):
    order = ['datr', 'sb', 'm_pixel_ratio', 'wd', 'c_user', 'fr', 'xs']
    parts = [f"{k}={cookies[k]}" for k in order if k in cookies]
    parts.extend(f"{k}={v}" for k, v in cookies.items() if k not in order)
    return '; '.join(parts)

def save_cookie(email, cookie):
    try:
        with open(SAVE_FILE, "a", encoding="utf-8") as f:
            f.write(f"{email}|{cookie}\n")
    except Exception: pass

# ══════════════════════════════════════════════════════════
# LOGIN LOGIC (Step 1)
# ══════════════════════════════════════════════════════════
def fb_login_step1(email, password, lang_code, use_proxy):
    accept_lang = LANG_MAP.get(lang_code, LANG_MAP['us'])[0]
    proxy = get_proxy_dict() if use_proxy else None
    
    session = cureq.Session()
    fp = {
        "impersonate": "safari15_5",
        "headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            "Accept-Language": accept_lang,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    }

    try:
        # Warmup
        session.get("https://m.facebook.com/", headers=fp["headers"], impersonate=fp["impersonate"], proxies=proxy, timeout=20)
        time.sleep(random.uniform(1.5, 3.0))
        
        # Login POST
        data = {"email": email, "pass": password, "login": "Log In"}
        login_url = "https://m.facebook.com/login/device-based/regular/login/?login_attempt=1"
        
        headers = dict(fp["headers"])
        headers.update({'Content-Type': 'application/x-www-form-urlencoded', 'origin': 'https://m.facebook.com', 'referer': 'https://m.facebook.com/'})

        r = session.post(login_url, headers=headers, data=data, impersonate=fp["impersonate"], proxies=proxy, timeout=30, allow_redirects=True)
        
        cookies = session.cookies.get_dict()
        
        if 'c_user' in cookies:
            return {"status": "success", "cookie": format_cookies(cookies)}
            
        html = r.text.lower()
        if 'checkpoint' in r.url or 'enter the code' in html or 'approvals_code' in html or 'login/checkpoint' in r.url:
            action_match = re.search(r'action="([^"]+)"', r.text)
            action_url = action_match.group(1).replace('&amp;', '&') if action_match else r.url
            if action_url.startswith('/'): action_url = "https://m.facebook.com" + action_url
            
            return {"status": "otp_required", "session": session, "action_url": action_url, "headers": headers, "proxy": proxy, "fp": fp}
            
        else:
            return {"status": "failed", "error": "Wrong password or Checkpoint"}
            
    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ══════════════════════════════════════════════════════════
# OTP LOGIC (Step 2)
# ══════════════════════════════════════════════════════════
def fb_login_step2(session, action_url, headers, otp, proxy, fp):
    try:
        otp_data = {"approvals_code": otp, "submit[Submit Code]": "Submit Code"}
        
        r = session.get(action_url, headers=headers, impersonate=fp["impersonate"], proxies=proxy, timeout=20)
        hidden_inputs = re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', r.text)
        for k, v in hidden_inputs:
            if k not in otp_data: otp_data[k] = v

        res2 = session.post(action_url, headers=headers, data=otp_data, impersonate=fp["impersonate"], proxies=proxy, timeout=30, allow_redirects=True)
        
        cookies = session.cookies.get_dict()
        
        if 'c_user' in cookies:
            # Trust Device
            if 'save-device' in res2.url or 'Trust this device' in res2.text:
                save_url_match = re.search(r'action="([^"]+save-device[^"]*)"', res2.text)
                if save_url_match:
                    save_url = save_url_match.group(1).replace('&amp;', '&')
                    if save_url.startswith('/'): save_url = "https://m.facebook.com" + save_url
                    session.get(save_url, headers=headers, impersonate=fp["impersonate"], proxies=proxy, timeout=30)
                    cookies = session.cookies.get_dict()
                    
            return {"status": "success", "cookie": format_cookies(cookies)}
        else:
            return {"status": "failed", "error": "Invalid OTP"}
            
    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ══════════════════════════════════════════════════════════
# TELEGRAM BOT LOGIC
# ══════════════════════════════════════════════════════════
user_states = {}

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('🔐 Login Facebook'))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to FB Login Bot! 🤖\n\nClick below to start.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == '🔐 Login Facebook')
def start_login(message):
    chat_id = message.chat.id
    user_states[chat_id] = {'step': 'lang'}
    
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=3)
    buttons = [KeyboardButton(code) for code in LANG_MAP.keys()]
    markup.add(*buttons)
    bot.send_message(chat_id, "🌍 Select Language Code (e.g., us, bd):", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'lang')
def handle_lang(message):
    chat_id = message.chat.id
    lang = message.text.strip().lower()
    
    if lang not in LANG_MAP:
        return bot.send_message(chat_id, "❌ Invalid language. Please select from buttons.")
        
    user_states[chat_id]['lang'] = lang
    user_states[chat_id]['step'] = 'proxy'
    
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('Use Proxy', 'No Proxy (Direct)')
    bot.send_message(chat_id, f"✅ Language: {lang.upper()}\n🌐 Use Proxy?", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'proxy')
def handle_proxy(message):
    chat_id = message.chat.id
    text = message.text
    
    if 'No Proxy' in text:
        user_states[chat_id]['use_proxy'] = False
    else:
        user_states[chat_id]['use_proxy'] = True
        
    user_states[chat_id]['step'] = 'combo'
    bot.send_message(chat_id, "🔑 Enter Combo (email|password):", reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'combo')
def handle_combo(message):
    chat_id = message.chat.id
    combo = message.text.strip()
    
    if '|' not in combo:
        return bot.send_message(chat_id, "❌ Invalid format. Use email|password")
        
    email, password = combo.split('|', 1)
    state = user_states[chat_id]
    
    msg = bot.send_message(chat_id, f"⏳ Logging in to `{email}`...", parse_mode='Markdown')
    
    # Run in background
    threading.Thread(target=process_login, args=(chat_id, email, password, state['lang'], state['use_proxy'], msg.message_id)).start()

def process_login(chat_id, email, password, lang, use_proxy, msg_id):
    res = fb_login_step1(email, password, lang, use_proxy)
    
    if res['status'] == 'success':
        bot.edit_message_text(f"✅ **LOGIN SUCCESSFUL!**\n\n`{res['cookie']}`", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown')
        save_cookie(email, res['cookie'])
        user_states[chat_id] = {}
        bot.send_message(chat_id, "Back to menu.", reply_markup=get_main_menu())
        
    elif res['status'] == 'otp_required':
        # Save session state for OTP
        user_states[chat_id]['otp_data'] = res
        user_states[chat_id]['step'] = 'otp'
        user_states[chat_id]['email'] = email
        
        bot.edit_message_text(f"⚠️ **OTP REQUIRED for `{email}`**\n\nFacebook sent a 5-digit code. Please enter it below:", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown')
        
    else:
        bot.edit_message_text(f"❌ **LOGIN FAILED**\n\nReason: {res['error']}", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown')
        user_states[chat_id] = {}
        bot.send_message(chat_id, "Back to menu.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'otp')
def handle_otp(message):
    chat_id = message.chat.id
    otp = message.text.strip()
    
    if not otp.isdigit() or len(otp) != 5:
        return bot.send_message(chat_id, "❌ Invalid code. Please enter the 5-digit code.")
        
    state = user_states[chat_id]
    data = state['otp_data']
    
    msg = bot.send_message(chat_id, "⏳ Verifying OTP...")
    
    # Run in background
    threading.Thread(target=process_otp, args=(chat_id, state['email'], otp, data, msg.message_id)).start()

def process_otp(chat_id, email, otp, data, msg_id):
    res = fb_login_step2(data['session'], data['action_url'], data['headers'], otp, data['proxy'], data['fp'])
    
    if res['status'] == 'success':
        bot.edit_message_text(f"✅ **LOGIN SUCCESSFUL!**\n\n`{res['cookie']}`", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown')
        save_cookie(email, res['cookie'])
    else:
        bot.edit_message_text(f"❌ **OTP FAILED**\n\nReason: {res['error']}", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown')
        
    user_states[chat_id] = {}
    bot.send_message(chat_id, "Back to menu.", reply_markup=get_main_menu())

# ══════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("Bot is running...")
    bot.infinity_polling()
