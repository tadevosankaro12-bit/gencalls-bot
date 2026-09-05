import os, json, telebot, requests, time, threading, logging
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ---- КОНФИГУРАЦИЯ И КЛЮЧИ ----
TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
ZVONOK_API_KEY = "d0808ab7450fca32147a9285018fe7a5"
CAMPAIGN_ID = "1783540036"
SMSRU_API_KEY = "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF"

LAVA_PAY_URL = "https://app.lava.top/products/a86f2412-debe-42a3-83fc-ab3abdc5a967"
SUPPORT_USERNAME = "tadevosankaro12"
ADMIN_IDS = ["8915393389"]

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

admin_cfg = load_json(CONFIG_FILE, {"call_price": 49, "max_referrals": 3, "admin_id": "8915393389"})
db = load_json(DB_FILE, {})
promocodes = load_json(PROMO_FILE, {"GEN2026": {"rub": 49, "uses": 100, "used_by": []}})
blacklist = load_json(BLACKLIST_FILE, [])

DEFAULT_PRANKS = {
    "babka": {
        "title": "👵 Бабка Лидия", 
        "tag": "ХИТ", 
        "dur": "0:35", 
        "desc": "Скандальная соседка требует вернуть долг и грозит участковым.",
        "file": "babka.mp3",
        "public": True
    },
    "tulip": {
        "title": "🌷 Тюльпаны оптом", 
        "tag": "ТОП", 
        "dur": "0:40", 
        "desc": "Срочный заказ 500 тюльпанов на свадьбу прямо сейчас.",
        "file": "tulip.mp3",
        "public": True
    },
    "rkn": {
        "title": "🏛️ Роскомнадзор", 
        "tag": "ШОК", 
        "dur": "0:45", 
        "desc": "Предупреждение о блокировке интернета за подозрительную активность.",
        "file": "rkn.mp3",
        "public": True
    },
    "django": {
        "title": "🕺 Джанго стриптизер", 
        "tag": "18+", 
        "dur": "0:38", 
        "desc": "Приватный стриптизер звонит в домофон с маслом и костюмами.",
        "file": "django.mp3",
        "public": True
    },
    "govnovoz": {
        "title": "🚛 Ассенизатор", 
        "tag": "УГАР", 
        "dur": "0:30", 
        "desc": "Машина приехала откачивать яму: «Куда шланг кидать?»",
        "file": "govnovoz.mp3",
        "public": True
    },
    "courier": {
        "title": "🍕 Голодный курьер", 
        "tag": "НОВОЕ", 
        "dur": "0:32", 
        "desc": "Курьер признаётся, что сам съел пиццу, так как никто не открыл.",
        "file": "courier.mp3",
        "public": True
    }
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
for k, v in DEFAULT_PRANKS.items():
    if k not in pranks_db:
        pranks_db[k] = v
save_json(CUSTOM_PRANKS_FILE, pranks_db)

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 3)

PACKAGES = {
    "pkg_1": {"icon": "📱", "title": "1 звонок", "price": "49 ₽", "badge": "Старт"},
    "pkg_5": {"icon": "⚡", "title": "5 звонков", "price": "149 ₽", "badge": "🔥 Выгода -40%"},
    "pkg_15": {"icon": "💥", "title": "15 звонков", "price": "299 ₽", "badge": "👑 Хит"},
    "pkg_50": {"icon": "🏆", "title": "50 звонков", "price": "699 ₽", "badge": "VIP"}
}

FAQ_ITEMS = {
    "faq_anon": {"q": "🕵️ Узнает ли жертва, кто звонил?", "a": "🛑 **Узнать невозможно.**\n\nКаждый звонок совершается с нового виртуального номера через защищённый международный шлюз. Ваш номер полностью скрыт."},
    "faq_refund": {"q": "🔄 Что если сбросили или занято?", "a": "💰 **Баланс не сгорает зря!**\n\nСписание происходит только в момент успешной отправки вызова в шлюз. Если номер недоступен, баланс сохраняется."},
    "faq_intl": {"q": "🌍 В какие страны доходят звонки?", "a": "🌐 **Мы дозваниваемся в любую точку мира!**\n• 🇷🇺 Россия & Казахстан (+7) — шлюз Zvonok.\n• 🇦🇲 Армения (+374), 🇬🇪 Грузия (+995), СНГ и Мир — шлюз SMS.RU Voice.\nМаршрутизация переключается автоматически!"}
}

