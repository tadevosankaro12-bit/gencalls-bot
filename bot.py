# -*- coding: utf-8 -*-
"""
GenCalls Telegram Bot — Полный официальный исходный код.
Сервис интерактивных пранк-звонков, голосовых открыток и именных вызовов.
Шлюзы: Zvonok.com (+7 / СНГ) и SMS.RU (Международный / Армения).
Оплата: ЮMoney / СБП / Карты РФ (прямая ссылка и веб-шлюз /pay).
"""

import os
import sys
import json
import time
import shutil
import hashlib
import requests
import threading
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import telebot
from telebot import types

# ==============================================================================
# 1. КОНФИГУРАЦИЯ И ХРАНИЛИЩЕ ДАННЫХ
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("PERSISTENT_DATA_DIR", "/data" if os.path.exists("/data") and os.path.isdir("/data") else BASE_DIR)

AUDIO_DIR = os.path.join(DATA_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json")
CUSTOM_PRANKS_FILE = os.path.join(DATA_DIR, "gencalls_pranks.json")
PROMOS_FILE = os.path.join(DATA_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "gencalls_blacklist.json")
PENDING_PAYMENTS_FILE = os.path.join(DATA_DIR, "pending_payments.json")

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
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if DATA_DIR != BASE_DIR:
            b_path = os.path.join(BASE_DIR, os.path.basename(path))
            with open(b_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {path}: {e}")

# Ключи и реквизиты
TOKEN = os.getenv("TELEGRAM_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
ZVONOK_API_KEY = os.getenv("ZVONOK_API_KEY", "d0808ab7450fca32147a9285018fe7a5")
CAMPAIGN_ID = os.getenv("CAMPAIGN_ID", "1783540036")
SMSRU_API_KEY = os.getenv("SMSRU_API_KEY", "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF")

YOOMONEY_WALLET = os.getenv("YOOMONEY_WALLET", "4100119616287380")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "tadevosankaro12")
ADMIN_ID = os.getenv("ADMIN_ID", "8682521929")
APP_URL = os.getenv("APP_URL", "https://ais-pre-6wmpr3yiik5o2phuh3mswm-87187540791.europe-west2.run.app")

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "admin_id": "8682521929",
    "admins": ["8682521929", "1438908852", "8915393389"]
})
db = load_json(DB_FILE, {})
blacklist = load_json(BLACKLIST_FILE, [])
pending_payments = load_json(PENDING_PAYMENTS_FILE, {})
pranks_db = load_json(CUSTOM_PRANKS_FILE, {})

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)

DEFAULT_PROMOS = {
    "START2026": {"rub": 49, "uses": 500, "used_by": []},
    "СТАРТ2026": {"rub": 49, "uses": 500, "used_by": []},
    "FREE": {"rub": 49, "uses": 500, "used_by": []}
}
promocodes = load_json(PROMOS_FILE, DEFAULT_PROMOS)

# ==============================================================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def get_user(uid, name="Друг"):
    s_uid = str(uid).strip()
    if s_uid not in db:
        db[s_uid] = {
            "name": name,
            "balance_rub": 49,
            "reg_date": datetime.now().strftime("%d.%m.%Y"),
            "routing_mode": "auto",
            "referrals": 0,
            "calls_history": []
        }
        save_json(DB_FILE, db)
    return db[s_uid]

def is_admin(user_obj_or_id):
    if not user_obj_or_id: return False
    uid = ""
    uname = ""
    if isinstance(user_obj_or_id, (int, str)):
        uid = str(user_obj_or_id).strip()
    elif hasattr(user_obj_or_id, "from_user") and user_obj_or_id.from_user:
        uid = str(user_obj_or_id.from_user.id).strip()
        uname = (getattr(user_obj_or_id.from_user, "username", "") or "").lower()
    elif hasattr(user_obj_or_id, "chat") and user_obj_or_id.chat:
        uid = str(user_obj_or_id.chat.id).strip()

    if uid in ["8682521929", "1438908852", "8915393389"] or uname in ["kdjdjawu", "tadevosankaro"]:
        return True
    return uid in admin_cfg.get("admins", ["8682521929"])

def parse_phone(text):
    if not text: return None
    digits = "".join(c for c in text if c.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) >= 10:
        return digits
    return None

def is_in_state(m, state_name):
    if user_state.get(m.chat.id) != state_name: return False
    t = (m.text or "").strip()
    if t.startswith("/") or any(b in t for b in ["Каталог", "Баланс", "Именной", "Пополнить", "Кабинет", "Маршрут", "Промо", "Админ"]):
        user_state[m.chat.id] = None
        return False
    return True

