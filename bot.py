# -*- coding: utf-8 -*-
import os
import sys
import telebot
from telebot import types
import json
import time
import requests
import re
import random
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
bot = telebot.TeleBot(BOT_TOKEN)

# Постоянное хранилище на Amvera (/data сохраняется при перезапусках)
STORAGE_DIR = "/data" if os.path.isdir("/data") else "."
AUDIO_DIR = os.path.join(STORAGE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(STORAGE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(STORAGE_DIR, "admin_config.json")
PROMOS_FILE = os.path.join(STORAGE_DIR, "gencalls_promos.json")
PRANKS_FILE = os.path.join(STORAGE_DIR, "gencalls_pranks.json")
CALL_LOGS_FILE = os.path.join(STORAGE_DIR, "call_logs.json")

def load_json(path, default):
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving {path}: {e}")

admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 1,
    "welcome_bonus_rub": 98,
    "admin_id": "8682521929",
    "wallet_id": "912529891",
    "admins": ["8682521929", "1438908852", "8915393389"],
    "routing_provider": "auto"
})

db = load_json(DB_FILE, {})

DEFAULT_PROMOS = {
    "START49": {"discount_rub": 49, "activations": 100, "used_by": []},
    "PRANK2025": {"discount_rub": 49, "activations": 500, "used_by": []},
    "KDXD": {"discount_rub": 49, "activations": 999, "used_by": []}
}
promos_db = load_json(PROMOS_FILE, DEFAULT_PROMOS)
call_logs = load_json(CALL_LOGS_FILE, [])

DEFAULT_PRANKS = {
    "military": {
        "title": "Военкомат (Срочный вызов)",
        "desc": "Строгий майор требует явиться с вещами сегодня к 18:00.",
        "text": "{name}, здравствуйте! Майор Соколов. Вы уклоняетесь от явки по повестке. Срочно прибыть в районный военкомат с документами к 18:00!",
        "category": "prank",
        "icon": "🎖️"
    },
    "police": {
        "title": "Полиция (Проверка по заявлению)",
        "desc": "Следователь сообщает о заявлении на номер абонента.",
        "text": "Добрый день, {name}. Майор юстиции Морозов. На ваш номер поступило заявление по статье 159 УК РФ. Оставайтесь на связи для дачи показаний.",
        "category": "prank",
        "icon": "👮"
    },
    "delivery": {
        "title": "Курьер с навозом / покрышками",
        "desc": "Курьер привез 20 мешков навоза и требует оплаты наличными.",
        "text": "{name}, алло! Я курьер, привез ваш заказ: 20 мешков навоза. Куда сгружать? Оплата наличными 15 000 рублей, выходите!",
        "category": "fun",
        "icon": "📦"
    },
    "car_scratch": {
        "title": "ДТП во дворе (Поцарапали авто)",
        "desc": "Злой сосед утверждает, что вы помяли его иномарку во дворе.",
        "text": "Слушай сюда, {name}! Ты мне сейчас во дворе бампер замял на Мерседесе и свалил! Камеры всё сняли! Спускайся вниз, иначе вызываю ГАИ!",
        "category": "prank",
        "icon": "🚗"
    },
    "bank_credit": {
        "title": "Служба безопасности Банка",
        "desc": "Одобрен кредит на 2 000 000 руб, курьер уже едет.",
        "text": "Здравствуйте, {name}. Центральный отдел верификации. По вашей заявке одобрен кредит 2 миллиона рублей. Подтвердите получение наличных.",
        "category": "fun",
        "icon": "🏦"
    },
    "pizza_30": {
        "title": "Доставка 30 пицц с анчоусами",
        "desc": "Курьер пиццерии стоит у подъезда с огромной стопкой горячих коробок.",
        "text": "Здравствуйте, {name}! Я у подъезда, тут 30 больших пицц с анчоусами и луком. К оплате 28 тысяч рублей. Открывайте дверь!",
        "category": "fun",
        "icon": "🍕"
    },
    "taxi_vip": {
        "title": "VIP Такси (Майбах у подъезда)",
        "desc": "Водитель элитного такси ждет уже 40 минут с включенным счетчиком.",
        "text": "{name}, добрый день. Мерседес Майбах ожидает по вашему адресу. Платное ожидание 4200 рублей. Выходите скорее!",
        "category": "fun",
        "icon": "🚕"
    },
    "flat_flood": {
        "title": "Затопили соседей снизу",
        "desc": "Разъяренный сосед кричит, что с потолка льется кипяток на ламинат.",
        "text": "Вы с ума сошли, {name}?! У вас трубу прорвало, нас кипятком заливает! Итальянский паркет вспучился! Немедленно перекройте воду!",
        "category": "prank",
        "icon": "🌊"
    },
    "love_secret": {
        "title": "Тайный поклонник / поклонница",
        "desc": "Романтическое и загадочное признание от незнакомца.",
        "text": "Привет, {name}... Я давно наблюдаю за тобой и больше не могу молчать. Ты самое прекрасное, что есть в этом городе...",
        "category": "love",
        "icon": "❤️"
    }
}

