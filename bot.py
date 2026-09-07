import os, json, telebot, requests, time, threading, logging, uuid
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ================= КОНФИГУРАЦИЯ =================
TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
ADMIN_IDS = ["8682521929", "8915393389"]
PRIMARY_ADMIN_ID = "8682521929"

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
AUDIO_STORAGE_FILE = os.path.join(BASE_DIR, "audio_storage_vault.json")

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
    "admin_id": PRIMARY_ADMIN_ID,
    "yookassa_shop_id": "YOUR_SHOP_ID",
    "yookassa_secret_key": "live_YOUR_SECRET_KEY",
    "channel_url": "https://t.me/gencalls_channel",
    "zvonok_key": "d0808ab7450fca32147a9285018fe7a5",
    "campaign_id": "1783540036",
    "smsru_key": "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF",
    "support": "tadevosankaro12"
})
save_json(CONFIG_FILE, admin_cfg)

db = load_json(DB_FILE, {})
promocodes = load_json(PROMO_FILE, {"GEN2026": {"rub": 49, "uses": 100, "used_by": []}})
blacklist = load_json(BLACKLIST_FILE, [])

# ================= ВЕЧНОЕ ХРАНИЛИЩЕ АУДИО (НЕ СТИРАЕТСЯ С СЕРВЕРА!) =================
# Сюда зашиваются file_id навсегда прямо в код!
PERMANENT_AUDIO_VAULT = {
    # Бот всегда сначала берёт аудио отсюда:
    "babka": "",
    "tulip": "",
    "rkn": "",
    "django": "",
    "govnovoz": "",
    "courier": ""
}

# Динамическая память + постоянная
audio_vault = load_json(AUDIO_STORAGE_FILE, {})
for k, v in PERMANENT_AUDIO_VAULT.items():
    if v and (k not in audio_vault or not audio_vault[k]):
        audio_vault[k] = v

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
    return uid_str in ADMIN_IDS or uid_str == PRIMARY_ADMIN_ID

def get_user(uid, uname="Друг"):
    s_uid = str(uid).strip()
    is_new = False
    if s_uid not in db:
        price = admin_cfg.get("call_price", 49)
        db[s_uid] = {
            "name": uname,
            "balance_rub": price * 2,
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
    digits = "".join(filter(str.isdigit, text.strip()))
    if not digits: return None
    if len(digits) == 10 and digits.startswith("9"): return "7" + digits
    elif len(digits) == 11 and digits.startswith("8"): return "7" + digits[1:]
    return digits

def ensure_fallback_audio(key, filename):
    path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(path) or os.path.getsize(path) < 100:
        mp3_silence = b'\xff\xfb\x90\x00' + b'\x00' * 1024
        try:
            with open(path, "wb") as f:
                f.write(mp3_silence * 15)
        except Exception: pass
    return path

def get_audio_for_player(key):
    # 1. Приоритет: вечный Telegram cloud file_id
    if key in audio_vault and audio_vault[key]:
        return audio_vault[key], "cloud"
    if key in PERMANENT_AUDIO_VAULT and PERMANENT_AUDIO_VAULT[key]:
        return PERMANENT_AUDIO_VAULT[key], "cloud"
        
    # 2. Локальный диск
    p = pranks_db.get(key, {})
    fn = p.get("file", f"{key}.mp3")
    for fld in [AUDIO_DIR, BASE_DIR]:
        local_p = os.path.join(fld, fn)
        if os.path.exists(local_p) and os.path.getsize(local_p) > 200:
            return local_p, "file"
    return ensure_fallback_audio(key, fn), "file"

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
                return False, f"Zvonok: {err_msg}", None
            call_id = res.get("call_id") or (res.get("data", {}).get("call_id") if isinstance(res.get("data"), dict) else None)
            return True, str(call_id or f"ZV-{int(time.time())}"), "zvonok"
        return False, f"Zvonok: {r.text[:100]}", None
    except Exception as e:
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
            except Exception: pass
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
            except Exception: pass
            time.sleep(8)
            
    if record_url:
        try:
            bot.send_audio(
                chat_id, record_url, 
                title=f"Реакция ({prank_title})", performer="GenCalls Запись",
                caption=f"🎉 **Звонок завершён! Запись разговора готова!**\n\n📞 Номер: `+{phone}`\n🎭 Розыгрыш: **{prank_title}**",
                parse_mode="Markdown"
            )
        except Exception: pass

def process_call_async(chat_id, phone, prank_key, p_title, wait_msg_id):
    u, _ = get_user(chat_id)
    price = admin_cfg.get("call_price", 49)
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
            if success_fb: success, call_id, service_name = True, call_id_fb, "🌍 SMS.RU (Резерв)"
    else:
        success, call_id, service_type = call_smsru_smart(phone)
        if not success and phone.startswith("7"):
            success_zb, call_id_zb, service_type = call_zvonok_campaign(phone)
            if success_zb: success, call_id, service_name = True, call_id_zb, "🇷🇺 Zvonok (Резерв)"

    if not success:
        try: bot.edit_message_text(f"❌ **Не удалось совершить вызов!**\n\nОтвет: `{call_id}`\n💰 Баланс НЕ списан.", chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id))
        except Exception: pass
        return

    u["balance_rub"] = max(0, u["balance_rub"] - price)
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m %H:%M"), "phone": phone, "prank": p_title, "service": service_name, "call_id": str(call_id)
    })
    save_json(DB_FILE, db)

    try:
        bot.edit_message_text(
            f"✅ **Звонок запущен!**\n\n📞 Номер: `+{phone}`\n🌐 Канал: **{service_name}**\n🎭 Розыгрыш: **{p_title}**\n💰 Остаток: **{u['balance_rub']} ₽** ({u['balance_rub'] // price} 📞)\n\n🎙️ _Запись разговора придёт в чат сразу после звонка!_",
            chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id)
        )
    except Exception: pass
    threading.Thread(target=track_call_and_send_record, args=(chat_id, call_id, phone, p_title, service_type), daemon=True).start()