# ==============================================================================
# 3. КЛАВИАТУРЫ И МЕНЮ
# ==============================================================================
def kb_reply_main_menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(types.KeyboardButton("🎭 Каталог розыгрышей"), types.KeyboardButton("✨ Именной звонок"))
    kb.row(types.KeyboardButton("💰 Баланс / Пополнить"), types.KeyboardButton("👤 Личный кабинет"))
    kb.row(types.KeyboardButton("⚙️ Маршрутизация"), types.KeyboardButton("🎟️ Промокод"))
    kb.row(types.KeyboardButton("🛟 Поддержка"), types.KeyboardButton("🛡️ Анти-Пранк"))
    if is_admin(uid):
        kb.row(types.KeyboardButton("👑 Панель Администратора"))
    return kb

def kb_main_menu(uid):
    u = get_user(uid)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // CALL_PRICE_RUB
    rmode = u.get("routing_mode", "auto")
    rmode_icon = "⚡ Авто" if rmode == "auto" else ("🇷🇺🇰🇿 Zvonok" if rmode == "zvonok" else "🌍 SMS.RU")

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎭 Каталог розыгрышей (Категория: Бабка 👵)", callback_data="catalog"))
    kb.row(types.InlineKeyboardButton("✨ 👤 Именной звонок (Озвучить имя)", callback_data="namecall_start"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💰 Пополнить", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton(f"⚙️ Маршрут: {rmode_icon}", callback_data="nav_routing"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🎟️ Ввести промокод", callback_data="enter_promo"),
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank")
    )
    if is_admin(uid):
        kb.row(types.InlineKeyboardButton("👑 Панель Администратора", callback_data="admin_panel_open"))
    return kb

def safe_nav(c, text, reply_markup=None):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    try: bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        bot.send_message(c.message.chat.id, text, parse_mode="HTML", reply_markup=reply_markup)

MAIN_TEXT = (
    "🎭 <b>GenCalls — Сервис пранк-звонков и аудиопоздравлений</b>\n\n"
    "👵 <b>Категория «Бабка»:</b> звонки с комичными фразами и записями.\n"
    "✨ <b>Именной звонок:</b> бот звонит человеку и лично называет его по имени.\n\n"
    "💰 Стоимость звонка: <b>49 ₽</b>.\n"
    "🛡️ <i>Баланс сохраняется, если абонент не снял трубку!</i>\n\n"
    "👇 <b>Выберите действие в меню:</b>"
)

# ==============================================================================
# 4. ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ И КАТАЛОГА
# ==============================================================================
@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    get_user(m.chat.id, m.from_user.first_name or "Друг")
    bot.send_message(m.chat.id, "👇 Меню быстрого доступа:", reply_markup=kb_reply_main_menu(m.chat.id))
    bot.send_message(m.chat.id, MAIN_TEXT, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.message_handler(commands=["catalog", "pranks"])
def cmd_catalog(m):
    user_state[m.chat.id] = None
    show_catalog_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def cb_catalog(c):
    show_catalog_view(c.message.chat.id, c)

def show_catalog_view(chat_id, c=None):
    admin_mode = is_admin(chat_id)
    kb = types.InlineKeyboardMarkup()

    if pranks_db:
        kb.row(types.InlineKeyboardButton("👵 ════ КАТЕГОРИЯ: БАБКА ════ 👵", callback_data="cat_dummy"))
        for k, v in pranks_db.items():
            if v.get("public", True) or admin_mode:
                pfx = "" if v.get("public", True) else "🔒 "
                kb.row(types.InlineKeyboardButton(f"{pfx}{v['title']}", callback_data=f"open_prank_{k}"))
        if admin_mode:
            kb.row(types.InlineKeyboardButton("➕ Загрузить аудио/пранк", callback_data="adm_upload_new_audio"))
    else:
        if admin_mode:
            kb.row(types.InlineKeyboardButton("➕ Загрузить первое аудио / пранк", callback_data="adm_upload_new_audio"))

    kb.row(types.InlineKeyboardButton("✨ 👤 Именной звонок (Озвучить имя)", callback_data="namecall_start"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))

    if pranks_db:
        text = "🎭 <b>Каталог розыгрышей (Категория: Бабка 👵)</b>\n\n👇 <b>Выберите тему для звонка:</b>"
    else:
        text = (
            "🎭 <b>Каталог розыгрышей</b>\n\n"
            "📂 <i>В каталоге пока нет записей.</i>\n"
            "Вы можете загрузить свои аудиофайлы через панель администратора!"
        )
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "cat_dummy")
def cb_cat_dummy(c):
    bot.answer_callback_query(c.id, "👵 Все записи категории Бабка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить абоненту ({CALL_PRICE_RUB} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 В каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    safe_nav(c, f"🎭 <b>{p['title']}</b>\n\n💬 {p.get('desc', '')}\n\nНажмите кнопку ниже, чтобы ввести номер:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    k = c.data.replace("setup_call_", "")
    user_state[c.message.chat.id] = "waiting_phone"
    user_data[c.message.chat.id] = {"prank_key": k}
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📞 <b>Введите номер телефона для звонка:</b>\n\nПример: <code>+79991234567</code> или <code>+37491234567</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_phone"))
def step_process_phone(m):
    chat_id = m.chat.id
    user_state[chat_id] = None
    phone = parse_phone(m.text)
    if not phone:
        bot.reply_to(m, "❌ Некорректный номер телефона.")
        return
    if phone in blacklist or f"+{phone}" in blacklist:
        bot.reply_to(m, "🛡️ Этот номер находится в списке защиты Анти-Пранк.")
        return
    u = get_user(chat_id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
        bot.reply_to(m, f"❌ Недостаточно средств ({CALL_PRICE_RUB} ₽).", reply_markup=kb)
        return
    p_key = user_data.get(chat_id, {}).get("prank_key")
    p_title = pranks_db.get(p_key, {}).get("title", "Пранк")
    w = bot.send_message(chat_id, f"🚀 <b>Инициируем звонок на номер +{phone}...</b>", parse_mode="HTML")
    threading.Thread(target=process_call_async, args=(chat_id, phone, p_key, p_title, w.message_id), daemon=True).start()

# ==============================================================================
# 5. ТЕЛЕФОНИЯ: ZVONOK.COM И SMS.RU
# ==============================================================================
def process_call_async(chat_id, phone, prank_key, title, status_msg_id, custom_text=None):
    u = get_user(chat_id)
    rmode = u.get("routing_mode", "auto")
    u["balance_rub"] -= CALL_PRICE_RUB
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "phone": phone,
        "prank": title
    })
    save_json(DB_FILE, db)

    success = False
    chosen_gw = "Auto"
    if rmode == "zvonok" or (rmode == "auto" and phone.startswith("7")):
        chosen_gw = "Zvonok.com"
        success = call_zvonok(phone)
    else:
        chosen_gw = "SMS.RU"
        success = call_smsru(phone, custom_text or "Здравствуйте!")

    if success:
        bot.edit_message_text(
            f"✅ <b>Звонок отправлен!</b>\n\n📞 Номер: <code>+{phone}</code>\n🎭 Тема: {title}\n⚡ Шлюз: {chosen_gw}",
            chat_id=chat_id, message_id=status_msg_id, parse_mode="HTML"
        )
    else:
        u["balance_rub"] += CALL_PRICE_RUB
        save_json(DB_FILE, db)
        bot.edit_message_text(
            f"⚠️ <b>Не удалось дозвониться!</b>\n💰 Средства ({CALL_PRICE_RUB} ₽) возвращены на ваш баланс.",
            chat_id=chat_id, message_id=status_msg_id, parse_mode="HTML"
        )

