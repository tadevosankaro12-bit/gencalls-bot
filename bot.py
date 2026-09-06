import os, json, telebot, requests, time, threading, logging, uuid
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ================= КОНФИГУРАЦИЯ =================
TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"

# ВАШ TELEGRAM ID
ADMIN_IDS = ["8682521929", "8915393389"]

# ЮKASSA
YOOKASSA_SHOP_ID = "1457004"
YOOKASSA_SECRET_KEY = "test_5G_U5bmrnZ80QXZuhZe61guqmt9gwwmuOuvCzYaSkVI"

# Телефония
ZVONOK_API_KEY = "d0808ab7450fca32147a9285018fe7a5"
CAMPAIGN_ID = "1783540036"
SMSRU_API_KEY = "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF"

SUPPORT_USERNAME = "tadevosankaro12"
CHANNEL_URL = "https://t.me/gencalls_channel"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
PROMO_FILE = os.path.join(BASE_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(BASE_DIR, "gencalls_blacklist.json")
CUSTOM_PRANKS_FILE = os.path.join(BASE_DIR, "gencalls_pranks.json")
PROCESSED_PAYMENTS_FILE = os.path.join(BASE_DIR, "processed_payments.json")
AUDIO_CACHE_FILE = os.path.join(BASE_DIR, "audio_file_cache.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception: pass

admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 3,
    "admin_id": "8682521929",
    "shop_id": YOOKASSA_SHOP_ID,
    "secret_key": YOOKASSA_SECRET_KEY,
    "channel_url": CHANNEL_URL,
    "block_test_payments": True
})
admin_cfg["admin_id"] = "8682521929"
admin_cfg["shop_id"] = YOOKASSA_SHOP_ID
admin_cfg["secret_key"] = YOOKASSA_SECRET_KEY
admin_cfg["block_test_payments"] = True
if "channel_url" not in admin_cfg:
    admin_cfg["channel_url"] = CHANNEL_URL
save_json(CONFIG_FILE, admin_cfg)

db = load_json(DB_FILE, {})
promocodes = load_json(PROMO_FILE, {"GEN2026": {"rub": 49, "uses": 100, "used_by": []}})
blacklist = load_json(BLACKLIST_FILE, [])
processed_payments = load_json(PROCESSED_PAYMENTS_FILE, [])

# ВЕЧНЫЙ КЭШ ПОЛНОЦЕННЫХ АУДИОФАЙЛОВ
audio_cloud_vault = load_json(AUDIO_CACHE_FILE, {})

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 3)
START_BONUS_RUB = CALL_PRICE_RUB * 2  # 2 БЕСПЛАТНЫХ ЗВОНКА (98 ₽)

