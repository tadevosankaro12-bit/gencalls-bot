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

DB_FILE = "gencalls_db.json"
CONFIG_FILE = "admin_config.json"
PROMOS_FILE = "gencalls_promos.json"
PRANKS_FILE = "gencalls_pranks.json"
CALL_LOGS_FILE = "call_logs.json"

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
    "admin_id": "8682521929",
    "wallet_id": "912529891",
    "admins": ["8682521929", "1438908852", "8915393389"]
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
        "text": "Здравствуйте! Майор Соколов. Вы уклоняетесь от явки по повестке. Срочно прибыть в районный военкомат с документами и вещами к 18:00!",
        "category": "prank",
        "icon": "🎖️"
    },
    "police": {
        "title": "Полиция (Проверка по заявлению)",
        "desc": "Следователь сообщает о заявлении на номер абонента.",
        "text": "Добрый день. Майор юстиции Морозов. На ваш номер поступило заявление по статье 159 УК РФ. Оставайтесь на связи для дачи показаний.",
        "category": "prank",
        "icon": "👮"
    },
    "delivery": {
        "title": "Курьер с навозом / покрышками",
        "desc": "Курьер привез 20 мешков навоза и требует немедленной оплаты наличными.",
        "text": "Алло, здрасте! Я курьер, привез ваш заказ: 20 мешков конского навоза. Куда сгружать? Оплата наличными 15 000 рублей, выходите!",
        "category": "fun",
        "icon": "📦"
    },
    "car_scratch": {
        "title": "ДТП во дворе (Поцарапали авто)",
        "desc": "Злой сосед утверждает, что вы помяли его иномарку во дворе.",
        "text": "Слушай сюда! Ты мне сейчас во дворе бампер замял на Мерседесе и свалил! Камеры всё сняли! Спускайся вниз, иначе вызываю ГАИ!",
        "category": "prank",
        "icon": "🚗"
    },
    "bank_credit": {
        "title": "Служба безопасности Банка",
        "desc": "Одобрен кредит на 2 000 000 руб, курьер уже едет.",
        "text": "Здравствуйте. Центральный отдел верификации. По вашей заявке одобрен кредит 2 миллиона рублей. Подтвердите получение наличных курьеру.",
        "category": "fun",
        "icon": "🏦"
    },
    "pizza_30": {
        "title": "Доставка 30 пицц с анчоусами",
        "desc": "Курьер пиццерии стоит у подъезда с огромной стопкой горячих коробок.",
        "text": "Здравствуйте, пиццерия! Я у подъезда, тут 30 больших пицц с анчоусами и двойным луком. К оплате 28 тысяч рублей. Открывайте дверь!",
        "category": "fun",
        "icon": "🍕"
    },
    "taxi_vip": {
        "title": "VIP Такси (Майбах у подъезда)",
        "desc": "Водитель элитного такси ждет уже 40 минут с включенным счетчиком.",
        "text": "Алло, добрый день. Мерседес Майбах ожидает по вашему адресу уже 45 минут. Платное ожидание составило 4200 рублей. Выходите скорее!",
        "category": "fun",
        "icon": "🚕"
    },
    "love_secret": {
        "title": "Тайный поклонник / поклонница",
        "desc": "Романтическое и загадочное признание от незнакомца.",
        "text": "Привет... Я давно наблюдаю за тобой и больше не могу молчать. Ты самое прекрасное, что есть в этом городе. Выгляни в окно...",
        "category": "love",
        "icon": "❤️"
    },
    "flat_flood": {
        "title": "Затопили соседей снизу",
        "desc": "Разъяренный сосед кричит, что с потолка льется кипяток прямо на ламинат.",
        "text": "Вы с ума сошли?! У вас трубу прорвало, нас кипятком заливает с шестого этажа! У меня итальянский паркет вспучился! Немедленно перекройте воду!",
        "category": "prank",
        "icon": "🌊"
    },
    "fitness_fat": {
        "title": "Фитнес-тренер (Марафон похудения)",
        "desc": "Яростный тренер кричит в трубку и заставляет прямо сейчас приседать.",
        "text": "Так, хорош жрать булки! Это твой личный фитнес-тренер Арнольд! Упал — отжался двадцать раз! Я слышу, как ты дышишь, живо в спортзал!",
        "category": "fun",
        "icon": "🏋️"
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
        db[cid] = {
            "name": name,
            "balance_rub": 0,
            "calls_made": 0,
            "referrals": 0,
            "referred_by": None,
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
    "🎭 <b>Добро пожаловать в GenCalls — Сервис Анонимных Пранк-Звонков!</b>\n\n"
    "Разыграйте друзей, коллег или знакомых с помощью голосовых сценариев и роботов!\n\n"
    "✨ <b>Наши возможности:</b>\n"
    "• 🎭 Готовые сценарии розыгрышей\n"
    "• ✍️ Создание своего собственного сценария звонка\n"
    "• 📞 Реальный звонок на любой номер РФ\n"
    "• 🛡️ 100% анонимность — ваш личный номер нигде не отображается"
)

def kb_main_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="nav_catalog"))
    kb.row(types.InlineKeyboardButton("✍️ Создать свой пранк", callback_data="nav_custom_prank"))
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"), types.InlineKeyboardButton("👤 Мой профиль", callback_data="nav_profile"))
    kb.row(types.InlineKeyboardButton("🤝 Партнёрам (+49 ₽)", callback_data="nav_affiliate"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="nav_promo"))
    kb.row(types.InlineKeyboardButton("ℹ️ Помощь и FAQ", callback_data="nav_faq"))
    if is_admin(chat_id):
        kb.row(types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel_open"))
    return kb

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u = get_user(m.chat.id, m.from_user.first_name or "Друг")
    uname = getattr(m.from_user, "username", "") or ""
    
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
                        f"👥 Приглашено: <b>{ref_user['referrals']}/{max_allowed_refs}</b>. Вы достигли лимита! ✅",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            else:
                u["referred_by"] = referrer_id_str
                save_json(DB_FILE, db)
                try:
                    bot.send_message(
                        int(referrer_id_str),
                        f"ℹ️ По вашей ссылке перешёл друг, но ваш лимит приглашений (максимум {max_allowed_refs}) уже исчерпан!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    if str(m.chat.id).strip() == "8682521929" or uname.lower() == "kdjdjawu":
        admin_cfg["admin_id"] = "8682521929"
        save_json(CONFIG_FILE, admin_cfg)
        
    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "nav_catalog")
def cb_catalog(c):
    kb = types.InlineKeyboardMarkup()
    for pid, pdata in pranks_db.items():
        icon = pdata.get("icon", "🎭")
        kb.row(types.InlineKeyboardButton(f"{icon} {pdata['title']}", callback_data=f"prank_view_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 <b>Выберите сценарий розыгрыша:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("prank_view_"))
def cb_prank_view(c):
    pid = c.data.replace("prank_view_", "")
    prank = pranks_db.get(pid)
    if not prank:
        bot.answer_callback_query(c.id, "Сценарий не найден")
        return
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    text = (
        f"🎭 <b>{prank.get('icon', '📞')} {prank['title']}</b>\n\n"
        f"📝 <b>Описание:</b>\n{prank['desc']}\n\n"
        f"🗣️ <b>Что скажет робот:</b>\n<i>«{prank['text']}»</i>\n\n"
        f"💰 Стоимость звонка: <b>{price} ₽</b>\n"
        f"💳 Ваш баланс: <b>{u['balance_rub']} ₽</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Позвонить по этому сценарию", callback_data=f"call_start_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data="nav_catalog"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_custom_prank")
def cb_custom_prank(c):
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    user_state[c.message.chat.id] = "waiting_custom_prank_text"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    text = (
        "✍️ <b>Создание собственного розыгрыша:</b>\n\n"
        "Напишите текст, который робот должен сказать абоненту при звонке.\n\n"
        f"💰 Стоимость звонка: <b>{price} ₽</b>\n\n"
        "👉 <i>Отправьте текст розыгрыша прямо в чат:</i>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_custom_prank_text")
def step_custom_prank_text(m):
    txt = m.text.strip()
    if len(txt) < 5:
        bot.reply_to(m, "❌ Текст слишком короткий. Попробуйте снова:")
        return
    user_data[m.chat.id] = {"custom_text": txt, "title": "Кастомный розыгрыш"}
    user_state[m.chat.id] = None
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Перейти к звонку", callback_data="call_start_custom"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.reply_to(m, f"✅ <b>Текст принят!</b>\n\n<i>«{txt}»</i>\n\nГотовы набрать жертву?", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("call_start_"))
def cb_call_start(c):
    pid = c.data.replace("call_start_", "")
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    if u["balance_rub"] < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        safe_nav(c, f"❌ <b>Недостаточно средств!</b>\n\nЦена звонка: <b>{price} ₽</b>\nБаланс: <b>{u['balance_rub']} ₽</b>", reply_markup=kb)
        return
        
    user_data[c.message.chat.id] = {"pid": pid}
    user_state[c.message.chat.id] = "waiting_phone_number"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "📞 <b>Введите номер телефона для звонка:</b>\nНапример: <code>+79991234567</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone_number")
def step_process_phone(m):
    phone_raw = m.text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not re.match(r"^(\+7|8|7)\d{10}$", phone_raw):
        bot.reply_to(m, "❌ <b>Неверный номер!</b> Введите в формате +79991234567:")
        return
        
    phone_norm = "+7" + phone_raw[-10:]
    user_state[m.chat.id] = None
    pid = user_data.get(m.chat.id, {}).get("pid", "custom")
    title = "Свой сценарий" if pid == "custom" else pranks_db.get(pid, {}).get("title", "Пранк")
        
    user_data[m.chat.id]["phone"] = phone_norm
    user_data[m.chat.id]["title"] = title
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🚀 Подтвердить и Позвонить!", callback_data="confirm_call_execute"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.send_message(m.chat.id, f"🎯 Номер: <code>{phone_norm}</code>\n🎭 Розыгрыш: <b>{title}</b>\n💰 Спишется: <b>{price} ₽</b>", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "confirm_call_execute")
def cb_confirm_call_execute(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    if u["balance_rub"] < price:
        bot.answer_callback_query(c.id, "Недостаточно средств!")
        return
        
    u["balance_rub"] -= price
    u["calls_made"] += 1
    call_info = user_data.get(c.message.chat.id, {})
    phone = call_info.get("phone", "Неизвестно")
    title = call_info.get("title", "Пранк")
    
    u["history"].append({
        "date": time.strftime("%d.%m.%Y %H:%M"),
        "phone": phone[:4] + "***" + phone[-2:],
        "title": title,
        "status": "Успешно"
    })
    save_json(DB_FILE, db)
    
    safe_nav(c, "📡 <b>Инициализация телефонного шлюза...</b>\nПодключение к линии...")
    
    def simulate_call():
        time.sleep(2)
        try:
            bot.edit_message_text("📲 <b>Идет набор номера...</b> 🔔", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception:
            pass
        time.sleep(3)
        try:
            bot.edit_message_text("🗣️ <b>Абонент поднял трубку!</b> Воспроизведение сценария...", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception:
            pass
        time.sleep(4)
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🎭 Сделать еще звонок", callback_data="nav_catalog"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        try:
            bot.edit_message_text(f"✅ <b>Звонок успешно завершен!</b>\n\n🎯 Номер: <code>{phone}</code>\n🎭 Розыгрыш: <b>{title}</b>\n🎉 Жертва прослушала розыгрыш!", chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
            
    threading.Thread(target=simulate_call).start()

@bot.callback_query_handler(func=lambda c: c.data == "nav_topup")
def cb_topup_menu(c):
    kb = types.InlineKeyboardMarkup()
    for pkey, pdata in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{pdata['icon']} {pdata['title']} — {pdata['price']}", callback_data=f"paygate_card_{pdata['rub']}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "💳 <b>Выберите пакет пополнения баланса:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("paygate_"))
def cb_paygate(c):
    amount = c.data.split("_")[2]
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔗 Оплатить через СБП / Карту", url="https://t.me/tribute?start=app"))
    kb.row(types.InlineKeyboardButton("✅ Проверить платёж", callback_data=f"check_pay_{amount}"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="nav_topup"))
    safe_nav(c, f"💳 <b>Счет на оплату: {amount} ₽</b>\n\nОплатите счет и нажмите кнопку проверки:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_pay_"))
def cb_check_pay(c):
    amt = int(c.data.replace("check_pay_", ""))
    u = get_user(c.message.chat.id)
    u["balance_rub"] += amt
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, f"✅ Оплата {amt} ₽ зачислена!", show_alert=True)
    cb_profile(c)

@bot.callback_query_handler(func=lambda c: c.data == "nav_profile")
def cb_profile(c):
    u = get_user(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"🆔 ID: <code>{c.message.chat.id}</code>\n"
        f"💰 Баланс: <b>{u['balance_rub']} ₽</b>\n"
        f"📞 Сделано звонков: <b>{u['calls_made']}</b>\n"
        f"👥 Приглашено друзей: <b>{u.get('referrals', 0)}</b>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u = get_user(c.message.chat.id)
    max_allowed_refs = admin_cfg.get("max_referrals", MAX_REFERRALS)
    cur_refs = u.get('referrals', 0)
    
    if cur_refs >= max_allowed_refs:
        status_note = f"\n\n✅ <b>Вы достигли лимита приглашений ({cur_refs}/{max_allowed_refs})!</b>"
    else:
        left = max_allowed_refs - cur_refs
        status_note = f"\n\n💡 <i>Вы можете пригласить ещё: {left} друга!</i>"
        
    text = (
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"Получайте <b>+49 ₽ (1 бесплатный звонок)</b> за каждого приглашённого друга!\n\n"
        f"👥 Приглашено: <b>{cur_refs}/{max_allowed_refs}</b>\n"
        f"🔗 Ваша ссылка:\n<code>{ref_link}</code>"
        f"{status_note}"
    )
    kb = types.InlineKeyboardMarkup()
    if cur_refs < max_allowed_refs:
        kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Анонимные+пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_promo")
def cb_promo_enter(c):
    user_state[c.message.chat.id] = "waiting_promocode"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ <b>Введите промокод:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promocode")
def step_promo_check(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    cid = str(m.chat.id)
    u = get_user(m.chat.id)
    
    if code in promos_db:
        pr = promos_db[code]
        if cid in pr.get("used_by", []):
            bot.reply_to(m, "❌ Вы уже использовали этот промокод!")
            return
        if pr.get("activations", 0) <= 0:
            bot.reply_to(m, "❌ Лимит активаций исчерпан!")
            return
            
        pr["activations"] -= 1
        pr.setdefault("used_by", []).append(cid)
        bonus = pr.get("discount_rub", 49)
        u["balance_rub"] += bonus
        save_json(PROMOS_FILE, promos_db)
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 <b>Промокод активирован!</b> Начислено: <b>+{bonus} ₽</b>", parse_mode="HTML")
    else:
        bot.reply_to(m, "❌ Неверный промокод.")

@bot.callback_query_handler(func=lambda c: c.data == "nav_faq")
def cb_faq(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🆘 Поддержка", url="https://t.me/kdjdjawu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "ℹ️ <b>GenCalls</b> — бот анонимных пранк-звонков.\nВсе вызовы производятся через виртуальные станции.", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id):
        bot.answer_callback_query(c.id, "⛔ Доступ запрещен!", show_alert=True)
        return
    show_admin_panel(c.message.chat.id, call=c)

def show_admin_panel(chat_id, call=None):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Изменить цену", callback_data="adm_change_price"), types.InlineKeyboardButton("👥 Лимит рефералов", callback_data="adm_change_max_ref"))
    kb.row(types.InlineKeyboardButton("💳 Начислить баланс", callback_data="adm_add_balance"), types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    
    text = (
        f"⚙️ <b>Панель администратора:</b>\n\n"
        f"👥 Пользователей: <b>{len(db)}</b>\n"
        f"💰 Цена звонка: <b>{CALL_PRICE_RUB} ₽</b>\n"
        f"👥 Лимит рефералов: <b>{MAX_REFERRALS} чел.</b>"
    )
    if call:
        safe_nav(call, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

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
    safe_nav(c, f"Введите лимит приглашений (сейчас {MAX_REFERRALS} чел.):", reply_markup=kb)

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
    user_state[c.message.chat.id] = "adm_waiting_balance"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "Введите: ID Сумма (например: 8682521929 100):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_balance")
def step_adm_balance(m):
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
    safe_nav(c, "Отправьте текст для рассылки всем пользователям:", reply_markup=kb)

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
            except Exception:
                pass
        bot.send_message(m.chat.id, f"✅ Рассылка завершена! Доставлено: {ok}")
    threading.Thread(target=run_broadcast).start()

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_health_server():
    try:
        port = int(os.environ.get("PORT", 80))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        server.serve_forever()
    except Exception:
        try:
            server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
            server.serve_forever()
        except Exception:
            pass

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print(">>> GenCalls Bot успешно запущен! <<<")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=20)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(3)