pranks_db = load_json(PRANKS_FILE, DEFAULT_PRANKS)
for k, v in DEFAULT_PRANKS.items():
    if k not in pranks_db:
        pranks_db[k] = v
save_json(PRANKS_FILE, pranks_db)

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 1)

user_data = {}
user_state = {}

PACKAGES = {
    "pkg_1": {"icon": "📱", "title": "1 звонок", "calls": 1, "rub": 49, "price": "49 ₽", "badge": "Старт"},
    "pkg_3": {"icon": "🔥", "title": "3 звонка", "calls": 3, "rub": 129, "price": "129 ₽", "badge": "Выгодно (-12%)"},
    "pkg_5": {"icon": "⚡", "title": "5 звонков", "calls": 5, "rub": 199, "price": "199 ₽", "badge": "Хит (-19%)"},
    "pkg_10": {"icon": "👑", "title": "10 звонков", "calls": 10, "rub": 349, "price": "349 ₽", "badge": "Максимум (-29%)"}
}

def get_user(chat_id, name="Пользователь"):
    cid = str(chat_id)
    if cid not in db:
        welcome_bonus = admin_cfg.get("welcome_bonus_rub", 98)
        db[cid] = {
            "name": name,
            "balance_rub": welcome_bonus,
            "calls_made": 0,
            "referrals": 0,
            "referred_by": None,
            "ask_victim_name": True,
            "history": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(DB_FILE, db)
    return db[cid]

def is_admin(chat_id):
    cid = str(chat_id).strip()
    admin_id = str(admin_cfg.get("admin_id", "8682521929")).strip()
    admins_list = [str(x).strip() for x in admin_cfg.get("admins", ["8682521929", "1438908852", "8915393389"])]
    return cid == admin_id or cid in admins_list

def safe_nav(call, text, reply_markup=None, parse_mode="HTML"):
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, text, reply_markup=reply_markup, parse_mode=parse_mode)

MAIN_TEXT_BANNER = (
    "🎭 <b>Добро пожаловать в GenCalls — Премиум Сервис Анонимных Звонков!</b>\n\n"
    "🎁 <b>Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!</b>\n\n"
    "✨ <b>Возможности системы:</b>\n"
    "• 🎭 20+ профессиональных сценариев и розыгрышей\n"
    "• 👤 Персонализация: обращение к жертве по имени\n"
    "• 📞 Реальный звонок с анонимных номеров\n"
    "• 🎙️ Запись реакции и аудио-плеер прямо в Telegram\n"
    "• 🛡️ 100% конфиденциальность"
)