def is_admin(uid):
    uid_str = str(uid).strip()
    configured_admin = str(admin_cfg.get("admin_id", "")).strip()
    return uid_str in ADMIN_IDS or uid_str == configured_admin

def get_user(uid, uname="Друг"):
    s_uid = str(uid).strip()
    if s_uid not in db:
        reg_date = datetime.now().strftime("%d.%m.%Y")
        db[s_uid] = {
            "name": uname,
            "balance_rub": 98,
            "calls_history": [],
            "referrals": 0,
            "referred_by": None,
            "reg_date": reg_date,
            "routing_mode": "auto"
        }
        save_json(DB_FILE, db)
    return db[s_uid]

def parse_phone(text):
    if not text: return None
    digits = "".join(filter(str.isdigit, text.strip()))
    if not digits: return None
    if len(digits) == 10 and digits.startswith("9"):
        return "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        return "7" + digits[1:]
    return digits

def kb_main_menu(uid):
    u = get_user(uid)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // CALL_PRICE_RUB
    rmode = u.get("routing_mode", "auto")
    
    if rmode == "zvonok":
        rmode_label = "⚙️ Маршрут: 🇷🇺 РФ (+7)"
    elif rmode == "smsru":
        rmode_label = "⚙️ Маршрут: 🌍 SMS.RU (+374/Мир)"
    else:
        rmode_label = "⚙️ Маршрут: ⚡ Авто-шлюз"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Отправить звонок-розыгрыш", callback_data="catalog"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💰 Пополнить", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton(rmode_label, callback_data="nav_routing"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🤝 Партнёрам", callback_data="nav_affiliate"),
        types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo")
    )
    kb.row(types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank"))
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
    "🎭 **GenCalls — Международные Пранк-Звонки**\n\n"
    "🕵️‍♂️ **Анонимность 100%** — ваш номер никогда не отобразится.\n"
    "🌍 **Два независимых канала связи:**\n"
    "• 🇷🇺 **Россия / Казахстан (+7)** — шлюз Zvonok\n"
    "• 🇦🇲 **Армения (+374) & Весь Мир** — шлюз SMS.RU Voice\n\n"
    "💰 Стоимость звонка — **от 49 ₽**.\n"
    "⚡ Бот автоматически выбирает лучший шлюз для дозвона!"
)

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u = get_user(m.chat.id, m.from_user.first_name or "Друг")
    if not admin_cfg.get("admin_id"):
        admin_cfg["admin_id"] = str(m.chat.id)
        save_json(CONFIG_FILE, admin_cfg)
    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="Markdown", reply_markup=kb_main_menu(m.chat.id))

# ---- ГИБКАЯ МАРШРУТИЗАЦИЯ (ИСПРАВЛЕНО И НАСТРОЕНО) ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_routing")
def cb_routing(c):
    u = get_user(c.message.chat.id)
    cur = u.get("routing_mode", "auto")
    
    text = (
        "⚙️ **Гибкая Маршрутизация Телефонии**\n\n"
        "Выберите, через какой шлюз отправлять вызовы:\n\n"
        f"1. ⚡ **Умный Авто-выбор** {'✅ [ВКЛЮЧЕНО]' if cur == 'auto' else ''}\n"
        "   _Номера +7 идут через Zvonok, остальные страны — через SMS.RU._\n\n"
        f"2. 🇷🇺 **Только Zvonok (+7 РФ/КЗ)** {'✅ [ВКЛЮЧЕНО]' if cur == 'zvonok' else ''}\n"
        "   _Прямой российский SIP-шлюз с высоким процентом дозвона._\n\n"
        f"3. 🌍 **Только SMS.RU Voice (+374 / СНГ / Мир)** {'✅ [ВКЛЮЧЕНО]' if cur == 'smsru' else ''}\n"
        "   _Международный маршрут (Армения, Грузия, СНГ, Европа)._"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"{'👉 ' if cur=='auto' else ''}⚡ Умный Авто-выбор", callback_data="set_route_auto"))
    kb.row(types.InlineKeyboardButton(f"{'👉 ' if cur=='zvonok' else ''}🇷🇺 Только Zvonok (+7)", callback_data="set_route_zvonok"))
    kb.row(types.InlineKeyboardButton(f"{'👉 ' if cur=='smsru' else ''}🌍 Только SMS.RU (+374 / Весь Мир)", callback_data="set_route_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_route_"))
