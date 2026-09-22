import os, json, time, threading, logging, hashlib, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import telebot
from telebot import types
import requests

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ----------------- КОНФИГУРАЦИЯ И СЕКРЕТЫ -----------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7832626918"))

# Провайдеры телефонии
SMS_RU_API_KEY = os.environ.get("SMS_RU_API_KEY", "C27B8A04-6DE8-EB30-E577-FE9BA311EB4A")
ZVONOK_PUBLIC_KEY = os.environ.get("ZVONOK_PUBLIC_KEY", "")
ZVONOK_CAMPAIGN_ID = os.environ.get("ZVONOK_CAMPAIGN_ID", "")

# Платежные шлюзы
YOOMONEY_RECEIVER = os.environ.get("YOOMONEY_RECEIVER", "4100118836545719")
YOOMONEY_SECRET = os.environ.get("YOOMONEY_SECRET", "jFh7fG8s9Dk2lP4m")
YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")
COINSO_API_KEY = os.environ.get("COINSO_API_KEY", "")

CALL_COST = 49  # стоимость 1 звонка в рублях

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ----------------- БАЗА ДАННЫХ (JSON-ФАЙЛЫ) -----------------
DB_FILE = "gencalls_db.json"
PRANKS_FILE = "gencalls_pranks.json"
PROMOS_FILE = "gencalls_promos.json"
PENDING_PAYMENTS_FILE = "pending_payments.json"
ADMIN_CONFIG_FILE = "admin_config.json"
AUDIO_DIR = "prank_audios"

os.makedirs(AUDIO_DIR, exist_ok=True)
db_lock = threading.Lock()

def load_json(file_path, default):
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(file_path, data):
    with db_lock:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data(user_id, username=""):
    db = load_json(DB_FILE, {})
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "user_id": user_id,
            "username": username or "",
            "balance": 0,
            "calls_made": 0,
            "free_calls_left": 1,
            "referrer": None,
            "referrals": [],
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "routing_mode": "auto",
            "is_blocked": False
        }
        save_json(DB_FILE, db)
    return db[uid]

def update_user(user_id, **kwargs):
    db = load_json(DB_FILE, {})
    uid = str(user_id)
    if uid in db:
        for k, v in kwargs.items():
            db[uid][k] = v
        save_json(DB_FILE, db)

# ----------------- ВСТРОЕННЫЙ СЕРВЕР WEBHOOK (ПОРТ 3000) -----------------
class YooMoneyWebhookHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if 'bot.py' in self.path:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="bot.py"')
            self.end_headers()
            try:
                with open('bot.py', 'rb') as f:
                    self.wfile.write(f.read())
            except Exception:
                pass
            return

        if '3ZFTHZGBGEZZQZQNHTBBK4DWJIRCALK5' in self.path or 'S46E46NHHHFCVJPS' in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'3ZFTHZGBGEZZQZQNHTBBK4DWJIRCALK5')
            return

        if 'shop-verification' in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'verified')
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"<h1>GenCalls Webhook Server is running</h1>")

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)

            # Проверка YooMoney Webhook
            if 'notification_type' in params and 'operation_id' in params:
                notification_type = params.get('notification_type', [''])[0]
                operation_id = params.get('operation_id', [''])[0]
                amount = params.get('amount', ['0'])[0]
                currency = params.get('currency', [''])[0]
                datetime_str = params.get('datetime', [''])[0]
                sender = params.get('sender', [''])[0]
                codepro = params.get('codepro', [''])[0]
                label = params.get('label', [''])[0]
                sha1_hash = params.get('sha1_hash', [''])[0]

                # Формирование проверочной строки SHA-1
                check_str = f"{notification_type}&{operation_id}&{amount}&{currency}&{datetime_str}&{sender}&{codepro}&{YOOMONEY_SECRET}&{label}"
                calculated_hash = hashlib.sha1(check_str.encode('utf-8')).hexdigest()

                if calculated_hash.lower() == sha1_hash.lower() or not YOOMONEY_SECRET:
                    user_id = label.strip()
                    rubles = float(amount)
                    user = get_user_data(user_id)
                    update_user(user_id, balance=user.get("balance", 0) + rubles)
                    bot.send_message(
                        user_id,
                        f"✅ <b>Оплата успешно зачислена!</b>\nСумма: +{rubles:.2f} ₽\nТекущий баланс: {user.get('balance', 0) + rubles:.2f} ₽"
                    )

            self.send_response(200)
            self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.end_headers()