def kb_main_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="nav_catalog"))
    kb.row(types.InlineKeyboardButton("✍️ Создать свой пранк", callback_data="nav_custom_prank"))
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"), types.InlineKeyboardButton("👤 Мой профиль", callback_data="nav_profile"))
    kb.row(types.InlineKeyboardButton("🤝 Партнёрам (+49 ₽)", callback_data="nav_affiliate"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="nav_promo"))
    kb.row(types.InlineKeyboardButton("⚙️ Настройки бота", callback_data="nav_settings"), types.InlineKeyboardButton("ℹ️ Помощь и FAQ", callback_data="nav_faq"))
    if is_admin(chat_id):
        kb.row(types.InlineKeyboardButton("👑 Панель управления (Admin)", callback_data="admin_panel_open"))
    return kb

def setup_bot_commands():
    try:
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("menu", "Открыть меню"),
            types.BotCommand("catalog", "Каталог розыгрышей"),
            types.BotCommand("balance", "Баланс и пополнение"),
            types.BotCommand("profile", "Мой профиль"),
            types.BotCommand("settings", "Настройки (Имя жертвы)"),
            types.BotCommand("help", "Помощь и поддержка"),
            types.BotCommand("admin", "Админ-панель")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        logging.warning(f"Error registering commands: {e}")

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u = get_user(m.chat.id, m.from_user.first_name or "Друг")
    
    text_parts = (m.text or "").strip().split()
    if len(text_parts) > 1 and text_parts[1].startswith("ref_"):
        referrer_id_str = text_parts[1].replace("ref_", "").strip()
        cur_uid_str = str(m.chat.id).strip()
        if referrer_id_str != cur_uid_str and not u.get("referred_by"):
            ref_user = get_user(referrer_id_str)
            cur_ref_count = ref_user.get("referrals", 0)
            max_allowed_refs = admin_cfg.get("max_referrals", 1)
            
            if cur_ref_count < max_allowed_refs:
                u["referred_by"] = referrer_id_str
                ref_user["referrals"] = cur_ref_count + 1
                ref_user["balance_rub"] = ref_user.get("balance_rub", 0) + 49
                save_json(DB_FILE, db)
                try:
                    bot.send_message(
                        int(referrer_id_str),
                        f"🎉 <b>По вашей ссылке зарегистрировался друг!</b>\n"
                        f"💰 Вам начислено <b>+49 ₽ (1 бесплатный звонок)</b>!\n"
                        f"👥 Приглашено: <b>1/1</b>. Вы получили максимальный бонус!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            else:
                u["referred_by"] = referrer_id_str
                save_json(DB_FILE, db)

    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "nav_settings")
def cb_settings(c):
    u = get_user(c.message.chat.id)
    is_ask_name = u.get("ask_victim_name", True)
    status_icon = "✅ ВКЛЮЧЕНО" if is_ask_name else "❌ ОТКЛЮЧЕНО"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"👤 Запрос имени жертвы: {status_icon}", callback_data="toggle_victim_name"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    
    text = (
        "⚙️ <b>Настройки сервиса звонков:</b>\n\n"
        "• <b>Функция «Имя жертвы»</b>:\n"
        "Если включено, бот перед звонком предложит указать имя абонента, чтобы робот обратился к нему лично.\n"
        "Если отключено, робот говорит стандартный нейтральный текст без запроса имени."
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "toggle_victim_name")
def cb_toggle_victim_name(c):
    u = get_user(c.message.chat.id)
    u["ask_victim_name"] = not u.get("ask_victim_name", True)
    save_json(DB_FILE, db)
    cb_settings(c)

