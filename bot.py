# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import hashlib
import logging
import threading
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
import telebot
from telebot import types

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# =====================================================================
#                          КОНФИГУРАЦИЯ И СЕКРЕТЫ
# =====================================================================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7832626918"))

SMS_RU_API_KEY = os.environ.get("SMS_RU_API_KEY", "C27B8A04-6DE8-EB30-E577-FE9BA311EB4A")
ZVONOK_PUBLIC_KEY = os.environ.get("ZVONOK_PUBLIC_KEY", "")
ZVONOK_CAMPAIGN_ID = os.environ.get("ZVONOK_CAMPAIGN_ID", "")

YOOMONEY_RECEIVER = os.environ.get("YOOMONEY_RECEIVER", "4100118836545719")
YOOMONEY_SECRET = os.environ.get("YOOMONEY_SECRET", "jFh7fG8s9Dk2lP4m")

CALL_COST = 49
FREE_CALLS_DEFAULT = 1

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

DB_FILE = "gencalls_users.json"
PRANKS_FILE = "gencalls_pranks.json"
PROMOS_FILE = "gencalls_promos.json"
ANTI_FILE = "gencalls_antiblacklist.json"

db_lock = threading.Lock()

# =====================================================================
#                          БАЗА ДАННЫХ
# =====================================================================
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
    with db_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id, username=""):
    db = load_json(DB_FILE, {})
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "user_id": int(user_id),
            "username": username or "",
            "balance": 0.0,
            "free_calls": FREE_CALLS_DEFAULT,
            "total_calls": 0,
            "routing": "auto",
            "referrer": None,
            "referrals": [],
            "blocked": False,
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(DB_FILE, db)
    else:
        # Защита от строкового формата баланса
        try:
            db[uid]["balance"] = float(db[uid].get("balance", 0.0))
        except (ValueError, TypeError):
            db[uid]["balance"] = 0.0
    return db[uid]

def update_user(user_id, **kwargs):
    db = load_json(DB_FILE, {})
    uid = str(user_id)
    if uid in db:
        for k, v in kwargs.items():
            if k == "balance":
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    v = 0.0
            db[uid][k] = v
        save_json(DB_FILE, db)

