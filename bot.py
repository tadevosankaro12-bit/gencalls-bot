import os, json, telebot, requests, time, threading, logging
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ---- ТОКЕН И КЛЮЧИ ----
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
    "babka": {"title": "👵 Бабка Лидия", "tag": "ХИТ", "dur": "0:35", "desc": "Соседка требует вернуть долг.", "file": "babka.mp3", "public": True},
    "tulip": {"title": "🌷 Тюльпаны оптом", "tag": "ТОП", "dur": "0:40", "desc": "Срочный заказ 500 тюльпанов.", "file": "tulip.mp3", "public": True},
    "rkn": {"title": "🏛️ Роскомнадзор", "tag": "ШОК", "dur": "0:45", "desc": "Блокировка за подозрительный трафик.", "file": "rkn.mp3", "public": True},
    "django": {"title": "🕺 Джанго стриптизер", "tag": "18+", "dur": "0:38", "desc": "Приватный заказ с маслами.", "file": "django.mp3", "public": True}
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
CALL_PRICE_RUB = admin_cfg.get("call_price", 49)

PACKAGES = {
    "pkg_1": {"title": "1 звонок", "price": "49 ₽", "badge": "Старт"},
    "pkg_5": {"title": "5 звонков", "price": "149 ₽", "badge": "🔥 Выгода"},
    "pkg_15": {"title": "15 звонков", "price": "299 ₽", "badge": "👑 Хит"}
}

def is_admin(uid):
    uid_str = str(uid).strip()
    return uid_str in ADMIN_IDS or uid_str == str(admin_cfg.get("admin_id", "")).strip()

def get_user(uid, uname="Друг"):
    s_uid = str(uid).strip()
    if s_uid not in db:
        db[s_uid] = {
            "name": uname,
            "balance_rub": 98,
            "calls_history": [],
            "routing_mode": "auto"
        }
        save_json(DB_FILE, db)
    return db[s_uid]

def parse_phone(text):
    if not text: return None
    digits = "".join(filter(str.isdigit, text.strip()))
    if len(digits) == 10 and digits.startswith("9"): return "7" + digits
    if len(digits) == 11 and digits.startswith("8"): return "7" + digits[1:]
    return digits