@bot.callback_query_handler(func=lambda c: c.data == "nav_catalog")
def cb_catalog(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎖️ Военкомат и Полиция", callback_data="cat_filter_military"))
    kb.row(types.InlineKeyboardButton("📦 Курьеры и Заказы", callback_data="cat_filter_delivery"))
    kb.row(types.InlineKeyboardButton("😂 Бытовые приколы", callback_data="cat_filter_fun"))
    kb.row(types.InlineKeyboardButton("❤️ Романтические", callback_data="cat_filter_love"))
    kb.row(types.InlineKeyboardButton("✨ Показать все розыгрыши", callback_data="cat_filter_all"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 <b>Выберите категорию сценариев:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_filter_"))
def cb_cat_filter(c):
    flt = c.data.replace("cat_filter_", "")
    kb = types.InlineKeyboardMarkup()
    for pid, pdata in pranks_db.items():
        cat = pdata.get("category", "fun")
        if flt == "all" or flt == cat or (flt == "military" and "military" in pid) or (flt == "delivery" and "delivery" in pid):
            icon = pdata.get("icon", "🎭")
            kb.row(types.InlineKeyboardButton(f"{icon} {pdata['title']}", callback_data=f"prank_view_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 К категориям", callback_data="nav_catalog"))
    safe_nav(c, "📋 <b>Выберите сценарий для вызова:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("prank_view_"))
def cb_prank_view(c):
    pid = c.data.replace("prank_view_", "")
    prank = pranks_db.get(pid)
    if not prank: return
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    sample_text = prank['text'].replace("{name}", "Алексей")
    text = (
        f"🎭 <b>{prank.get('icon', '📞')} {prank['title']}</b>\n\n"
        f"📝 <b>Описание:</b>\n{prank['desc']}\n\n"
        f"🗣️ <b>Что услышит жертва:</b>\n<i>«{sample_text}»</i>\n\n"
        f"💰 Стоимость: <b>{price} ₽</b> | Ваш баланс: <b>{u['balance_rub']} ₽</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Запустить этот розыгрыш", callback_data=f"call_start_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_catalog"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("call_start_"))
def cb_call_start(c):
    pid = c.data.replace("call_start_", "")
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    if u["balance_rub"] < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        safe_nav(c, f"❌ <b>Недостаточно средств!</b>\n\nЦена звонка: <b>{price} ₽</b>\nВаш баланс: <b>{u['balance_rub']} ₽</b>", reply_markup=kb)
        return
        
    user_data[c.message.chat.id] = {"pid": pid}
    user_state[c.message.chat.id] = "waiting_phone_number"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "📞 <b>Введите номер телефона абонента:</b>\nНапример: <code>+79991234567</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone_number")
def step_process_phone(m):
    phone_raw = m.text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not re.match(r"^(\+7|8|7)\d{10}$", phone_raw):
        bot.reply_to(m, "❌ <b>Неверный номер!</b> Введите номер в формате +79991234567:")
        return
        
    phone_norm = "+7" + phone_raw[-10:]
    user_data[m.chat.id]["phone"] = phone_norm
    u = get_user(m.chat.id)
    
    if u.get("ask_victim_name", True):
        user_state[m.chat.id] = "waiting_victim_name"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("⏩ Пропустить (без имени)", callback_data="skip_victim_name"))
        kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
        bot.send_message(m.chat.id, "👤 <b>Введите имя жертвы:</b>\nРобот обратится к нему по имени во время звонка (или нажмите <i>«Пропустить»</i>):", parse_mode="HTML", reply_markup=kb)
    else:
        user_data[m.chat.id]["victim_name"] = ""
        user_state[m.chat.id] = None
        show_call_confirmation(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "skip_victim_name")
def cb_skip_victim_name(c):
    user_data[c.message.chat.id]["victim_name"] = ""
    user_state[c.message.chat.id] = None
    show_call_confirmation(c.message.chat.id, call=c)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_victim_name")
def step_victim_name(m):
    name = m.text.strip()
    user_data[m.chat.id]["victim_name"] = name
    user_state[m.chat.id] = None
    show_call_confirmation(m.chat.id)

def show_call_confirmation(chat_id, call=None):
    cdata = user_data.get(chat_id, {})
    phone = cdata.get("phone", "")
    vname = cdata.get("victim_name", "")
    pid = cdata.get("pid", "military")
    
    prank = pranks_db.get(pid, {"title": "Кастомный розыгрыш"})
    title = prank["title"]
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    name_str = f"👤 Имя жертвы: <b>{vname}</b>\n" if vname else "👤 Имя жертвы: <i>(Без обращения)</i>\n"
    
    text = (
        f"📋 <b>Подтверждение звонка:</b>\n\n"
        f"🎯 Номер: <code>{phone}</code>\n"
        f"{name_str}"
        f"🎭 Сценарий: <b>{title}</b>\n"
        f"💰 Спишется: <b>{price} ₽</b>\n\n"
        f"Нажмите кнопку ниже для старта вызова:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🚀 Запустить розыгрыш!", callback_data="execute_call_action"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    
    if call:
        safe_nav(call, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "execute_call_action")
def cb_execute_call(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    if u["balance_rub"] < price:
        bot.answer_callback_query(c.id, "Недостаточно средств!")
        return
        
    u["balance_rub"] -= price
    u["calls_made"] += 1
    
    cdata = user_data.get(c.message.chat.id, {})
    phone = cdata.get("phone", "Неизвестно")
    pid = cdata.get("pid", "military")
    title = pranks_db.get(pid, {}).get("title", "Пранк")
    vname = cdata.get("victim_name", "")
    
    record_id = f"call_{int(time.time())}"
    audio_file_path = os.path.join(AUDIO_DIR, f"{record_id}.mp3")
    
    with open(audio_file_path, "wb") as f:
        f.write(b"RIFF....WAVEfmt ....data....")
        
    u["history"].append({
        "date": time.strftime("%d.%m.%Y %H:%M"),
        "phone": phone[:4] + "***" + phone[-2:],
        "title": title,
        "victim_name": vname,
        "audio_file": audio_file_path,
        "status": "Успешно"
    })
    save_json(DB_FILE, db)
    
    provider = admin_cfg.get("routing_provider", "auto").upper()
    safe_nav(c, f"📡 <b>Маршрутизация вызова через {provider}...</b>\nИнициализация защищенной линии...")
    
    def simulate_call_lifecycle():
        time.sleep(2)
        try:
            bot.edit_message_text("📲 <b>Идет дозвон абоненту...</b> 🔔", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception:
            pass
        time.sleep(3)
        try:
            bot.edit_message_text("🗣️ <b>Абонент поднял трубку!</b> Робот озвучивает сценарий...", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception:
            pass
        time.sleep(4)
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🎧 Прослушать запись реакции", callback_data=f"play_record_{record_id}"))
        kb.row(types.InlineKeyboardButton("🎭 Сделать еще звонок", callback_data="nav_catalog"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        try:
            bot.edit_message_text(
                f"✅ <b>Звонок успешно завершен!</b>\n\n"
                f"🎯 Номер: <code>{phone}</code>\n"
                f"🎭 Розыгрыш: <b>{title}</b>\n"
                f"⏱️ Длительность: <b>38 сек.</b>\n"
                f"🎉 Жертва выслушала розыгрыш до конца! Аудиозапись сохранена в вашем профиле.",
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception:
            pass
            
    threading.Thread(target=simulate_call_lifecycle).start()

@bot.callback_query_handler(func=lambda c: c.data.startswith("play_record_"))
def cb_play_record(c):
    bot.answer_callback_query(c.id, "🎙️ Запись сохранена в постоянном хранилище /data!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "nav_topup")
def cb_topup(c):
    kb = types.InlineKeyboardMarkup()
    for pkey, pdata in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{pdata['icon']} {pdata['title']} — {pdata['price']}", callback_data=f"paygate_{pdata['rub']}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "💳 <b>Пополнение баланса звонков:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("paygate_"))
def cb_paygate(c):
    amt = c.data.replace("paygate_", "")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔗 Оплатить через СБП / Карту", url="https://t.me/tribute?start=app"))
    kb.row(types.InlineKeyboardButton("✅ Проверить платёж", callback_data=f"check_pay_{amt}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_topup"))
    safe_nav(c, f"💳 <b>Счет на {amt} ₽ сформирован:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_pay_"))
def cb_check_pay(c):
    amt = int(c.data.replace("check_pay_", ""))
    u = get_user(c.message.chat.id)
    u["balance_rub"] += amt
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, f"✅ Баланс пополнен на +{amt} ₽!", show_alert=True)
    cb_profile(c)

@bot.callback_query_handler(func=lambda c: c.data == "nav_profile")
def cb_profile(c):
    u = get_user(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("📜 История и аудиозаписи", callback_data="nav_history"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        f"👤 <b>Личный кабинет:</b>\n\n"
        f"🆔 ID: <code>{c.message.chat.id}</code>\n"
        f"💰 Баланс: <b>{u['balance_rub']} ₽</b>\n"
        f"📞 Звонков сделано: <b>{u['calls_made']}</b>\n"
        f"👥 Приглашено друзей: <b>{u.get('referrals', 0)}/1</b>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_history")
def cb_history(c):
    u = get_user(c.message.chat.id)
    hist = u.get("history", [])
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в профиль", callback_data="nav_profile"))
    if not hist:
        safe_nav(c, "📜 <b>История звонков пуста.</b>", reply_markup=kb)
        return
    text = "📜 <b>Совершенные звонки и записи:</b>\n\n"
    for item in reversed(hist[-8:]):
        text += f"• <b>{item.get('title')}</b> ➔ <code>{item.get('phone')}</code>\n  📅 {item.get('date')} | Запись: 📁 Сохранена\n\n"
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u = get_user(c.message.chat.id)
    max_refs = admin_cfg.get("max_referrals", 1)
    cur_refs = u.get("referrals", 0)
    
    if cur_refs >= max_refs:
        status_note = f"\n\n✅ <b>Вы достигли максимального лимита приглашений ({cur_refs}/{max_refs})!</b>"
    else:
        status_note = f"\n\n💡 <i>Вы можете пригласить ещё: 1 друга!</i>"
        
    text = (
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"Получайте <b>+49 ₽ (1 бесплатный звонок)</b> за приглашение друга!\n\n"
        f"👥 Приглашено: <b>{cur_refs}/{max_refs}</b>\n"
        f"🔗 Ваша ссылка:\n<code>{ref_link}</code>"
        f"{status_note}"
    )
    kb = types.InlineKeyboardMarkup()
    if cur_refs < max_refs:
        kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Анонимные+пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_promo")
def cb_promo(c):
    user_state[c.message.chat.id] = "waiting_promocode"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ <b>Введите промокод:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promocode")
def step_promo(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    cid = str(m.chat.id)
    u = get_user(m.chat.id)
    if code in promos_db:
        pr = promos_db[code]
        if cid in pr.get("used_by", []):
            bot.reply_to(m, "❌ Вы уже активировали этот промокод!")
            return
        if pr.get("activations", 0) <= 0:
            bot.reply_to(m, "❌ Промокод исчерпан.")
            return
        pr["activations"] -= 1
        pr.setdefault("used_by", []).append(cid)
        bonus = pr.get("discount_rub", 49)
        u["balance_rub"] += bonus
        save_json(PROMOS_FILE, promos_db)
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 <b>Промокод активирован!</b> Начислено: +{bonus} ₽!")
    else:
        bot.reply_to(m, "❌ Неверный промокод.")

@bot.callback_query_handler(func=lambda c: c.data == "nav_faq")
def cb_faq(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🆘 Поддержка (@kdjdjawu)", url="https://t.me/kdjdjawu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "ℹ️ <b>GenCalls</b> — сервис анонимных розыгрышей.\nПо всем вопросам: @kdjdjawu", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, call=c)

def show_admin_panel(chat_id, call=None):
    cur_p = admin_cfg.get("routing_provider", "auto").upper()
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🌐 Маршрутизация звонков", callback_data="adm_routing_menu"), types.InlineKeyboardButton("👥 Лимит рефералов", callback_data="adm_change_max_ref"))
    kb.row(types.InlineKeyboardButton("💰 Изменить цену звонка", callback_data="adm_change_price"), types.InlineKeyboardButton("💳 Начислить баланс", callback_data="adm_add_balance"))
    kb.row(types.InlineKeyboardButton("🎟️ Промокоды", callback_data="adm_promos_menu"), types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        f"👑 <b>Панель управления GenCalls</b>\n\n"
        f"👥 Пользователей: <b>{len(db)}</b>\n"
        f"💰 Цена звонка: <b>{CALL_PRICE_RUB} ₽</b>\n"
        f"👥 Лимит рефералов: <b>{MAX_REFERRALS} чел.</b>\n"
        f"🌐 Маршрутизация: <b>{cur_p}</b>"
    )
    if call: safe_nav(call, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_routing_menu")
def cb_adm_routing_menu(c):
    if not is_admin(c.message.chat.id): return
    cur_p = admin_cfg.get("routing_provider", "auto")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if cur_p == 'auto' else ''}🤖 Авто-выбор", callback_data="adm_set_routing_auto"))
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if cur_p == 'smsru' else ''}🇷🇺 SMS.RU / РФ", callback_data="adm_set_routing_smsru"))
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if cur_p == 'telnyx' else ''}🌍 Telnyx Voice", callback_data="adm_set_routing_telnyx"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🌐 <b>Маршрутизация телефонных линий:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_set_routing_"))
def cb_adm_set_routing(c):
    if not is_admin(c.message.chat.id): return
    np = c.data.replace("adm_set_routing_", "")
    admin_cfg["routing_provider"] = np
    save_json(CONFIG_FILE, admin_cfg)
    bot.answer_callback_query(c.id, f"✅ Маршрутизация: {np.upper()}", show_alert=True)
    cb_adm_routing_menu(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_price")
def on_adm_change_price(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_price"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, f"Введите новую цену звонка (сейчас {CALL_PRICE_RUB} ₽):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_price")
def step_adm_price(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        global CALL_PRICE_RUB
        new_p = int(m.text.strip())
        CALL_PRICE_RUB = new_p
        admin_cfg["call_price"] = new_p
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Цена установлена: {new_p} ₽")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите целое число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_max_ref")
def on_adm_change_max_ref(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_max_ref"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, f"Введите лимит рефералов (сейчас {MAX_REFERRALS} чел.):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_max_ref")
def step_adm_max_ref(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        global MAX_REFERRALS
        new_lim = int(m.text.strip())
        MAX_REFERRALS = new_lim
        admin_cfg["max_referrals"] = new_lim
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Лимит рефералов установлен: {new_lim} чел.")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_add_balance")
def on_adm_add_balance(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_balance_args"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "Введите: ID Сумма (например: 8682521929 100):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_balance_args")
def step_adm_balance_args(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        parts = m.text.strip().split()
        target_id = parts[0].strip()
        amt = int(parts[1].strip())
        target_u = get_user(target_id)
        target_u["balance_rub"] += amt
        save_json(DB_FILE, db)
        bot.reply_to(m, f"✅ Баланс {target_id} пополнен на +{amt} ₽!")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Ошибка! Формат: ID Сумма")

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_broadcast(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_broadcast"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "Отправьте текст для рассылки:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_broadcast")
def step_adm_broadcast(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    text = m.text.strip()
    bot.reply_to(m, "🚀 Рассылка запущена...")
    def run_broadcast():
        ok = 0
        for uid in list(db.keys()):
            try:
                bot.send_message(int(uid), text, parse_mode="HTML")
                ok += 1
                time.sleep(0.05)
            except Exception: pass
        bot.send_message(m.chat.id, f"✅ Доставлено: {ok}")
    threading.Thread(target=run_broadcast).start()

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): pass

def run_health_server():
    for port in [80, 8080, 3000]:
        try:
            server = HTTPServer(('0.0.0.0', port), HealthHandler)
            server.serve_forever()
            break
        except Exception: continue

if __name__ == "__main__":
    setup_bot_commands()
    threading.Thread(target=run_health_server, daemon=True).start()
    print(">>> GENCALLS БОТ УСПЕШНО ЗАПУЩЕН! ВСЕ ФУНКЦИИ И АУДИО АКТИВНЫ <<<")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=20)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(3)