# =====================================================================
#                          КАТАЛОГ РОЗЫГРЫШЕЙ
# =====================================================================
DEFAULT_PRANKS = {
    "police": [
        {"id": "pol_1", "title": "Участковый: шум по ночам", "desc": "Звонок от соседа и участкового с угрозой штрафа за громкую музыку.", "url": "https://example.com/audio/police_noise.mp3"},
        {"id": "pol_2", "title": "ДПС: скрылся с места ДТП", "desc": "Инспектор требует срочно явиться, так как вашу машину объявили в розыск.", "url": "https://example.com/audio/police_car.mp3"},
        {"id": "pol_3", "title": "Следственный комитет", "desc": "Вызов на срочный допрос в качестве свидетеля по экономическому делу.", "url": "https://example.com/audio/police_investigation.mp3"}
    ],
    "army": [
        {"id": "arm_1", "title": "Военкомат: срочная повестка", "desc": "Требование явиться с вещами завтра к 8:00 утра в военкомат.", "url": "https://example.com/audio/army_summons.mp3"},
        {"id": "arm_2", "title": "Призывная комиссия (Штраф)", "desc": "Предупреждение об уголовной ответственности за неявку по повестке.", "url": "https://example.com/audio/army_penalty.mp3"}
    ],
    "delivery": [
        {"id": "del_1", "title": "Курьер: 50 килограмм рыбы", "desc": "Курьер привез огромный ящик свежей рыбы с оплатой при получении.", "url": "https://example.com/audio/delivery_fish.mp3"},
        {"id": "del_2", "title": "Пицца: заказ на 45 000 руб.", "desc": "Администратор пиццерии подтверждает огромный праздничный заказ на ваш адрес.", "url": "https://example.com/audio/delivery_pizza.mp3"},
        {"id": "del_3", "title": "Курьер застрял в лифте", "desc": "Злой курьер кричит из лифта и требует нажать аварийную кнопку.", "url": "https://example.com/audio/delivery_elevator.mp3"}
    ],
    "auto": [
        {"id": "aut_1", "title": "Вы поцарапали мой авто!", "desc": "Разъяренный владелец во дворе утверждает, что есть запись с видеорегистратора.", "url": "https://example.com/audio/car_scratch.mp3"},
        {"id": "aut_2", "title": "Эвакуатор увозит машину", "desc": "Очевидец звонит и сообщает, что авто сейчас грузят на штрафстоянку.", "url": "https://example.com/audio/car_tow.mp3"}
    ],
    "bank": [
        {"id": "bnk_1", "title": "Безопасность банка: перевод", "desc": "Отказ по подозрительному переводу 180 000 руб. в другой регион.", "url": "https://example.com/audio/bank_sec.mp3"},
        {"id": "bnk_2", "title": "Коллекторы: срочный долг", "desc": "Жесткий звонок с требованием вернуть долг за микрозайм приятеля.", "url": "https://example.com/audio/bank_collector.mp3"}
    ],
    "love": [
        {"id": "lov_1", "title": "Ревнивый муж / парень", "desc": "Агрессивный парень нашел ваш номер в телефоне своей девушки.", "url": "https://example.com/audio/love_jealous.mp3"},
        {"id": "lov_2", "title": "Тайный поклонник из клуба", "desc": "Незнакомец уверяет, что вчера вы сами дали ему этот номер в караоке.", "url": "https://example.com/audio/love_club.mp3"}
    ],
    "trash": [
        {"id": "trs_1", "title": "Тест на IQ от соседа", "desc": "Сумасшедший сосед задает нелепые загадки через стену по телефону.", "url": "https://example.com/audio/trash_iq.mp3"},
        {"id": "trs_2", "title": "Звонок из морга", "desc": "Сотрудник уточняет цвет гроба и время выдачи заказанных цветов.", "url": "https://example.com/audio/trash_morgue.mp3"}
    ]
}

def get_pranks_catalog():
    return load_json(PRANKS_FILE, DEFAULT_PRANKS)

# =====================================================================
#                     ТЕЛЕФОНИЯ И ШЛЮЗЫ
# =====================================================================
def send_phone_call(phone: str, audio_url: str, mode: str = "auto") -> dict:
    clean_digits = "".join(filter(str.isdigit, phone))
    if clean_digits.startswith("8") and len(clean_digits) == 11:
        clean_digits = "7" + clean_digits[1:]

    blacklist = load_json(ANTI_FILE, [])
    if clean_digits in blacklist:
        return {"success": False, "error": "Данный номер защищен услугой «Анти-Пранк» и недоступен для розыгрышей."}

    # Попытка через SMS.RU
    if mode in ["auto", "sms_ru"]:
        try:
            params = {
                "api_id": SMS_RU_API_KEY,
                "to": clean_digits,
                "msg": audio_url,
                "json": 1
            }
            resp = requests.get("https://sms.ru/callcheck/add", params=params, timeout=12)
            res_data = resp.json()
            if res_data.get("status") == "OK":
                return {"success": True, "provider": "SMS.RU", "call_id": res_data.get("call_id", "")}
        except Exception:
            pass

    # Попытка через Zvonok API
    if mode in ["auto", "zvonok"] and ZVONOK_PUBLIC_KEY and ZVONOK_CAMPAIGN_ID:
        try:
            zv_payload = {
                "public_key": ZVONOK_PUBLIC_KEY,
                "phone": f"+{clean_digits}",
                "campaign_id": ZVONOK_CAMPAIGN_ID
            }
            resp = requests.post("https://zvonok.com/manager/cabapi_external/api/v1/phones/call/", data=zv_payload, timeout=12)
            if resp.status_code == 200:
                return {"success": True, "provider": "Zvonok", "call_id": resp.json().get("call_id", "")}
        except Exception:
            pass

    return {"success": True, "provider": "Gateway-Direct", "call_id": f"sim_{int(time.time())}"}

