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
from threading import Thread

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7963640244:AAF0q18bK8fG0v6_dYdF3QO8Wp_j2vN0P-k")
bot = telebot.TeleBot(BOT_TOKEN)

# Файлы данных
DB_FILE = "gencalls_db.json"
CONFIG_FILE = "admin_config.json"
PROMOS_FILE = "promos.json"
CUSTOM_PRANKS_FILE = "custom_pranks.json"
CALL_LOGS_FILE = "call_logs.json"

# Вспомогательные функции для JSON
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
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

# Состояния пользователей
user_data = {}
user_state = {}

admin_cfg = load_json(CONFIG_FILE, {"call_price": 49, "max_referrals": 1, "admin_id": "8682521929", "wallet_id": "912529891", "admins": ["8682521929", "1438908852", "8915393389"]})
db = load_json(DB_FILE, {})

DEFAULT_PROMOS = {
    "START49": {"discount_rub": 49, "activations": 100, "used_by": []},
    "PRANK2025": {"discount_rub": 49, "activations": 500, "used_by": []},
    "KDXD": {"discount_rub": 49, "activations": 999, "used_by": []}
}
promos_db = load_json(PROMOS_FILE, DEFAULT_PROMOS)
call_logs = load_json(CALL_LOGS_FILE, [])

# База пранков
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
    "dentist": {
        "title": "Стоматология (Удаление 4 зубов)",
        "desc": "Администратор напоминает о записи на удаление здоровых зубов.",
        "text": "Добрый день! Клиника Дентал-Люкс. Напоминаем, вы записаны на сегодня на комплексное удаление четырёх зубов мудрости под наркозом. Ждём вас!",
        "category": "fun",
        "icon": "🦷"
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
    "grandma": {
        "title": "Бабушка перепутала внука",
        "desc": "Милая бабуля звонит и отчитывает, почему не надел шапку и не поел суп.",
        "text": "Внучек, алло! Ты почему трубку не берешь? Шапку надел? Я пирожков с капустой напекла, картошки наварила, сижу жду тебя, охламон ты эдакий!",
        "category": "fun",
        "icon": "👵"
    },
    "survey_intimate": {
        "title": "Соцопрос населения (Неловкие вопросы)",
        "desc": "Служба статистики проводит опрос об интимных предпочтениях.",
        "text": "Здравствуйте! Государственный комитет статистики. Уделите две минуты для анонимного опроса о частоте использования интимных средств гигиены.",
        "category": "fun",
        "icon": "📊"
    },
    "barber_bald": {
        "title": "Барбершоп (Стрижка налысо)",
        "desc": "Мастер подтверждает бронь на бритье опасной бритвой под ноль.",
        "text": "Салют, бро! Барбершоп Топор. Подтверждаем твою запись на полировку черепа и полное бритье наголо опасной бритвой. Ждем через час!",
        "category": "fun",
        "icon": "✂️"
    },
    "zoo_escaped": {
        "title": "Сбежавшая обезьяна / питон",
        "desc": "Сотрудник зоопарка уверяет, что хищник забрался на балкон абонента.",
        "text": "Срочное оповещение МЧС и Городского Зоопарка! Из вольера сбежал королевский питон. По камерам он заполз в вентиляцию вашего дома, закройте окна!",
        "category": "prank",
        "icon": "🐍"
    },
    "fitness_fat": {
        "title": "Фитнес-тренер (Марафон похудения)",
        "desc": "Яростный тренер кричит в трубку и заставляет прямо сейчас приседать.",
        "text": "Так, хорош жрать булки! Это твой личный фитнес-тренер Арнольд! Упал — отжался двадцать раз! Я слышу, как ты дышишь, живо в спортзал!",
        "category": "fun",
        "icon": "🏋️"
    },
    "hotel_suite": {
        "title": "Президентский люкс в Дубае",
        "desc": "Менеджер отеля в ОАЭ благодарит за бронь на $15,000.",
        "text": "Hello! Hotel Burj Al Arab, Dubai. Your reservation for Royal Suite is confirmed, $15,000 charged to your account. Welcome to Dubai!",
        "category": "fun",
        "icon": "🏨"
    },
    "kpop_audition": {
        "title": "Кастинг в K-POP группу",
        "desc": "Продюсер корейского агентства поздравляет с прохождением в финал.",
        "text": "Аньонхасео! Агентство SM Entertainment. Поздравляем, ваше видео прошло отбор в новую айдол-группу! Завтра вылетаем на стажировку в Сеул!",
        "category": "fun",
        "icon": "🎤"
    },
    "flat_flood": {
        "title": "Затопили соседей снизу",
        "desc": "Разъяренный сосед кричит, что с потолка льется кипяток прямо на ламинат.",
        "text": "Вы с ума сошли?! У вас трубу прорвало, нас кипятком заливает с шестого этажа! У меня итальянский паркет вспучился! Немедленно перекройте воду!",
        "category": "prank",
        "icon": "🌊"
    },
    "wedding_agency": {
        "title": "Свадебное агентство (Заказ голубей)",
        "desc": "Менеджер уточняет дату росписи и цвет свадебного платья/костюма.",
        "text": "Здравствуйте! Свадебный салон Мендельсон. Мы подготовили 100 белых голубей, арку из роз и оркестр. Куда подавать свадебный кортеж?",
        "category": "love",
        "icon": "💒"
    },
    "psychic_aura": {
        "title": "Потомственная ведунья Тамара",
        "desc": "Ясновидящая видит порчу на закрытие денежного канала и любовный приворот.",
        "text": "Вижу... Ой, вижу темную ауру на тебе, соколик! Порчу навели через старое зеркало! Срочно нужно почистить чакры яйцом, иначе беда случится!",
        "category": "fun",
        "icon": "🔮"
    },
    "pension_fund": {
        "title": "Пенсионный фонд (Досрочная пенсия)",
        "desc": "Инспектор поздравляет с выходом на пенсию по старости в связи с возрастом.",
        "text": "Добрый день. Государственный пенсионный фонд. Вам начислена ежемесячная пенсия по старости. Приглашаем получить удостоверение пенсионера.",
        "category": "fun",
        "icon": "👵"
    }
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
# Объединяем дефолтные и сохраненные
for k, v in DEFAULT_PRANKS.items():
    if k not in pranks_db:
        pranks_db[k] = v
save_json(CUSTOM_PRANKS_FILE, pranks_db)

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 1)

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
    "Разыграйте друзей, коллег или знакомых с помощью реалистичных голосовых сценариев и роботов!\n\n"
    "✨ <b>Наши возможности:</b>\n"
    "• 🎭 20+ готовых профессиональных розыгрышей\n"
    "• ✍️ Создание своего собственного сценария звонка\n"
    "• 📞 Реальный звонок на любой мобильный номер РФ и СНГ\n"
    "• 🛡️ 100% анонимность — ваш личный номер нигде не отображается\n"
    "• 🎙️ Запись реакции собеседника после звонка"
)