def on_set_route(c):
    mode = c.data.replace("set_route_", "")
    u = get_user(c.message.chat.id)
    u["routing_mode"] = mode
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Настройки маршрутизации обновлены!")
    cb_routing(c)

# ---- КАТАЛОГ РОЗЫГРЫШЕЙ И ПЛЕЕР ----
@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog(c):
    admin_mode = is_admin(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        is_pub = v.get("public", True)
        if is_pub or admin_mode:
            prefix_tag = "" if is_pub else "🔒 [Скрытый] "
            kb.row(types.InlineKeyboardButton(f"{prefix_tag}{v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
        
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 **Каталог розыгрышей:**\n\nВыберите нужный пранк для звонка:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({CALL_PRICE_RUB} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    audio_path = os.path.join(AUDIO_DIR, p.get("file", f"{k}.mp3"))
    desc_text = (
        f"🎭 **{p['title']}** [{p.get('tag', 'ТОП')}]\n\n"
        f"⏱ **Длительность:** `{p.get('dur', '0:35')}`\n"
        f"💬 **Сценарий:** {p.get('desc', '')}\n\n"
        f"👇 _Нажмите кнопку ниже, чтобы ввести номер телефона:_"
    )
    
    if os.path.exists(audio_path):
        try:
            bot.answer_callback_query(c.id)
            with open(audio_path, "rb") as a_file:
                bot.send_voice(c.message.chat.id, a_file, caption=desc_text, parse_mode="Markdown", reply_markup=kb)
            return
        except Exception: pass
        
    safe_nav(c, desc_text, reply_markup=kb)

# ---- ЗВОНКИ И ОБРАБОТКА ВЫЗОВОВ ----
@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    u = get_user(c.message.chat.id)
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

def call_zvonok(phone):
    url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    params = {"campaign_id": CAMPAIGN_ID, "phone": f"+{phone}", "public_key": ZVONOK_API_KEY, "check_duplicate": "0"}
    try:
        r = requests.get(url, params=params, verify=False, timeout=12)
        res = r.json()
        if isinstance(res, dict):
            if res.get("status") == "error" or "error" in res:
                err_msg = res.get("data") or res.get("message") or res.get("error") or str(res)
                return False, f"Zvonok: {err_msg}"
            call_id = res.get("call_id") or (res.get("data", {}).get("call_id") if isinstance(res.get("data"), dict) else None)
            return True, str(call_id or f"ZV-{int(time.time())}")
        return False, f"Zvonok: {r.text[:100]}"
    except Exception as e:
        return False, f"Zvonok ошибка: {str(e)}"

def call_smsru(phone):
    url = "https://sms.ru/code/call"
    params = {"phone": phone, "api_id": SMSRU_API_KEY, "json": 1}
    try:
        r = requests.get(url, params=params, timeout=12)
        res = r.json()
        if res.get("status") == "OK":
            call_id = res.get("call_id") or res.get("code") or f"SMS-{int(time.time())}"
            return True, str(call_id)
        else:
            url2 = "https://sms.ru/callcheck/add"
            r2 = requests.get(url2, params=params, timeout=12)
            res2 = r2.json()
            if res2.get("status") == "OK":
                return True, str(res2.get("check_id") or f"SMS-{int(time.time())}")
            return False, f"SMS.RU: {res.get('status_text') or res.get('error_text')}"
    except Exception as e:
        return False, f"SMS.RU ошибка: {str(e)}"

def process_call_async(chat_id, phone, prank_key, p_title, wait_msg_id):
    u = get_user(chat_id)
    rmode = u.get("routing_mode", "auto")
    
    use_service = "zvonok"
    if rmode == "smsru": use_service = "smsru"
    elif rmode == "zvonok": use_service = "zvonok"
    else:
        use_service = "zvonok" if phone.startswith("7") else "smsru"

    success = False
    call_id = None
    service_name = "🇷🇺 Zvonok (+7)" if use_service == "zvonok" else "🌍 SMS.RU Voice"

    if use_service == "zvonok":
        success, call_id = call_zvonok(phone)
        if not success:
            success_fb, call_id_fb = call_smsru(phone)
            if success_fb:
                success, call_id, service_name = True, call_id_fb, "🌍 SMS.RU (Резерв)"
    else:
        success, call_id = call_smsru(phone)
        if not success and phone.startswith("7"):
            success_zb, call_id_zb = call_zvonok(phone)
            if success_zb:
                success, call_id, service_name = True, call_id_zb, "🇷🇺 Zvonok (Резерв)"

    if not success:
        bot.edit_message_text(
            f"❌ **Не удалось совершить вызов!**\n\nПричина: `{call_id}`\n\n💰 Баланс НЕ списан.",
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
        f"✅ **Звонок успешно отправлен!**\n\n"
        f"📞 Номер: `+{phone}`\n"
        f"🌐 Канал связи: **{service_name}**\n"
        f"🎭 Розыгрыш: **{p_title}**\n"
        f"🆔 ID звонка: `{call_id}`\n"
        f"💰 Баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞)\n\n"
        f"_Идёт дозвон абоненту..._",
        chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id)
    )

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

# ---- АККАУНТ И ОПЛАТА ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u = get_user(c.message.chat.id)
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
            text += f"• `+{h['phone']}` — {h['prank']} ({h.get('service', 'Шлюз')})\n"
    else:
        text += "_История звонков пуста._"

    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    text = "💰 **Пополнение баланса:**\n\nВыберите подходящий пакет звонков:"
    kb = types.InlineKeyboardMarkup()
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['icon']} {p['title']} — {p['price']} ({p['badge']})", callback_data=f"buy_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_pkg_"))
def on_buy_package(c):
    pid = c.data.replace("buy_", "")
    pkg = PACKAGES.get(pid, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"💳 Оплатить {pkg.get('price')}", url=LAVA_PAY_URL))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="packages_menu"))
    safe_nav(c, f"📦 **{pkg.get('title')} ({pkg.get('price')})**\n\nНажмите для безопасной оплаты картой или СБП:", reply_markup=kb)