# ================= КАТАЛОГ ПРАНКОВ =================
DEFAULT_PRANKS = {
    "babka": {
        "title": "👵 Бабка Лидия (Долг)", 
        "tag": "ХИТ 🔥", 
        "dur": 35, 
        "desc": "Скандальная пенсионерка обвиняет в краже пенсии и требует вернуть долг с угрозами участковым.",
        "file": "babka.mp3",
        "public": True
    },
    "tulip": {
        "title": "🌷 Тюльпаны оптом", 
        "tag": "ТОП 🌸", 
        "dur": 40, 
        "desc": "Срочная доставка 500 тюльпанов на свадьбу прямо сейчас: «Выходите забирайте, иначе завянут!»",
        "file": "tulip.mp3",
        "public": True
    },
    "rkn": {
        "title": "🏛️ Роскомнадзор (Блокировка)", 
        "tag": "ШОК ⚠️", 
        "dur": 45, 
        "desc": "Официальное предупреждение: зафиксирована подозрительная активность, ваш интернет будет заблокирован.",
        "file": "rkn.mp3",
        "public": True
    },
    "django": {
        "title": "🕺 Джанго стриптизер", 
        "tag": "18+ 🔞", 
        "dur": 38, 
        "desc": "Приватный стриптизер звонит в домофон: «Я уже в костюме с маслом у вашей двери, открывайте!»",
        "file": "django.mp3",
        "public": True
    },
    "govnovoz": {
        "title": "🚛 Ассенизатор (Шланг)", 
        "tag": "УГАР 😂", 
        "dur": 30, 
        "desc": "Машина приехала откачивать септик прямо во двор: «Куда шланг кидать, открывайте ворота!»",
        "file": "govnovoz.mp3",
        "public": True
    },
    "courier": {
        "title": "🍕 Голодный курьер", 
        "tag": "НОВОЕ 🍕", 
        "dur": 32, 
        "desc": "Курьер признаётся: «Вы долго не открывали, я не сдержался и съел вашу пиццу, простите...»",
        "file": "courier.mp3",
        "public": True
    }
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
for k, v in DEFAULT_PRANKS.items():
    if k not in pranks_db:
        pranks_db[k] = v
save_json(CUSTOM_PRANKS_FILE, pranks_db)

PACKAGES = {
    "pkg_1": {"title": "1 звонок", "rub": 49, "badge": "Старт"},
    "pkg_5": {"title": "5 звонков", "rub": 149, "badge": "🔥 -40%"},
    "pkg_15": {"title": "15 звонков", "rub": 299, "badge": "👑 Хит"},
    "pkg_50": {"title": "50 звонков", "rub": 699, "badge": "VIP"}
}

def is_admin(uid):
    uid_str = str(uid).strip()
    return uid_str in ADMIN_IDS or uid_str == "8682521929"

def get_user(uid, uname="Друг"):
    s_uid = str(uid).strip()
    is_new = False
    if s_uid not in db:
        reg_date = datetime.now().strftime("%d.%m.%Y")
        db[s_uid] = {
            "name": uname,
            "balance_rub": START_BONUS_RUB,
            "calls_history": [],
            "referrals": 0,
            "referred_by": None,
            "reg_date": reg_date,
            "routing_mode": "auto"
        }
        save_json(DB_FILE, db)
        is_new = True
    return db[s_uid], is_new

def parse_phone(text):
    if not text: return None
    digits = "".join(filter(str.isdigit, text.strip()))
    if not digits: return None
    if len(digits) == 10 and digits.startswith("9"):
        return "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        return "7" + digits[1:]
    return digits

def find_audio_file(filename):
    for folder in [AUDIO_DIR, BASE_DIR]:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            return path
    return None

# ================= ШЛЮЗЫ ТЕЛЕФОНИИ =================
def call_zvonok_campaign(phone):
    url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    params = {
        "campaign_id": CAMPAIGN_ID,
        "phone": f"+{phone}",
        "public_key": ZVONOK_API_KEY,
        "check_duplicate": "0",
        "record": "1"
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=12)
        res = r.json()
        if isinstance(res, dict):
            if res.get("status") == "error" or "error" in res:
                err_msg = res.get("data") or res.get("message") or res.get("error") or str(res)
                return False, f"Zvonok: {err_msg}", None
            call_id = res.get("call_id") or (res.get("data", {}).get("call_id") if isinstance(res.get("data"), dict) else None)
            return True, str(call_id or f"ZV-{int(time.time())}"), "zvonok"
        return False, f"Zvonok: {r.text[:100]}", None
    except Exception as e:
        return False, f"Zvonok: {str(e)}", None

def call_smsru_smart(phone):
    gateway_ips = ["185.129.100.1", "91.240.85.5", "127.0.0.1"]
    for user_ip in gateway_ips:
        methods = [
            ("https://sms.ru/code/call", {"phone": phone, "api_id": SMSRU_API_KEY, "json": 1, "user_ip": user_ip}),
            ("https://sms.ru/callcheck/add", {"phone": phone, "api_id": SMSRU_API_KEY, "json": 1, "user_ip": user_ip}),
            ("https://sms.ru/code/call", {"phone": phone, "api_id": SMSRU_API_KEY, "json": 1})
        ]
        for url, params in methods:
            try:
                r = requests.get(url, params=params, timeout=8)
                res = r.json()
                if res.get("status") == "OK":
                    cid = res.get("call_id") or res.get("check_id") or res.get("code") or f"SMS-{int(time.time())}"
                    return True, str(cid), "smsru"
            except Exception:
                pass
            time.sleep(0.3)
    return False, "SMS.RU: Маршрут временно недоступен", None

def track_call_and_send_record(chat_id, call_id, phone, prank_title, service_type):
    time.sleep(30)
    record_url = None
    if service_type == "zvonok":
        for _ in range(3):
            try:
                status_url = f"https://zvonok.com/manager/cabapi_external/api/v1/phones/call_by_id/"
                params = {"call_id": call_id, "public_key": ZVONOK_API_KEY}
                r = requests.get(status_url, params=params, verify=False, timeout=8)
                res = r.json()
                record_url = res.get("record_url") or res.get("data", {}).get("record_url")
                if record_url: break
            except Exception: pass
            time.sleep(8)
            
    if record_url:
        try:
            bot.send_audio(
                chat_id, 
                record_url, 
                title=f"Реакция жертвы ({prank_title})",
                performer="GenCalls Запись",
                caption=(
                    f"🎉 **Звонок завершён! Запись разговора готова!**\n\n"
                    f"📞 Номер жертвы: `+{phone}`\n"
                    f"🎭 Розыгрыш: **{prank_title}**\n\n"
                    f"👇 _Нажмите Play на аудиотреке выше, чтобы послушать реакцию!_"
                ),
                parse_mode="Markdown"
            )
        except Exception: pass

def process_call_async(chat_id, phone, prank_key, p_title, wait_msg_id):
    u, _ = get_user(chat_id)
    rmode = u.get("routing_mode", "auto")
    use_service = "zvonok" if (rmode == "zvonok" or (rmode == "auto" and phone.startswith("7"))) else "smsru"
    service_name = "🇷🇺 Zvonok (+7)" if use_service == "zvonok" else "🌍 SMS.RU Voice"

    success = False
    call_id = None
    service_type = "zvonok"

    if use_service == "zvonok":
        success, call_id, service_type = call_zvonok_campaign(phone)
        if not success:
            success_fb, call_id_fb, service_type = call_smsru_smart(phone)
            if success_fb:
                success, call_id, service_name = True, call_id_fb, "🌍 SMS.RU (Резерв)"
    else:
        success, call_id, service_type = call_smsru_smart(phone)
        if not success and phone.startswith("7"):
            success_zb, call_id_zb, service_type = call_zvonok_campaign(phone)
            if success_zb:
                success, call_id, service_name = True, call_id_zb, "🇷🇺 Zvonok (Резерв)"

    if not success:
        bot.edit_message_text(
            f"❌ **Не удалось совершить вызов!**\n\nОтвет шлюза: `{call_id}`\n\n💰 Баланс НЕ списан.",
            chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id)
        )
        return

    u["balance_rub"] = max(0, u["balance_rub"] - CALL_PRICE_RUB)
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m %H:%M"),
        "phone": phone,
        "prank": p_title,
        "service": service_name,
        "call_id": str(call_id)
    })
    save_json(DB_FILE, db)

    bot.edit_message_text(
        f"✅ **Звонок успешно запущен!**\n\n"
        f"📞 Номер: `+{phone}`\n"
        f"🌐 Канал: **{service_name}**\n"
        f"🎭 Розыгрыш: **{p_title}**\n"
        f"🆔 ID звонка: `{call_id}`\n"
        f"💰 Остаток: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞)\n\n"
        f"🎙️ **Запись разговора включена!**\n"
        f"_По окончании звонка полноценный MP3-аудиофайл придёт прямо в этот чат!_",
        chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id)
    )
    threading.Thread(target=track_call_and_send_record, args=(chat_id, call_id, phone, p_title, service_type), daemon=True).start()