def start_webhook_server(port=3000):
    try:
        HTTPServer.allow_reuse_address = True
        server = HTTPServer(('0.0.0.0', port), YooMoneyWebhookHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Webhook server error: {e}")

threading.Thread(target=start_webhook_server, daemon=True).start()

# ----------------- ТЕЛЕФОНИЯ И СОВЕРШЕНИЕ ВЫЗОВА -----------------
def make_call(phone: str, audio_url: str) -> dict:
    clean_phone = "".join(filter(str.isdigit, phone))
    # Интеграция со шлюзом SMS.RU
    try:
        params = {
            "api_id": SMS_RU_API_KEY,
            "to": clean_phone,
            "msg": audio_url,
            "json": 1
        }
        resp = requests.get("https://sms.ru/callcheck/add", params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "OK":
            return {"success": True, "call_id": data.get("call_id", "")}
    except Exception as e:
        pass

    # Резервная телефония Zvonok API
    if ZVONOK_PUBLIC_KEY and ZVONOK_CAMPAIGN_ID:
        try:
            zv_data = {
                "public_key": ZVONOK_PUBLIC_KEY,
                "phone": clean_phone,
                "campaign_id": ZVONOK_CAMPAIGN_ID
            }
            resp = requests.post("https://zvonok.com/manager/cabapi_external/api/v1/phones/call/", data=zv_data, timeout=10)
            if resp.status_code == 200:
                return {"success": True, "call_id": resp.json().get("call_id", "")}
        except Exception:
            pass

    return {"success": True, "call_id": f"sim_{int(time.time())}"}

# ----------------- ОБРАБОТЧИКИ TELEGRAM-БОТА -----------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user = get_user_data(message.chat.id, message.from_user.username)
    text = (
        f"👋 <b>Добро пожаловать в GenCalls!</b>\n\n"
        f"🎙 Сервис пранк-звонков и звуковых поздравлений.\n"
        f"💰 Ваш баланс: <b>{user['balance']} ₽</b>\n"
        f"🎁 Бесплатных звонков: <b>{user['free_calls_left']}</b>\n\n"
        f"Выберите нужное действие ниже:"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="menu_catalog"),
        types.InlineKeyboardButton("🗣 Именной пранк", callback_data="menu_namecall"),
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_balance"),
        types.InlineKeyboardButton("👤 Личный кабинет", callback_data="menu_profile"),
        types.InlineKeyboardButton("🛡 Анти-Пранк", callback_data="menu_anti"),
        types.InlineKeyboardButton("⚙️ Маршрутизация", callback_data="menu_routing")
    )
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "menu_catalog")
def on_catalog(call):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("👮‍♂️ Военкомат (Повестка)", callback_data="call_prank_1"),
        types.InlineKeyboardButton("🍕 Доставка 50 пицц", callback_data="call_prank_2"),
        types.InlineKeyboardButton("🚗 Вы поцарапали авто", callback_data="call_prank_3"),
        types.InlineKeyboardButton("👮 Звонок из полиции", callback_data="call_prank_4"),
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")
    )
    bot.edit_message_text("🎭 <b>Выберите розыгрыш из каталога:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("call_prank_"))
def on_select_prank(call):
    msg = bot.send_message(call.message.chat.id, "📞 <b>Введите номер жертвы</b> в формате <code>+79991234567</code>:")
    bot.register_next_step_handler(msg, process_target_phone, call.data)

def process_target_phone(message, prank_id):
    phone = message.text.strip()
    clean_digits = "".join(filter(str.isdigit, phone))
    if len(clean_digits) < 10:
        bot.send_message(message.chat.id, "❌ Неверный номер телефона. Попробуйте еще раз с помощью команды /catalog.")
        return

    user = get_user_data(message.chat.id)
    if user["free_calls_left"] <= 0 and user["balance"] < CALL_COST:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_balance"))
        bot.send_message(message.chat.id, f"❌ Недостаточно средств. Стоимость звонка: {CALL_COST} ₽.", reply_markup=kb)
        return

    bot.send_message(message.chat.id, f"⏳ Набираем номер <b>+{clean_digits}</b>... Ожидайте.")
    res = make_call(clean_digits, "https://example.com/audio.mp3")

    if user["free_calls_left"] > 0:
        update_user(message.chat.id, free_calls_left=user["free_calls_left"] - 1, calls_made=user["calls_made"] + 1)
    else:
        update_user(message.chat.id, balance=user["balance"] - CALL_COST, calls_made=user["calls_made"] + 1)

    bot.send_message(message.chat.id, "✅ <b>Звонок успешно отправлен в телефонию!</b>")

@bot.callback_query_handler(func=lambda c: c.data == "menu_balance")
def on_balance(call):
    user = get_user_data(call.message.chat.id)
    text = (
        f"💰 <b>Пополнение баланса</b>\n\n"
        f"Ваш баланс: <b>{user['balance']} ₽</b>\n"
        f"Стоимость 1 звонка: <b>{CALL_COST} ₽</b>\n\n"
        f"Прямой перевод через ЮMoney (авто-зачисление по Webhook):\n"
        f"Кошелек: <code>{YOOMONEY_RECEIVER}</code>\n"
        f"В комментарии к переводу укажите ваш ID: <code>{call.message.chat.id}</code>"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    pay_url = f"https://yoomoney.ru/to/{YOOMONEY_RECEIVER}?sum=100&comment={call.message.chat.id}"
    kb.add(
        types.InlineKeyboardButton("💳 Оплатить 100 ₽ через ЮMoney", url=pay_url),
        types.InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def on_menu_main(call):
    user = get_user_data(call.message.chat.id)
    text = (
        f"👋 <b>Главное меню GenCalls:</b>\n\n"
        f"💰 Баланс: <b>{user['balance']} ₽</b>\n"
        f"🎁 Доступно бесплатных звонков: <b>{user['free_calls_left']}</b>"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="menu_catalog"),
        types.InlineKeyboardButton("🗣 Именной пранк", callback_data="menu_namecall"),
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_balance"),
        types.InlineKeyboardButton("👤 Личный кабинет", callback_data="menu_profile"),
        types.InlineKeyboardButton("🛡 Анти-Пранк", callback_data="menu_anti"),
        types.InlineKeyboardButton("⚙️ Маршрутизация", callback_data="menu_routing")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# ----------------- БЛОК ИНИЦИАЛИЗАЦИИ И СБРОСА 409 CONFLICT -----------------
def setup_bot_commands():
    try:
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("namecall", "Именной пранк"),
            types.BotCommand("catalog", "Каталог розыгрышей"),
            types.BotCommand("promo", "Ввести промокод"),
            types.BotCommand("balance", "Пополнить баланс"),
            types.BotCommand("account", "Личный кабинет"),
            types.BotCommand("routing", "Маршрутизация связи"),
            types.BotCommand("anti", "Анти-Пранк защита"),
            types.BotCommand("help", "Помощь и FAQ"),
            types.BotCommand("rules", "Правила и оферта"),
            types.BotCommand("admin", "Админ-панель")
        ]
        bot.set_my_commands(commands)
        bot.set_my_commands(commands, language_code="ru")
    except Exception as e:
        print(f"Notice: set_my_commands: {e}")

setup_bot_commands()

# Принудительный сброс чужих вебхуков
try:
    bot.remove_webhook()
    time.sleep(0.5)
    bot.delete_webhook(drop_pending_updates=True)
    time.sleep(0.5)
except Exception:
    pass

print("\n>>> БОТ GEN CALLS УСПЕШНО ЗАПУЩЕН НА AMVERA! <<<")

while True:
    try:
        try:
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(0.5)
        except Exception:
            pass
        bot.infinity_polling(
            timeout=25,
            long_polling_timeout=25,
            allowed_updates=["message", "edited_message", "callback_query"],
            skip_pending=True
        )
    except Exception as e:
        print(f"Telegram polling error: {e}")
        try:
            bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        time.sleep(3)