# ---- ПОДДЕРЖКА, ПРОМОКОДЫ, ПАРТНЁРКА, АНТИ-ПРАНК ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_support(c):
    kb = types.InlineKeyboardMarkup()
    for f_key, f_val in FAQ_ITEMS.items():
        kb.row(types.InlineKeyboardButton(f_val["q"], callback_data=f_key))
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать создателю", url=f"https://t.me/{SUPPORT_USERNAME}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🛟 **Служба поддержки & FAQ:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in FAQ_ITEMS)
def on_faq_answer(c):
    f_info = FAQ_ITEMS[c.data]
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад к FAQ", callback_data="nav_help"))
    safe_nav(c, f"{f_info['a']}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u = get_user(c.message.chat.id)
    text = (
        f"🤝 **Партнёрская программа**\n\n"
        f"Получайте **+49 ₽ (1 бесплатный звонок)** за каждого приглашённого друга!\n\n"
        f"👥 Приглашено: **{u.get('referrals', 0)}/{MAX_REFERRALS}**\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`"
    )
    kb = types.InlineKeyboardMarkup()
    if u.get("referrals", 0) < MAX_REFERRALS:
        kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Анонимные+пранк-звонки+🔥"))
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
    u = get_user(m.chat.id)
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
    safe_nav(c, "🛡️ **Анти-Пранк защита**\n\nВведите номер, который хотите навсегда защитить от любых звонков бота:", reply_markup=kb)

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

# ================= СКРЫТАЯ АДМИН-ПАНЕЛЬ (/admin) =================
@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not is_admin(m.chat.id):
        bot.reply_to(m, "⛔ У вас нет доступа к этой команде.")
        return
    user_state[m.chat.id] = None
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, c)

