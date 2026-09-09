import os, json, telebot, requests, time, threading, logging, traceback, urllib.parse
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

# ================= КОНФИГУРАЦИЯ =================
TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
ADMIN_IDS = ["8682521929", "8915393389"]
PRIMARY_ADMIN_ID = "8682521929"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

ERROR_LOGS = []

def log_error(source, error_text):
    t = datetime.now().strftime("%d.%m %H:%M:%S")
    entry = f"[{t}] [{source}] {str(error_text)}"
    ERROR_LOGS.append(entry)
    if len(ERROR_LOGS) > 30:
        ERROR_LOGS.pop(0)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
PROMO_FILE = os.path.join(BASE_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(BASE_DIR, "gencalls_blacklist.json")
CUSTOM_PRANKS_FILE = os.path.join(BASE_DIR, "gencalls_pranks.json")
AUDIO_STORAGE_FILE = os.path.join(BASE_DIR, "audio_storage_vault.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_error("JSON_LOAD", f"{path}: {e}")
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error("JSON_SAVE", f"{path}: {e}")

DEFAULT_CONFIG = {
    "call_price": 49,
    "welcome_bonus_calls": 2,
    "max_referrals": 3,
    "admin_id": PRIMARY_ADMIN_ID,
    "global_routing": "auto",
    "crystal_auth_login": "dhdhe1728jd",
    "crystal_secret": "c5fdf612bfd5e816a1a7447d2b942a3b03e36c04",
    "crystal_salt": "a7e84e5da09dff11eb7be2ac0c6b83647a28efc1",
    "channel_url": "https://t.me/gencalls_channel",
    "zvonok_key": "d0808ab7450fca32147a9285018fe7a5",
    "campaign_id": "1783540036",
    "smsru_key": "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF",
    "support": "tadevosankaro12"
}

admin_cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
for k, v in DEFAULT_CONFIG.items():
    if k not in admin_cfg:
        admin_cfg[k] = v
save_json(CONFIG_FILE, admin_cfg)

db = load_json(DB_FILE, {})
promocodes = load_json(PROMO_FILE, {"GEN2026": {"rub": 49, "uses": 100, "used_by": []}})
blacklist = load_json(BLACKLIST_FILE, [])

# ВАША СВЕЖАЯ ССЫЛКА НА CLOUDINARY ДЛЯ БАБКИ:
PERMANENT_CLOUD_AUDIO = {
    "babka": "https://res.cloudinary.com/idthhkcn/video/upload/v1788934847/%D0%91%D0%B0%D0%B1%D0%BA%D0%B0_%D1%82%D1%80%D0%B5%D0%B1%D1%83%D0%B5%D1%82_%D0%B1%D0%B0%D0%B1%D0%BA%D0%B8.mp3",
    "tulip": "https://actions.google.com/sounds/v1/human_voices/male_cheering.ogg",
    "rkn": "https://actions.google.com/sounds/v1/emergency/siren_emergency.ogg",
    "django": "https://actions.google.com/sounds/v1/cartoon/whistling_slide.ogg",
    "govnovoz": "https://actions.google.com/sounds/v1/transportation/truck_horn.ogg",
    "courier": "https://actions.google.com/sounds/v1/household/doorbell.ogg"
}

audio_vault = load_json(AUDIO_STORAGE_FILE, {})
# Автоматически обновляем ссылку на бабку в хранилище
audio_vault["babka"] = PERMANENT_CLOUD_AUDIO["babka"]
for k, v in PERMANENT_CLOUD_AUDIO.items():
    if k not in audio_vault or not audio_vault[k]:
        audio_vault[k] = v
save_json(AUDIO_STORAGE_FILE, audio_vault)

DEFAULT_PRANKS = {
    "babka": {"title": "👵 Бабка Лидия (Долг)", "tag": "ХИТ 🔥", "dur": 35, "desc": "Скандальная пенсионерка обвиняет в краже пенсии и требует вернуть долг с угрозами участковым.", "file": "babka.mp3", "public": True},
    "tulip": {"title": "🌷 Тюльпаны оптом", "tag": "ТОП 🌸", "dur": 40, "desc": "Срочная доставка 500 тюльпанов на свадьбу прямо сейчас: «Выходите забирайте, иначе завянут!»", "file": "tulip.mp3", "public": True},
    "rkn": {"title": "🏛️ Роскомнадзор (Блокировка)", "tag": "ШОК ⚠️", "dur": 45, "desc": "Официальное предупреждение: зафиксирована подозрительная активность, ваш интернет будет заблокирован.", "file": "rkn.mp3", "public": True},
    "django": {"title": "🕺 Джанго стриптизер", "tag": "18+ 🔞", "dur": 38, "desc": "Приватный стриптизер звонит в домофон: «Я уже в костюме с маслом у вашей двери, открывайте!»", "file": "django.mp3", "public": True},
    "govnovoz": {"title": "🚛 Ассенизатор (Шланг)", "tag": "УГАР 😂", "dur": 30, "desc": "Машина приехала откачивать септик прямо во двор: «Куда шланг кидать, открывайте ворота!»", "file": "govnovoz.mp3", "public": True},
    "courier": {"title": "🍕 Голодный курьер", "tag": "НОВОЕ 🍕", "dur": 32, "desc": "Курьер признаётся: «Вы долго не открывали, я не сдержался и съел вашу пиццу, простите...»", "file": "courier.mp3", "public": True}
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
for k, v in DEFAULT_PRANKS.items():
    if k not in pranks_db: pranks_db[k] = v
save_json(CUSTOM_PRANKS_FILE, pranks_db)

PACKAGES = {
    "pkg_1": {"title": "1 звонок", "rub": 49, "badge": "Старт"},
    "pkg_5": {"title": "5 звонков", "rub": 149, "badge": "🔥 -40%"},
    "pkg_15": {"title": "15 звонков", "rub": 299, "badge": "👑 Хит"},
    "pkg_50": {"title": "50 звонков", "rub": 699, "badge": "VIP"}
}

def is_admin(uid):
    uid_str = str(uid).strip()
    return uid_str in ADMIN_IDS or uid_str == str(PRIMARY_ADMIN_ID)

def get_user(uid, uname="Друг"):
    s_uid = str(uid).strip()
    is_new = False
    if s_uid not in db:
        price = admin_cfg.get("call_price", 49)
        welcome_bonus = admin_cfg.get("welcome_bonus_calls", 2)
        db[s_uid] = {
            "name": uname,
            "balance_rub": price * welcome_bonus,
            "calls_history": [],
            "referrals": 0,
            "referred_by": None,
            "reg_date": datetime.now().strftime("%d.%m.%Y"),
            "routing_mode": "auto"
        }
        save_json(DB_FILE, db)
        is_new = True
    return db[s_uid], is_new

def parse_phone(text):
    if not text: return None
    digits = "".join(filter(str.isdigit, str(text).strip()))
    if not digits: return None
    if len(digits) == 10 and digits.startswith("9"): return "7" + digits
    elif len(digits) == 11 and digits.startswith("8"): return "7" + digits[1:]
    return digits

def safe_url_encode(url):
    if not url or not str(url).startswith("http"): return url
    try:
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(parts.path, safe="/:")
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
    except Exception:
        return url

def get_audio_source(key):
    if key in audio_vault and audio_vault[key]:
        return safe_url_encode(audio_vault[key])
    if key in PERMANENT_CLOUD_AUDIO:
        return safe_url_encode(PERMANENT_CLOUD_AUDIO[key])
    fn = pranks_db.get(key, {}).get("file", f"{key}.mp3")
    local_p = os.path.join(AUDIO_DIR, fn)
    if os.path.exists(local_p):
        return local_p
    return safe_url_encode(PERMANENT_CLOUD_AUDIO.get("babka"))

# ================= ШЛЮЗЫ ТЕЛЕФОНИИ =================
def call_zvonok_campaign(phone):
    url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    params = {
        "campaign_id": admin_cfg.get("campaign_id", "1783540036"),
        "phone": f"+{phone}",
        "public_key": admin_cfg.get("zvonok_key", "d0808ab7450fca32147a9285018fe7a5"),
        "check_duplicate": "0",
        "record": "1"
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=12)
        res = r.json()
        if isinstance(res, dict):
            if res.get("status") == "error" or "error" in res:
                err_msg = res.get("data") or res.get("message") or res.get("error") or str(res)
                log_error("ZVONOK_API", err_msg)
                return False, f"Zvonok: {err_msg}", None
            call_id = res.get("call_id") or (res.get("data", {}).get("call_id") if isinstance(res.get("data"), dict) else None)
            return True, str(call_id or f"ZV-{int(time.time())}"), "zvonok"
        log_error("ZVONOK_API", r.text[:200])
        return False, f"Zvonok: {r.text[:100]}", None
    except Exception as e:
        log_error("ZVONOK_EXC", str(e))
        return False, f"Zvonok: {str(e)}", None

def call_smsru_smart(phone):
    sms_key = admin_cfg.get("smsru_key", "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF")
    for user_ip in ["185.129.100.1", "91.240.85.5", "127.0.0.1"]:
        for url, params in [
            ("https://sms.ru/code/call", {"phone": phone, "api_id": sms_key, "json": 1, "user_ip": user_ip}),
            ("https://sms.ru/callcheck/add", {"phone": phone, "api_id": sms_key, "json": 1, "user_ip": user_ip})
        ]:
            try:
                r = requests.get(url, params=params, timeout=8)
                res = r.json()
                if res.get("status") == "OK":
                    cid = res.get("call_id") or res.get("check_id") or res.get("code") or f"SMS-{int(time.time())}"
                    return True, str(cid), "smsru"
                else:
                    log_error("SMSRU_WARN", f"Status {res.get('status')}: {res.get('status_text')}")
            except Exception as e:
                log_error("SMSRU_EXC", str(e))
            time.sleep(0.3)
    return False, "SMS.RU: Маршрут временно недоступен", None

def track_call_and_send_record(chat_id, call_id, phone, prank_title, service_type):
    time.sleep(30)
    record_url = None
    if service_type == "zvonok":
        for _ in range(3):
            try:
                status_url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call_by_id/"
                params = {"call_id": call_id, "public_key": admin_cfg.get("zvonok_key")}
                r = requests.get(status_url, params=params, verify=False, timeout=8)
                res = r.json()
                record_url = res.get("record_url") or res.get("data", {}).get("record_url")
                if record_url: break
            except Exception as e:
                log_error("RECORD_FETCH", str(e))
            time.sleep(8)
            
    if record_url:
        try:
            bot.send_audio(
                chat_id, record_url, 
                title=f"Реакция ({prank_title})", performer="GenCalls Запись",
                caption=f"🎉 Звонок завершён! Запись разговора готова!\n\n📞 Номер: +{phone}\n🎭 Розыгрыш: {prank_title}"
            )
        except Exception as e:
            log_error("SEND_RECORD", str(e))

def process_call_async(chat_id, phone, prank_key, p_title, wait_msg_id):
    u, _ = get_user(chat_id)
    price = admin_cfg.get("call_price", 49)
    
    global_mode = admin_cfg.get("global_routing", "auto")
    user_mode = u.get("routing_mode", "auto")
    rmode = user_mode if user_mode != "auto" else global_mode

    if rmode == "zvonok":
        use_service = "zvonok"
    elif rmode == "smsru":
        use_service = "smsru"
    else:
        use_service = "zvonok" if str(phone).startswith("7") else "smsru"

    service_name = "🇷🇺 Zvonok (+7)" if use_service == "zvonok" else "🌍 SMS.RU Voice"
    success = False
    call_id = None
    service_type = "zvonok"

    if use_service == "zvonok":
        success, call_id, service_type = call_zvonok_campaign(phone)
        if not success:
            success_fb, call_id_fb, service_type = call_smsru_smart(phone)
            if success_fb: success, call_id, service_name = True, call_id_fb, "🌍 SMS.RU (Резерв)"
    else:
        success, call_id, service_type = call_smsru_smart(phone)
        if not success and str(phone).startswith("7"):
            success_zb, call_id_zb, service_type = call_zvonok_campaign(phone)
            if success_zb: success, call_id, service_name = True, call_id_zb, "🇷🇺 Zvonok (Резерв)"

    if not success:
        try: bot.edit_message_text(f"❌ Не удалось совершить вызов!\n\nПричина: {call_id}\n💰 Баланс НЕ списан.", chat_id, wait_msg_id, reply_markup=kb_main_menu(chat_id))
        except Exception: pass
        return

    u["balance_rub"] = max(0, u["balance_rub"] - price)
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m %H:%M"), "phone": phone, "prank": p_title, "service": service_name, "call_id": str(call_id)
    })
    save_json(DB_FILE, db)

    try:
        bot.edit_message_text(
            f"✅ Звонок запущен!\n\n📞 Номер: +{phone}\n🌐 Канал: {service_name}\n🎭 Розыгрыш: {p_title}\n💰 Остаток: {u['balance_rub']} ₽ ({u['balance_rub'] // price} 📞)\n\n🎙️ Запись разговора придёт в чат сразу после звонка!",
            chat_id, wait_msg_id, reply_markup=kb_main_menu(chat_id)
        )
    except Exception: pass
    threading.Thread(target=track_call_and_send_record, args=(chat_id, call_id, phone, p_title, service_type), daemon=True).start()

# ================= КАССА CRYSTALPAY =================
def create_crystal_invoice(amount, desc):
    auth_login = admin_cfg.get("crystal_auth_login", "dhdhe1728jd").strip()
    secret = admin_cfg.get("crystal_secret", "").strip()
    
    url = "https://api.crystalpay.io/v2/invoice/create/"
    payload = {
        "auth_login": auth_login,
        "auth_secret": secret,
        "amount": amount,
        "type": "purchase",
        "lifetime": 60,
        "description": desc,
        "redirect_url": admin_cfg.get("channel_url", "https://t.me/gencalls_channel")
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if not res.get("error"):
            return True, res.get("url"), res.get("id")
        err_msg = res.get("errors", [str(res)])[0]
        log_error("CRYSTAL_CREATE", err_msg)
        return False, err_msg, None
    except Exception as e:
        log_error("CRYSTAL_EXC", str(e))
        return False, str(e), None

def check_crystal_invoice(invoice_id):
    auth_login = admin_cfg.get("crystal_auth_login", "dhdhe1728jd").strip()
    secret = admin_cfg.get("crystal_secret", "").strip()
    url = "https://api.crystalpay.io/v2/invoice/info/"
    payload = {"auth_login": auth_login, "auth_secret": secret, "id": invoice_id}
    try:
        r = requests.post(url, json=payload, timeout=8)
        res = r.json()
        if not res.get("error") and res.get("state") == "payed":
            return True
        elif res.get("error"):
            log_error("CRYSTAL_CHECK", res.get("errors"))
    except Exception as e:
        log_error("CRYSTAL_CHECK_EXC", str(e))
    return False

# ================= НАВИГАЦИЯ =================
def safe_nav(c, text, reply_markup=None):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    try:
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        try: bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception: pass
        try: bot.send_message(c.message.chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e: log_error("NAV_ERROR", str(e))

def kb_main_menu(uid):
    u, _ = get_user(uid)
    price = admin_cfg.get("call_price", 49)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // price
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Открыть каталог розыгрышей", callback_data="catalog"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton("📜 Правила и Оферта", callback_data="nav_rules"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo"),
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank")
    )
    kb.row(
        types.InlineKeyboardButton("📢 Telegram-канал", url=admin_cfg.get("channel_url", "https://t.me/gencalls_channel"))
    )
    return kb

MAIN_TEXT_BANNER = (
    "🎭 **GenCalls — Пранк-Звонки с записью реакции!**\n\n"
    "🎁 Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!\n\n"
    "🕵️‍♂️ Анонимность 100% — ваш номер скрыт.\n"
    "🎵 MP3-Плеер — слушайте пранки перед звонком!\n"
    "🎙️ Запись реакции — запись разговора прямо в этот чат!\n"
    "⚡ Оплата онлайн через CrystalPAY (Карты РФ, SberPay, ЮMoney, Тест).\n\n"
    "👇 Выберите действие в меню:"
)

# ================= КОМАНДЫ =================
@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u, is_new = get_user(m.chat.id, m.from_user.first_name or "Друг")
    welcome = MAIN_TEXT_BANNER
    if is_new:
        welcome = f"🎉 Добро пожаловать в GenCalls!\n\n🎁 Мы подарили вам 2 БЕСПЛАТНЫХ ЗВОНКА!\n\n" + MAIN_TEXT_BANNER
    bot.send_message(m.chat.id, welcome, reply_markup=kb_main_menu(m.chat.id), parse_mode="Markdown")

# ================= КАТАЛОГ =================
@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog_cb(c):
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        if v.get("public", True):
            kb.row(types.InlineKeyboardButton(f"🎵 {v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 **Каталог голосовых розыгрышей:**\nВыберите любой для прослушивания:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({price} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    desc_text = f"🎭 **{p['title']}** [{p.get('tag', 'ТОП')}]\n\n💬 Сценарий: {p.get('desc', '')}\n\n🎙️ После звонка запись разговора придёт в чат!"
    audio_source = get_audio_source(k)
    try:
        bot.answer_callback_query(c.id)
        if str(audio_source).startswith("http") or str(audio_source).startswith("AgAC") or len(str(audio_source)) > 40:
            bot.send_audio(c.message.chat.id, audio_source, title=p['title'], performer="GenCalls", caption=desc_text, reply_markup=kb)
        else:
            with open(audio_source, "rb") as a_file:
                sent = bot.send_audio(c.message.chat.id, a_file, title=p['title'], performer="GenCalls", caption=desc_text, reply_markup=kb)
                if sent.audio:
                    audio_vault[k] = sent.audio.file_id
                    save_json(AUDIO_STORAGE_FILE, audio_vault)
        return
    except Exception as e:
        log_error("PLAY_AUDIO", f"{k}: {e}")
        safe_nav(c, desc_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    if u.get("balance_rub", 0) < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
        safe_nav(c, f"❌ Недостаточно средств\n\nЦена звонка: {price} ₽\nВаш баланс: {u.get('balance_rub', 0)} ₽", reply_markup=kb)
        return
    k = c.data.replace("setup_call_", "")
    user_data[c.message.chat.id] = {"prank": k}
    user_state[c.message.chat.id] = "waiting_phone"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📱 Введите номер телефона жертвы:\n\n• Россия: +79991234567\n• Любая страна: +...", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def step_phone_input(m):
    chat_id = m.chat.id
    phone = parse_phone(m.text)
    if not phone or len(phone) < 8 or phone in blacklist:
        bot.reply_to(m, "❌ Номер некорректен или находится в защитном списке бота.")
        return
    user_state[chat_id] = None
    prank_key = user_data.get(chat_id, {}).get("prank", "babka")
    p = pranks_db.get(prank_key, pranks_db.get("babka"))
    w = bot.send_message(chat_id, f"🚀 Набираем +{phone}...")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, p["title"], w.message_id), daemon=True).start()

# ================= ОПЛАТА =================
@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['title']} — {p['rub']} ₽ ({p['badge']})", callback_data=f"buy_cryst_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "💳 Пополнение баланса через CrystalPAY:\nВыберите пакет звонков:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_cryst_"))
def on_buy_crystal(c):
    pid = c.data.replace("buy_cryst_", "")
    pkg = PACKAGES.get(pid)
    if not pkg: return
    
    amount = pkg["rub"]
    ok, pay_url, inv_id = create_crystal_invoice(amount, f"GenCalls {pkg['title']}")
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    if ok and pay_url:
        kb.row(types.InlineKeyboardButton("🟢 Перейти к оплате (Карты / SberPay / Тест)", url=pay_url))
        kb.row(types.InlineKeyboardButton("🔄 Я оплатил (Проверить платёж)", callback_data=f"chk_cr_{inv_id}_{amount}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
        text = (
            f"⚡ Счёт на оплату готов!\n\n"
            f"📦 Пакет: {pkg['title']}\n"
            f"💰 Сумма: {amount} ₽\n\n"
            f"1. Нажмите зелёную кнопку для оплаты.\n"
            f"2. Оплатите счёт (Картой, Сбербанком или тестовым методом).\n"
            f"3. Нажмите кнопку «Я оплатил» — баланс зачислится мгновенно!"
        )
    else:
        kb.row(types.InlineKeyboardButton("👨‍💻 Написать в поддержку", url=f"https://t.me/{admin_cfg.get('support')}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
        text = f"⚠️ Ошибка кассы CrystalPAY:\n{pay_url}\n\nОбратитесь к администратору: @{admin_cfg.get('support')}"
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("chk_cr_"))
def on_chk_crystal(c):
    parts = c.data.split("_")
    inv_id, amount = parts[2], int(parts[3])
    
    if check_crystal_invoice(inv_id):
        u, _ = get_user(c.message.chat.id)
        u["balance_rub"] += amount
        save_json(DB_FILE, db)
        bot.answer_callback_query(c.id, "🎉 Оплата подтверждена!", show_alert=True)
        safe_nav(c, f"🎉 УРА! Платёж на {amount} ₽ успешно зачислен!\nВаш баланс: {u['balance_rub']} ₽", reply_markup=kb_main_menu(c.message.chat.id))
    else:
        bot.answer_callback_query(c.id, "⏳ Оплата ещё не поступила. Завершите перевод и нажмите ещё раз через 10 секунд.", show_alert=True)

# ================= МЕНЮ =================
@bot.callback_query_handler(func=lambda c: c.data == "nav_rules")
def cb_rules(c):
    rules_text = (
        "📜 **ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ И ПРАВИЛА (ОФЕРТА)**\n\n"
        "1. Сервис «GenCalls» предоставляет услуги голосовых поздравлений и розыгрышей.\n"
        "2. Оплата фиксированная, списание только при успешном дозвоне.\n"
        "3. Любой номер можно бесплатно внести в защиту «🛡️ Анти-Пранк».\n"
        f"4. Поддержка: @{admin_cfg.get('support')}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, rules_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"👤 **Личный кабинет**\n\n🆔 ID: `{c.message.chat.id}`\n💰 Баланс: {u['balance_rub']} ₽ ({u['balance_rub'] // price} 📞)", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_help(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать администратору", url=f"https://t.me/{admin_cfg.get('support')}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"🛟 Служба заботы и поддержки:\n\nПо любым вопросам пишите: @{admin_cfg.get('support')}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def on_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ Введите промокод в чат:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promo")
def step_promo(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    u, _ = get_user(m.chat.id)
    if code in promocodes and str(m.chat.id) not in promocodes[code].get("used_by", []):
        promocodes[code].setdefault("used_by", []).append(str(m.chat.id))
        bonus = promocodes[code].get("rub", 49)
        save_json(PROMO_FILE, promocodes)
        u["balance_rub"] += bonus
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 Промокод активирован! +{bonus} ₽ начислено.", reply_markup=kb_main_menu(m.chat.id))
    else:
        bot.reply_to(m, "❌ Промокод недействителен.", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "anti_prank")
def on_anti_prank(c):
    user_state[c.message.chat.id] = "waiting_bl"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🛡️ Введите номер для защиты от розыгрышей:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_bl")
def step_bl(m):
    user_state[m.chat.id] = None
    num = parse_phone(m.text)
    if num and num not in blacklist:
        blacklist.extend([num, f"+{num}"])
        save_json(BLACKLIST_FILE, blacklist)
    bot.reply_to(m, f"🛡️ Номер +{num} защищён от розыгрышей!", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def on_back(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

# ================= ГЛАВНАЯ АДМИН-ПАНЕЛЬ (/admin) =================
@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, c)

def show_admin_panel(chat_id, c=None):
    active_audios = len(audio_vault)
    curr_routing = admin_cfg.get("global_routing", "auto")
    routing_labels = {"auto": "🔄 Авто", "zvonok": "🇷🇺 Zvonok", "smsru": "🌍 SMS.RU"}
    
    text = (
        "👑 **Панель Управления GenCalls**\n\n"
        f"⚙️ **Маршрутизация:** `{routing_labels.get(curr_routing, 'Авто')}`\n"
        f"💎 **Касса CrystalPAY:** `{admin_cfg.get('crystal_auth_login')}`\n"
        f"🏷️ **Цена 1 звонка:** `{admin_cfg.get('call_price')} ₽`\n"
        f"🎭 **Розыгрышей:** {len(pranks_db)} шт. (☁️ Аудио: {active_audios} шт.)\n"
        f"👥 **Пользователей:** {len(db)}\n"
        f"🚨 **Ошибок в памяти:** {len(ERROR_LOGS)} шт."
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("⚙️ НАСТРОЙКИ СИСТЕМЫ И КЛЮЧЕЙ", callback_data="adm_full_settings"))
    kb.row(types.InlineKeyboardButton("🎭 ПОЛНОЦЕННЫЙ РЕДАКТОР РОЗЫГРЫШЕЙ", callback_data="adm_pranks_manager"))
    kb.row(types.InlineKeyboardButton("🚨 ЖУРНАЛ ОШИБОК И ДИАГНОСТИКА", callback_data="adm_error_logs"))
    kb.row(types.InlineKeyboardButton("💳 Выдать баланс юзеру", callback_data="adm_add_balance"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

# ================= ПОЛНЫЙ РАЗДЕЛ НАСТРОЕК =================
@bot.callback_query_handler(func=lambda c: c.data == "adm_full_settings")
def on_full_settings(c):
    if not is_admin(c.message.chat.id): return
    curr = admin_cfg.get("global_routing", "auto")
    routing_map = {"auto": "🔄 Авто", "zvonok": "🇷🇺 Zvonok", "smsru": "🌍 SMS.RU"}
    
    text = (
        "⚙️ **ВСЕ НАСТРОЙКИ СИСТЕМЫ GENCALLS**\n\n"
        f"• 🔄 **Маршрутизация:** `{routing_map.get(curr, 'Авто')}`\n"
        f"• 🏷️ **Цена за звонок:** `{admin_cfg.get('call_price')} ₽`\n"
        f"• 🎁 **Бонус при старте:** `{admin_cfg.get('welcome_bonus_calls', 2)} звонка`\n"
        f"• 💎 **Касса CrystalPAY:** `{admin_cfg.get('crystal_auth_login')}`\n"
        f"• 🇷🇺 **Кампания Zvonok:** `{admin_cfg.get('campaign_id')}`\n"
        f"• 🌍 **Ключ SMS.RU:** `{admin_cfg.get('smsru_key')[:8]}...`\n"
        f"• 🛟 **Поддержка:** `@{admin_cfg.get('support')}`\n\n"
        "👇 Выберите параметр для настройки:"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🔄 Маршрутизация звонков", callback_data="adm_routing_settings"))
    kb.row(types.InlineKeyboardButton("🏷️ Изменить цену звонка", callback_data="adm_change_price"))
    kb.row(types.InlineKeyboardButton("💎 Настройки CrystalPAY", callback_data="adm_set_crystal"))
    kb.row(types.InlineKeyboardButton("📞 Настройки Zvonok.com", callback_data="adm_set_zvonok"))
    kb.row(types.InlineKeyboardButton("🌍 Настройки SMS.RU", callback_data="adm_set_smsru"))
    kb.row(types.InlineKeyboardButton("🛟 Контакт поддержки", callback_data="adm_set_support"))
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    safe_nav(c, text, reply_markup=kb)

# ---- МАРШРУТИЗАЦИЯ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_routing_settings")
def on_routing_settings(c):
    if not is_admin(c.message.chat.id): return
    curr = admin_cfg.get("global_routing", "auto")
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if curr=='auto' else ''}🔄 Авто (Zvonok для РФ / SMS.RU для мира)", callback_data="set_route_auto"))
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if curr=='zvonok' else ''}🇷🇺 Всегда через Zvonok", callback_data="set_route_zvonok"))
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if curr=='smsru' else ''}🌍 Всегда через SMS.RU", callback_data="set_route_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к настройкам", callback_data="adm_full_settings"))
    
    text = "⚙️ **Выбор шлюза маршрутизации звонков:**"
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_route_"))
def on_set_route(c):
    if not is_admin(c.message.chat.id): return
    mode = c.data.replace("set_route_", "")
    admin_cfg["global_routing"] = mode
    save_json(CONFIG_FILE, admin_cfg)
    bot.answer_callback_query(c.id, f"✅ Маршрутизация переключена на {mode.upper()}!", show_alert=True)
    on_routing_settings(c)

# ---- ЦЕНА ЗВОНКА ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_change_price")
def on_adm_price(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_price"
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.row(
        types.InlineKeyboardButton("29 ₽", callback_data="set_price_29"),
        types.InlineKeyboardButton("39 ₽", callback_data="set_price_39"),
        types.InlineKeyboardButton("49 ₽", callback_data="set_price_49")
    )
    kb.row(
        types.InlineKeyboardButton("69 ₽", callback_data="set_price_69"),
        types.InlineKeyboardButton("99 ₽", callback_data="set_price_99"),
        types.InlineKeyboardButton("149 ₽", callback_data="set_price_149")
    )
    kb.row(types.InlineKeyboardButton("🔙 Назад к настройкам", callback_data="adm_full_settings"))
    safe_nav(c, f"🏷️ **Текущая цена:** `{admin_cfg.get('call_price')} ₽`\n\nВыберите готовую цену кнопкой или напишите желаемую сумму числом в чат:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_price_"))
def on_set_price_fast(c):
    if not is_admin(c.message.chat.id): return
    p = int(c.data.replace("set_price_", ""))
    admin_cfg["call_price"] = p
    save_json(CONFIG_FILE, admin_cfg)
    bot.answer_callback_query(c.id, f"✅ Цена установлена: {p} ₽!", show_alert=True)
    on_full_settings(c)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_price")
def step_adm_price_manual(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        p = int("".join(filter(str.isdigit, m.text)))
        admin_cfg["call_price"] = p
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Новая цена: {p} ₽!")
    except Exception as e:
        log_error("PRICE_CHANGE", str(e))
    show_admin_panel(m.chat.id)

# ---- CRYSTALPAY НАСТРОЙКИ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_set_crystal")
def on_set_crystal(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_crystal_login"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_full_settings"))
    text = (
        f"💎 **Настройки кассы CrystalPAY**\n\n"
        f"• Текущий логин кассы: `{admin_cfg.get('crystal_auth_login')}`\n"
        f"• Текущий секретный ключ: `{admin_cfg.get('crystal_secret')[:8]}...`\n\n"
        "Отправьте сообщением в чат логин кассы и секретный ключ через запятую:\n"
        "Пример: `dhdhe1728jd, c5fdf612bfd5e816a1a7447d2b942a3b03e36c04`"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_crystal_login")
def step_save_crystal(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    parts = [p.strip() for p in m.text.split(",")]
    if len(parts) >= 1 and parts[0]: admin_cfg["crystal_auth_login"] = parts[0]
    if len(parts) >= 2 and parts[1]: admin_cfg["crystal_secret"] = parts[1]
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, "✅ Настройки CrystalPAY обновлены!")
    show_admin_panel(m.chat.id)

# ---- ZVONOK НАСТРОЙКИ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_set_zvonok")
def on_set_zvonok(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_zvonok_cfg"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_full_settings"))
    text = (
        f"📞 **Настройки Zvonok.com**\n\n"
        f"• ID кампании: `{admin_cfg.get('campaign_id')}`\n"
        f"• Ключ API: `{admin_cfg.get('zvonok_key')[:8]}...`\n\n"
        "Отправьте ID кампании и API-ключ через запятую:\n"
        "Пример: `1783540036, d0808ab7450fca32147a9285018fe7a5`"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_zvonok_cfg")
def step_save_zvonok(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    parts = [p.strip() for p in m.text.split(",")]
    if len(parts) >= 1 and parts[0]: admin_cfg["campaign_id"] = parts[0]
    if len(parts) >= 2 and parts[1]: admin_cfg["zvonok_key"] = parts[1]
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, "✅ Настройки Zvonok.com сохранены!")
    show_admin_panel(m.chat.id)

# ---- SMS.RU НАСТРОЙКИ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_set_smsru")
def on_set_smsru(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_smsru_cfg"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_full_settings"))
    text = (
        f"🌍 **Настройки SMS.RU Voice**\n\n"
        f"• API ID: `{admin_cfg.get('smsru_key')}`\n\n"
        "Отправьте новый API ID от SMS.RU сообщением в чат:"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_smsru_cfg")
def step_save_smsru(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = m.text.strip()
    if k:
        admin_cfg["smsru_key"] = k
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, "✅ API ключ SMS.RU обновлен!")
    show_admin_panel(m.chat.id)

# ---- ПОДДЕРЖКА ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_set_support")
def on_set_support(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_support_cfg"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_full_settings"))
    safe_nav(c, f"🛟 Введите юзернейм поддержки (без @):\nТекущий: @{admin_cfg.get('support')}", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_support_cfg")
def step_save_support(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    u = m.text.strip().replace("@", "")
    if u:
        admin_cfg["support"] = u
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Поддержка установлена на @{u}!")
    show_admin_panel(m.chat.id)

# ================= ПОЛНОЦЕННЫЙ РЕДАКТОР РОЗЫГРЫШЕЙ =================
@bot.callback_query_handler(func=lambda c: c.data == "adm_pranks_manager")
def on_pranks_manager(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.row(types.InlineKeyboardButton("➕ СОЗДАТЬ НОВЫЙ РОЗЫГРЫШ", callback_data="adm_prank_create_new"))
    
    for k, v in pranks_db.items():
        pub_icon = "👁️" if v.get("public", True) else "🔒"
        audio_icon = "☁️" if k in audio_vault else "⚪"
        btn_title = f"{pub_icon} {audio_icon} {v['title']} [{v.get('tag', 'ТОП')}]"
        kb.row(types.InlineKeyboardButton(btn_title, callback_data=f"adm_edit_prank_{k}"))
        
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    
    text = (
        "🎭 **ПОЛНОЦЕННЫЙ РЕДАКТОР РОЗЫГРЫШЕЙ**\n\n"
        "Обозначения:\n"
        "• 👁️ — Виден в каталоге клиентам\n"
        "• 🔒 — Скрыт из каталога\n"
        "• ☁️ — Аудио зафиксировано в облаке навсегда\n\n"
        "👇 Нажмите на любой розыгрыш для полного редактирования или создайте новый:"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_edit_prank_"))
def on_edit_single_prank(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_edit_prank_", "")
    p = pranks_db.get(k)
    if not p:
        on_pranks_manager(c)
        return
        
    audio_status = "☁️ Загружено в облако" if k in audio_vault else "⚪ Используется локальный резерв"
    pub_status = "🟢 Виден клиентам" if p.get("public", True) else "🔴 Скрыт из каталога"
    
    text = (
        f"🎭 **Управление розыгрышем:**\n\n"
        f"🏷️ **Название:** {p.get('title')}\n"
        f"🔖 **Тег:** `{p.get('tag', 'ТОП')}`\n"
        f"📝 **Сценарий:** {p.get('desc', 'Без описания')}\n"
        f"🎵 **Аудио:** {audio_status}\n"
        f"👁️ **Статус:** {pub_status}\n"
        f"🔑 **ID ключа:** `{k}`"
    )
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("▶️ Послушать аудио", callback_data=f"adm_play_{k}"))
    kb.row(
        types.InlineKeyboardButton("🏷️ Изменить название", callback_data=f"adm_ch_title_{k}"),
        types.InlineKeyboardButton("🔖 Изменить тег", callback_data=f"adm_ch_tag_{k}")
    )
    kb.row(
        types.InlineKeyboardButton("📝 Изменить сценарий", callback_data=f"adm_ch_desc_{k}"),
        types.InlineKeyboardButton("🎵 Заменить аудио (MP3/Ссылка)", callback_data=f"adm_ch_audio_{k}")
    )
    pub_toggle_text = "🔒 Скрыть из каталога" if p.get("public", True) else "👁️ Сделать видимым"
    kb.row(types.InlineKeyboardButton(pub_toggle_text, callback_data=f"adm_toggle_pub_{k}"))
    kb.row(types.InlineKeyboardButton("❌ УДАЛИТЬ РОЗЫГРЫШ", callback_data=f"adm_del_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 К списку розыгрышей", callback_data="adm_pranks_manager"))
    
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_play_"))
def on_adm_play(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_play_", "")
    p = pranks_db.get(k)
    if not p: return
    audio_source = get_audio_source(k)
    bot.answer_callback_query(c.id, "🎵 Отправляю аудио...")
    try:
        if str(audio_source).startswith("http") or str(audio_source).startswith("AgAC") or len(str(audio_source)) > 40:
            bot.send_audio(c.message.chat.id, audio_source, title=p['title'], performer="GenCalls Cloud Preview")
        else:
            with open(audio_source, "rb") as a_file:
                bot.send_audio(c.message.chat.id, a_file, title=p['title'], performer="GenCalls Local Preview")
    except Exception as e:
        log_error("ADM_PLAY", str(e))
        bot.send_message(c.message.chat.id, f"⚠️ Не удалось воспроизвести: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_toggle_pub_"))
def on_toggle_pub(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_toggle_pub_", "")
    if k in pranks_db:
        pranks_db[k]["public"] = not pranks_db[k].get("public", True)
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.answer_callback_query(c.id, "✅ Статус видимости изменён!")
    on_edit_single_prank(c)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_ch_title_"))
def on_ch_title(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_ch_title_", "")
    user_data[c.message.chat.id] = {"edit_k": k}
    user_state[c.message.chat.id] = "waiting_new_prank_title"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data=f"adm_edit_prank_{k}"))
    safe_nav(c, "🏷️ Введите новое название для розыгрыша:\n(например: 👵 Бабка Лидия)", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_new_prank_title")
def step_save_new_title(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("edit_k")
    if k and k in pranks_db:
        pranks_db[k]["title"] = m.text.strip()
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.reply_to(m, "✅ Название успешно обновлено!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_ch_tag_"))
def on_ch_tag(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_ch_tag_", "")
    user_data[c.message.chat.id] = {"edit_k": k}
    user_state[c.message.chat.id] = "waiting_new_prank_tag"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data=f"adm_edit_prank_{k}"))
    safe_nav(c, "🔖 Введите новый тег для розыгрыша:\n(например: ХИТ 🔥, 18+ 🔞, ТОП 🌸)", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_new_prank_tag")
def step_save_new_tag(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("edit_k")
    if k and k in pranks_db:
        pranks_db[k]["tag"] = m.text.strip()
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.reply_to(m, "✅ Тег успешно обновлен!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_ch_desc_"))
def on_ch_desc(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_ch_desc_", "")
    user_data[c.message.chat.id] = {"edit_k": k}
    user_state[c.message.chat.id] = "waiting_new_prank_desc"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data=f"adm_edit_prank_{k}"))
    safe_nav(c, "📝 Введите новый текст описания/сценария розыгрыша:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_new_prank_desc")
def step_save_new_desc(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("edit_k")
    if k and k in pranks_db:
        pranks_db[k]["desc"] = m.text.strip()
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.reply_to(m, "✅ Сценарий успешно обновлен!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_ch_audio_"))
def on_ch_audio(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_ch_audio_", "")
    user_data[c.message.chat.id] = {"edit_k": k}
    user_state[c.message.chat.id] = "waiting_new_prank_audio"
    p = pranks_db.get(k, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data=f"adm_edit_prank_{k}"))
    safe_nav(c, f"🎵 Отправьте **прямую ссылку из Cloudinary** (или аудиофайл .mp3/голосовое) для:\n\n🎭 **{p.get('title', k)}**\n\n(Оно навсегда сохранится в облаке)", reply_markup=kb)

@bot.message_handler(content_types=["text", "audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "waiting_new_prank_audio")
def step_save_new_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("edit_k")
    
    val = None
    if m.text and m.text.startswith("http"):
        val = safe_url_encode(m.text.strip())
    elif m.audio:
        val = m.audio.file_id
    elif m.voice:
        val = m.voice.file_id
    elif m.document:
        val = m.document.file_id
        
    if val and k:
        audio_vault[k] = val
        save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.reply_to(m, f"🎉 УСПЕХ! Аудио/ссылка Cloudinary привязана к «{pranks_db.get(k, {}).get('title', k)}» навсегда!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_prank_create_new")
def on_create_prank_start(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_prank_new_title"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_pranks_manager"))
    safe_nav(c, "➕ **Шаг 1 из 3:** Введите название нового розыгрыша:\n(например: 🍕 Пицца с сюрпризом)", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_title")
def step_prank_new_title(m):
    if not is_admin(m.chat.id): return
    user_data[m.chat.id] = {"new_title": m.text.strip(), "new_key": f"prank_{int(time.time())}"}
    user_state[m.chat.id] = "adm_prank_new_desc"
    bot.reply_to(m, "📝 **Шаг 2 из 3:** Введите краткое описание сценария:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_desc")
def step_prank_new_desc(m):
    if not is_admin(m.chat.id): return
    user_data[m.chat.id]["new_desc"] = m.text.strip()
    user_state[m.chat.id] = "adm_prank_new_audio"
    bot.reply_to(m, "🎵 **Шаг 3 из 3:** Отправьте ссылку из Cloudinary или MP3 файл:")

@bot.message_handler(content_types=["text", "audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_audio")
def step_prank_new_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    d = user_data.get(m.chat.id, {})
    k = d.get("new_key")
    
    val = None
    if m.text and m.text.startswith("http"):
        val = safe_url_encode(m.text.strip())
    elif m.audio:
        val = m.audio.file_id
    elif m.voice:
        val = m.voice.file_id
    elif m.document:
        val = m.document.file_id
    
    if k and val:
        pranks_db[k] = {
            "title": d.get("new_title", "Новый розыгрыш"),
            "tag": "NEW 🔥",
            "dur": 30,
            "desc": d.get("new_desc", ""),
            "file": f"{k}.mp3",
            "public": True
        }
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        audio_vault[k] = val
        save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.reply_to(m, f"🎉 Розыгрыш «{d.get('new_title')}» успешно опубликован в каталоге с вечным облачным аудио!")
        show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_del_prank_"))
def on_del_prank(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_del_prank_", "")
    if k in pranks_db:
        del pranks_db[k]
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        if k in audio_vault:
            del audio_vault[k]
            save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.answer_callback_query(c.id, "✅ Розыгрыш удален!", show_alert=True)
    on_pranks_manager(c)

# ================= ЖУРНАЛ ОШИБОК И ДИАГНОСТИКА =================
@bot.callback_query_handler(func=lambda c: c.data == "adm_error_logs")
def on_error_logs(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.row(types.InlineKeyboardButton("🧪 Проверить связь со всеми API", callback_data="adm_test_apis"))
    kb.row(types.InlineKeyboardButton("🧹 Очистить журнал ошибок", callback_data="adm_clear_logs"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    
    if not ERROR_LOGS:
        log_text = "✅ Журнал чист! Никаких критических ошибок не зафиксировано."
    else:
        recent = ERROR_LOGS[-10:]
        log_text = "🚨 **ПОСЛЕДНИЕ ЗАФИКСИРОВАННЫЕ ОШИБКИ:**\n\n" + "\n\n".join(recent)
    
    safe_nav(c, log_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_clear_logs")
def on_clear_logs(c):
    if not is_admin(c.message.chat.id): return
    ERROR_LOGS.clear()
    bot.answer_callback_query(c.id, "🧹 Журнал очищен!", show_alert=True)
    on_error_logs(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_test_apis")
def on_test_apis(c):
    if not is_admin(c.message.chat.id): return
    bot.answer_callback_query(c.id, "⏳ Проверяем...")
    
    cr_login = admin_cfg.get("crystal_auth_login")
    cr_secret = admin_cfg.get("crystal_secret")
    try:
        r_cr = requests.post("https://api.crystalpay.io/v2/invoice/create/", json={"auth_login": cr_login, "auth_secret": cr_secret, "amount": 10, "type": "purchase", "lifetime": 15}, timeout=5).json()
        cr_status = "🟢 OK" if not r_cr.get("error") else f"🔴 Ошибка: {r_cr.get('errors')}"
    except Exception as e: cr_status = f"🔴 {e}"

    try:
        r_zv = requests.get("https://zvonok.com/manager/cabapi_external/api/v1/phones/call/", params={"public_key": admin_cfg.get("zvonok_key"), "campaign_id": admin_cfg.get("campaign_id")}, verify=False, timeout=5).json()
        zv_status = "🟢 API отвечает" if isinstance(r_zv, dict) else "🔴 Ошибка"
    except Exception as e: zv_status = f"🔴 {e}"

    try:
        r_sms = requests.get("https://sms.ru/my/balance", params={"api_id": admin_cfg.get("smsru_key"), "json": 1}, timeout=5).json()
        sms_status = f"🟢 Баланс: {r_sms.get('balance')} ₽" if r_sms.get("status") == "OK" else f"🔴 {r_sms.get('status_text')}"
    except Exception as e: sms_status = f"🔴 {e}"

    report = (
        "🧪 **РЕЗУЛЬТАТЫ ДИАГНОСТИКИ:**\n\n"
        f"💎 **CrystalPAY:** {cr_status}\n\n"
        f"🇷🇺 **Zvonok.com:** {zv_status}\n\n"
        f"🌍 **SMS.RU:** {sms_status}\n\n"
        f"🤖 **Telegram Polling:** 🟢 Активен"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад к журналу", callback_data="adm_error_logs"))
    safe_nav(c, report, reply_markup=kb)

# ---- ВЫДАЧА БАЛАНСА И РАССЫЛКА ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_add_balance")
def on_adm_add(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_uid"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 Введите ID пользователя:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_uid")
def step_adm_uid(m):
    if not is_admin(m.chat.id): return
    uid = "".join(filter(str.isdigit, m.text))
    user_data[m.chat.id] = {"target_uid": uid}
    user_state[m.chat.id] = "adm_sum"
    bot.reply_to(m, f"Сколько рублей начислить пользователю {uid}:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_sum")
def step_adm_sum(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        s = int(m.text.strip())
        t_uid = user_data[m.chat.id]["target_uid"]
        u, _ = get_user(t_uid)
        u["balance_rub"] += s
        save_json(DB_FILE, db)
        bot.reply_to(m, f"✅ Начислено {s} ₽ пользователю {t_uid}!")
    except Exception as e:
        log_error("ADD_BALANCE", str(e))
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_bc(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_bc"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 Введите текст рассылки:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_bc")
def step_adm_bc(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    t = m.text
    cnt = 0
    for u in db.keys():
        try:
            bot.send_message(int(u), f"📢 {t}")