def kb_main_menu(uid):
    u, _ = get_user(uid)
    price = admin_cfg.get("call_price", 49)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // price
    rmode = u.get("routing_mode", "auto")
    rmode_label = "⚙️ Маршрут: 🇷🇺 РФ (+7)" if rmode == "zvonok" else ("⚙️ Маршрут: 🌍 SMS.RU" if rmode == "smsru" else "⚙️ Маршрут: ⚡ Авто-шлюз")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Открыть каталог розыгрышей", callback_data="catalog"))
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
        types.InlineKeyboardButton("📢 Наш Telegram-канал", url=admin_cfg.get("channel_url")),
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank")
    )
    return kb

def safe_nav(c, text, reply_markup=None):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    try: bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        try: bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception: pass
        bot.send_message(c.message.chat.id, text, parse_mode="Markdown", reply_markup=reply_markup)

MAIN_TEXT_BANNER = (
    "🎭 **GenCalls — Пранк-Звонки с записью реакции!**\n\n"
    "🎁 **Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!**\n\n"
    "🕵️‍♂️ **Анонимность 100%** — ваш номер скрыт.\n"
    "🎵 **MP3-Плеер** — слушайте пранки перед звонком!\n"
    "🎙️ **Запись реакции** — запись разговора прямо в этот чат!\n"
    "⚡ **Оплата онлайн:** SberPay и банковские карты через ЮKassa.\n\n"
    "👇 _Выберите пранк и разыграйте друга:_"
)

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u, is_new = get_user(m.chat.id, m.from_user.first_name or "Друг")
    welcome = MAIN_TEXT_BANNER
    if is_new:
        welcome = f"🎉 **Добро пожаловать в GenCalls!**\n\n🎁 Мы подарили вам **2 БЕСПЛАТНЫХ ЗВОНКА**!\n\n" + MAIN_TEXT_BANNER
    bot.send_message(m.chat.id, welcome, parse_mode="Markdown", reply_markup=kb_main_menu(m.chat.id))