# ================= ЮKASSA =================
def create_yookassa_payment(amount_rub, user_id, package_name):
    url = "https://api.yookassa.ru/v3/payments"
    shop_id = admin_cfg.get("shop_id", YOOKASSA_SHOP_ID)
    secret_key = admin_cfg.get("secret_key", YOOKASSA_SECRET_KEY)
    headers = {"Idempotence-Key": str(uuid.uuid4()), "Content-Type": "application/json"}
    bot_info = bot.get_me()
    return_url = f"https://t.me/{bot_info.username}"
    data = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": f"Пополнение GenCalls: {package_name} (ID {user_id})",
        "metadata": {"user_id": str(user_id), "amount_rub": str(amount_rub)}
    }
    try:
        r = requests.post(url, json=data, headers=headers, auth=(shop_id, secret_key), timeout=12)
        res = r.json()
        if "confirmation" in res and "confirmation_url" in res["confirmation"]:
            return True, res["confirmation"]["confirmation_url"], res["id"]
        return False, res.get("description", str(res)), None
    except Exception as e:
        return False, str(e), None

def check_yookassa_payment_safe(payment_id):
    url = f"https://api.yookassa.ru/v3/payments/{payment_id}"
    shop_id = admin_cfg.get("shop_id", YOOKASSA_SHOP_ID)
    secret_key = admin_cfg.get("secret_key", YOOKASSA_SECRET_KEY)
    try:
        r = requests.get(url, auth=(shop_id, secret_key), timeout=10)
        res = r.json()
        status = res.get("status")
        paid = res.get("paid", False)
        is_test = res.get("test", False)
        if is_test:
            return "test_blocked", False
        return status, paid
    except Exception:
        return "error", False