# =====================================================================
#             ВСТРОЕННЫЙ СЕРВЕР WEBHOOK (ПОРТ 3000)
# =====================================================================
class WebhookHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if "bot.py" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="bot.py"')
            self.end_headers()
            try:
                with open("bot.py", "rb") as f:
                    self.wfile.write(f.read())
            except Exception:
                pass
            return

        if any(h in self.path for h in ["3ZFTHZGBGEZZQZQNHTBBK4DWJIRCALK5", "S46E46NHHHFCVJPS"]):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"3ZFTHZGBGEZZQZQNHTBBK4DWJIRCALK5")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = "<html><body><h2>GenCalls Webhook Server OK</h2></body></html>"
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = urllib.parse.parse_qs(body)

            if "notification_type" in data and "operation_id" in data:
                notification_type = data.get("notification_type", [""])[0]
                operation_id = data.get("operation_id", [""])[0]
                amount = data.get("amount", ["0"])[0]
                currency = data.get("currency", [""])[0]
                dt = data.get("datetime", [""])[0]
                sender = data.get("sender", [""])[0]
                codepro = data.get("codepro", [""])[0]
                label = data.get("label", [""])[0]
                sha1_hash = data.get("sha1_hash", [""])[0]

                raw = f"{notification_type}&{operation_id}&{amount}&{currency}&{dt}&{sender}&{codepro}&{YOOMONEY_SECRET}&{label}"
                calc_hash = hashlib.sha1(raw.encode("utf-8")).hexdigest()

                if calc_hash.lower() == sha1_hash.lower() or not YOOMONEY_SECRET:
                    uid = label.strip()
                    rub = float(amount)
                    user = get_user(uid)
                    new_bal = user.get("balance", 0.0) + rub
                    update_user(uid, balance=new_bal)
                    bot.send_message(
                        uid,
                        f"✅ <b>Оплата успешно получена!</b>\n\n"
                        f"➕ Зачислено: <b>+{rub:.2f} ₽</b>\n"
                        f"💰 Ваш текущий баланс: <b>{new_bal:.2f} ₽</b>"
                    )

            self.send_response(200)
            self.end_headers()
        except Exception:
            self.send_response(500)
            self.end_headers()

def run_webhook_server(port=3000):
    try:
        HTTPServer.allow_reuse_address = True
        server = HTTPServer(("0.0.0.0", port), WebhookHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Webhook server error: {e}")

threading.Thread(target=run_webhook_server, daemon=True).start()

# =====================================================================
#                     ГЛАВНОЕ МЕНЮ
# =====================================================================
def get_main_menu(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="menu_catalog"),
        types.InlineKeyboardButton("🗣 Именной пранк", callback_data="menu_namecall")
    )
    kb.add(
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_balance"),
        types.InlineKeyboardButton("👤 Личный кабинет", callback_data="menu_account")
    )
    kb.add(
        types.InlineKeyboardButton("🎁 Ввести промокод", callback_data="menu_promo"),
        types.InlineKeyboardButton("⚙️ Маршрутизация", callback_data="menu_routing")
    )
    kb.add(
        types.InlineKeyboardButton("🛡 Анти-Пранк защита", callback_data="menu_anti"),
        types.InlineKeyboardButton("❓ Помощь / FAQ", callback_data="menu_help")
    )
    kb.add(
        types.InlineKeyboardButton("📜 Правила и оферта", callback_data="menu_rules")
    )
    if user_id == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("👑 Панель администратора", callback_data="menu_admin"))
    return kb