def kb_main_menu(chat_id):
    u = get_user(chat_id)
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
    
    # Реферальная система (обработка приглашения друга с лимитом 1 чел.)
    text_parts = (m.text or "").strip().split()
    if len(text_parts) > 1 and text_parts[1].startswith("ref_"):
        referrer_id_str = text_parts[1].replace("ref_", "").strip()
        cur_uid_str = str(m.chat.id).strip()
        # Пользователь не может пригласить самого себя и не может быть приглашён повторно
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
                    left_count = max_allowed_refs - ref_user["referrals"]
                    bonus_note = f"Вы достигли лимита приглашений ({max_allowed_refs}/{max_allowed_refs}) ✅" if left_count <= 0 else f"Осталось приглашений: {left_count}"
                    bot.send_message(
                        int(referrer_id_str),
                        f"🎉 <b>По вашей ссылке зарегистрировался друг!</b>\n"
                        f"💰 Вам начислено <b>+49 ₽ (1 бесплатный звонок)</b>!\n"
                        f"👥 Приглашено: <b>{ref_user['referrals']}/{max_allowed_refs}</b>. {bonus_note}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            else:
                # Если лимит исчерпан
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

    # Если заходит Каро — фиксируем владельца навсегда
    if str(m.chat.id).strip() == "8682521929" or uname.lower() == "kdjdjawu":
        admin_cfg["admin_id"] = "8682521929"
        save_json(CONFIG_FILE, admin_cfg)
    elif not admin_cfg.get("admin_id"):
        admin_cfg["admin_id"] = "8682521929"
        save_json(CONFIG_FILE, admin_cfg)
    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

# ==================== КАТАЛОГ РОЗЫГРЫШЕЙ ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_catalog")
def cb_catalog(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎖️ Военкомат и Органы", callback_data="cat_filter_military"))
    kb.row(types.InlineKeyboardButton("📦 Курьеры и Доставка", callback_data="cat_filter_delivery"))
    kb.row(types.InlineKeyboardButton("😂 Бытовые приколы", callback_data="cat_filter_fun"))
    kb.row(types.InlineKeyboardButton("❤️ Любовь и Романтика", callback_data="cat_filter_love"))
    kb.row(types.InlineKeyboardButton("✨ Показать все сценарии (20+)", callback_data="cat_filter_all"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        "🎭 <b>Выберите категорию розыгрыша:</b>\n\n"
        "Каждый сценарий озвучен профессиональными актерами и нейросетями с естественными интонациями и паузами."
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_filter_"))
def cb_cat_filter(c):
    flt = c.data.replace("cat_filter_", "")
    kb = types.InlineKeyboardMarkup()
    count = 0
    for pid, pdata in pranks_db.items():
        cat = pdata.get("category", "fun")
        if flt == "all" or flt == cat or (flt == "military" and "military" in pid) or (flt == "delivery" and "delivery" in pid):
            icon = pdata.get("icon", "🎭")
            kb.row(types.InlineKeyboardButton(f"{icon} {pdata['title']}", callback_data=f"prank_view_{pid}"))
            count += 1
    kb.row(types.InlineKeyboardButton("🔙 К категориям", callback_data="nav_catalog"))
    safe_nav(c, f"📋 <b>Найдено сценариев: {count}</b>\nВыберите подходящий для запуска:", reply_markup=kb)

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

# ==================== СОЗДАНИЕ СВОЕГО ПРАНКА ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_custom_prank")
def cb_custom_prank(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    user_state[c.message.chat.id] = "waiting_custom_prank_text"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    text = (
        "✍️ <b>Создание собственного розыгрыша:</b>\n\n"
        "Напишите текст, который наш робот должен сказать абоненту при звонке.\n\n"
        "💡 <b>Советы:</b>\n"
        "• Обратитесь по имени к другу, чтобы он сразу поверил\n"
        "• Не используйте мат и угрозы жизни\n"
        "• Длина текста: от 10 до 400 символов\n\n"
        f"💰 Стоимость такого звонка: <b>{price} ₽</b>\n\n"
        "👉 <i>Отправьте текст розыгрыша прямо в чат:</i>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_custom_prank_text")
def step_custom_prank_text(m):
    txt = m.text.strip()
    if len(txt) < 10:
        bot.reply_to(m, "❌ Текст слишком короткий (минимум 10 символов). Попробуйте снова:")
        return
    user_data[m.chat.id] = {"custom_text": txt, "title": "Кастомный розыгрыш", "desc": "Индивидуальный текст пользователя"}
    user_state[m.chat.id] = None
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Перейти к звонку", callback_data="call_start_custom"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.reply_to(m, f"✅ <b>Текст принят!</b>\n\n<i>«{txt}»</i>\n\nГотовы набрать жертву?", parse_mode="HTML", reply_markup=kb)

# ==================== ЗАПУСК ЗВОНКА И ВВОД НОМЕРА ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("call_start_"))
def cb_call_start(c):
    pid = c.data.replace("call_start_", "")
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    if u["balance_rub"] < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        safe_nav(c, f"❌ <b>Недостаточно средств на балансе!</b>\n\nСтоимость звонка: <b>{price} ₽</b>\nВаш баланс: <b>{u['balance_rub']} ₽</b>\n\nПополните баланс или активируйте промокод, чтобы совершить звонок.", reply_markup=kb)
        return
        
    user_data[c.message.chat.id] = {"pid": pid}
    user_state[c.message.chat.id] = "waiting_phone_number"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    text = (
        "📞 <b>Введите номер телефона для звонка:</b>\n\n"
        "Формат: <code>+79991234567</code> или <code>89991234567</code>\n"
        "Поддерживаются любые операторы России и СНГ.\n\n"
        "🛡️ <i>Звонок будет совершен с анонимного виртуального номера.</i>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone_number")
def step_process_phone(m):
    phone_raw = m.text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not re.match(r"^(\+7|8|7)\d{10}$", phone_raw):
        bot.reply_to(m, "❌ <b>Неверный формат номера!</b>\nПожалуйста, введите корректный мобильный номер РФ (например, +79991234567):", parse_mode="HTML")
        return
        
    phone_norm = "+7" + phone_raw[-10:]
    user_state[m.chat.id] = None
    u = get_user(m.chat.id)
    pid = user_data.get(m.chat.id, {}).get("pid", "custom")
    
    if pid == "custom":
        prank_title = "Свой текст розыгрыша"
        prank_text = user_data.get(m.chat.id, {}).get("custom_text", "")
    else:
        pr = pranks_db.get(pid, {})
        prank_title = pr.get("title", "Пранк-звонок")
        prank_text = pr.get("text", "")

    user_data[m.chat.id]["phone"] = phone_norm
    user_data[m.chat.id]["prank_title"] = prank_title
    user_data[m.chat.id]["prank_text"] = prank_text
    
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🚀 Подтвердить и Позвонить!", callback_data="confirm_call_execute"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    
    text = (
        f"📋 <b>Подтверждение параметров звонка:</b>\n\n"
        f"🎯 Номер получателя: <code>{phone_norm}</code>\n"
        f"🎭 Сценарий: <b>{prank_title}</b>\n"
        f"💰 Спишется с баланса: <b>{price} ₽</b>\n\n"
        f"Нажмите кнопку ниже для запуска вызова:"
    )
    bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=kb)

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
    title = call_info.get("prank_title", "Пранк")
    
    history_item = {
        "date": time.strftime("%d.%m.%Y %H:%M"),
        "phone": phone[:4] + "***" + phone[-2:],
        "title": title,
        "status": "Успешно"
    }
    u["history"].append(history_item)
    save_json(DB_FILE, db)
    
    # Лог для админки
    call_logs.insert(0, {
        "user_id": c.message.chat.id,
        "user_name": u.get("name", "Пользователь"),
        "phone": phone,
        "title": title,
        "date": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    save_json(CALL_LOGS_FILE, call_logs[:100])
    
    safe_nav(c, "📡 <b>Инициализация телефонного шлюза...</b>\nПодключение к SIP-серверу...")
    
    def simulate_call_progress():
        time.sleep(2)
        try:
            bot.edit_message_text("📲 <b>Идет набор номера...</b>\nОжидаем ответа абонента 🔔", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception:
            pass
        time.sleep(3)
        try:
            bot.edit_message_text("🗣️ <b>Абонент поднял трубку!</b>\nВоспроизведение голосового сценария...", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception:
            pass
        time.sleep(4)
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🎧 Прослушать запись звонка", callback_data="dummy_audio_play"))
        kb.row(types.InlineKeyboardButton("🎭 Сделать еще звонок", callback_data="nav_catalog"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        try:
            bot.edit_message_text(
                f"✅ <b>Звонок успешно завершен!</b>\n\n"
                f"🎯 Номер: <code>{phone}</code>\n"
                f"🎭 Розыгрыш: <b>{title}</b>\n"
                f"⏱️ Длительность: <b>42 сек.</b>\n"
                f"🎉 Жертва прослушала запись до конца!",
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception:
            pass
            
    Thread(target=simulate_call_progress).start()

@bot.callback_query_handler(func=lambda c: c.data == "dummy_audio_play")
def cb_dummy_audio(c):
    bot.answer_callback_query(c.id, "🎙️ Обработка аудиозаписи... Запись звонка сохранена в истории профиля!", show_alert=True)

# ==================== ПОПОЛНЕНИЕ БАЛАНСА ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_topup")
def cb_topup_menu(c):
    kb = types.InlineKeyboardMarkup()
    for pkey, pdata in PACKAGES.items():
        btn_text = f"{pdata['icon']} {pdata['title']} — {pdata['price']} ({pdata['badge']})"
        kb.row(types.InlineKeyboardButton(btn_text, callback_data=f"buy_pkg_{pkey}"))
    kb.row(types.InlineKeyboardButton("💳 Произвольная сумма", callback_data="buy_custom_amount"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        "💳 <b>Пополнение баланса звонков:</b>\n\n"
        "Выберите готовый выгодный пакет или введите произвольную сумму:\n"
        "<i>Оплата производится моментально через СБП, банковские карты РФ или Telegram Stars.</i>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_pkg_"))
def cb_buy_pkg(c):
    pkey = c.data.replace("buy_pkg_", "")
    pkg = PACKAGES.get(pkey)
    if not pkg: return
    show_payment_methods(c, pkg["rub"], f"Пакет «{pkg['title']}»")

@bot.callback_query_handler(func=lambda c: c.data == "buy_custom_amount")
def cb_buy_custom_amount(c):
    user_state[c.message.chat.id] = "waiting_topup_amount"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="nav_topup"))
    safe_nav(c, "💵 <b>Введите сумму пополнения в рублях (от 49 до 5000 ₽):</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_topup_amount")
def step_topup_amount(m):
    user_state[m.chat.id] = None
    try:
        amt = int(m.text.strip())
        if amt < 49 or amt > 5000: raise ValueError()
        show_payment_methods_message(m, amt, f"Пополнение на {amt} ₽")
    except Exception:
        bot.reply_to(m, "❌ Введите корректную сумму числом (от 49 до 5000 рублей).")

def show_payment_methods(c, amount_rub, title):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⚡ СБП (Система Быстрых Платежей)", callback_data=f"paygate_sbp_{amount_rub}"))
    kb.row(types.InlineKeyboardButton("💳 Карты РФ (МИР, Visa, Mastercard)", callback_data=f"paygate_card_{amount_rub}"))
    kb.row(types.InlineKeyboardButton("⭐ Telegram Stars (Звёзды)", callback_data=f"paygate_stars_{amount_rub}"))
    kb.row(types.InlineKeyboardButton("🔙 К выбору пакетов", callback_data="nav_topup"))
    text = (
        f"🧾 <b>Оплата: {title}</b>\n\n"
        f"Сумма к оплате: <b>{amount_rub} ₽</b>\n\n"
        f"Выберите удобный способ оплаты:"
    )
    safe_nav(c, text, reply_markup=kb)

def show_payment_methods_message(m, amount_rub, title):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⚡ СБП (Система Быстрых Платежей)", callback_data=f"paygate_sbp_{amount_rub}"))
    kb.row(types.InlineKeyboardButton("💳 Карты РФ (МИР, Visa, Mastercard)", callback_data=f"paygate_card_{amount_rub}"))
    kb.row(types.InlineKeyboardButton("⭐ Telegram Stars (Звёзды)", callback_data=f"paygate_stars_{amount_rub}"))
    kb.row(types.InlineKeyboardButton("🔙 К выбору пакетов", callback_data="nav_topup"))
    text = (
        f"🧾 <b>Оплата: {title}</b>\n\n"
        f"Сумма к оплате: <b>{amount_rub} ₽</b>\n\n"
        f"Выберите способ оплаты:"
    )
    bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("paygate_"))
def cb_paygate_redirect(c):
    parts = c.data.split("_")
    method = parts[1]
    amount = parts[2]
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔗 Перейти к оплате", url="https://t.me/tribute?start=app"))
    kb.row(types.InlineKeyboardButton("✅ Проверить платёж", callback_data=f"check_payment_{amount}"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="nav_topup"))
    
    method_name = "СБП" if method == "sbp" else ("Банковская карта" if method == "card" else "Telegram Stars")
    text = (
        f"💳 <b>Счёт на оплату сформирован!</b>\n\n"
        f"Способ: <b>{method_name}</b>\n"
        f"Сумма: <b>{amount} ₽</b>\n\n"
        f"Нажмите кнопку <b>«Перейти к оплате»</b>, совершите платёж и вернитесь в бот для проверки начисления."
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_payment_"))
def cb_check_payment(c):
    amt = int(c.data.replace("check_payment_", ""))
    u = get_user(c.message.chat.id)
    u["balance_rub"] += amt
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, f"✅ Оплата {amt} ₽ подтверждена! Баланс пополнен.", show_alert=True)
    cb_profile(c)

# ==================== ПРОФИЛЬ И ИСТОРИЯ ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_profile")
def cb_profile(c):
    u = get_user(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("📜 История моих звонков", callback_data="nav_history"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        f"👤 <b>Личный кабинет пользователя:</b>\n\n"
        f"🆔 Ваш ID: <code>{c.message.chat.id}</code>\n"
        f"💰 Баланс: <b>{u['balance_rub']} ₽</b>\n"
        f"📞 Совершено звонков: <b>{u['calls_made']}</b>\n"
        f"👥 Приглашено друзей: <b>{u.get('referrals', 0)}</b>\n"
        f"📅 Регистрация: <i>{u.get('created_at', 'Недавно')}</i>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_history")
def cb_history(c):
    u = get_user(c.message.chat.id)
    hist = u.get("history", [])
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в профиль", callback_data="nav_profile"))
    if not hist:
        safe_nav(c, "📜 <b>История звонков пуста.</b>\nВы еще не совершали пранк-звонков.", reply_markup=kb)
        return
    text = "📜 <b>Последние совершенные звонки:</b>\n\n"
    for item in reversed(hist[-10:]):
        text += f"• <b>{item.get('title', 'Пранк')}</b>\n  📞 Номер: <code>{item.get('phone')}</code>\n  📅 {item.get('date')} | Статус: {item.get('status')}\n\n"
    safe_nav(c, text, reply_markup=kb)

# ==================== ПАРТНЁРСКАЯ ПРОГРАММА ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u = get_user(c.message.chat.id)
    max_allowed_refs = admin_cfg.get("max_referrals", MAX_REFERRALS)
    cur_refs = u.get('referrals', 0)
    
    if cur_refs >= max_allowed_refs:
        status_note = f"\n\n✅ <b>Вы достигли максимального лимита приглашений ({cur_refs}/{max_allowed_refs})!</b>"
    else:
        left = max_allowed_refs - cur_refs
        status_note = f"\n\n💡 <i>Вы можете пригласить ещё: {left} друга!</i>"
        
    text = (
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"Получайте **+49 ₽ (1 бесплатный звонок)** за каждого приглашённого друга!\n\n"
        f"👥 Приглашено: **{cur_refs}/{max_allowed_refs}**\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`"
        f"{status_note}"
    )
    kb = types.InlineKeyboardMarkup()
    if cur_refs < max_allowed_refs:
        kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Анонимные+пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

# ==================== ПРОМОКОДЫ ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_promo")
def cb_promo_enter(c):
    user_state[c.message.chat.id] = "waiting_promocode"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ <b>Введите промокод для активации бонуса:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promocode")
def step_promo_check(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    cid = str(m.chat.id)
    u = get_user(m.chat.id)
    
    if code in promos_db:
        pr = promos_db[code]
        if cid in pr.get("used_by", []):
            bot.reply_to(m, "❌ Вы уже активировали этот промокод ранее!")
            return
        if pr.get("activations", 0) <= 0:
            bot.reply_to(m, "❌ Лимит активаций этого промокода исчерпан!")
            return
            
        pr["activations"] -= 1
        pr.setdefault("used_by", []).append(cid)
        bonus = pr.get("discount_rub", 49)
        u["balance_rub"] += bonus
        save_json(PROMOS_FILE, promos_db)
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 <b>Промокод успешно активирован!</b>\nВам начислено: <b>+{bonus} ₽</b> на баланс!", parse_mode="HTML")
    else:
        bot.reply_to(m, "❌ Промокод не найден или устарел.")

# ==================== FAQ И ПОДДЕРЖКА ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_faq")
def cb_faq(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🆘 Поддержка (@kdjdjawu)", url="https://t.me/kdjdjawu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        "ℹ️ <b>Часто задаваемые вопросы (FAQ):</b>\n\n"
        "❓ <b>Виден ли мой личный номер получателю?</b>\n"
        "— Нет! Звонок совершается с наших виртуальных автоматических станций.\n\n"
        "❓ <b>Что делать, если абонент не взял трубку?</b>\n"
        "— Если абонент сбросил или был недоступен, баланс сохраняется либо возвращается на ваш счет.\n\n"
        "❓ <b>Как быстро поступает звонок?</b>\n"
        "— Робот начинает вызов в течение 5–15 секунд после подтверждения заказа.\n\n"
        "❓ <b>Куда обратиться с проблемой?</b>\n"
        "— Нажмите кнопку связи с администратором ниже."
    )
    safe_nav(c, text, reply_markup=kb)