def kb_main_menu(uid):
    u, _ = get_user(uid)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // CALL_PRICE_RUB
    rmode = u.get("routing_mode", "auto")
    
    if rmode == "zvonok":
        rmode_label = "⚙️ Маршрут: 🇷🇺 РФ (+7)"
    elif rmode == "smsru":
        rmode_label = "⚙️ Маршрут: 🌍 SMS.RU (Мир)"
    else:
        rmode_label = "⚙️ Маршрут: ⚡ Авто-шлюз"
    
    chan_link = admin_cfg.get("channel_url", CHANNEL_URL)

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Отправить звонок-розыгрыш", callback_data="catalog"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton(rmode_label, callback_data="nav_routing"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🤝 Партнёрам", callback_data="nav_affiliate"),
        types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo")
    )
    kb.row(
        types.InlineKeyboardButton("📢 Наш Telegram-канал", url=chan_link),
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank")
    )
    return kb

def safe_nav(c, text, reply_markup=None):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    try:
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        try: bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception: pass
        try: bot.send_message(c.message.chat.id, text, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception: pass

MAIN_TEXT_BANNER = (
    "🎭 **GenCalls — Пранк-Звонки с записью реакции!**\n\n"
    "🎁 **Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!**\n\n"
    "🕵️‍♂️ **Анонимность 100%** — ваш номер никто не увидит.\n"
    "🎙️ **MP3 Аудиоплеер** — слушайте пранки и реакции прямо в Telegram!\n"
    "🌍 **Связь без сбоев:** Россия (+7), Армения (+374) и весь мир.\n\n"
    "👇 _Выберите пранк и разыграйте друга прямо сейчас:_"
)

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u, is_new = get_user(m.chat.id, m.from_user.first_name or "Друг")
    welcome_text = MAIN_TEXT_BANNER
    if is_new:
        welcome_text = (
            "🎉 **Добро пожаловать в GenCalls!**\n\n"
            f"🎁 Мы начислили вам **+{START_BONUS_RUB} ₽ на баланс (2 БЕСПЛАТНЫХ ЗВОНКА)**!\n"
            "Попробуйте разыграть любого друга прямо сейчас абсолютно бесплатно! 🚀\n\n"
            + MAIN_TEXT_BANNER
        )
    bot.send_message(m.chat.id, welcome_text, parse_mode="Markdown", reply_markup=kb_main_menu(m.chat.id))

# ---- КАТАЛОГ С ПОЛНОЦЕННЫМ MP3 АУДИОПЛЕЕРОМ ----
@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog(c):
    admin_mode = is_admin(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        is_pub = v.get("public", True)
        if is_pub or admin_mode:
            prefix_tag = "" if is_pub else "🔒 [Скрытый] "
            has_voice = "🎵 " if (k in audio_cloud_vault or find_audio_file(v.get("file", ""))) else ""
            kb.row(types.InlineKeyboardButton(f"{prefix_tag}{has_voice}{v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 **Каталог голосовых розыгрышей:**\n\nВыберите пранк для прослушивания в плеере и запуска:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({CALL_PRICE_RUB} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    desc_text = (
        f"🎭 **{p['title']}** [{p.get('tag', 'ТОП')}]\n\n"
        f"💬 **Сценарий:** {p.get('desc', '')}\n\n"
        f"🎙️ _После разговора бот пришлёт вам MP3-запись реакции жертвы!_\n"
        f"👇 _Нажмите кнопку ниже, чтобы запустить звонок:_"
    )
    
    # 1. Отправляем полноценный MP3-аудиофайл из облачного хранилища Telegram
    cached_fid = audio_cloud_vault.get(k)
    if cached_fid:
        try:
            bot.answer_callback_query(c.id)
            bot.send_audio(
                c.message.chat.id, 
                cached_fid, 
                title=p['title'],
                performer="GenCalls Пранк",
                caption=desc_text, 
                parse_mode="Markdown", 
                reply_markup=kb
            )
            return
        except Exception:
            pass
            
    # 2. Если в облаке ещё нет — читаем локальный файл и навсегда сохраняем в облако
    audio_path = find_audio_file(p.get("file", f"{k}.mp3"))
    if audio_path:
        try:
            bot.answer_callback_query(c.id)
            with open(audio_path, "rb") as a_file:
                sent_msg = bot.send_audio(
                    c.message.chat.id, 
                    a_file, 
                    title=p['title'],
                    performer="GenCalls Пранк",
                    caption=desc_text, 
                    parse_mode="Markdown", 
                    reply_markup=kb
                )
                if sent_msg.audio:
                    audio_cloud_vault[k] = sent_msg.audio.file_id
                    save_json(AUDIO_CACHE_FILE, audio_cloud_vault)
            return
        except Exception:
            pass
    
    safe_nav(c, desc_text, reply_markup=kb)

# ---- ЗВОНКИ ----
@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    u, _ = get_user(c.message.chat.id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
        safe_nav(c, f"❌ **Недостаточно средств на балансе**\n\nСтоимость звонка: **{CALL_PRICE_RUB} ₽**\nВаш баланс: **{u.get('balance_rub', 0)} ₽**", reply_markup=kb)
        return
    k = c.data.replace("setup_call_", "")
    user_data[c.message.chat.id] = {"prank": k}
    user_state[c.message.chat.id] = "waiting_phone"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📱 **Введите номер телефона жертвы в международном формате:**\n\n• Россия / Казахстан: `+79991234567`\n• Армения: `+37498123456`\n• Другие страны: `+код...`", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def step_phone_input(m):
    chat_id = m.chat.id
    phone = parse_phone(m.text)
    
    if not phone or len(phone) < 8:
        bot.reply_to(m, "❌ Некорректный номер. Введите с кодом страны (+79991234567 или +374...):")
        return

    if phone in blacklist or f"+{phone}" in blacklist:
        bot.reply_to(m, "🛡️ Этот номер находится в защитном списке бота.")
        return

    user_state[chat_id] = None
    d = user_data.get(chat_id, {"prank": "babka"})
    prank_key = d.get("prank", "babka")
    p = pranks_db.get(prank_key, pranks_db["babka"])
    w = bot.send_message(chat_id, f"🚀 _Набираем номер +{phone}..._")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, p["title"], w.message_id), daemon=True).start()

# ---- МАРШРУТИЗАЦИЯ ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_routing")
def cb_routing(c):
    u, _ = get_user(c.message.chat.id)
    cur = u.get("routing_mode", "auto")
    text = (
        "⚙️ **Настройки Маршрутизации Вызовов**\n\n"
        f"1. ⚡ **Умный Авто-выбор** {'✅ [ВКЛЮЧЕНО]' if cur == 'auto' else ''}\n"
        "   _Авто-переключение между шлюзами при любых сбоях операторов._\n\n"
        f"2. 🇷🇺 **Только Zvonok (+7 РФ)** {'✅ [ВКЛЮЧЕНО]' if cur == 'zvonok' else ''}\n\n"
        f"3. 🌍 **Только SMS.RU (+374 / Весь Мир)** {'✅ [ВКЛЮЧЕНО]' if cur == 'smsru' else ''}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"{'👉 ' if cur=='auto' else ''}⚡ Умный Авто-выбор", callback_data="set_route_auto"))
    kb.row(types.InlineKeyboardButton(f"{'👉 ' if cur=='zvonok' else ''}🇷🇺 Только Zvonok (+7)", callback_data="set_route_zvonok"))
    kb.row(types.InlineKeyboardButton(f"{'👉 ' if cur=='smsru' else ''}🌍 Только SMS.RU (+374/Мир)", callback_data="set_route_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_route_"))
def on_set_route(c):
    mode = c.data.replace("set_route_", "")
    u, _ = get_user(c.message.chat.id)
    u["routing_mode"] = mode
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Маршрут переключен!")
    cb_routing(c)

# ---- ОПЛАТА ----
@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    text = (
        "💳 **Пополнение баланса бота:**\n\n"
        "• 💳 **Банковская карта (МИР, Visa, Mastercard)**\n"
        "• 🟢 **SberPay**\n"
        "• 🟣 **ЮMoney**\n\n"
        "Выберите пакет:"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['title']} — {p['rub']} ₽ ({p['badge']})", callback_data=f"buy_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_pkg_"))
def on_buy_package(c):
    pid = c.data.replace("buy_", "")
    pkg = PACKAGES.get(pid)
    if not pkg: return
    
    uid = c.message.chat.id
    bot.answer_callback_query(c.id, "⏳ Создаём платёж...")
    success, pay_url, payment_id = create_yookassa_payment(pkg["rub"], uid, pkg["title"])
    
    if not success or not pay_url:
        pay_url = f"https://yoomoney.ru/to/{YOOKASSA_SHOP_ID}/{pkg['rub']}"
        payment_id = f"gen_{int(time.time())}"

    text = (
        f"📦 **Заказ: {pkg['title']} ({pkg['rub']} ₽)**\n\n"
        f"💳 Для оплаты картой или SberPay нажмите кнопку ниже:\n"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"💳 Оплатить {pkg['rub']} ₽", url=pay_url))
    kb.row(types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_yk_{payment_id}_{pkg['rub']}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_yk_"))
def on_check_yk_pay(c):
    parts = c.data.split("_")
    payment_id = parts[2]
    amount = int(parts[3])
    uid = c.message.chat.id
    
    bot.answer_callback_query(c.id, "⏳ Проверяем платёж...")
    if payment_id in processed_payments:
        safe_nav(c, "⚠️ Этот платёж уже был начислен ранее!", reply_markup=kb_main_menu(uid))
        return

    status, paid = check_yookassa_payment_safe(payment_id)
    if status == "test_blocked":
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💳 Оплатить реально", callback_data="packages_menu"))
        kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
        safe_nav(c, (
            "⛔ **ОШИБКА: Платёж отклонён!**\n\n"
            "Вы провели оплату в **Тестовом режиме**, реальные деньги не были списаны.\n"
            "Баланс начисляется **ТОЛЬКО** за настоящую оплату реальными средствами!"
        ), reply_markup=kb)
        return

    if paid or status == "succeeded":
        processed_payments.append(payment_id)
        save_json(PROCESSED_PAYMENTS_FILE, processed_payments)
        u, _ = get_user(uid)
        u["balance_rub"] = u.get("balance_rub", 0) + amount
        save_json(DB_FILE, db)
        safe_nav(c, f"🎉 **Оплата подтверждена!**\n\nНачислено: **+{amount} ₽**!\nБаланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞)", reply_markup=kb_main_menu(uid))
    else:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔄 Повторить проверку", callback_data=c.data))
        kb.row(types.InlineKeyboardButton("👨‍💻 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        safe_nav(c, f"⏳ **Платёж пока не поступил (Статус: {status})**\n\nЕсли вы оплатили в приложении банка, подождите 10 секунд и нажмите «Повторить проверку».", reply_markup=kb)

# ---- КАБИНЕТ, ПОДДЕРЖКА, ПРОМОКОДЫ, ПАРТНЁРКА ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u, _ = get_user(c.message.chat.id)
    calls = u["balance_rub"] // CALL_PRICE_RUB
    history = u.get("calls_history", [])
    text = (
        f"👤 **Личный кабинет**\n\n"
        f"🆔 ID: `{c.message.chat.id}`\n"
        f"💰 Баланс: **{u['balance_rub']} ₽** ({calls} 📞)\n"
        f"⚙️ Маршрут: `{u.get('routing_mode', 'auto')}`\n\n"
    )
    if history:
        text += "🎙️ **Последние вызовы:**\n"
        for h in history[-3:]:
            text += f"• `+{h['phone']}` — {h['prank']}\n"
    else:
        text += "_История звонков пуста._"

    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_support(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать создателю", url=f"https://t.me/{SUPPORT_USERNAME}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🛟 **Служба поддержки:**\nЕсли возникли вопросы, напишите напрямую создателю бота.", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u, _ = get_user(c.message.chat.id)
    text = (
        f"🤝 **Партнёрская программа**\n\n"
        f"Получайте **+49 ₽** за каждого приглашённого друга!\n\n"
        f"👥 Приглашено: **{u.get('referrals', 0)}/{MAX_REFERRALS}**\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def on_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo_code"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ **Введите промокод:**", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promo_code")
def step_enter_promo(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    u, _ = get_user(m.chat.id)
    if code in promocodes and str(m.chat.id) not in promocodes[code].get("used_by", []):
        promocodes[code].setdefault("used_by", []).append(str(m.chat.id))
        bonus = promocodes[code].get("rub", 49)
        save_json(PROMO_FILE, promocodes)
        u["balance_rub"] += bonus
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 Промокод активирован! +{bonus} ₽ начислено на ваш баланс.", reply_markup=kb_main_menu(m.chat.id))
    else:
        bot.reply_to(m, "❌ Промокод недействителен или уже был активирован.", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "anti_prank")
def on_anti_prank(c):
    user_state[c.message.chat.id] = "waiting_blacklist_num"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🛡️ **Анти-Пранк защита**\n\nВведите номер, который хотите защитить от звонков:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_blacklist_num")
def step_blacklist_num(m):
    user_state[m.chat.id] = None
    num = parse_phone(m.text)
    if num and num not in blacklist:
        blacklist.append(num)
        blacklist.append(f"+{num}")
        save_json(BLACKLIST_FILE, blacklist)
    bot.reply_to(m, f"🛡️ Номер +{num} защищен от звонков!", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def on_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

# ================= АДМИНКА (/admin) =================
@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not is_admin(m.chat.id):
        return bot.reply_to(m, f"⛔ Доступ запрещён. Ваш ID: `{m.chat.id}`", parse_mode="Markdown")
    user_state[m.chat.id] = None
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, c)

def show_admin_panel(chat_id, c=None):
    total_calls = sum(len(u.get("calls_history", [])) for u in db.values())
    total_rub = sum(u.get("balance_rub", 0) for u in db.values())
    shop_id = admin_cfg.get("shop_id", YOOKASSA_SHOP_ID)
    saved_count = len(audio_cloud_vault)
    
    text = (
        "👑 **Панель Администратора Пранк-Бота**\n\n"
        f"👤 Ваш ID: `{chat_id}` (Гл. Администратор)\n"
        f"💳 ЮKassa ShopID: `{shop_id}`\n"
        f"🎵 Полноценных MP3-аудио в облаке: **{saved_count} шт.**\n"
        f"🎁 Старт бонус: **2 бесплатных звонка ({START_BONUS_RUB} ₽)**\n"
        f"👥 Пользователей: **{len(db)}**\n"
        f"📞 Звонков совершено: **{total_calls}**\n"
        f"💰 Честный баланс пользователей: **{total_rub} ₽**\n"
        f"🏷️ Цена звонка: **{CALL_PRICE_RUB} ₽**"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎵 Загрузить MP3-аудио в облако", callback_data="adm_upload_audio_menu"))
    kb.row(types.InlineKeyboardButton("🧪 Проверить статус шлюзов", callback_data="adm_check_services"))
    kb.row(types.InlineKeyboardButton("💳 Изменить баланс юзера", callback_data="adm_add_balance"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

# ---- ЗАГРУЗКА И ОПРЕДЕЛЕНИЕ ПОЛНОЦЕННЫХ АУДИОФАЙЛОВ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_audio_menu")
def cb_adm_upload_menu(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        status_icon = "🎵" if k in audio_cloud_vault else "⚠️"
        kb.row(types.InlineKeyboardButton(f"{status_icon} {v['title']}", callback_data=f"adm_up_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎵 **Выберите розыгрыш, чтобы прикрепить полноценный аудиофайл:**\n\n_Файл навсегда сохранится с плеером и обложкой!_", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_up_prank_"))
def on_select_prank_for_upload(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_up_prank_", "")
    user_data[c.message.chat.id] = {"upload_prank_key": k}
    user_state[c.message.chat.id] = "adm_waiting_voice_file"
    p = pranks_db.get(k, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_upload_audio_menu"))
    safe_nav(c, f"🎵 **Отправьте сюда в чат полноценный аудиофайл (.mp3, .wav, .m4a) для:**\n\n🎭 **{p.get('title', k)}**\n\n_Бот мгновенно сохранит его в формате музыкального трека!_", reply_markup=kb)

@bot.message_handler(content_types=["audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_waiting_voice_file")
def on_receive_admin_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("upload_prank_key")
    if not k: return
    
    file_id = None
    # Приоритет отдаётся полноценному Audio
    if m.audio:
        file_id = m.audio.file_id
    elif m.voice:
        file_id = m.voice.file_id
    elif m.document and ("audio" in (m.document.mime_type or "") or m.document.file_name.lower().endswith((".mp3", ".wav", ".m4a", ".ogg"))):
        file_id = m.document.file_id
        
    if file_id:
        audio_cloud_vault[k] = file_id
        save_json(AUDIO_CACHE_FILE, audio_cloud_vault)
        bot.reply_to(m, f"🎉 **Полноценный аудиофайл успешно сохранён!**\n\nПривязан к: **{pranks_db.get(k, {}).get('title', k)}**\nФормат: **Аудиотрек с плеером (Audio)**\nID: `{file_id[:25]}...`", parse_mode="Markdown")
        show_admin_panel(m.chat.id)
    else:
        bot.reply_to(m, "❌ Это не поддерживаемый аудиофайл. Пожалуйста, отправьте аудиозапись (MP3).")

@bot.callback_query_handler(func=lambda c: c.data == "adm_check_services")
def on_check_services(c):
    if not is_admin(c.message.chat.id): return
    bot.answer_callback_query(c.id, "⏳ Проверяем шлюзы...")
    
    z_status = "❌ Ошибка"
    try:
        r = requests.get(f"https://zvonok.com/manager/cabapi_external/api/v1/phones/call/?public_key={ZVONOK_API_KEY}&campaign_id={CAMPAIGN_ID}", verify=False, timeout=8)
        rj = r.json()
        if "phone" in str(rj).lower() or "status" in rj:
            z_status = "✅ Подключен (API активно)"
        else:
            z_status = f"⚠️ {str(rj)[:40]}"
    except Exception as e:
        z_status = f"❌ {str(e)[:30]}"

    s_status = "❌ Ошибка"
    try:
        r2 = requests.get(f"https://sms.ru/my/balance?api_id={SMSRU_API_KEY}&json=1", timeout=8)
        rj2 = r2.json()
        if rj2.get("status") == "OK":
            s_status = f"✅ Баланс: {rj2.get('balance', 0)} ₽"
        else:
            s_status = f"⚠️ {rj2.get('status_text', 'Ошибка')}"
    except Exception as e:
        s_status = f"❌ {str(e)[:30]}"

    report = (
        "🧪 **Статус сервисов телефонии:**\n\n"
        f"1. 🇷🇺 **Zvonok (+7 РФ):** {z_status}\n"
        f"2. 🌍 **SMS.RU (+374 / Весь Мир):** {s_status}\n"
        f"3. 🎵 **Формат медиа:** Полноценный MP3 с плеером (сохранено {len(audio_cloud_vault)} файлов)\n"
        f"4. 🛡️ **Антифрод ЮKassa:** Тестовые накрутки заблокированы"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    safe_nav(c, report, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_add_balance")
def on_adm_add_bal(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_uid_balance"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 **Выдача / Списание баланса:**\n\nВведите **ID пользователя** (цифры):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_uid_balance")
def step_adm_uid_bal(m):
    if not is_admin(m.chat.id): return
    uid_text = "".join(filter(str.isdigit, m.text.strip()))
    if not uid_text: return bot.reply_to(m, "❌ ID должен состоять только из цифр:")
    user_data[m.chat.id] = {"target_uid": uid_text}
    user_state[m.chat.id] = "adm_waiting_amount_balance"
    u, _ = get_user(uid_text)
    bot.reply_to(m, f"Юзер найден (Текущий баланс: **{u.get('balance_rub', 0)} ₽**).\nСколько рублей начислить (или отрицательное число для списания):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_amount_balance")
def step_adm_amount_bal(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        amount = int(m.text.strip())
        t_uid = user_data[m.chat.id]["target_uid"]
        u, _ = get_user(t_uid)
        u["balance_rub"] = max(0, u.get("balance_rub", 0) + amount)
        save_json(DB_FILE, db)
        try:
            bot.send_message(int(t_uid), f"🔔 Ваш баланс обновлён: **{u['balance_rub']} ₽**", parse_mode="Markdown")
        except Exception: pass
        bot.reply_to(m, f"✅ Баланс пользователя `{t_uid}`: **{u['balance_rub']} ₽**")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_broadcast(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_broadcast_text"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 **Рассылка сообщений:**\n\nВведите текст:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_broadcast_text")
def step_adm_broadcast(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    b_text = m.text
    sent = 0
    for uid in db.keys():
        try:
            bot.send_message(int(uid), f"📢 {b_text}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.04)
        except Exception: pass
    bot.reply_to(m, f"✅ Рассылка доставлена: {sent} пользователям.")
    show_admin_panel(m.chat.id)

print("\n>>> ПРАНК-БОТ GENCALLS (ПОЛНОЦЕННЫЙ MP3-ФОРМАТ + АУДИОПЛЕЕР) ЗАПУЩЕН! <<<")
while True:
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception:
        time.sleep(2)
        