@bot.message_handler(commands=["catalog", "pranks"])
def cmd_catalog(m):
    admin_mode = is_admin(m.chat.id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        if v.get("public", True) or admin_mode:
            kb.row(types.InlineKeyboardButton(f"🎵 {v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    bot.send_message(m.chat.id, "🎭 **Каталог голосовых розыгрышей:**", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog_cb(c):
    admin_mode = is_admin(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        if v.get("public", True) or admin_mode:
            kb.row(types.InlineKeyboardButton(f"🎵 {v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 **Каталог голосовых розыгрышей:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({price} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    desc_text = f"🎭 **{p['title']}** [{p.get('tag', 'ТОП')}]\n\n💬 **Сценарий:** {p.get('desc', '')}\n\n🎙️ _После звонка запись разговора придёт в чат!_"
    audio_source, source_type = get_audio_for_player(k)
    try:
        bot.answer_callback_query(c.id)
        if source_type == "cloud":
            bot.send_audio(c.message.chat.id, audio_source, title=p['title'], performer="GenCalls", caption=desc_text, parse_mode="Markdown", reply_markup=kb)
        else:
            with open(audio_source, "rb") as a_file:
                sent = bot.send_audio(c.message.chat.id, a_file, title=p['title'], performer="GenCalls", caption=desc_text, parse_mode="Markdown", reply_markup=kb)
                if sent.audio:
                    audio_vault[k] = sent.audio.file_id
                    save_json(AUDIO_STORAGE_FILE, audio_vault)
        return
    except Exception:
        safe_nav(c, desc_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    if u.get("balance_rub", 0) < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
        safe_nav(c, f"❌ **Недостаточно средств**\n\nЦена: **{price} ₽**\nБаланс: **{u.get('balance_rub', 0)} ₽**", reply_markup=kb)
        return
    k = c.data.replace("setup_call_", "")
    user_data[c.message.chat.id] = {"prank": k}
    user_state[c.message.chat.id] = "waiting_phone"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📱 **Введите номер телефона жертвы:**\n\n• Россия: `+79991234567`\n• Армения: `+374...`", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def step_phone_input(m):
    chat_id = m.chat.id
    phone = parse_phone(m.text)
    if not phone or len(phone) < 8 or phone in blacklist:
        bot.reply_to(m, "❌ Номер некорректен или находится в защитном списке бота.")
        return
    user_state[chat_id] = None
    prank_key = user_data.get(chat_id, {}).get("prank", "babka")
    p = pranks_db.get(prank_key, pranks_db["babka"])
    w = bot.send_message(chat_id, f"🚀 _Набираем +{phone}..._")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, p["title"], w.message_id), daemon=True).start()

# ================= АВТО-ОПЛАТА ЮКАССА: SBERPAY И БАНКОВСКИЕ КАРТЫ =================
@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['title']} — {p['rub']} ₽ ({p['badge']})", callback_data=f"choose_pay_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "💳 **Пополнение баланса:**\n\nВыберите пакет звонков:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("choose_pay_"))
def on_choose_pay(c):
    pid = c.data.replace("choose_pay_", "")
    pkg = PACKAGES.get(pid)
    if not pkg: return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.row(types.InlineKeyboardButton("🟢 Оплатить через SberPay (Сбербанк Онлайн)", callback_data=f"pay_yk_sber_{pid}"))
    kb.row(types.InlineKeyboardButton("💳 Банковская карта (МИР, Visa, Mastercard)", callback_data=f"pay_yk_card_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
    
    text = (
        f"📦 Выбран пакет: **{pkg['title']}**\n"
        f"💰 Сумма: **{pkg['rub']} ₽**\n\n"
        f"Выберите способ оплаты через официальную ЮKassa:"
    )
    safe_nav(c, text, reply_markup=kb)

def create_yookassa_payment(amount_rub, description, pay_type="sberbank"):
    shop_id = admin_cfg.get("yookassa_shop_id", "")
    secret_key = admin_cfg.get("yookassa_secret_key", "")
    
    if not shop_id or "YOUR_" in shop_id:
        return False, "Shop_ID не настроен", None
        
    url = "https://api.yookassa.ru/v3/payments"
    order_id = str(uuid.uuid4())
    headers = {"Idempotence-Key": order_id, "Content-Type": "application/json"}
    
    payload = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": admin_cfg.get("channel_url", "https://t.me/gencalls_channel")
        },
        "description": description
    }
    
    if pay_type == "sberbank":
        payload["payment_method_data"] = {"type": "sberbank"}
    elif pay_type == "bank_card":
        payload["payment_method_data"] = {"type": "bank_card"}

    try:
        r = requests.post(url, auth=(shop_id, secret_key), json=payload, headers=headers, timeout=12)
        res = r.json()
        pay_url = res.get("confirmation", {}).get("confirmation_url")
        pay_id = res.get("id")
        if pay_url and pay_id:
            return True, pay_url, pay_id
        return False, res.get("description", str(res)), None
    except Exception as e:
        return False, str(e), None

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_yk_sber_") or c.data.startswith("pay_yk_card_"))
def on_exec_pay(c):
    is_sber = c.data.startswith("pay_yk_sber_")
    pid = c.data.replace("pay_yk_sber_", "").replace("pay_yk_card_", "")
    pkg = PACKAGES.get(pid)
    if not pkg: return
    
    pay_type = "sberbank" if is_sber else "bank_card"
    method_name = "🟢 SberPay (Сбербанк Онлайн)" if is_sber else "💳 Банковская карта"
    desc = f"Пополнение GenCalls {pkg['title']}"
    
    ok, pay_url, pay_id = create_yookassa_payment(pkg["rub"], desc, pay_type)
    
    if not ok:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("👨‍💻 Написать в поддержку", url=f"https://t.me/{admin_cfg.get('support')}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="packages_menu"))
        safe_nav(c, f"⚠️ **Платёжная касса настраивается!**\n\nОшибка: `{pay_url}`\nАдминистратор может настроить ShopID и Secret_Key в меню `/admin`.", reply_markup=kb)
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    btn_text = "🟢 Оплатить в Сбербанк Онлайн" if is_sber else "💳 Перейти к оплате картой"
    kb.row(types.InlineKeyboardButton(btn_text, url=pay_url))
    kb.row(types.InlineKeyboardButton("🔄 Я оплатил (Проверить платёж)", callback_data=f"check_pay_{pay_id}_{pkg['rub']}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
    
    text = (
        f"⚡ **Счёт на оплату успешно создан!**\n\n"
        f"Способ: **{method_name}**\n"
        f"Сумма: **{pkg['rub']} ₽** ({pkg['title']})\n\n"
        f"1. Нажмите кнопку **«{btn_text}»** ниже.\n"
        f"2. Подтвердите оплату в приложении.\n"
        f"3. Вернитесь сюда и нажмите **«🔄 Я оплатил (Проверить платёж)»** — баланс зачислится мгновенно!"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_pay_"))
def on_check_payment_status(c):
    parts = c.data.split("_")
    pay_id, amount = parts[2], int(parts[3])
    shop_id = admin_cfg.get("yookassa_shop_id", "")
    secret_key = admin_cfg.get("yookassa_secret_key", "")
    
    try:
        r = requests.get(f"https://api.yookassa.ru/v3/payments/{pay_id}", auth=(shop_id, secret_key), timeout=10)
        res = r.json()
        status = res.get("status")
        
        if status == "succeeded":
            u, _ = get_user(c.message.chat.id)
            u["balance_rub"] += amount
            save_json(DB_FILE, db)
            bot.answer_callback_query(c.id, "🎉 Оплата подтверждена!", show_alert=True)
            safe_nav(c, (
                f"🎉 **ОПЛАТА УСПЕШНО ЗАЧИСЛЕНА!**\n\n"
                f"💰 Начислено: **+{amount} ₽**\n"
                f"📞 Ваш баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // admin_cfg.get('call_price', 49)} звонков)\n\n"
                f"Приятных розыгрышей! 🚀"
            ), reply_markup=kb_main_menu(c.message.chat.id))
            return
        elif status == "pending" or status == "waiting_for_capture":
            bot.answer_callback_query(c.id, "⏳ Оплата ещё обрабатывается банком. Завершите перевод и нажмите ещё раз через 10 секунд.", show_alert=True)
            return
        elif status == "canceled":
            bot.answer_callback_query(c.id, "❌ Платёж был отменён в банке.", show_alert=True)
            return
    except Exception: pass
    
    bot.answer_callback_query(c.id, "⚠️ Платёж пока не поступил. Попробуйте через пару секунд.", show_alert=True)

# ================= МЕНЮ И НАВИГАЦИЯ =================
@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"👤 **Личный кабинет**\n\n🆔 ID: `{c.message.chat.id}`\n💰 Баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // price} 📞)", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_help(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Поддержка", url=f"https://t.me/{admin_cfg.get('support')}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🛟 **Поддержка:** Нажмите кнопку ниже для связи с создателем:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    binfo = bot.get_me()
    link = f"https://t.me/{binfo.username}?start=ref_{c.message.chat.id}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={link}&text=Пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"🤝 **Партнёрка:** Приглашайте друзей и получайте +49 ₽!\n\n🔗 Ссылка:\n`{link}`", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def on_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ **Введите промокод:**", reply_markup=kb)

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
    safe_nav(c, "🛡️ Введите номер телефона для защиты от звонков:", reply_markup=kb)

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

# ================= ПОЛНОЦЕННАЯ АДМИНКА + РЕДАКТОР РОЗЫГРЫШЕЙ (/admin) =================
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
    yk_status = "✅ Настроена" if (admin_cfg.get("yookassa_shop_id") and "YOUR_" not in admin_cfg.get("yookassa_shop_id")) else "⚠️ Требует настройки"
    text = (
        "👑 **Панель Управления GenCalls (Защита от сброса)**\n\n"
        f"🎭 Розыгрышей в каталоге: **{len(pranks_db)} шт.**\n"
        f"🎵 Привязано MP3 в облаке: **{active_audios} шт.**\n"
        f"💳 ЮKassa (SberPay / Карты): **{yk_status}**\n"
        f"🆔 Shop_ID: `{admin_cfg.get('yookassa_shop_id')}`\n"
        f"🏷️ Цена звонка: **{admin_cfg.get('call_price')} ₽**\n"
        f"👥 Пользователей в базе: **{len(db)}**"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎭 РЕДАКТОР РОЗЫГРЫШЕЙ", callback_data="adm_pranks_manager"))
    kb.row(types.InlineKeyboardButton("🎵 Загрузить аудио к пранку", callback_data="adm_upload_audio_menu"))
    kb.row(types.InlineKeyboardButton("💳 Настроить ЮKassa (API-ключи)", callback_data="adm_change_yk_keys"))
    kb.row(types.InlineKeyboardButton("🏷️ Изменить цену звонка", callback_data="adm_change_price"))
    kb.row(types.InlineKeyboardButton("💳 Выдать баланс юзеру", callback_data="adm_add_balance"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка сообщений", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

# ---- РЕДАКТОР РОЗЫГРЫШЕЙ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_pranks_manager")
def on_pranks_manager(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ ДОБАВИТЬ НОВЫЙ РОЗЫГРЫШ", callback_data="adm_prank_create_new"))
    for k, v in pranks_db.items():
        kb.row(
            types.InlineKeyboardButton(f"🎵 {v['title']}", callback_data=f"adm_up_{k}"),
            types.InlineKeyboardButton("❌ Удалить", callback_data=f"adm_del_prank_{k}")
        )
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎭 **Управление каталогом розыгрышей:**\n\nВы можете добавить новый пранк или удалить ненужный:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_prank_create_new")
def on_create_prank_start(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_prank_new_title"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_pranks_manager"))
    safe_nav(c, "➕ **Шаг 1 из 3:** Введите название нового розыгрыша (например: `🍕 Пицца с сюрпризом`):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_title")
def step_prank_new_title(m):
    if not is_admin(m.chat.id): return
    user_data[m.chat.id] = {"new_title": m.text.strip(), "new_key": f"prank_{int(time.time())}"}
    user_state[m.chat.id] = "adm_prank_new_desc"
    bot.reply_to(m, "📝 **Шаг 2 из 3:** Введите краткое описание сценария розыгрыша:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_desc")
def step_prank_new_desc(m):
    if not is_admin(m.chat.id): return
    user_data[m.chat.id]["new_desc"] = m.text.strip()
    user_state[m.chat.id] = "adm_prank_new_audio"
    bot.reply_to(m, "🎵 **Шаг 3 из 3:** Отправьте сюда MP3-аудиофайл или голосовое сообщение для этого розыгрыша:")

@bot.message_handler(content_types=["audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_audio")
def step_prank_new_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    d = user_data.get(m.chat.id, {})
    k = d.get("new_key")
    fid = m.audio.file_id if m.audio else (m.voice.file_id if m.voice else m.document.file_id)
    
    if k and fid:
        pranks_db[k] = {
            "title": d.get("new_title", "Новый розыгрыш"),
            "tag": "NEW 🔥",
            "dur": 30,
            "desc": d.get("new_desc", ""),
            "file": f"{k}.mp3",
            "public": True
        }
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        audio_vault[k] = fid
        save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.reply_to(m, f"🎉 **Розыгрыш «{d.get('new_title')}» успешно создан!**\n\n📌 Вечный ID файла: `{fid}`")
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
        bot.answer_callback_query(c.id, "✅ Розыгрыш удален!")
    on_pranks_manager(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_audio_menu")
def on_upload_menu(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        status = "🎵 " if k in audio_vault else "⚪ "
        kb.row(types.InlineKeyboardButton(f"{status}{v['title']}", callback_data=f"adm_up_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎵 **Выберите розыгрыш для привязки MP3 файла:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_up_"))
def on_sel_up(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_up_", "")
    user_data[c.message.chat.id] = {"prank_up": k}
    user_state[c.message.chat.id] = "adm_audio_file"
    p = pranks_db.get(k, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_upload_audio_menu"))
    safe_nav(c, f"🎵 **Отправьте аудиофайл (.mp3 или голосовое) для:**\n\n🎭 **{p.get('title', k)}**", reply_markup=kb)

@bot.message_handler(content_types=["audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_audio_file")
def step_adm_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("prank_up")
    fid = m.audio.file_id if m.audio else (m.voice.file_id if m.voice else m.document.file_id)
    if fid and k:
        audio_vault[k] = fid
        save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.reply_to(m, (
            f"🎉 **УСПЕХ! Аудиофайл привязан к {pranks_db.get(k, {}).get('title', k)}!**\n\n"
            f"📌 **Вечный ID в Telegram:**\n`{fid}`\n\n"
            f"_Теперь этот трек сохранён в памяти бота навсегда!_"
        ))
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_yk_keys")
def on_adm_yk_keys(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_yk_keys"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 **Введите Shop_ID и Секретный ключ ЮKassa через запятую:**\n\n_Формат:_ `Shop_ID, live_Secret_Key`", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_yk_keys")
def step_adm_yk_keys(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    parts = [p.strip() for p in m.text.split(",")]
    if len(parts) >= 1: admin_cfg["yookassa_shop_id"] = parts[0]
    if len(parts) >= 2: admin_cfg["yookassa_secret_key"] = parts[1]
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, "✅ Ключи ЮKassa сохранены! SberPay и карты работают автоматически!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_price")
def on_adm_price(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_price"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "🏷️ **Введите цену 1 звонка в рублях:**", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_price")
def step_adm_price(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        p = int("".join(filter(str.isdigit, m.text)))
        admin_cfg["call_price"] = p
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Цена звонка: {p} ₽!")
    except Exception: pass
    show_admin_panel(m.chat.id)

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
    bot.reply_to(m, f"Сколько рублей начислить пользователю `{uid}`:")

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
        bot.reply_to(m, f"✅ Начислено {s} ₽!")
    except Exception: pass
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
            bot.send_message(int(u), f"📢 {t}", parse_mode="Markdown")
            cnt += 1
            time.sleep(0.04)
        except Exception: pass
    bot.reply_to(m, f"✅ Доставлено {cnt} пользователям.")
    show_admin_panel(m.chat.id)

print("\n>>> GENCALLS: ЗАЩИТА АУДИОФАЙЛОВ ОТ СБРОСА СЕРВЕРА АКТИВНА! <<<")
while True:
    try: bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception: time.sleep(2)