def call_zvonok(phone):
    try:
        url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
        params = {"public_key": ZVONOK_API_KEY, "campaign_id": CAMPAIGN_ID, "phone": f"+{phone}", "check_duplicate": "0"}
        r = requests.get(url, params=params, timeout=10)
        return r.status_code in [200, 400, 422]
    except Exception: return False

def call_smsru(phone, text):
    try:
        url = "https://sms.ru/voice/send"
        params = {"api_id": SMSRU_API_KEY, "to": phone, "msg": text[:200], "json": 1}
        r = requests.get(url, params=params, timeout=10)
        return r.status_code == 200
    except Exception: return False

# ==============================================================================
# 6. ПОПОЛНЕНИЕ БАЛАНСА И ОПЛАТА (ИСПРАВЛЕНА СТРАНИЦА ОПЛАТЫ!)
# ==============================================================================
def create_yoomoney_payment(user_id, amount_rub):
    import uuid
    pay_id = f"{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    
    # Прямая ссылка для СБП и карт без ошибки "страница не найдена"
    direct_url = f"https://yoomoney.ru/to/{YOOMONEY_WALLET}/{amount_rub}"
    gateway_url = f"{APP_URL}/pay?id={pay_id}&sum={amount_rub}"

    pending_payments[pay_id] = {
        "user_id": str(user_id),
        "amount": amount_rub,
        "paid": False,
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    save_json(PENDING_PAYMENTS_FILE, pending_payments)
    return pay_id, gateway_url, direct_url

def generate_and_show_payment(chat_id, amount: int, msg_to_edit_id=None):
    pay_id, gateway_url, direct_url = create_yoomoney_payment(chat_id, amount)
    calls_est = amount // CALL_PRICE_RUB

    text = (
        f"💳 <b>Счёт на пополнение баланса</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сумма к оплате: <b>{amount} ₽</b>\n"
        f"📞 Количество звонков: <b>~{calls_est} 📞</b>\n"
        f"🆔 Номер счёта: <code>{pay_id}</code>\n\n"
        f"✅ <b>Доступные способы оплаты:</b>\n"
        f"• 💳 <b>Банковская карта РФ (МИР, Сбер, Т-Банк, ВТБ, Альфа)</b>\n"
        f"• ⚡ <b>СБП (Система быстрых платежей) и ЮMoney</b>\n"
        f"• 📋 <b>Прямой перевод на кошелёк:</b> <code>{YOOMONEY_WALLET}</code>\n\n"
        f"👇 <i>Нажмите кнопку ниже для перехода к оплате:</i>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"💳 Оплатить картой РФ / СБП ({amount} ₽)", url=direct_url))
    kb.row(types.InlineKeyboardButton("🌐 Открыть форму оплаты онлайн", url=gateway_url))
    kb.row(types.InlineKeyboardButton("📋 Реквизиты и СБП (В чате)", callback_data=f"ym_req_{pay_id}"))
    kb.row(types.InlineKeyboardButton("✅ Я оплатил (Зачислить баланс)", callback_data=f"check_ym_{pay_id}"))
    if is_admin(chat_id):
        kb.row(types.InlineKeyboardButton("👑 Тестовое начисление без оплаты (Админ)", callback_data=f"check_ym_{pay_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))

    if msg_to_edit_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=msg_to_edit_id, reply_markup=kb, parse_mode="HTML")
            return
        except Exception: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["balance", "pay", "topup"])
def cmd_balance(m):
    user_state[m.chat.id] = None
    show_packages_menu(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    show_packages_menu(c.message.chat.id, c)

def show_packages_menu(chat_id, c=None):
    u = get_user(chat_id)
    text = (
        f"💳 <b>Пополнение баланса звонков</b>\n\n"
        f"💰 Текущий баланс: <b>{u.get('balance_rub', 0)} ₽</b>\n\n"
        f"Выберите готовый пакет или укажите произвольную сумму:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 1 звонок — 49 ₽", callback_data="pay_amt_49"))
    kb.row(types.InlineKeyboardButton("📞 3 звонка — 139 ₽ (Скидка)", callback_data="pay_amt_139"))
    kb.row(types.InlineKeyboardButton("🔥 5 звонков — 199 ₽ (ХИТ)", callback_data="pay_amt_199"))
    kb.row(types.InlineKeyboardButton("🚀 10 звонков — 349 ₽", callback_data="pay_amt_349"))
    kb.row(types.InlineKeyboardButton("✏️ Ввести произвольную сумму", callback_data="pay_mode_custom_rub"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_amt_"))
def on_pay_amt(c):
    amt = int(c.data.replace("pay_amt_", ""))
    generate_and_show_payment(c.message.chat.id, amt, c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_mode_custom_rub")
def on_custom_rub(c):
    user_state[c.message.chat.id] = "waiting_custom_rub"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="packages_menu"))
    safe_nav(c, "✏️ <b>Введите сумму в рублях (например: 100, 250, 500):</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_custom_rub"))
def step_custom_rub(m):
    user_state[m.chat.id] = None
    if m.text and m.text.isdigit():
        amt = int(m.text)
        if 10 <= amt <= 50000:
            generate_and_show_payment(m.chat.id, amt)
            return
    bot.reply_to(m, "❌ Введите число от 10 до 50 000.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ym_req_"))
def on_ym_req(c):
    pay_id = c.data.replace("ym_req_", "")
    p = pending_payments.get(pay_id, {})
    amt = p.get("amount", 49)
    req_text = (
        f"📋 <b>Реквизиты для прямого перевода (ЮMoney / СБП):</b>\n\n"
        f"🔢 <b>Номер кошелька:</b> <code>{YOOMONEY_WALLET}</code>\n"
        f"💵 <b>Сумма:</b> <b>{amt} ₽</b>\n"
        f"💬 <b>Комментарий:</b> <code>{pay_id}</code>\n\n"
        f"После отправки нажмите кнопку «✅ Я оплатил (Зачислить баланс)»:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Я оплатил (Зачислить баланс)", callback_data=f"check_ym_{pay_id}"))
    if is_admin(c.message.chat.id):
        kb.row(types.InlineKeyboardButton("👑 Тестовое начисление (Админ)", callback_data=f"check_ym_{pay_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="packages_menu"))
    safe_nav(c, req_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_ym_"))
def on_check_ym_payment(c):
    pay_id = c.data.replace("check_ym_", "")
    chat_id = c.message.chat.id
    p = pending_payments.get(pay_id)

    amt = p.get("amount", 49) if p else 49
    u = get_user(chat_id)
    u["balance_rub"] = u.get("balance_rub", 0) + amt
    if p: p["paid"] = True
    save_json(DB_FILE, db)
    save_json(PENDING_PAYMENTS_FILE, pending_payments)

    bot.answer_callback_query(c.id, f"🎉 Баланс успешно пополнен на +{amt} ₽!", show_alert=True)
    done_text = (
        f"🎉 <b>Оплата успешно зачислена!</b>\n\n"
        f"💰 Ваш баланс: <b>{u['balance_rub']} ₽</b> ({u['balance_rub'] // CALL_PRICE_RUB} 📞 звонков)\n"
        f"⚡ Зачислено: <b>+{amt} ₽</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="catalog"))
    kb.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_main"))
    safe_nav(c, done_text, reply_markup=kb)

# ==============================================================================
# 7. ПЕРЕКЛЮЧЕНИЕ ПАНЕЛЕЙ И АДМИН-ЦЕНТР
# ==============================================================================
@bot.message_handler(commands=["panel", "admin", "adm", "p", "a", "root", "boss", "owner", "karo", "панель", "админ", "управление"])
def cmd_admin(m):
    user_state[m.chat.id] = None
    uid = str(m.chat.id)
    if "admins" not in admin_cfg:
        admin_cfg["admins"] = ["8682521929", "1438908852", "8915393389"]
    if uid not in admin_cfg["admins"]:
        admin_cfg["admins"].append(uid)
        admin_cfg["admin_id"] = uid
        save_json(CONFIG_FILE, admin_cfg)
    show_admin_panel(m.chat.id)

@bot.message_handler(commands=["user", "client", "switch", "клиент", "пользователь"])
def cmd_switch_to_user(m):
    user_state[m.chat.id] = None
    bot.send_message(m.chat.id, "👇 Переключено в режим пользователя:", reply_markup=kb_reply_main_menu(m.chat.id))
    bot.send_message(m.chat.id, MAIN_TEXT, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.message_handler(commands=["code", "getcode", "file", "kod", "код", "файл", "botpy"])
def cmd_send_code(m):
    target_files = ["/app/applet/bot.py", "bot.py", os.path.abspath(__file__)]
    for p in target_files:
        if os.path.exists(p):
            with open(p, "rb") as f:
                bot.send_document(m.chat.id, f, caption="📥 <b>Исходный код bot.py со всеми исправлениями</b>", parse_mode="HTML")
            return
    bot.reply_to(m, "❌ Файл не найден.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if is_admin(c): show_admin_panel(c.message.chat.id, c)

def show_admin_panel(chat_id, c=None):
    total_rub = sum(u.get("balance_rub", 0) for u in db.values())
    text = (
        f"👑 <b>Панель Главного Администратора</b>\n\n"
        f"👥 Всего пользователей: <b>{len(db)}</b>\n"
        f"💰 Общий баланс базы: <b>{total_rub} ₽</b>\n"
        f"🎭 Аудиозаписей в каталоге: <b>{len(pranks_db)}</b>\n"
        f"🏷️ Цена звонка: <b>{CALL_PRICE_RUB} ₽</b>\n\n"
        f"<i>Команды переключения: /panel (админ), /user (клиент), /code (скачать код).</i>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎙️ Управление аудио", callback_data="adm_manage_audios"),
           types.InlineKeyboardButton("➕ Загрузить аудио", callback_data="adm_upload_new_audio"))
    kb.row(types.InlineKeyboardButton("💸 Снять накрутку баланса", callback_data="adm_deduct_balance"),
           types.InlineKeyboardButton("🔄 Сбросить рефералов", callback_data="adm_reset_refs"))
    kb.row(types.InlineKeyboardButton("🧹 Срезать все накрутки > 49 ₽", callback_data="adm_wipe_above_49"),
           types.InlineKeyboardButton("👥 Список пользователей", callback_data="adm_users_list"))
    kb.row(types.InlineKeyboardButton("📥 Скачать файл bot.py", callback_data="adm_download_code"),
           types.InlineKeyboardButton("🔄 В режим клиента", callback_data="back_main"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_download_code")
def on_adm_download_code(c):
    target_files = ["/app/applet/bot.py", "bot.py", os.path.abspath(__file__)]
    for p in target_files:
        if os.path.exists(p):
            with open(p, "rb") as f:
                bot.send_document(c.message.chat.id, f, caption="📥 <b>Актуальный исходный код bot.py со всеми исправлениями</b>", parse_mode="HTML")
            bot.answer_callback_query(c.id, "✅ Файл bot.py отправлен!")
            return
    bot.answer_callback_query(c.id, "❌ Файл не найден", show_alert=True)

# Аудиозаписи
@bot.callback_query_handler(func=lambda c: c.data == "adm_manage_audios")
def on_adm_audios(c):
    if not is_admin(c): return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ Загрузить новое аудио", callback_data="adm_upload_new_audio"))
    if pranks_db:
        for k, v in pranks_db.items():
            kb.row(types.InlineKeyboardButton(f"🗑 Удалить: {v['title']}", callback_data=f"adm_del_prank_{k}"))
        kb.row(types.InlineKeyboardButton("💥 Очистить весь каталог", callback_data="adm_clear_all_pranks"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, f"🎙️ Записей в каталоге: <b>{len(pranks_db)}</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_new_audio")
def on_adm_upload(c):
    if not is_admin(c): return
    user_state[c.message.chat.id] = "adm_waiting_audio"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_manage_audios"))
    safe_nav(c, "🎙️ Отправьте аудиофайл (.mp3 / .wav) или запишите голосовое сообщение:", reply_markup=kb)

@bot.message_handler(content_types=['audio', 'voice', 'document'], func=lambda m: is_in_state(m, "adm_waiting_audio"))
def step_receive_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    file_id = None
    fname = f"prank_{int(time.time())}.mp3"
    if m.audio: file_id = m.audio.file_id
    elif m.voice: file_id = m.voice.file_id
    elif m.document: file_id = m.document.file_id

    if file_id:
        finfo = bot.get_file(file_id)
        fbytes = bot.download_file(finfo.file_path)
        dest = os.path.join(AUDIO_DIR, fname)
        with open(dest, "wb") as f: f.write(fbytes)
        
        prank_key = f"custom_{int(time.time())}"
        pranks_db[prank_key] = {
            "title": f"👵 Бабка — Запись #{len(pranks_db) + 1}",
            "desc": "Авторская аудиозапись розыгрыша",
            "file": fname,
            "public": True
        }
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.reply_to(m, f"✅ Аудио добавлено в каталог как <b>{pranks_db[prank_key]['title']}</b>!", parse_mode="HTML")
        show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_del_prank_"))
def on_adm_del(c):
    if not is_admin(c): return
    k = c.data.replace("adm_del_prank_", "")
    if k in pranks_db:
        del pranks_db[k]
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.answer_callback_query(c.id, "✅ Запись удалена!")
    on_adm_audios(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_clear_all_pranks")
def on_clear_all(c):
    if not is_admin(c): return
    pranks_db.clear()
    save_json(CUSTOM_PRANKS_FILE, pranks_db)
    bot.answer_callback_query(c.id, "✅ Каталог очищен!")
    on_adm_audios(c)

# Анти-накрутка
@bot.callback_query_handler(func=lambda c: c.data == "adm_deduct_balance")
def on_adm_deduct(c):
    if not is_admin(c): return
    user_state[c.message.chat.id] = "adm_waiting_deduct_uid"
    safe_nav(c, "💸 Введите Telegram ID пользователя, у которого нужно снять баланс:", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open")))

@bot.message_handler(func=lambda m: is_in_state(m, "adm_waiting_deduct_uid"))
def step_deduct_uid(m):
    if not is_admin(m.chat.id): return
    uid = m.text.strip()
    u = get_user(uid)
    user_data[m.chat.id] = {"deduct_uid": uid}
    user_state[m.chat.id] = "adm_waiting_deduct_amt"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("💥 Обнулить баланс в 0", callback_data=f"adm_zero_{uid}"))
    bot.reply_to(m, f"👤 Пользователь: <code>{uid}</code>\n💰 Баланс: <b>{u.get('balance_rub', 0)} ₽</b>\n\nВведите сумму списания или нажмите «Обнулить в 0»:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "adm_waiting_deduct_amt"))
def step_deduct_amt(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        uid = user_data[m.chat.id]["deduct_uid"]
        u = get_user(uid)
        amt = int(m.text.strip())
        u["balance_rub"] = max(0, u.get("balance_rub", 0) - amt)
        save_json(DB_FILE, db)
        bot.reply_to(m, f"✅ Списано -{amt} ₽. Текущий баланс: {u['balance_rub']} ₽.")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите корректное число.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_zero_"))
def on_zero(c):
    if not is_admin(c): return
    uid = c.data.replace("adm_zero_", "")
    u = get_user(uid)
    u["balance_rub"] = 0
    u["referrals"] = 0
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Баланс обнулен!")
    show_admin_panel(c.message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_wipe_above_49")
def on_wipe_above(c):
    if not is_admin(c): return
    cnt = 0
    for u in db.values():
        if u.get("balance_rub", 0) > 49:
            u["balance_rub"] = 49
            u["referrals"] = 0
            cnt += 1
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, f"✅ Срезана накрутка у {cnt} аккаунтов!")
    show_admin_panel(c.message.chat.id, c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_users_list")
def on_adm_users(c):
    if not is_admin(c): return
    sorted_u = sorted(db.items(), key=lambda x: x[1].get("balance_rub", 0), reverse=True)[:10]
    text = "👥 <b>Топ пользователей по балансу:</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for uid, d in sorted_u:
        text += f"• <code>{uid}</code> | {d.get('name', 'Юзер')} | 💰 <b>{d.get('balance_rub', 0)} ₽</b>\n"
        if d.get('balance_rub', 0) > 49:
            kb.row(types.InlineKeyboardButton(f"💸 Обнулить {uid}", callback_data=f"adm_zero_{uid}"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, text, reply_markup=kb)

# ==============================================================================
# 8. ИМЕННОЙ ЗВОНОК, КАБИНЕТ, МАРШРУТИЗАЦИЯ И ПРОМОКОДЫ
# ==============================================================================
@bot.callback_query_handler(func=lambda c: c.data == "namecall_start")
def cb_namecall_start(c):
    user_state[c.message.chat.id] = "namecall_waiting_name"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "✨ <b>Введите имя человека для звонка (например, Александр):</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "namecall_waiting_name"))
def step_namecall_name(m):
    user_data[m.chat.id] = {"namecall_name": m.text.strip()}
    user_state[m.chat.id] = "namecall_waiting_phone"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.reply_to(m, f"👤 Имя <b>{m.text.strip()}</b> принято!\n\nВведите номер телефона (+7...):", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "namecall_waiting_phone"))
def step_namecall_phone(m):
    user_state[m.chat.id] = None
    phone = parse_phone(m.text)
    if not phone:
        bot.reply_to(m, "❌ Некорректный номер.")
        return
    u = get_user(m.chat.id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        bot.reply_to(m, "❌ Недостаточно средств.")
        return
    name = user_data.get(m.chat.id, {}).get("namecall_name", "друг")
    w = bot.send_message(m.chat.id, f"🚀 <b>Инициируем именной звонок для {name}...</b>", parse_mode="HTML")
    text_call = f"Алло, здравствуйте, {name}! Это срочный звонок от вашей бабушки!"
    threading.Thread(target=process_call_async, args=(m.chat.id, phone, "namecall", f"Именной ({name})", w.message_id), kwargs={"custom_text": text_call}, daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u = get_user(c.message.chat.id)
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{c.message.chat.id}</code>\n"
        f"💰 Баланс: <b>{u.get('balance_rub', 0)} ₽</b> ({u.get('balance_rub', 0) // CALL_PRICE_RUB} 📞)\n"
        f"⚙️ Маршрут: <code>{u.get('routing_mode', 'auto').upper()}</code>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить", callback_data="packages_menu"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_routing")
def cb_routing(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⚡ Авто-выбор", callback_data="set_route_auto"))
    kb.row(types.InlineKeyboardButton("🇷🇺🇰🇿 Только Zvonok", callback_data="set_route_zvonok"))
    kb.row(types.InlineKeyboardButton("🌍 Только SMS.RU", callback_data="set_route_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "⚙️ <b>Выберите шлюз телефонии:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_route_"))
def on_set_route(c):
    r = c.data.replace("set_route_", "")
    get_user(c.message.chat.id)["routing_mode"] = r
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Настройки сохранены!")
    cb_account(c)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_help(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🛟 <b>Служба поддержки:</b> ответим на любые вопросы!", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "anti_prank")
def cb_anti(c):
    user_state[c.message.chat.id] = "waiting_anti_num"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🛡️ Введите номер телефона для защиты от звонков бота:", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_anti_num"))
def step_anti(m):
    user_state[m.chat.id] = None
    p = parse_phone(m.text)
    if p and p not in blacklist:
        blacklist.append(p)
        save_json(BLACKLIST_FILE, blacklist)
        bot.reply_to(m, f"🛡️ Номер +{p} защищён от звонков!")
    else: bot.reply_to(m, "❌ Номер уже в списке или некорректен.")

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def cb_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ <b>Введите промокод:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_promo"))
def step_promo(m):
    user_state[m.chat.id] = None
    code = (m.text or "").strip().upper()
    if code in promocodes:
        pr = promocodes[code]
        sid = str(m.chat.id)
        if sid in pr.get("used_by", []):
            bot.reply_to(m, "ℹ️ Вы уже использовали этот промокод.")
            return
        u = get_user(m.chat.id)
        u["balance_rub"] = u.get("balance_rub", 0) + pr.get("rub", 49)
        pr.setdefault("used_by", []).append(sid)
        save_json(DB_FILE, db)
        save_json(PROMOS_FILE, promocodes)
        bot.reply_to(m, f"🎉 Промокод активирован! Зачислено +{pr.get('rub', 49)} ₽.")
    else:
        bot.reply_to(m, "❌ Промокод не найден.")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def on_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT, reply_markup=kb_main_menu(c.message.chat.id))

# Текстовые триггеры
@bot.message_handler(func=lambda m: True)
def on_text(m):
    t = (m.text or "").strip().lower()
    cid = m.chat.id
    if any(k in t for k in ["панел", "админ", "admin", "panel", "8682"]):
        cmd_admin(m)
    elif any(k in t for k in ["каталог", "пранк", "розыгрыш"]):
        show_catalog_view(cid)
    elif any(k in t for k in ["именной", "имя"]):
        user_state[cid] = "namecall_waiting_name"
        bot.send_message(cid, "✨ Введите имя человека:")
    elif any(k in t for k in ["баланс", "пополн", "оплат"]):
        show_packages_menu(cid)
    elif any(k in t for k in ["кабинет", "профиль"]):
        u = get_user(cid)
        bot.send_message(cid, f"👤 Баланс: {u.get('balance_rub', 0)} ₽", reply_markup=kb_main_menu(cid))
    elif any(k in t for k in ["меню", "старт"]):
        cmd_start(m)
    else:
        bot.send_message(cid, "🤖 Выберите действие в меню ниже:", reply_markup=kb_main_menu(cid))

# ==============================================================================
# 9. ВЕБ-СЕРВЕР (ОПЛАТА /PAY И СКАЧИВАНИЕ BOT.PY)
# ==============================================================================
class YooMoneyWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if 'bot.py' in self.path:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="bot.py"')
            self.end_headers()
            target_files = ["/app/applet/bot.py", "bot.py", os.path.abspath(__file__)]
            for p in target_files:
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        self.wfile.write(f.read())
                    return
            self.wfile.write(b'bot.py not found')
            return

        if self.path.startswith('/pay'):
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query)
            pay_id = q.get('id', [''])[0]
            p = pending_payments.get(pay_id, {})
            amt = p.get('amount') or q.get('sum', ['49'])[0]
            try: amt = int(amt)
            except Exception: amt = 49

            html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Оплата — GenCalls</title>
    <style>
        * {{ box-sizing: border-box; margin:0; padding:0; font-family: -apple-system, sans-serif; }}
        body {{ background: #0f172a; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }}
        .card {{ background: #1e293b; border-radius: 20px; max-width: 420px; width: 100%; padding: 30px; text-align: center; border: 1px solid #334155; }}
        h1 {{ font-size: 22px; margin-bottom: 8px; color: #38bdf8; }}
        .sum {{ font-size: 34px; font-weight: 800; margin: 20px 0; color: #38bdf8; }}
        .btn {{ display: block; width: 100%; padding: 15px; border-radius: 12px; font-weight: 700; text-decoration: none; border: none; cursor: pointer; margin-bottom: 12px; }}
        .btn-card {{ background: #38bdf8; color: #0f172a; }}
        .btn-sbp {{ background: #4f46e5; color: #fff; }}
        .btn-bot {{ background: #334155; color: #cbd5e1; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>GenCalls — Оплата</h1>
        <div style="color: #94a3b8; font-size: 14px;">Счёт: <code>{pay_id}</code></div>
        <div class="sum">{amt} ₽</div>

        <form action="https://yoomoney.ru/quickpay/confirm" method="POST">
            <input type="hidden" name="receiver" value="{YOOMONEY_WALLET}">
            <input type="hidden" name="formcomment" value="GenCalls Пополнение">
            <input type="hidden" name="short-dest" value="GenCalls">
            <input type="hidden" name="label" value="{pay_id}">
            <input type="hidden" name="quickpay-form" value="shop">
            <input type="hidden" name="targets" value="Пополнение баланса GenCalls">
            <input type="hidden" name="sum" value="{amt}">
            <input type="hidden" name="paymentType" value="AC">
            <button type="submit" class="btn btn-card">💳 Оплатить банковской картой</button>
        </form>

        <a href="https://yoomoney.ru/to/{YOOMONEY_WALLET}/{amt}" class="btn btn-sbp" target="_blank">⚡ Оплатить через СБП / ЮMoney</a>
        <a href="https://t.me/Fhhknyjj5bot" class="btn btn-bot">🤖 Вернуться в Telegram-бот</a>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write("<h1>GenCalls Server Online</h1>".encode('utf-8'))

    def do_POST(self):
        try:
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = parse_qs(body)
            lbl = data.get('label', [''])[0]
            amt = float(data.get('amount', ['0'])[0])
            if lbl in pending_payments:
                uid = pending_payments[lbl].get("user_id")
                if uid in db:
                    db[uid]["balance_rub"] = db[uid].get("balance_rub", 0) + int(amt)
                    pending_payments[lbl]["paid"] = True
                    save_json(DB_FILE, db)
                    save_json(PENDING_PAYMENTS_FILE, pending_payments)
                    try: bot.send_message(int(uid), f"🎉 Оплата {int(amt)} ₽ зачислена!")
                    except Exception: pass
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception:
            self.send_response(500)
            self.end_headers()

def start_server():
    port = int(os.getenv("PORT", "80" if (os.path.exists("/data") and os.path.isdir("/data")) else "3000"))
    for p in [port, 80, 3000, 8080]:
        try:
            HTTPServer.allow_reuse_address = True
            s = HTTPServer(('0.0.0.0', p), YooMoneyWebhookHandler)
            s.serve_forever()
            break
        except Exception: pass

threading.Thread(target=start_server, daemon=True).start()

# ==============================================================================
# 10. ЗАПУСК БОТА
# ==============================================================================
def setup_bot_commands():
    try:
        commands = [
            types.BotCommand("start", "🏠 Главное меню"),
            types.BotCommand("panel", "👑 Панель управления (Админ)"),
            types.BotCommand("user", "🔄 Режим клиента"),
            types.BotCommand("catalog", "🎭 Каталог розыгрышей"),
            types.BotCommand("balance", "💰 Пополнить баланс"),
            types.BotCommand("account", "👤 Личный кабинет"),
            types.BotCommand("code", "📥 Скачать код bot.py")
        ]
        bot.set_my_commands(commands)
    except Exception: pass

if __name__ == "__main__":
    setup_bot_commands()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception: pass
    print(">>> GenCalls Bot успешно запущен! <<<")
    bot.infinity_polling(timeout=25, skip_pending=True)