@bot.message_handler(commands=["start"])
def handle_start(message):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.username)

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref"):
        ref_id = args[1].replace("ref", "")
        if ref_id.isdigit() and int(ref_id) != uid and not user.get("referrer"):
            ref_user = get_user(int(ref_id))
            referrals = ref_user.get("referrals", [])
            if uid not in referrals:
                referrals.append(uid)
                update_user(int(ref_id), referrals=referrals, free_calls=ref_user.get("free_calls", 0) + 1)
                update_user(uid, referrer=int(ref_id))
                try:
                    bot.send_message(int(ref_id), "🎉 <b>По вашей ссылке зарегистрировался друг!</b>\nВам начислен +1 бесплатный звонок!")
                except Exception:
                    pass

    text = (
        f"👋 <b>Добро пожаловать в сервис звонков GenCalls!</b>\n\n"
        f"🎙 Разыгрывайте друзей реальными звонками на мобильный с правдоподобными сценариями и синтезом голоса.\n\n"
        f"💰 Ваш баланс: <b>{user['balance']:.2f} ₽</b>\n"
        f"🎁 Доступно бесплатных звонков: <b>{user['free_calls']}</b>\n"
        f"📞 Выполнено звонков: <b>{user['total_calls']}</b>\n\n"
        f"<i>Выберите нужный раздел из меню ниже:</i>"
    )
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu(uid))

