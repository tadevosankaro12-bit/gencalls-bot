# -*- coding: utf-8 -*-
"""
GenCalls Telegram Bot — Полный единый код.
Категория: «Бабка» (8 тем). Кнопка каталога на первом месте.
Поддержка двух шлюзов (Zvonok + SMS.RU), вебхука оплаты и постоянного хранилища /data.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import requests
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import telebot
from telebot import types

# ==============================================================================
# 1. ПУТИ И ПОСТОЯННОЕ ХРАНИЛИЩЕ (AMVERA /DATA)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("PERSISTENT_DATA_DIR", "/data" if os.path.exists("/data") and os.path.isdir("/data") else BASE_DIR)

AUDIO_DIR = os.path.join(DATA_DIR, "prank_audios")
BASE_AUDIO_DIR = os.path.join(BASE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(BASE_AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json")
CUSTOM_PRANKS_FILE = os.path.join(DATA_DIR, "gencalls_pranks.json")
PROMOS_FILE = os.path.join(DATA_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "gencalls_blacklist.json")
ERRORS_LOG_FILE = os.path.join(DATA_DIR, "service_errors.json")
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
        # Резервная копия в BASE_DIR, если пишем в /data
        if DATA_DIR != BASE_DIR:
            base_backup = os.path.join(BASE_DIR, os.path.basename(path))
            with open(base_backup, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {path}: {e}")

# Синхронизация файлов при первом запуске с /data
def init_storage():
    if DATA_DIR != BASE_DIR:
        for fname in ["gencalls_db.json", "admin_config.json", "gencalls_pranks.json", "gencalls_promos.json"]:
            src = os.path.join(BASE_DIR, fname)
            dst = os.path.join(DATA_DIR, fname)
            if not os.path.exists(dst) and os.path.exists(src):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
        if os.path.exists(BASE_AUDIO_DIR):
            for af in os.listdir(BASE_AUDIO_DIR):
                src_a = os.path.join(BASE_AUDIO_DIR, af)
                dst_a = os.path.join(AUDIO_DIR, af)
                if not os.path.exists(dst_a) and os.path.isfile(src_a):
                    try:
                        shutil.copy2(src_a, dst_a)
                    except Exception:
                        pass

init_storage()

# ==============================================================================
# 2. КОНФИГУРАЦИЯ И КЛЮЧИ API
# ==============================================================================
TOKEN = os.getenv("TELEGRAM_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
ZVONOK_API_KEY = os.getenv("ZVONOK_API_KEY", "d0808ab7450fca32147a9285018fe7a5")
CAMPAIGN_ID = os.getenv("CAMPAIGN_ID", "1783540036")
SMSRU_API_KEY = os.getenv("SMSRU_API_KEY", "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF")

YOOMONEY_WALLET = os.getenv("YOOMONEY_WALLET", "4100119616287380")
YOOMONEY_SECRET = os.getenv("YOOMONEY_SECRET", "D2LS1zPM2UPAZ9wLeEVdbx7i")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "tadevosankaro12")
ADMIN_ID = os.getenv("ADMIN_ID", "8682521929")

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 1,
    "admin_id": "8682521929",
    "admins": ["8682521929", "1438908852", "8915393389"]
})
db = load_json(DB_FILE, {})
blacklist = load_json(BLACKLIST_FILE, [])
pending_payments = load_json(PENDING_PAYMENTS_FILE, {})

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 1)

# ==============================================================================
# 3. БАЗА РОЗЫГРЫШЕЙ: ТОЛЬКО КАТЕГОРИЯ «БАБКА»
# ==============================================================================
DEFAULT_PRANKS = {
    "babka_dolg": {
        "title": "👵 Бабка Лидия — Долг и участковый",
        "tag": "ХИТ",
        "dur": "0:38",
        "desc": "Соседка Лидия Васильевна кричит в трубку, требует вернуть 5000 рублей и грозит вызвать участкового прямо к двери.",
        "file": "babka_dolg.mp3",
        "public": True
    },
    "babka_zatop": {
        "title": "👵 Бабка Клавдия — Затопили кипятком",
        "tag": "ШОК",
        "dur": "0:42",
        "desc": "Соседка снизу в панике кричит, что с потолка хлещет горячая вода, обои вздулись, и требует срочно перекрыть краны.",
        "file": "babka_zatop.mp3",
        "public": True
    },
    "babka_vnuk": {
        "title": "👵 Бабка Зинаида — Алло, внучок?",
        "tag": "УГАР",
        "dur": "0:35",
        "desc": "Глуховатая бабуля перепутала номер, принимает собеседника за блудного внука, отчитывает за холодные пирожки и дедово давление.",
        "file": "babka_vnuk.mp3",
        "public": True
    },
    "babka_sverlo": {
        "title": "👵 Бабка Тамара — Перфоратор и дрель",
        "tag": "ТОП",
        "dur": "0:40",
        "desc": "Разъярённая пенсионерка обвиняет соседа в незаконном ремонте: «Ты сколько будешь стены долбить, люстра упала и кот заикается!»",
        "file": "babka_sverlo.mp3",
        "public": True
    },
    "babka_podjezd": {
        "title": "👵 Бабка Антонина — Подъездный сыщик",
        "tag": "ОР",
        "dur": "0:36",
        "desc": "Старшая по подъезду заявляет, что зафиксировала подозрительные ночные визиты в квартиру и собирает подписи на выселение.",
        "file": "babka_podjezd.mp3",
        "public": True
    },
    "babka_znakomstvo": {
        "title": "👵 Бабка Галина — Клуб знакомств 70+",
        "tag": "ХИТ",
        "dur": "0:45",
        "desc": "Одинокая бабушка Галя звонит по анкете из газеты «Сваха», хвалит свой холодец и настойчиво предлагает съехаться на даче.",
        "file": "babka_znakomstvo.mp3",
        "public": True
    },
    "babka_navoz": {
        "title": "👵 Бабка Нина — 10 мешков навоза",
        "tag": "УМОРА",
        "dur": "0:34",
        "desc": "Голосистая дачница утверждает, что заказанный свежий навоз выгрузили под подъезд, и требует немедленно выйти и оплатить доставку.",
        "file": "babka_navoz.mp3",
        "public": True
    },
    "babka_analizy": {
        "title": "👵 Бабка Евдокия — Анализы поликлиники",
        "tag": "ШОК",
        "dur": "0:37",
        "desc": "Сотрудница регистратуры пенсионного возраста требует явиться на повторный забор анализов из-за крайне подозрительных результатов.",
        "file": "babka_analizy.mp3",
        "public": True
    }
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
for pk, pv in DEFAULT_PRANKS.items():
    if pk not in pranks_db:
        pranks_db[pk] = pv
save_json(CUSTOM_PRANKS_FILE, pranks_db)

# Промокоды
DEFAULT_PROMOS = {
    "START2026": {"rub": 49, "uses": 500, "used_by": []},
    "СТАРТ2026": {"rub": 49, "uses": 500, "used_by": []},
    "BONUS50": {"rub": 50, "uses": 500, "used_by": []},
    "FREE": {"rub": 49, "uses": 500, "used_by": []}
}
promocodes = load_json(PROMOS_FILE, DEFAULT_PROMOS)

# ==============================================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
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
            "referred_by": None,
            "calls_history": []
        }
        save_json(DB_FILE, db)
    return db[s_uid]

def is_admin(user_obj_or_id):
    if not user_obj_or_id:
        return False
    uid = None
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
    admins = admin_cfg.get("admins", ["8682521929"])
    return uid in admins or uid == str(admin_cfg.get("admin_id", "8682521929"))

def is_in_state(m, state_name):
    if user_state.get(m.chat.id) != state_name:
        return False
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        user_state[m.chat.id] = None
        return False
    if any(btn in txt for btn in [
        "Каталог", "Именной", "Баланс", "Пополнить", "Кабинет", "Аккаунт",
        "Маршрутизация", "Маршрут", "Промокод", "Анти-Пранк", "Поддержка", "Админ",
        "Партнёр", "Партнер", "Правила", "Оферта"
    ]):
        user_state[m.chat.id] = None
        return False
    return True

def parse_phone(text):
    if not text:
        return None
    raw = "".join(c for c in text if c.isdigit() or c == "+")
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) >= 10:
        return digits
    return None

def normalize_promocode(code):
    if not code:
        return ""
    trans = str.maketrans("ABEKMHOPCTXaekmhopctx", "АВЕКМНОРСТХаекмнорстх")
    return code.strip().upper().translate(trans)

# ==============================================================================
# 5. КЛАВИАТУРЫ И МЕНЮ
# ==============================================================================
def kb_reply_main_menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(types.KeyboardButton("🎭 Каталог розыгрышей"), types.KeyboardButton("✨ Именной звонок"))
    kb.row(types.KeyboardButton("💰 Баланс / Пополнить"), types.KeyboardButton("👤 Личный кабинет"))
    kb.row(types.KeyboardButton("⚙️ Маршрутизация"), types.KeyboardButton("🎟️ Промокод"))
    kb.row(types.KeyboardButton("🤝 Партнёрам"), types.KeyboardButton("🛟 Поддержка"))
    kb.row(types.KeyboardButton("🛡️ Анти-Пранк"), types.KeyboardButton("📜 Правила"))
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
    # КАТАЛОГ РОЗЫГРЫШЕЙ НА ГЛАВНОМ ПЕРВОМ МЕСТЕ:
    kb.row(types.InlineKeyboardButton("🎭 Каталог розыгрышей (Категория: Бабка 👵)", callback_data="catalog"))
    kb.row(types.InlineKeyboardButton("✨ 👤 Именной звонок (Озвучить имя жертвы)", callback_data="namecall_start"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💰 Пополнить", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton(f"⚙️ Маршрут: {rmode_icon}", callback_data="nav_routing"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🤝 Партнёрам (+49 ₽)", callback_data="nav_affiliate"),
        types.InlineKeyboardButton("🎟️ Промокод (RU/EN)", callback_data="enter_promo")
    )
    kb.row(
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank"),
        types.InlineKeyboardButton("📜 Правила и Оферта", callback_data="legal_info")
    )
    kb.row(types.InlineKeyboardButton("👑 Панель Администратора", callback_data="admin_panel_open"))
    return kb

def safe_nav(c, text, reply_markup=None):
    try:
        bot.answer_callback_query(c.id)
    except Exception:
        pass
    chat_id = c.message.chat.id
    msg_id = c.message.message_id
    try:
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        try:
            bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            pass

MAIN_TEXT_BANNER = (
    "🎭 <b>GenCalls — Профессиональный сервис пранк-звонков</b>\n\n"
    "👵 <b>Категория «Бабка»:</b> 8 уморительных тем (долг, участковый, кипяток, внучок, навоз и др.)!\n"
    "✨ <b>Именной звонок:</b> бот позвонит и лично назовет жертву по имени.\n\n"
    "🕵️‍♂️ <b>100% Анонимность</b> — ваш личный номер никогда не отобразится.\n"
    "🌍 <b>Надёжная международная телефония:</b>\n"
    "• 🇷🇺🇰🇿 <b>Россия & Казахстан (+7)</b> — выделенный шлюз Zvonok\n"
    "• 🇦🇲🌍 <b>Армения (+374) & Весь Мир</b> — шлюз SMS.RU Voice\n\n"
    "💰 Стоимость звонка — <b>всего 49 ₽</b>.\n"
    "🛡️ <i>Баланс сохраняется, если абонент не взял трубку!</i>\n\n"
    "👇 <b>Выберите действие в меню ниже:</b>"
)

# ==============================================================================
# 6. КОМАНДЫ И ОБРАБОТЧИКИ НАВИГАЦИИ
# ==============================================================================
@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u = get_user(m.chat.id, m.from_user.first_name or "Друг")

    # Обработка реферала
    text_parts = (m.text or "").strip().split()
    if len(text_parts) > 1 and text_parts[1].startswith("ref_"):
        ref_id = text_parts[1].replace("ref_", "").strip()
        if ref_id != str(m.chat.id) and not u.get("referred_by"):
            ref_u = get_user(ref_id)
            if ref_u.get("referrals", 0) < MAX_REFERRALS:
                u["referred_by"] = ref_id
                ref_u["referrals"] = ref_u.get("referrals", 0) + 1
                ref_u["balance_rub"] = ref_u.get("balance_rub", 0) + 49
                save_json(DB_FILE, db)
                try:
                    bot.send_message(int(ref_id), "🎉 <b>По вашей ссылке пришёл друг!</b> Вам начислено <b>+49 ₽</b>!", parse_mode="HTML")
                except Exception:
                    pass

    bot.send_message(m.chat.id, "👇 Главное меню (кнопки быстрого доступа):", reply_markup=kb_reply_main_menu(m.chat.id))
    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.message_handler(commands=["catalog", "prank", "pranks"])
def cmd_catalog(m):
    user_state[m.chat.id] = None
    show_catalog_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog(c):
    show_catalog_view(c.message.chat.id, c)

def show_catalog_view(chat_id, c=None):
    admin_mode = is_admin(chat_id)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👵 ════ КАТЕГОРИЯ: БАБКА ════ 👵", callback_data="catalog_info_babka"))

    for k, v in pranks_db.items():
        is_pub = v.get("public", True)
        if is_pub or admin_mode:
            prefix_tag = "" if is_pub else "🔒 [Скрытый] "
            kb.row(types.InlineKeyboardButton(f"{prefix_tag}{v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))

    kb.row(types.InlineKeyboardButton("✨ 👤 Именной пранк (Сказать имя жертвы)", callback_data="namecall_start"))
    if admin_mode:
        kb.row(types.InlineKeyboardButton("🎙️ Студия аудиозаписей (Админ)", callback_data="adm_manage_audios"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))

    text = (
        "🎭 <b>Каталог розыгрышей — Категория «Бабка» 👵</b>\n\n"
        "<i>Все лишние категории удалены. Доступны отборные темы от легендарной Бабки:</i>\n\n"
        "• 👵 <b>Долг и вызов участкового</b> — крики и требования вернуть 5000 ₽\n"
        "• 👵 <b>Затопили кипятком</b> — паника соседки снизу\n"
        "• 👵 <b>«Алло, внучок?»</b> — остывшие пирожки и дедушка\n"
        "• 👵 <b>Перфоратор</b> — скандал из-за ремонта в выходной\n"
        "• 👵 <b>Подъездный сыщик</b> — разоблачение ночных визитов\n"
        "• 👵 <b>Клуб знакомств 70+</b> — поиск жениха с квартирой\n"
        "• 👵 <b>10 мешков навоза</b> — доставка свежих удобрений\n"
        "• 👵 <b>Анализы поликлиники</b> — срочный вызов к участковому врачу\n\n"
        "👇 <b>Выберите тему для звонка:</b>"
    )
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "catalog_info_babka")
def on_catalog_info_babka(c):
    bot.answer_callback_query(c.id, "👵 Все 8 тем категории «Бабка» представлены ниже!", show_alert=False)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return

    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({CALL_PRICE_RUB} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))

    desc_text = (
        f"🎭 <b>{p['title']}</b> [{p.get('tag', 'ТОП')}]\n\n"
        f"⏱ <b>Длительность:</b> <code>{p.get('dur', '0:38')}</code>\n"
        f"💬 <b>Сценарий:</b> {p.get('desc', '')}\n\n"
        f"👇 <i>Нажмите кнопку ниже, чтобы ввести номер телефона:</i>"
    )
    safe_nav(c, desc_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    k = c.data.replace("setup_call_", "")
    user_state[c.message.chat.id] = "waiting_phone"
    user_data[c.message.chat.id] = {"prank_key": k}
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📞 <b>Введите номер телефона для звонка:</b>\n\nНапример: <code>+79991234567</code> или <code>+37491234567</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_phone"))
def step_process_phone(m):
    chat_id = m.chat.id
    user_state[chat_id] = None
    phone = parse_phone(m.text)

    if not phone:
        bot.reply_to(m, "❌ <b>Некорректный номер телефона!</b>\nПожалуйста, укажите номер в международном формате (+7... или +374...).", parse_mode="HTML")
        return

    if phone in blacklist or f"+{phone}" in blacklist:
        bot.reply_to(m, "🛡️ <b>Этот номер внесён в стоп-лист (Анти-Пранк) и защищён от звонков!</b>", parse_mode="HTML")
        return

    p_data = user_data.get(chat_id, {})
    prank_key = p_data.get("prank_key", "babka_dolg")
    prank = pranks_db.get(prank_key, DEFAULT_PRANKS["babka_dolg"])

    u = get_user(chat_id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
        bot.reply_to(m, f"❌ <b>Недостаточно средств на балансе!</b>\nСтоимость звонка: <b>{CALL_PRICE_RUB} ₽</b>\nВаш баланс: <b>{u.get('balance_rub', 0)} ₽</b>", parse_mode="HTML", reply_markup=kb)
        return

    # Запуск звонка
    w = bot.send_message(chat_id, f"🚀 <b>Инициируем звонок на номер +{phone}...</b>\nСценарий: <i>{prank['title']}</i>", parse_mode="HTML")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, prank['title'], w.message_id), daemon=True).start()

# ==============================================================================
# 7. ТЕЛЕФОНИЯ: ZVONOK + SMS.RU
# ==============================================================================
def process_call_async(chat_id, phone, prank_key, title, status_msg_id, custom_text=None):
    u = get_user(chat_id)
    route_mode = u.get("routing_mode", "auto")

    # Списание баланса
    u["balance_rub"] -= CALL_PRICE_RUB
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "phone": phone,
        "prank": title,
        "service": "Auto"
    })
    save_json(DB_FILE, db)

    success = False
    chosen_gateway = ""

    # Выбор шлюза
    if route_mode == "zvonok" or (route_mode == "auto" and phone.startswith("7")):
        chosen_gateway = "Zvonok.com"
        success = call_zvonok(phone, prank_key)
    elif route_mode == "smsru" or (route_mode == "auto" and not phone.startswith("7")):
        chosen_gateway = "SMS.RU Voice"
        success = call_smsru(phone, custom_text or "Здравствуйте! Это юмористический звонок.")
    else:
        chosen_gateway = "Zvonok / SMS.RU"
        success = call_zvonok(phone, prank_key) or call_smsru(phone, custom_text or "Здравствуйте!")

    if success:
        bot.edit_message_text(
            f"✅ <b>Звонок успешно отправлен в телефонию!</b>\n\n"
            f"📞 <b>Номер:</b> <code>+{phone}</code>\n"
            f"🎭 <b>Тема:</b> {title}\n"
            f"⚡ <b>Шлюз:</b> {chosen_gateway}\n"
            f"💰 <b>Списано:</b> {CALL_PRICE_RUB} ₽\n\n"
            f"<i>Абоненту поступает входящий вызов прямо сейчас!</i>",
            chat_id=chat_id,
            message_id=status_msg_id,
            parse_mode="HTML"
        )
    else:
        # Возврат средств при ошибке дозвона
        u["balance_rub"] += CALL_PRICE_RUB
        save_json(DB_FILE, db)
        bot.edit_message_text(
            f"⚠️ <b>Не удалось совершить вызов!</b>\n"
            f"Шлюз телефонии временно недоступен или номер недосягаем.\n"
            f"💰 <b>Средства ({CALL_PRICE_RUB} ₽) полностью возвращены на ваш баланс!</b>",
            chat_id=chat_id,
            message_id=status_msg_id,
            parse_mode="HTML"
        )

def call_zvonok(phone, prank_key):
    try:
        url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
        params = {
            "public_key": ZVONOK_API_KEY,
            "campaign_id": CAMPAIGN_ID,
            "phone": f"+{phone}",
            "check_duplicate": "0"
        }
        res = requests.get(url, params=params, timeout=10)
        return res.status_code in [200, 400, 422]
    except Exception as e:
        print(f"Zvonok exception: {e}")
        return False

def call_smsru(phone, text):
    try:
        url = "https://sms.ru/voice/send"
        params = {
            "api_id": SMSRU_API_KEY,
            "to": phone,
            "msg": text[:200],
            "json": 1
        }
        res = requests.get(url, params=params, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"SMS.RU exception: {e}")
        return False

# ==============================================================================
# 8. ИМЕННОЙ ЗВОНОК, ЛИЧНЫЙ КАБИНЕТ, ПОПОЛНЕНИЕ, ПОДДЕРЖКА
# ==============================================================================
@bot.message_handler(commands=["namecall", "name", "imya"])
def cmd_namecall(m):
    user_state[m.chat.id] = None
    start_namecall_flow(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "namecall_start")
def cb_namecall_start(c):
    start_namecall_flow(c.message.chat.id, c)

def start_namecall_flow(chat_id, c=None):
    user_state[chat_id] = "namecall_waiting_name"
    text = (
        "✨ <b>Именной звонок (Озвучить имя жертвы)</b>\n\n"
        "Робот позвонит абоненту и лично обратится к нему по имени!\n\n"
        "👇 <b>Введите имя человека (например: <i>Александр</i>, <i>Алёна</i>):</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "namecall_waiting_name"))
def step_namecall_name(m):
    chat_id = m.chat.id
    name = (m.text or "").strip()
    user_data[chat_id] = {"victim_name": name}
    user_state[chat_id] = "namecall_waiting_phone"

    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.reply_to(m, f"👤 Имя <b>{name}</b> принято!\n\nТеперь введите номер телефона для звонка:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "namecall_waiting_phone"))
def step_namecall_phone(m):
    chat_id = m.chat.id
    user_state[chat_id] = None
    phone = parse_phone(m.text)

    if not phone:
        bot.reply_to(m, "❌ <b>Некорректный номер телефона!</b>", parse_mode="HTML")
        return

    name = user_data.get(chat_id, {}).get("victim_name", "друг")
    u = get_user(chat_id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        bot.reply_to(m, f"❌ Недостаточно средств на балансе ({CALL_PRICE_RUB} ₽).", parse_mode="HTML")
        return

    w = bot.send_message(chat_id, f"🚀 <b>Инициируем именной звонок для {name}...</b>", parse_mode="HTML")
    custom_msg = f"Алло, здравствуйте, {name}! Это срочный звонок от вашей любимой бабушки!"
    threading.Thread(target=process_call_async, args=(chat_id, phone, "namecall", f"Именной звонок ({name})", w.message_id), kwargs={"custom_text": custom_msg}, daemon=True).start()

# Личный кабинет
@bot.message_handler(commands=["account", "profile", "me", "cabinet"])
def cmd_account(m):
    user_state[m.chat.id] = None
    show_account_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    show_account_view(c.message.chat.id, c)

def show_account_view(chat_id, c=None):
    u = get_user(chat_id)
    bal = u.get("balance_rub", 0)
    calls = bal // CALL_PRICE_RUB
    rmode = u.get("routing_mode", "auto")

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 <b>Ваш ID:</b> <code>{chat_id}</code>\n"
        f"💰 <b>Баланс:</b> <b>{bal} ₽</b> ({calls} 📞 звонков)\n"
        f"⚙️ <b>Шлюз телефонии:</b> <code>{rmode.upper()}</code>\n"
        f"👥 <b>Приглашено друзей:</b> <code>{u.get('referrals', 0)}</code>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo"))
    kb.row(types.InlineKeyboardButton("⚙️ Изменить маршрут", callback_data="nav_routing"), types.InlineKeyboardButton("🤝 Партнёрка", callback_data="nav_affiliate"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

# Пополнение баланса
@bot.message_handler(commands=["balance", "pay", "topup"])
def cmd_balance(m):
    user_state[m.chat.id] = None
    show_packages_menu(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    show_packages_menu(c.message.chat.id, c)

def show_packages_menu(chat_id, c=None):
    text = (
        "💰 <b>Пополнение баланса звонков GenCalls</b>\n\n"
        "Выберите готовый пакет или укажите сумму в чате:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 1 звонок — 49 ₽", callback_data="pay_amt_49"))
    kb.row(types.InlineKeyboardButton("📞 3 звонка — 139 ₽ (Скидка)", callback_data="pay_amt_139"))
    kb.row(types.InlineKeyboardButton("🔥 5 звонков — 199 ₽ (ХИТ)", callback_data="pay_amt_199"))
    kb.row(types.InlineKeyboardButton("🚀 10 звонков — 349 ₽ (ВЫГОДНО)", callback_data="pay_amt_349"))
    kb.row(types.InlineKeyboardButton("✏️ Ввести произвольную сумму", callback_data="pay_mode_custom_rub"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_amt_"))
def on_pay_amt(c):
    amt = int(c.data.replace("pay_amt_", ""))
    pay_url = f"https://yoomoney.ru/transfer/quickpay?requestId={c.message.chat.id}&receiver={YOOMONEY_WALLET}&sum={amt}&targets=GenCalls_{c.message.chat.id}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"💳 Оплатить {amt} ₽ (ЮMoney / Карта)", url=pay_url))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
    safe_nav(c, f"💳 <b>Счёт на сумму {amt} ₽ сформирован!</b>\nПосле оплаты баланс пополнится автоматически.", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "pay_mode_custom_rub")
def on_custom_rub(c):
    user_state[c.message.chat.id] = "waiting_custom_rub"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="packages_menu"))
    safe_nav(c, "✏️ <b>Введите сумму пополнения в рублях (от 49 до 10 000):</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_custom_rub"))
def step_custom_rub(m):
    user_state[m.chat.id] = None
    if m.text and m.text.isdigit():
        amt = int(m.text)
        if 10 <= amt <= 50000:
            pay_url = f"https://yoomoney.ru/transfer/quickpay?receiver={YOOMONEY_WALLET}&sum={amt}&targets=GenCalls_{m.chat.id}"
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton(f"💳 Оплатить {amt} ₽", url=pay_url))
            kb.row(types.InlineKeyboardButton("🔙 Меню", callback_data="back_main"))
            bot.send_message(m.chat.id, f"💳 <b>Счёт на {amt} ₽ готов:</b>", reply_markup=kb, parse_mode="HTML")
            return
    bot.reply_to(m, "❌ Введите корректное число от 10 до 50 000.")

# Маршрутизация
@bot.message_handler(commands=["routing", "route", "gateway"])
def cmd_routing(m):
    user_state[m.chat.id] = None
    show_routing_menu(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "nav_routing")
def cb_routing(c):
    show_routing_menu(c.message.chat.id, c)

def show_routing_menu(chat_id, c=None):
    u = get_user(chat_id)
    cur = u.get("routing_mode", "auto")
    text = (
        "⚙️ <b>Маршрутизация телефонии GenCalls</b>\n\n"
        f"Текущий режим: <b>{cur.upper()}</b>\n\n"
        "• ⚡ <b>Авто-выбор:</b> Zvonok для РФ/КЗ (+7), SMS.RU для других стран\n"
        "• 🇷🇺🇰🇿 <b>Только Zvonok:</b> Россия и Казахстан (+7)\n"
        "• 🌍 <b>Только SMS.RU:</b> Армения (+374) и Весь Мир"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⚡ Умный Авто-выбор", callback_data="set_route_auto"))
    kb.row(types.InlineKeyboardButton("🇷🇺🇰🇿 Только Zvonok (+7)", callback_data="set_route_zvonok"))
    kb.row(types.InlineKeyboardButton("🌍 Только SMS.RU (Мир)", callback_data="set_route_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_route_"))
def on_set_route(c):
    mode = c.data.replace("set_route_", "")
    u = get_user(c.message.chat.id)
    u["routing_mode"] = mode
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Настройки сохранены!")
    show_routing_menu(c.message.chat.id, c)

# Партнёрская программа
def show_affiliate_view(chat_id, c=None):
    try:
        b_user = bot.get_me().username
    except Exception:
        b_user = "gencalls_bot"
    ref_link = f"https://t.me/{b_user}?start=ref_{chat_id}"
    u = get_user(chat_id)
    cur_refs = u.get("referrals", 0)

    text = (
        f"🤝 <b>Партнёрская программа GenCalls</b>\n\n"
        f"Получайте <b>+49 ₽ (1 бесплатный звонок)</b> за каждого приглашённого друга!\n\n"
        f"👥 Приглашено друзей: <b>{cur_refs}/{MAX_REFERRALS}</b>\n"
        f"🔗 Ваша ссылка:\n<code>{ref_link}</code>"
    )
    kb = types.InlineKeyboardMarkup()
    if cur_refs < MAX_REFERRALS:
        kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Анонимные+пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["ref", "referral", "affiliate", "partner"])
def cmd_affiliate(m):
    user_state[m.chat.id] = None
    show_affiliate_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    show_affiliate_view(c.message.chat.id, c)

# Поддержка и оферта
@bot.message_handler(commands=["help", "support", "faq"])
def cmd_help(m):
    user_state[m.chat.id] = None
    show_help_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_support(c):
    show_help_view(c.message.chat.id, c)

def show_help_view(chat_id, c=None):
    text = (
        "🛟 <b>Служба поддержки & FAQ</b>\n\n"
        "• <b>Как работает сервис?</b> Бот совершает звонок на указанный номер и проигрывает аудиозапись выбранной Бабки.\n"
        "• <b>Анонимно ли это?</b> Да, ваш личный номер нигде не отображается.\n"
        "• <b>Что если абонент не взял трубку?</b> Баланс сохраняется на вашем аккаунте."
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["rules", "legal", "oferta", "terms"])
def cmd_rules(m):
    user_state[m.chat.id] = None
    show_legal_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "legal_info")
def cb_legal(c):
    show_legal_view(c.message.chat.id, c)

def show_legal_view(chat_id, c=None):
    text = (
        "📜 <b>Правила сервиса и публичная оферта</b>\n\n"
        "• Сервис предназначен исключительно для развлекательных розыгрышей и поздравлений.\n"
        "• Запрещены звонки в экстренные службы (112, 101, 102, 103, 104).\n"
        "• При несостоявшемся вызове средства не списываются."
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

# Анти-Пранк (Черный список)
@bot.message_handler(commands=["anti", "antiprank", "stop", "blacklist"])
def cmd_anti(m):
    user_state[m.chat.id] = "waiting_blacklist_num"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.send_message(m.chat.id, "🛡️ <b>Анти-Пранк защита:</b>\nВведите номер, который хотите защитить от звонков бота:", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "anti_prank")
def cb_anti(c):
    user_state[c.message.chat.id] = "waiting_blacklist_num"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🛡️ <b>Анти-Пранк защита:</b>\nВведите номер, который хотите защитить от звонков бота:", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_blacklist_num"))
def step_blacklist_num(m):
    user_state[m.chat.id] = None
    num = parse_phone(m.text)
    if num:
        if num not in blacklist:
            blacklist.append(num)
            blacklist.append(f"+{num}")
            save_json(BLACKLIST_FILE, blacklist)
        bot.reply_to(m, f"🛡️ Номер +{num} успешно добавлен в стоп-лист и защищён от звонков!", reply_markup=kb_main_menu(m.chat.id))
    else:
        bot.reply_to(m, "❌ Некорректный номер.")

# Промокоды
@bot.message_handler(commands=["promo", "promocode", "code"])
def cmd_promo(m):
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) > 1:
        apply_promo(m.chat.id, parts[1], m)
    else:
        user_state[m.chat.id] = "waiting_promo_code"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
        bot.send_message(m.chat.id, "🎟️ <b>Введите промокод:</b>", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def cb_promo(c):
    user_state[c.message.chat.id] = "waiting_promo_code"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ <b>Введите промокод:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: is_in_state(m, "waiting_promo_code"))
def step_enter_promo(m):
    user_state[m.chat.id] = None
    apply_promo(m.chat.id, m.text, m)

def apply_promo(chat_id, raw_code, msg_obj=None):
    code = (raw_code or "").strip().upper()
    norm = normalize_promocode(code)
    target_key = code if code in promocodes else (norm if norm in promocodes else None)

    if not target_key:
        bot.send_message(chat_id, "❌ Промокод не найден или устарел.")
        return

    p = promocodes[target_key]
    s_id = str(chat_id)
    if s_id in p.get("used_by", []):
        bot.send_message(chat_id, "ℹ️ Вы уже использовали этот промокод.")
        return

    rub = p.get("rub", 49)
    u = get_user(chat_id)
    u["balance_rub"] = u.get("balance_rub", 0) + rub
    p.setdefault("used_by", []).append(s_id)
    save_json(DB_FILE, db)
    save_json(PROMOS_FILE, promocodes)

    bot.send_message(chat_id, f"🎉 <b>Промокод активирован!</b> Начислено: <b>+{rub} ₽</b>!", parse_mode="HTML", reply_markup=kb_main_menu(chat_id))

# ==============================================================================
# 9. ПАНЕЛЬ АДМИНИСТРАТОРА
# ==============================================================================
@bot.message_handler(commands=["admin", "adm", "panel", "root"])
def cmd_admin(m):
    if is_admin(m):
        show_admin_panel(m.chat.id)
    else:
        user_state[m.chat.id] = "waiting_admin_password"
        bot.send_message(m.chat.id, "🔒 Введите пароль администратора:")

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel_open(c):
    if is_admin(c):
        show_admin_panel(c.message.chat.id, c)
    else:
        user_state[c.message.chat.id] = "waiting_admin_password"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
        safe_nav(c, "🔒 <b>Введите пароль администратора в чат:</b>", reply_markup=kb)

def show_admin_panel(chat_id, c=None):
    total_users = len(db)
    total_rub = sum(u.get("balance_rub", 0) for u in db.values())
    text = (
        f"👑 <b>Панель Администратора GenCalls</b>\n\n"
        f"👥 Пользователей в базе: <b>{total_users}</b>\n"
        f"💰 Общий баланс на счетах: <b>{total_rub} ₽</b>\n"
        f"📞 Стоимость 1 звонка: <b>{CALL_PRICE_RUB} ₽</b>\n"
        f"👵 Активных тем Бабки: <b>{len(pranks_db)}</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎙️ Управление аудио Бабки", callback_data="adm_manage_audios"))
    kb.row(types.InlineKeyboardButton("💰 Изменить цену звонка", callback_data="adm_change_price"))
    kb.row(types.InlineKeyboardButton("🎟️ Управление промокодами", callback_data="adm_promos_menu"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка всем пользователям", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_manage_audios")
def on_adm_audios(c):
    if not is_admin(c): return
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        is_p = v.get("public", True)
        st = "🌐" if is_p else "🔒"
        kb.row(types.InlineKeyboardButton(f"{st} {v['title']}", callback_data=f"adm_toggle_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎙️ <b>Темы Бабки (нажмите для скрытия/публикации):</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_toggle_"))
def on_adm_toggle(c):
    if not is_admin(c): return
    k = c.data.replace("adm_toggle_", "")
    if k in pranks_db:
        pranks_db[k]["public"] = not pranks_db[k].get("public", True)
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.answer_callback_query(c.id, "✅ Статус обновлен!")
    on_adm_audios(c)

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def on_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

# ==============================================================================
# 10. ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ И КНОПОК МЕНЮ
# ==============================================================================
@bot.message_handler(content_types=['text', 'photo'])
def on_user_general_message(m):
    chat_id = m.chat.id
    raw_text = (m.text or "").strip()
    t = raw_text.lower()

    # Пароль администратора
    if raw_text in ["8682", "8682521929", "karo"]:
        s_id = str(chat_id)
        if s_id not in admin_cfg.get("admins", []):
            admin_cfg.setdefault("admins", []).append(s_id)
            save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, "👑 <b>Доступ администратора активирован!</b>", parse_mode="HTML")
        show_admin_panel(chat_id)
        return

    # Маршрутизация по кнопкам быстрого меню (Reply)
    if any(k in t for k in ["админ", "admin", "панел"]):
        show_admin_panel(chat_id)
        return
    elif any(k in t for k in ["каталог", "розыгрыш", "пранк"]):
        show_catalog_view(chat_id)
        return
    elif any(k in t for k in ["именной", "имя"]):
        start_namecall_flow(chat_id)
        return
    elif any(k in t for k in ["баланс", "пополн", "купить"]):
        show_packages_menu(chat_id)
        return
    elif any(k in t for k in ["кабинет", "аккаунт", "профиль"]):
        show_account_view(chat_id)
        return
    elif any(k in t for k in ["маршрут", "шлюз", "связ"]):
        show_routing_menu(chat_id)
        return
    elif any(k in t for k in ["поддержк", "хелп", "помощ", "faq"]):
        show_help_view(chat_id)
        return
    elif any(k in t for k in ["правил", "оферт"]):
        show_legal_view(chat_id)
        return
    elif any(k in t for k in ["партнер", "партнёр", "реферал"]):
        show_affiliate_view(chat_id)
        return
    elif any(k in t for k in ["анти", "черный"]):
        cmd_anti(m)
        return
    elif "промо" in t:
        cmd_promo(m)
        return
    elif any(k in t for k in ["меню", "старт", "главн"]):
        cmd_start(m)
        return
    else:
        bot.send_message(chat_id, "🤖 Используйте кнопки меню для управления:", reply_markup=kb_main_menu(chat_id))

# ==============================================================================
# 11. ВЕБХУК ДЛЯ ПРИЁМА ПЛАТЕЖЕЙ
# ==============================================================================
class YooMoneyWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write("<h1>GenCalls Webhook Server Online</h1>".encode('utf-8'))

    def do_POST(self):
        try:
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            params = parse_qs(body)
            # Извлекаем ID пользователя из targets: GenCalls_123456789
            targets = params.get('targets', [''])[0]
            amount = float(params.get('amount', ['0'])[0])
            if "GenCalls_" in targets:
                uid = targets.replace("GenCalls_", "").strip()
                if uid in db:
                    db[uid]["balance_rub"] = db[uid].get("balance_rub", 0) + int(amount)
                    save_json(DB_FILE, db)
                    try:
                        bot.send_message(int(uid), f"🎉 <b>Оплата {int(amount)} ₽ успешно зачислена!</b>", parse_mode="HTML")
                    except Exception:
                        pass
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            print(f"Webhook error: {e}")
            self.send_response(500)
            self.end_headers()

def start_webhook_server():
    port = int(os.getenv("PORT", "80" if (os.path.exists("/data") and os.path.isdir("/data")) else "3000"))
    for p in [port, 80, 3000, 8080]:
        try:
            HTTPServer.allow_reuse_address = True
            server = HTTPServer(('0.0.0.0', p), YooMoneyWebhookHandler)
            print(f"Webhook running on port {p}")
            server.serve_forever()
            break
        except Exception:
            continue

threading.Thread(target=start_webhook_server, daemon=True).start()

# ==============================================================================
# 12. ЗАПУСК БОТА
# ==============================================================================
if __name__ == "__main__":
    try:
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("catalog", "🎭 Каталог розыгрышей (Бабка)"),
            types.BotCommand("namecall", "✨ Именной звонок"),
            types.BotCommand("balance", "💰 Пополнить баланс"),
            types.BotCommand("account", "👤 Личный кабинет"),
            types.BotCommand("routing", "⚙️ Маршрутизация связи"),
            types.BotCommand("promo", "🎟️ Ввести промокод"),
            types.BotCommand("ref", "🤝 Партнёрская программа"),
            types.BotCommand("anti", "🛡️ Анти-Пранк защита"),
            types.BotCommand("help", "🛟 Помощь и FAQ"),
            types.BotCommand("rules", "📜 Правила и оферта"),
            types.BotCommand("admin", "👑 Панель администратора")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Error setting commands: {e}")

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    print(">>> Бот GenCalls успешно запущен с категорией «Бабка»! <<<")
    bot.infinity_polling(timeout=25, long_polling_timeout=25, skip_pending=True)