def show_admin_panel(chat_id, c=None):
    total_calls = sum(len(u.get("calls_history", [])) for u in db.values())
    total_rub = sum(u.get("balance_rub", 0) for u in db.values())
    
    text = (
        "👑 **Панель Администратора Пранк-Бота**\n\n"
        f"👥 Всего пользователей: **{len(db)}**\n"
        f"📞 Всего звонков совершено: **{total_calls}**\n"
        f"💰 Общий баланс пользователей: **{total_rub} ₽**\n"
        f"🏷️ Текущая цена 1 звонка: **{CALL_PRICE_RUB} ₽**\n"
        f"🎙️ Всего пранков в базе: **{len(pranks_db)}**"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🧪 Проверить статус шлюзов", callback_data="adm_check_services"))
    kb.row(
        types.InlineKeyboardButton("💳 Выдать баланс юзеру", callback_data="adm_add_balance"),
        types.InlineKeyboardButton("➖ Списать баланс", callback_data="adm_deduct_balance")
    )
    kb.row(
        types.InlineKeyboardButton("💰 Изменить цену звонка", callback_data="adm_change_price"),
        types.InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast")
    )
    kb.row(types.InlineKeyboardButton("🔙 Выйти из админки", callback_data="back_main"))
    
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

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
        f"2. 🌍 **SMS.RU (+374 Армения / Мир):** {s_status}"
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
    safe_nav(c, "💳 **Выдача баланса:**\n\nВведите **ID пользователя** (цифры):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_uid_balance")
def step_adm_uid_bal(m):
    if not is_admin(m.chat.id): return
    uid_text = "".join(filter(str.isdigit, m.text.strip()))
    if not uid_text:
        bot.reply_to(m, "❌ ID должен состоять только из цифр:")
        return
    user_data[m.chat.id] = {"target_uid": uid_text}
    user_state[m.chat.id] = "adm_waiting_amount_balance"
    u = get_user(uid_text)
    bot.reply_to(m, f"Юзер найден (Текущий баланс: **{u.get('balance_rub', 0)} ₽**).\nСколько рублей начислить? (например: `49`, `100`):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_amount_balance")
def step_adm_amount_bal(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        amount = int(m.text.strip())
        t_uid = user_data[m.chat.id]["target_uid"]
        u = get_user(t_uid)
        u["balance_rub"] = max(0, u.get("balance_rub", 0) + amount)
        save_json(DB_FILE, db)
        try:
            bot.send_message(int(t_uid), f"🎁 **Администратор пополнил ваш баланс на +{amount} ₽!**\nТеперь доступно: **{u['balance_rub']} ₽**", parse_mode="Markdown")
        except Exception: pass
        bot.reply_to(m, f"✅ Пользователю `{t_uid}` успешно начислено **{amount} ₽**!\nНовый баланс: **{u['balance_rub']} ₽**")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите целое число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_broadcast(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_broadcast_text"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 **Рассылка сообщений:**\n\nВведите текст рассылки:", reply_markup=kb)

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
    bot.reply_to(m, f"✅ Рассылка завершена! Доставлено: {sent} пользователям.")
    show_admin_panel(m.chat.id)

print("\n>>> ПРАНК-БОТ GENCALLS УСПЕШНО ЗАПУЩЕН! <<<")
while True:
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception:
        time.sleep(2)
        