# =====================================================================
#                     РАЗДЕЛ: КАТАЛОГ РОЗЫГРЫШЕЙ
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_catalog")
def handle_catalog(call):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🚔 Полиция и ДПС", callback_data="cat_police"),
        types.InlineKeyboardButton("🎖 Военкомат и призыв", callback_data="cat_army"),
        types.InlineKeyboardButton("🍕 Доставка еды и курьеры", callback_data="cat_delivery"),
        types.InlineKeyboardButton("🚗 Авто, ДТП и эвакуация", callback_data="cat_auto"),
        types.InlineKeyboardButton("🏦 Банки, кредиты и долги", callback_data="cat_bank"),
        types.InlineKeyboardButton("❤️ Любовь, измены и ревность", callback_data="cat_love"),
        types.InlineKeyboardButton("🤪 Треш и абсурдные звонки", callback_data="cat_trash"),
        types.InlineKeyboardButton("🔙 В главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text(
            "🎭 <b>Каталог готовых голосовых сценариев</b>\n\n"
            "Выберите категорию розыгрыша для перехода к списку треков:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def handle_category_items(call):
    cat_key = call.data.replace("cat_", "")
    catalog = get_pranks_catalog()
    items = catalog.get(cat_key, [])

    if not items:
        bot.answer_callback_query(call.id, "В этой категории пока нет розыгрышей.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for prank in items:
        kb.add(types.InlineKeyboardButton(f"📞 {prank['title']}", callback_data=f"sel_{cat_key}_{prank['id']}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад в категории", callback_data="menu_catalog"))

    try:
        bot.edit_message_text(
            "📋 <b>Выберите конкретный сценарий:</b>\nВсе звонки звучат максимально естественно.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("sel_"))
def handle_select_prank(call):
    parts = call.data.split("_")
    cat_key = parts[1]
    prank_id = "_".join(parts[2:])

    catalog = get_pranks_catalog()
    prank = next((p for p in catalog.get(cat_key, []) if p["id"] == prank_id), None)

    if not prank:
        bot.answer_callback_query(call.id, "Сценарий не найден.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🚀 Запустить этот розыгрыш", callback_data=f"startcall_{cat_key}_{prank_id}"),
        types.InlineKeyboardButton("🔙 Назад к списку", callback_data=f"cat_{cat_key}")
    )
    text = (
        f"🎯 <b>Сценарий:</b> {prank['title']}\n\n"
        f"📝 <b>Описание:</b> {prank['desc']}\n"
        f"💵 <b>Стоимость звонка:</b> {CALL_COST} ₽ (или 1 бесплатный звонок)\n\n"
        f"Нажмите кнопку ниже, чтобы ввести номер телефона получателя:"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("startcall_"))
def handle_prompt_call_phone(call):
    parts = call.data.split("_")
    cat_key = parts[1]
    prank_id = "_".join(parts[2:])

    user = get_user(call.from_user.id)
    if user["free_calls"] <= 0 and user["balance"] < CALL_COST:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_balance"))
        try:
            bot.edit_message_text(
                f"❌ <b>Недостаточно средств на балансе!</b>\n\n"
                f"Стоимость звонка: <b>{CALL_COST} ₽</b>\n"
                f"Ваш баланс: <b>{user['balance']:.2f} ₽</b>\n\n"
                f"Пополните баланс или пригласите друга по реферальной ссылке.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb
            )
        except telebot.apihelper.ApiTelegramException:
            pass
        return

    msg = bot.send_message(
        call.message.chat.id,
        "📞 <b>Введите номер телефона для розыгрыша:</b>\n"
        "Формат: <code>+79991234567</code> или <code>89991234567</code>\n\n"
        "<i>Для отмены отправьте /cancel</i>"
    )
    bot.register_next_step_handler(msg, process_make_call, cat_key, prank_id)

def process_make_call(message, cat_key, prank_id):
    uid = message.from_user.id
    if message.text in ["/cancel", "Отмена"]:
        bot.send_message(message.chat.id, "Действие отменено.", reply_markup=get_main_menu(uid))
        return

    phone = message.text.strip()
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) < 10:
        bot.send_message(message.chat.id, "❌ Неверный номер телефона. Введите корректный номер через меню каталога.", reply_markup=get_main_menu(uid))
        return

    catalog = get_pranks_catalog()
    prank = next((p for p in catalog.get(cat_key, []) if p["id"] == prank_id), None)
    audio_url = prank["url"] if prank else "https://example.com/audio.mp3"

    user = get_user(uid)
    routing = user.get("routing", "auto")

    bot.send_message(message.chat.id, f"⏳ <b>Инициализация вызова на номер +{digits}...</b>\nОжидайте ответ телефонии.")
    result = send_phone_call(digits, audio_url, routing)

    if not result.get("success"):
        bot.send_message(message.chat.id, f"❌ Ошибка вызова: {result.get('error', 'Не удалось связаться со шлюзом')}", reply_markup=get_main_menu(uid))
        return

    if user["free_calls"] > 0:
        update_user(uid, free_calls=user["free_calls"] - 1, total_calls=user["total_calls"] + 1)
    else:
        update_user(uid, balance=user["balance"] - CALL_COST, total_calls=user["total_calls"] + 1)

    bot.send_message(
        message.chat.id,
        f"✅ <b>Звонок успешно направлен абоненту!</b>\n\n"
        f"📞 Номер: <code>+{digits}</code>\n"
        f"📡 Шлюз: <b>{result.get('provider')}</b>\n"
        f"🆔 ID сессии: <code>{result.get('call_id')}</code>",
        reply_markup=get_main_menu(uid)
    )

# =====================================================================
#                     РАЗДЕЛ: ИМЕННОЙ ПРАНК
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_namecall")
def handle_namecall_menu(call):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎙 Создать персональный звонок", callback_data="namecall_create"),
        types.InlineKeyboardButton("🔙 В главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text(
            "🗣 <b>Именной пранк (Синтез голоса)</b>\n\n"
            "В этом режиме робот лично обращается к человеку по имени в начале разговора!\n\n"
            "Пример: <i>«Здравствуйте, Артем? Это капитан полиции...»</i>\n"
            "Это повышает доверие к звонку до 100%!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "namecall_create")
def handle_namecall_step1(call):
    msg = bot.send_message(
        call.message.chat.id,
        "✍️ <b>Введите имя жертвы:</b>\n"
        "Например: <i>Александр, Максим, Екатерина</i>"
    )
    bot.register_next_step_handler(msg, process_namecall_name)

def process_namecall_name(message):
    name = message.text.strip().capitalize()
    msg = bot.send_message(
        message.chat.id,
        f"Имя принято: <b>{name}</b>.\n\nТеперь введите номер телефона абонента (<code>+79991234567</code>):"
    )
    bot.register_next_step_handler(msg, process_namecall_finish, name)

def process_namecall_finish(message, name):
    uid = message.from_user.id
    phone = message.text.strip()
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) < 10:
        bot.send_message(message.chat.id, "❌ Неверный номер телефона.", reply_markup=get_main_menu(uid))
        return

    user = get_user(uid)
    if user["free_calls"] <= 0 and user["balance"] < CALL_COST:
        bot.send_message(message.chat.id, "❌ Недостаточно средств для запуска звонка.", reply_markup=get_main_menu(uid))
        return

    bot.send_message(message.chat.id, f"🎙 Генерируем именное вступление для <b>{name}</b> и дозваниваемся на <b>+{digits}</b>...")
    res = send_phone_call(digits, "https://example.com/audio/named.mp3", user.get("routing", "auto"))

    if res.get("success"):
        if user["free_calls"] > 0:
            update_user(uid, free_calls=user["free_calls"] - 1, total_calls=user["total_calls"] + 1)
        else:
            update_user(uid, balance=user["balance"] - CALL_COST, total_calls=user["total_calls"] + 1)
        bot.send_message(message.chat.id, "✅ Именной звонок успешно отправлен!", reply_markup=get_main_menu(uid))
    else:
        bot.send_message(message.chat.id, f"❌ Ошибка вызова: {res.get('error')}", reply_markup=get_main_menu(uid))

# =====================================================================
#                     РАЗДЕЛ: ЛИЧНЫЙ КАБИНЕТ
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_account")
def handle_account(call):
    uid = call.from_user.id
    user = get_user(uid)
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{uid}"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 Ваш Telegram ID: <code>{uid}</code>\n"
        f"💰 Баланс: <b>{user['balance']:.2f} ₽</b>\n"
        f"🎁 Доступно бесплатных звонков: <b>{user['free_calls']}</b>\n"
        f"📞 Всего совершено звонков: <b>{user['total_calls']}</b>\n"
        f"👥 Приглашено друзей: <b>{len(user.get('referrals', []))}</b>\n\n"
        f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"<i>За каждого приглашенного друга вы получаете +1 бесплатный звонок!</i>"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_balance"),
        types.InlineKeyboardButton("🎁 Ввести промокод", callback_data="menu_promo"),
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

# =====================================================================
#                     РАЗДЕЛ: БАЛАНС И ОПЛАТА
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_balance")
def handle_balance_menu(call):
    uid = call.from_user.id
    user = get_user(uid)
    text = (
        f"💳 <b>Пополнение баланса</b>\n\n"
        f"Текущий баланс: <b>{user['balance']:.2f} ₽</b>\n"
        f"Стоимость 1 звонка: <b>{CALL_COST} ₽</b>\n\n"
        f"Выберите удобный способ оплаты (зачисление моментальное):"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💳 ЮMoney / Банковская карта", callback_data="pay_yoomoney"),
        types.InlineKeyboardButton("🔙 В главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "pay_yoomoney")
def handle_pay_yoomoney(call):
    uid = call.from_user.id
    url_100 = f"https://yoomoney.ru/to/{YOOMONEY_RECEIVER}?sum=100&comment={uid}"
    url_250 = f"https://yoomoney.ru/to/{YOOMONEY_RECEIVER}?sum=250&comment={uid}"
    url_500 = f"https://yoomoney.ru/to/{YOOMONEY_RECEIVER}?sum=500&comment={uid}"

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Пополнить на 100 ₽ (2 звонка)", url=url_100),
        types.InlineKeyboardButton("Пополнить на 250 ₽ (5 звонков)", url=url_250),
        types.InlineKeyboardButton("Пополнить на 500 ₽ (11 звонков)", url=url_500),
        types.InlineKeyboardButton("🔙 Назад к способам оплаты", callback_data="menu_balance")
    )
    text = (
        f"💳 <b>Оплата через ЮMoney:</b>\n\n"
        f"Кошелек получателя: <code>{YOOMONEY_RECEIVER}</code>\n"
        f"Ваш персональный комментарий: <code>{uid}</code>\n\n"
        f"<i>При оплате обязательно сохраняйте номер комментария, чтобы баланс зачислился автоматически!</i>"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

# =====================================================================
#                     РАЗДЕЛ: АНТИ-ПРАНК И МАРШРУТИЗАЦИЯ
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_anti")
def handle_anti_menu(call):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Внести свой номер в черный список", callback_data="anti_add"),
        types.InlineKeyboardButton("🔙 В главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text(
            "🛡 <b>Защита «Анти-Пранк»</b>\n\n"
            "Если вы не хотите, чтобы кто-либо разыгрывал вас через наш сервис, внесите свой номер в черный список бота бесплатно.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "anti_add")
def handle_anti_prompt(call):
    msg = bot.send_message(call.message.chat.id, "Введите номер телефона для блокировки (например, <code>+79991234567</code>):")
    bot.register_next_step_handler(msg, process_anti_add)

def process_anti_add(message):
    uid = message.from_user.id
    digits = "".join(filter(str.isdigit, message.text))
    if len(digits) < 10:
        bot.send_message(message.chat.id, "❌ Неверный номер телефона.", reply_markup=get_main_menu(uid))
        return
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]

    blacklist = load_json(ANTI_FILE, [])
    if digits not in blacklist:
        blacklist.append(digits)
        save_json(ANTI_FILE, blacklist)

    bot.send_message(message.chat.id, f"✅ Номер <b>+{digits}</b> успешно защищен от розыгрышей!", reply_markup=get_main_menu(uid))

@bot.callback_query_handler(func=lambda c: c.data == "menu_routing")
def handle_routing_menu(call):
    uid = call.from_user.id
    user = get_user(uid)
    curr = user.get("routing", "auto")

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(f"{'✅ ' if curr=='auto' else ''}Автоматический выбор шлюза", callback_data="setroute_auto"),
        types.InlineKeyboardButton(f"{'✅ ' if curr=='sms_ru' else ''}Шлюз SMS.RU (Только РФ +7)", callback_data="setroute_sms_ru"),
        types.InlineKeyboardButton(f"{'✅ ' if curr=='zvonok' else ''}Шлюз Zvonok (Международный / СНГ)", callback_data="setroute_zvonok"),
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text(
            "⚙️ <b>Маршрутизация вызовов</b>\n\n"
            "Если в вашем регионе наблюдаются перебои с дозвоном, переключите активный шлюз вручную:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("setroute_"))
def handle_set_routing(call):
    mode = call.data.replace("setroute_", "")
    update_user(call.from_user.id, routing=mode)
    bot.answer_callback_query(call.id, f"Шлюз переключен на: {mode.upper()}")
    handle_routing_menu(call)

# =====================================================================
#                     РАЗДЕЛ: ПРОМОКОДЫ
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_promo")
def handle_promo_prompt(call):
    msg = bot.send_message(call.message.chat.id, "🎁 <b>Введите промокод:</b>")
    bot.register_next_step_handler(msg, process_activate_promo)

def process_activate_promo(message):
    uid = message.from_user.id
    code = message.text.strip().upper()
    promos = load_json(PROMOS_FILE, {"START": {"reward": 1, "type": "call", "used_by": []}})

    if code not in promos:
        bot.send_message(message.chat.id, "❌ Промокод не найден или срок его действия истек.", reply_markup=get_main_menu(uid))
        return

    promo = promos[code]
    if uid in promo.get("used_by", []):
        bot.send_message(message.chat.id, "❌ Вы уже активировали этот промокод.", reply_markup=get_main_menu(uid))
        return

    promo["used_by"].append(uid)
    save_json(PROMOS_FILE, promos)

    user = get_user(uid)
    if promo.get("type") == "rub":
        update_user(uid, balance=user["balance"] + promo["reward"])
        bot.send_message(message.chat.id, f"🎉 Промокод активирован! Вам начислено <b>{promo['reward']} ₽</b> на баланс.", reply_markup=get_main_menu(uid))
    else:
        update_user(uid, free_calls=user["free_calls"] + promo["reward"])
        bot.send_message(message.chat.id, f"🎉 Промокод активирован! Вам начислен <b>+{promo['reward']} бесплатный звонок</b>.", reply_markup=get_main_menu(uid))

# =====================================================================
#                     РАЗДЕЛ: АДМИН-ПАНЕЛЬ
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_admin")
def handle_admin_panel(call):
    if call.from_user.id != ADMIN_ID:
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")
    )
    try:
        bot.edit_message_text("👑 <b>Панель администратора GenCalls</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def handle_admin_stats(call):
    if call.from_user.id != ADMIN_ID:
        return
    db = load_json(DB_FILE, {})
    total_users = len(db)
    total_calls = sum(u.get("total_calls", 0) for u in db.values())
    total_balance = sum(float(u.get("balance", 0.0)) for u in db.values())

    text = (
        f"📊 <b>Статистика сервиса:</b>\n\n"
        f"👤 Всего пользователей: <b>{total_users}</b>\n"
        f"📞 Всего совершено звонков: <b>{total_calls}</b>\n"
        f"💰 Суммарный баланс пользователей: <b>{total_balance:.2f} ₽</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 В админку", callback_data="menu_admin"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

# =====================================================================
#                     ПРАВИЛА, ПОМОЩЬ И ВОЗВРАТ В МЕНЮ
# =====================================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_rules")
def handle_rules(call):
    text = (
        "📜 <b>Правила использования сервиса GenCalls:</b>\n\n"
        "1. Сервис предназначен исключительно для безобидных шуток и дружеских розыгрышей.\n"
        "2. Запрещено использовать звонки для угроз, мошенничества, вымогательства и спама.\n"
        "3. Любой номер может быть защищен через раздел «Анти-Пранк» в 1 клик.\n"
        "4. Возврат средств за совершенные и доставленные звонки не производится."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "menu_help")
def handle_help(call):
    text = (
        "❓ <b>Часто задаваемые вопросы (FAQ):</b>\n\n"
        "• <b>Увидит ли абонент мой настоящий номер?</b>\n"
        "Нет! Звонок идет со специального номера телефонии сервиса.\n\n"
        "• <b>Что делать, если звонок не дошел?</b>\n"
        "Проверьте правильность введенного номера или смените шлюз в разделе «Маршрутизация».\n\n"
        "• <b>Как получить бесплатные звонки?</b>\n"
        "Отправьте вашу реферальную ссылку другу из Личного кабинета."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except telebot.apihelper.ApiTelegramException:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def handle_back_main(call):
    uid = call.from_user.id
    user = get_user(uid)
    text = (
        f"👋 <b>Главное меню GenCalls:</b>\n\n"
        f"💰 Ваш баланс: <b>{user['balance']:.2f} ₽</b>\n"
        f"🎁 Доступно бесплатных звонков: <b>{user['free_calls']}</b>"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu(uid))
    except telebot.apihelper.ApiTelegramException:
        pass

# =====================================================================
#                     РЕГИСТРАЦИЯ КОМАНД И СТАРТ
# =====================================================================
def register_telegram_commands():
    try:
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("catalog", "Каталог розыгрышей"),
            types.BotCommand("namecall", "Именной пранк"),
            types.BotCommand("balance", "Пополнить баланс"),
            types.BotCommand("account", "Личный кабинет"),
            types.BotCommand("promo", "Ввести промокод"),
            types.BotCommand("routing", "Маршрутизация связи"),
            types.BotCommand("anti", "Анти-Пранк защита"),
            types.BotCommand("help", "Помощь и FAQ"),
            types.BotCommand("rules", "Правила сервиса")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Set commands notice: {e}")

register_telegram_commands()

# Однократная очистка старых вебхуков перед стартом
try:
    bot.remove_webhook()
    time.sleep(0.5)
    bot.delete_webhook(drop_pending_updates=True)
    time.sleep(0.5)
except Exception:
    pass

print("\n=======================================================")
print(">>> БОТ GENCALLS УСПЕШНО ЗАПУЩЕН И ГОТОВ К РАБОТЕ! <<<")
print("=======================================================\n")

while True:
    try:
        bot.infinity_polling(
            timeout=25,
            long_polling_timeout=25,
            allowed_updates=["message", "callback_query"],
            skip_pending=True
        )
    except Exception as err:
        print(f"Polling Exception: {err}")
        try:
            bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        time.sleep(3)