def kb_main_menu(uid):
    u = get_user(uid)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // CALL_PRICE_RUB
    rmode = u.get("routing_mode", "auto")
    rmode_icon = "⚡ Авто" if rmode == "auto" else ("🇷🇺 РФ" if rmode == "zvonok" else "🌍 SMS.RU")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Отправить звонок-розыгрыш", callback_data="catalog"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💰 Пополнить", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton(f"⚙️ Маршрут: {rmode_icon}", callback_data="nav_routing"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo"))
    return kb

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    get_user(m.chat.id, m.from_user.first_name or "Друг")
    if not admin_cfg.get("admin_id"):
        admin_cfg["admin_id"] = str(m.chat.id)
        save_json(CONFIG_FILE, admin_cfg)
    
    text = (
        "🎭 **GenCalls — Международные Пранк-Звонки**\n\n"
        "🕵️‍♂️ **Анонимность 100%** — ваш номер защищён.\n"
        "🌍 **Два независимых шлюза:**\n"
        "• 🇷🇺 **Россия / Казахстан (+7)** — шлюз Zvonok\n"
        "• 🇦🇲 **Армения (+374) & Весь Мир** — шлюз SMS.RU Voice\n\n"
        "Выберите действие ниже:"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog(c):
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        kb.row(types.InlineKeyboardButton(f"{v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    bot.edit_message_text("🎭 **Каталог розыгрышей:**", c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить ({CALL_PRICE_RUB} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"))
    text = f"🎭 **{p.get('title')}**\n\n💬 {p.get('desc')}\n\nНажмите кнопку для ввода номера:"
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    u = get_user(c.message.chat.id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        bot.answer_callback_query(c.id, f"Недостаточно средств! Нужно {CALL_PRICE_RUB} ₽", show_alert=True)
        return
    k = c.data.replace("setup_call_", "")
    user_data[c.message.chat.id] = {"prank": k}
    user_state[c.message.chat.id] = "waiting_phone"
    bot.edit_message_text("📱 **Введите номер телефона жертвы (+79991234567 или +374...):**", c.message.chat.id, c.message.message_id, parse_mode="Markdown")

def call_zvonok(phone):
    url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    params = {"campaign_id": CAMPAIGN_ID, "phone": f"+{phone}", "public_key": ZVONOK_API_KEY, "check_duplicate": "0"}
    try:
        r = requests.get(url, params=params, verify=False, timeout=12)
        res = r.json()
        if isinstance(res, dict) and (res.get("status") == "error" or "error" in res):
            return False, str(res)
        return True, str(res.get("call_id") or f"ZV-{int(time.time())}")
    except Exception as e:
        return False, str(e)

def call_smsru(phone):
    url = "https://sms.ru/code/call"
    params = {"phone": phone, "api_id": SMSRU_API_KEY, "json": 1}
    try:
        r = requests.get(url, params=params, timeout=12)
        res = r.json()
        if res.get("status") == "OK":
            return True, str(res.get("call_id") or f"SMS-{int(time.time())}")
        return False, res.get("status_text", "Ошибка SMS.RU")
    except Exception as e:
        return False, str(e)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def step_phone(m):
    phone = parse_phone(m.text)
    if not phone or len(phone) < 8:
        return bot.reply_to(m, "❌ Некорректный номер. Введите в международном формате:")
    user_state[m.chat.id] = None
    w = bot.reply_to(m, f"🚀 _Набираем номер +{phone}..._")
    
    def run_call():
        u = get_user(m.chat.id)
        is_rf = phone.startswith("7")
        success, call_id = (call_zvonok(phone) if is_rf else call_smsru(phone))
        if not success:
            # Резервный шлюз
            success, call_id = (call_smsru(phone) if is_rf else call_zvonok(phone))
            
        if success:
            u["balance_rub"] = max(0, u["balance_rub"] - CALL_PRICE_RUB)
            save_json(DB_FILE, db)
            bot.edit_message_text(f"✅ **Звонок запущен!**\n\nНомер: `+{phone}`\nID вызова: `{call_id}`\nОстаток: **{u['balance_rub']} ₽**", m.chat.id, w.message_id, parse_mode="Markdown")
        else:
            bot.edit_message_text(f"❌ Не удалось дозвониться: {call_id}\nБаланс НЕ списан.", m.chat.id, w.message_id)
            
    threading.Thread(target=run_call, daemon=True).start()

# ---- КАБИНЕТ, ОПЛАТА, МЕНЮ ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_acc(c):
    u = get_user(c.message.chat.id)
    bot.edit_message_text(f"👤 **Личный кабинет**\n\n🆔 ID: `{c.message.chat.id}`\n💰 Баланс: **{u.get('balance_rub', 0)} ₽** ({u.get('balance_rub', 0)//CALL_PRICE_RUB} 📞)", c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("💳 Пополнить", callback_data="packages_menu")).row(types.InlineKeyboardButton("🔙 Меню", callback_data="back_main")))

@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_pkgs(c):
    kb = types.InlineKeyboardMarkup()
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['title']} — {p['price']} ({p['badge']})", url=LAVA_PAY_URL))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    bot.edit_message_text("💰 **Пополнение баланса картой / СБП:**", c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_help(c):
    bot.edit_message_text("🛟 **Поддержка:**\nЕсли есть вопросы — напишите администратору:", c.message.chat.id, c.message.message_id, reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("👨‍💻 Написать", url=f"https://t.me/{SUPPORT_USERNAME}")).row(types.InlineKeyboardButton("🔙 Меню", callback_data="back_main")))

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def cb_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    bot.edit_message_text("🎟️ **Введите промокод:**", c.message.chat.id, c.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promo")
def step_pr(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    u = get_user(m.chat.id)
    if code in promocodes and str(m.chat.id) not in promocodes[code].get("used_by", []):
        promocodes[code].setdefault("used_by", []).append(str(m.chat.id))
        bonus = promocodes[code].get("rub", 49)
        u["balance_rub"] += bonus
        save_json(DB_FILE, db)
        save_json(PROMO_FILE, promocodes)
        bot.reply_to(m, f"🎉 Промокод активирован! +{bonus} ₽ начислено!")
    else:
        bot.reply_to(m, "❌ Промокод недействителен.")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back(c):
    user_state[c.message.chat.id] = None
    cmd_start(c.message)

# ---- СКРЫТАЯ АДМИНКА (/admin) ----
@bot.message_handler(commands=["admin"])
def cmd_adm(m):
    if not is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Доступ запрещён.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Начислить баланс", callback_data="adm_give_bal"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    bot.send_message(m.chat.id, f"👑 **Админ-панель**\n\nПользователей: {len(db)}\nБаланс юзеров: {sum(u.get('balance_rub', 0) for u in db.values())} ₽", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_give_bal")
def on_give_bal(c):
    user_state[c.message.chat.id] = "adm_get_id"
    bot.send_message(c.message.chat.id, "Введите ID пользователя для пополнения:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_get_id")
def step_adm_id(m):
    uid = "".join(filter(str.isdigit, m.text.strip()))
    if not uid: return bot.reply_to(m, "Нужен числовой ID.")
    user_data[m.chat.id] = {"target_id": uid}
    user_state[m.chat.id] = "adm_get_sum"
    bot.reply_to(m, f"Юзер: `{uid}`. Введите сумму (в рублях):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_get_sum")
def step_adm_sum(m):
    user_state[m.chat.id] = None
    try:
        val = int(m.text.strip())
        t_id = user_data[m.chat.id]["target_id"]
        u = get_user(t_id)
        u["balance_rub"] += val
        save_json(DB_FILE, db)
        try: bot.send_message(int(t_id), f"🎁 Администратор начислил вам +{val} ₽!")
        except Exception: pass
        bot.reply_to(m, f"✅ Пользователю `{t_id}` начислено +{val} ₽!")
    except Exception: bot.reply_to(m, "Ошибка числа.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_broad(c):
    user_state[c.message.chat.id] = "adm_text"
    bot.send_message(c.message.chat.id, "Введите текст сообщения для всех:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_text")
def step_broad(m):
    user_state[m.chat.id] = None
    for uid in db.keys():
        try:
            bot.send_message(int(uid), f"📢 {m.text}")
            time.sleep(0.04)
        except Exception: pass
    bot.reply_to(m, "✅ Рассылка отправлена!")

print(">>> ПРАНК БОТ ЗАПУЩЕН <<<")
while True:
    try: bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception: time.sleep(2)
        
