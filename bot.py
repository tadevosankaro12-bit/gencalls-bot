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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
PROMO_FILE = os.path.join(BASE_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(BASE_DIR, "gencalls_blacklist.json")
CUSTOM_PRANKS_FILE = os.path.join(BASE_DIR, "gencalls_pranks.json")
PENDING_PAYMENTS_FILE = os.path.join(BASE_DIR, "pending_payments.json")

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

TOKEN = os.getenv("TELEGRAM_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
ZVONOK_API_KEY = os.getenv("ZVONOK_API_KEY", "d0808ab7450fca32147a9285018fe7a5")
CAMPAIGN_ID = os.getenv("CAMPAIGN_ID", "1783540036")
SMSRU_API_KEY = os.getenv("SMSRU_API_KEY", "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF")

YOOMONEY_WALLET = os.getenv("YOOMONEY_WALLET", "4100119616287380")
YOOMONEY_SECRET = os.getenv("YOOMONEY_SECRET", "D2LS1zPM2UPAZ9wLeEVdbx7i")
LAVA_API_KEY = os.getenv("LAVA_API_KEY", "HyjXt7zeMvX1Z6JKtbyMoINHhIsyeMh5NGXI9c3Il4wdS35EFeHVqPtnrc9s3pBP")
LAVA_DEFAULT_PRODUCT = os.getenv("LAVA_DEFAULT_PRODUCT", "https://app.lava.top/products/a86f2412-debe-42a3-83fc-ab3abdc5a967")

CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "633014:AAdLxwOMJi6TOq3NVYRy5yyjJKVlNNTtMVO")

def create_crypto_invoice(user_id, amount_rub, title=""):
    try:
        url = "https://pay.crypt.bot/api/createInvoice"
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        data = {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": str(amount_rub),
            "description": f"Пополнение GenCalls: {title} ({amount_rub} руб)",
            "payload": f"{user_id}:{amount_rub}"
        }
        res = requests.post(url, headers=headers, json=data, timeout=8).json()
        if res.get("ok"):
            inv = res["result"]
            inv_id = str(inv["invoice_id"])
            pay_url = inv.get("bot_invoice_url") or inv.get("mini_app_invoice_url") or inv.get("pay_url")
            
            pending_payments[inv_id] = {
                "user_id": str(user_id),
                "amount": int(amount_rub),
                "time": time.time(),
                "paid": False,
                "service": "cryptobot"
            }
            save_json(PENDING_PAYMENTS_FILE, pending_payments)
            return inv_id, pay_url
    except Exception as e:
        print("CryptoPay create error:", e)
    return None, None

def check_crypto_invoice(invoice_id):
    try:
        url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        res = requests.get(url, headers=headers, timeout=8).json()
        if res.get("ok"):
            items = res.get("result", {}).get("items", [])
            if items:
                status = items[0].get("status")
                return status == "paid"
    except Exception as e:
        print("CryptoPay check error:", e)
    return False

pending_payments = load_json(PENDING_PAYMENTS_FILE, {})
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "tadevosankaro12")

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

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
    "pkg_1": {"icon": "📱", "title": "1 звонок", "calls": 1, "rub": 49, "price": "49 ₽", "badge": "Старт"},
    "pkg_5": {"icon": "⚡", "title": "5 звонков", "calls": 5, "rub": 149, "price": "149 ₽", "badge": "🔥 Выгода -40%"},
    "pkg_15": {"icon": "💥", "title": "15 звонков", "calls": 15, "rub": 299, "price": "299 ₽", "badge": "👑 Хит"},
    "pkg_50": {"icon": "🏆", "title": "50 звонков", "calls": 50, "rub": 699, "price": "699 ₽", "badge": "VIP"}
}

FAQ_ITEMS = {
    "faq_anon": {"q": "🕵️ Узнает ли жертва, кто звонил?", "a": "🛑 **Узнать невозможно.**\n\nКаждый звонок совершается с нового виртуального номера через защищённый международный шлюз. Ваш личный номер полностью скрыт."},
    "faq_refund": {"q": "🔄 Что если не взяли трубку / сбросили?", "a": "💰 **Баланс сохраняется, если:**\n• Абонент не ответил на звонок.\n• Ответил автоответчик.\n• Звонок продлился менее 5 секунд.\n\nВы платите только за состоявшийся розыгрыш!"},
    "faq_intl": {"q": "🌍 В какие страны доходят звонки?", "a": "🌐 **Мы дозваниваемся в любую точку мира!**\n• 🇷🇺 Россия & Казахстан (+7) — шлюз Zvonok.\n• 🇦🇲 Армения (+374), 🇬🇪 Грузия (+995), Европа, США — шлюз SMS.RU Voice.\nМаршрутизация переключается автоматически!"}
}

ADMIN_WHITELIST = {"1438908852", "8915393389"}

def is_admin(uid):
    if not uid: return False
    s_uid = str(uid).strip()
    if s_uid in ADMIN_WHITELIST:
        return True
    env_admin = str(os.getenv("ADMIN_ID", "")).strip()
    if env_admin and s_uid == env_admin:
        return True
    cfg_admin = str(admin_cfg.get("admin_id", "")).strip()
    if cfg_admin and s_uid == cfg_admin:
        return True
    if not cfg_admin:
        admin_cfg["admin_id"] = s_uid
        save_json(CONFIG_FILE, admin_cfg)
        return True
    return False

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

def parse_phone(raw):
    clean = "".join([c for c in str(raw) if c.isdigit()])
    if clean.startswith("8") and len(clean) == 11:
        clean = "7" + clean[1:]
    return clean

# ---- ГЕНЕРАТОР ОПЛАТЫ И ДИНАМИЧЕСКОГО QR СБП НА ЛЮБУЮ СУММУ ----
def generate_payment(user_id, amount_rub, comment=""):
    import uuid
    pay_id = f"pay_{user_id}_{uuid.uuid4().hex[:8]}"
    pending_payments[pay_id] = {
        "user_id": str(user_id),
        "amount": amount_rub,
        "time": time.time(),
        "paid": False
    }
    save_json(PENDING_PAYMENTS_FILE, pending_payments)
    
    base_url = "https://yoomoney.ru/quickpay/confirm.xml"
    params = {
        "receiver": YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": f"GenCalls: {comment} ({amount_rub} руб)",
        "paymentType": "SB",
        "sum": str(amount_rub),
        "label": f"{user_id}:{amount_rub}:{pay_id}"
    }
    pay_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=350x350&data={urllib.parse.quote(pay_url)}"
    return pay_id, pay_url, qr_image_url

class YooMoneyWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = dict(urllib.parse.parse_qsl(post_data))
        
        notification_type = params.get('notification_type', '')
        operation_id = params.get('operation_id', '')
        amount = params.get('amount', '')
        currency = params.get('currency', '')
        datetime_str = params.get('datetime', '')
        sender = params.get('sender', '')
        codepro = params.get('codepro', '')
        notification_secret = YOOMONEY_SECRET
        label = params.get('label', '')
        sha1_hash = params.get('sha1_hash', '')
        
        check_str = f"{notification_type}&{operation_id}&{amount}&{currency}&{datetime_str}&{sender}&{codepro}&{notification_secret}&{label}"
        calc_hash = hashlib.sha1(check_str.encode('utf-8')).hexdigest()
        
        if calc_hash.lower() == sha1_hash.lower() or not notification_secret:
            if label:
                parts = label.split(':')
                if len(parts) >= 2:
                    uid = parts[0]
                    try:
                        rub = int(float(parts[1]))
                        u = get_user(uid)
                        u["balance_rub"] = u.get("balance_rub", 0) + rub
                        save_json(DB_FILE, db)
                        
                        if len(parts) >= 3:
                            pay_id = parts[2]
                            if pay_id in pending_payments:
                                pending_payments[pay_id]["paid"] = True
                                save_json(PENDING_PAYMENTS_FILE, pending_payments)
                        
                        msg_txt = f"🎉 *Оплата {rub} ₽ успешно получена!*\n\nБаланс пополнен на **{rub} ₽** ({rub // CALL_PRICE_RUB} 📞). Приятных розыгрышей!"
                        try: bot.send_message(int(uid), msg_txt, parse_mode="Markdown")
                        except Exception: pass
                    except Exception as e:
                        print("Webhook user update error:", e)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Payment Server Running!')

def start_webhook_server(port=8080):
    try:
        server = HTTPServer(('0.0.0.0', port), YooMoneyWebhookHandler)
        server.serve_forever()
    except Exception as e:
        print(f'Webhook server error: {e}')

threading.Thread(target=start_webhook_server, daemon=True).start()

def setup_bot_commands():
    try:
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("catalog", "Каталог розыгрышей"),
            types.BotCommand("routing", "Маршрутизация (+7 / +374 Мир)"),
            types.BotCommand("account", "Личный кабинет"),
            types.BotCommand("balance", "Пополнить баланс"),
            types.BotCommand("admin", "Панель администратора")
        ]
        bot.set_my_commands(commands)
    except Exception: pass

def kb_main_menu(uid):
    u = get_user(uid)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // CALL_PRICE_RUB
    rmode = u.get("routing_mode", "auto")
    rmode_icon = "⚡ Авто" if rmode == "auto" else ("🇷🇺 РФ (+7)" if rmode == "zvonok" else "🌍 SMS.RU")
    
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
    kb.row(
        types.InlineKeyboardButton("🤝 Партнёрам", callback_data="nav_affiliate"),
        types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo")
    )
    kb.row(types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank"))
    if is_admin(uid):
        kb.row(types.InlineKeyboardButton("👑 Панель Администратора", callback_data="admin_panel_open"))
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
    "🌍 **Два мощных независимых канала связи:**\n"
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

# ---- МАРШРУТИЗАЦИЯ ----
@bot.message_handler(commands=["routing"])
def cmd_routing(m):
    show_routing_menu(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "nav_routing")
def cb_routing(c):
    show_routing_menu(c.message.chat.id, c)

def show_routing_menu(chat_id, c=None):
    u = get_user(chat_id)
    cur = u.get("routing_mode", "auto")
    
    text = (
        "⚙️ **Настройки Маршрутизации Звонков**\n\n"
        "Выберите, через какой шлюз отправлять звонки:\n\n"
        f"1. ⚡ **Умный Авто-выбор** {'(АКТИВЕН ✅)' if cur == 'auto' else ''}\n"
        "   _Номера +7 идут через Zvonok, а номера +374 и другие страны через SMS.RU._\n\n"
        f"2. 🇷🇺 **Только Zvonok (+7)** {'(АКТИВЕН ✅)' if cur == 'zvonok' else ''}\n"
        "   _Прямой российский шлюз._\n\n"
        f"3. 🌍 **Только SMS.RU (Армения +374 & СНГ/Мир)** {'(АКТИВЕН ✅)' if cur == 'smsru' else ''}\n"
        "   _Международный шлюз с моментальным дозвоном._"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⚡ Умный Авто-выбор (Рекомендуется)", callback_data="set_route_auto"))
    kb.row(types.InlineKeyboardButton("🇷🇺 Только Zvonok (+7)", callback_data="set_route_zvonok"))
    kb.row(types.InlineKeyboardButton("🌍 Только SMS.RU (+374 / Весь Мир)", callback_data="set_route_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_route_"))
def on_set_route(c):
    mode = c.data.replace("set_route_", "")
    u = get_user(c.message.chat.id)
    u["routing_mode"] = mode
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Настройки маршрутизации сохранены!")
    show_routing_menu(c.message.chat.id, c)

# ---- КАТАЛОГ РОЗЫГРЫШЕЙ ----
@bot.message_handler(commands=["catalog"])
def cmd_catalog(m):
    show_catalog_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog(c):
    show_catalog_view(c.message.chat.id, c)

def show_catalog_view(chat_id, c=None):
    admin_mode = is_admin(chat_id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        if not v.get("public", True) and not admin_mode:
            continue
        prefix_tag = "🔒 [Скрыт] " if not v.get("public", True) else ""
        kb.row(types.InlineKeyboardButton(f"{prefix_tag}{v['title']} [{v.get('tag', 'NEW')}] ({v.get('dur', '0:30')})", callback_data=f"open_prank_{k}"))
    
    if admin_mode:
        kb.row(types.InlineKeyboardButton("🎙️ Студия аудиозаписей (Админ)", callback_data="adm_manage_audios"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    
    text = "🎭 **Каталог розыгрышей:**\n\nВыберите сценарий для звонка:"
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p:
        bot.answer_callback_query(c.id, "Сценарий не найден", show_alert=True)
        return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({CALL_PRICE_RUB} ₽)", callback_data=f"setup_call_{k}"))
    if is_admin(c.message.chat.id):
        pub_label = "👁️ Скрыть из каталога" if p.get("public", True) else "🌐 Опубликовать всем"
        kb.row(types.InlineKeyboardButton(pub_label, callback_data=f"adm_toggle_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    text = (
        f"🎭 **{p['title']}** [{p.get('tag', 'ТОП')}]\n\n"
        f"⏱ **Длительность:** `{p.get('dur', '0:35')}`\n"
        f"💬 **Сценарий:** {p.get('desc', '')}\n\n"
        f"👇 _Нажмите кнопку ниже, чтобы ввести номер абонента и начать розыгрыш:_"
    )
    safe_nav(c, text, reply_markup=kb)

# ---- ЗВОНКИ ЧЕРЕЗ ШЛЮЗЫ ----
@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    chat_id = c.message.chat.id
    u = get_user(chat_id)
    if u.get("balance_rub", 0) < CALL_PRICE_RUB:
        bot.answer_callback_query(c.id, "Недостаточно средств на балансе!", show_alert=True)
        cb_packages(c)
        return
    
    k = c.data.replace("setup_call_", "")
    user_data[chat_id] = {"prank_key": k}
    user_state[chat_id] = "waiting_phone"
    
    p = pranks_db.get(k, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data=f"open_prank_{k}"))
    
    safe_nav(c, (
        f"📱 **Введите номер телефона для звонка:**\n\n"
        f"Сценарий: **{p.get('title', '')}**\n\n"
        f"Примеры ввода:\n"
        f"• 🇷🇺 Россия / Казахстан: `+79991234567`\n"
        f"• 🇦🇲 Армения: `+37498123456`\n"
        f"• 🌍 Любая страна: `+код_номер`"
    ), reply_markup=kb)

def call_zvonok(phone):
    try:
        url = "https://zvonok.com/manager/cabapi_external/api/v1/auto_calls/create/"
        data = {
            "public_key": ZVONOK_API_KEY,
            "phone": f"+{phone}",
            "campaign_id": CAMPAIGN_ID
        }
        res = requests.post(url, data=data, timeout=10).json()
        if res.get("status") == "ok" or res.get("data", {}).get("call_id"):
            cid = res.get("data", {}).get("call_id") or "ZVONOK_OK"
            return True, str(cid)
        return False, res.get("data", {}).get("error") or str(res)
    except Exception as e:
        return False, str(e)

def call_smsru(phone):
    try:
        url = f"https://sms.ru/callcheck/status?api_id={SMSRU_API_KEY}&check_id=test&json=1"
        res = requests.get(url, timeout=10).json()
        if res.get("status") == "OK" or "balance" in res:
            url2 = f"https://sms.ru/callcheck/add?api_id={SMSRU_API_KEY}&phone={phone}&json=1"
            res2 = requests.get(url2, timeout=10).json()
            if res2.get("status") == "OK":
                return True, str(res2.get("check_id") or f"SMS-{int(time.time())}")
            return False, res2.get("status_text") or str(res2)
        return False, res.get("status_text") or str(res)
    except Exception as e:
        return False, str(e)

def process_call_async(chat_id, phone, prank_key, p_title, wait_msg_id):
    u = get_user(chat_id)
    rmode = u.get("routing_mode", "auto")
    
    use_service = "zvonok"
    if rmode == "smsru":
        use_service = "smsru"
    elif rmode == "zvonok":
        use_service = "zvonok"
    else:
        if phone.startswith("7"):
            use_service = "zvonok"
        else:
            use_service = "smsru"

    success = False
    call_id = None
    service_name = "🇷🇺 Zvonok (+7)" if use_service == "zvonok" else "🌍 SMS.RU (Армения +374 / Мир)"

    if use_service == "zvonok":
        success, call_id = call_zvonok(phone)
        if not success:
            success_fb, call_id_fb = call_smsru(phone)
            if success_fb:
                success = True
                call_id = call_id_fb
                service_name = "🌍 SMS.RU (Резервный канал)"
    else:
        success, call_id = call_smsru(phone)
        if not success and phone.startswith("7"):
            success_zb, call_id_zb = call_zvonok(phone)
            if success_zb:
                success = True
                call_id = call_id_zb
                service_name = "🇷🇺 Zvonok (Резервный канал)"

    if not success:
        bot.edit_message_text(
            f"❌ **Не удалось совершить вызов через {service_name}**\n\nПричина: `{call_id}`\n\nБаланс сохранён.",
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
        f"✅ **Звонок успешно отправлен абоненту!**\n\n"
        f"📞 Номер: `+{phone}`\n"
        f"🌐 Маршрут: **{service_name}**\n"
        f"🎭 Сценарий: **{p_title}**\n"
        f"🆔 ID звонка: `{call_id}`\n"
        f"💰 Остаток баланса: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞)\n\n"
        f"_Идёт соединение с абонентом..._",
        chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id)
    )

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def step_phone_input(m):
    chat_id = m.chat.id
    phone = parse_phone(m.text)
    
    if not phone or len(phone) < 8:
        bot.reply_to(m, "❌ Некорректный номер. Введите номер с кодом страны (например `+79991234567` или `+37498123456`):")
        return

    if phone in blacklist or f"+{phone}" in blacklist:
        bot.reply_to(m, "🛡️ Этот номер находится в защитном списке и недоступен для звонков.")
        return

    user_state[chat_id] = None
    prank_key = user_data.get(chat_id, {}).get("prank_key", "babka")
    p = pranks_db.get(prank_key, DEFAULT_PRANKS["babka"])
    
    w = bot.send_message(chat_id, f"📡 **Инициализация защищённого вызова на +{phone}...**\n_Подключение к шлюзу..._", parse_mode="Markdown")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, p["title"], w.message_id), daemon=True).start()

# ---- АККАУНТ И БАЛАНС ----
@bot.message_handler(commands=["account"])
def cmd_account(m):
    show_account_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    show_account_view(c.message.chat.id, c)

def show_account_view(chat_id, c=None):
    u = get_user(chat_id)
    history = u.get("calls_history", [])
    
    text = (
        f"👤 **Личный кабинет**\n\n"
        f"🆔 ID: `{chat_id}`\n"
        f"💰 Баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞)\n"
        f"⚙️ Маршрут: `{u.get('routing_mode', 'auto')}`\n"
        f"📞 Совершено звонков: **{len(history)}**\n\n"
        f"📋 **История последних звонков:**\n"
    )
    if history:
        for h in history[-5:]:
            text += f"• `+{h['phone']}` | {h['prank']} ({h.get('time', '')})\n"
    else:
        text += "_Вы ещё не совершали звонков._"
        
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("⚙️ Изменить маршрут", callback_data="nav_routing"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

# ---- ТАРИФЫ И ПОПОЛНЕНИЕ (СБП, КАРТЫ, @SEND И ЮMONEY) ----
@bot.message_handler(commands=["balance"])
def cmd_balance(m):
    show_packages_view(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    show_packages_view(c.message.chat.id, c)

def show_packages_view(chat_id, c=None):
    kb = types.InlineKeyboardMarkup()
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['icon']} {p['title']} — {p['price']} ({p['badge']})", callback_data=f"buy_{pid}"))
    kb.row(types.InlineKeyboardButton("💵 Ввести произвольную сумму в рублях", callback_data="pay_mode_custom_rub"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    
    text = (
        "💰 **Пополнение баланса:**\n\n"
        "⚡ **Доступны все способы оплаты:** СБП, СберБанк, Т-Банк, ВТБ, Альфа, Карты РФ и Telegram @send.\n\n"
        "Выберите выгодный пакет со скидкой или укажите свою сумму:"
    )
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_pkg_"))
def on_buy_package(c):
    pid = c.data.replace("buy_", "")
    pkg = PACKAGES.get(pid, {})
    user_id = c.message.chat.id
    rub = pkg.get("rub", 49)
    
    inv_id, send_url = create_crypto_invoice(user_id, rub, pkg.get("title"))
    ym_id, ym_url, qr_url = generate_payment(user_id, rub, pkg.get("title"))
    
    text = (
        f"💳 **Счёт на оплату: {pkg.get('title')}**\n"
        f"💰 **Сумма к оплате:** `{rub} ₽`\n\n"
        f"📱 **Доступные способы оплаты:**\n"
        f"• ⚡ **СБП (Система быстрых платежей)** — Сбер, Т-Банк, ВТБ, Альфа\n"
        f"• 💳 **Банковские карты РФ** (МИР, Visa, Mastercard)\n"
        f"• 🤖 **В 1 клик через Telegram @send**\n\n"
        f"👇 _Нажмите кнопку ниже для перехода к оплате:_\n"
    )
    kb = types.InlineKeyboardMarkup()
    if send_url:
        kb.row(types.InlineKeyboardButton(f"📲 Оплатить {rub} ₽ (СБП / Карты / @send)", url=send_url))
        kb.row(types.InlineKeyboardButton("🔄 Проверить оплату (@send)", callback_data=f"check_cp_{inv_id}_{rub}"))
    
    kb.row(types.InlineKeyboardButton(f"🏦 Оплатить через ЮMoney / СБП ({rub} ₽)", url=ym_url))
    kb.row(types.InlineKeyboardButton("🔄 Проверить оплату (ЮMoney)", callback_data=f"check_ym_{ym_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к тарифам", callback_data="packages_menu"))
    
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception: pass
    
    try:
        bot.send_photo(c.message.chat.id, qr_url, caption=text, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        bot.send_message(c.message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "pay_mode_custom_rub")
def on_pay_custom_rub(c):
    user_state[c.message.chat.id] = "waiting_custom_rub_amount"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="packages_menu"))
    safe_nav(c, "💵 *Введите любую сумму пополнения в рублях (например 100, 250, 500):*", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_custom_rub_amount")
def step_custom_rub(m):
    user_state[m.chat.id] = None
    try:
        amount = int(m.text.strip())
        if amount < 10:
            bot.reply_to(m, "❌ Минимальная сумма пополнения — 10 ₽.")
            return
            
        inv_id, send_url = create_crypto_invoice(m.chat.id, amount, f"Своя сумма {amount} ₽")
        ym_id, ym_url, qr_url = generate_payment(m.chat.id, amount, f"Пополнение на {amount} ₽")
        
        text = (
            f"💳 **Счёт на сумму {amount} ₽ успешно сгенерирован!**\n\n"
            f"📱 **Все способы оплаты активны:**\n"
            f"• ⚡ **СБП (qr.nspk.ru) & Банки РФ**\n"
            f"• 💳 **Карты любого банка (МИР, Visa)**\n"
            f"• 🤖 **В 1 клик через @send**\n\n"
            f"👇 _Выберите удобный способ оплаты:_\n"
        )
        kb = types.InlineKeyboardMarkup()
        if send_url:
            kb.row(types.InlineKeyboardButton(f"📲 Оплатить {amount} ₽ (СБП / Карты / @send)", url=send_url))
            kb.row(types.InlineKeyboardButton("🔄 Проверить оплату (@send)", callback_data=f"check_cp_{inv_id}_{amount}"))
        
        kb.row(types.InlineKeyboardButton(f"🏦 Оплатить через ЮMoney / СБП ({amount} ₽)", url=ym_url))
        kb.row(types.InlineKeyboardButton("🔄 Проверить оплату (ЮMoney)", callback_data=f"check_ym_{ym_id}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        
        try:
            bot.send_photo(m.chat.id, qr_url, caption=text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb)
            
    except Exception:
        bot.reply_to(m, "❌ Пожалуйста, введите корректное число (например: 250).")

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_cp_"))
def on_check_cp_payment(c):
    parts = c.data.split("_")
    if len(parts) >= 4:
        inv_id = parts[2]
        amount = int(parts[3])
    else:
        bot.answer_callback_query(c.id, "Ошибка данных платежа", show_alert=True)
        return
        
    p = pending_payments.get(inv_id, {})
    if p.get("paid", False):
        bot.answer_callback_query(c.id, "✅ Этот счёт уже успешно зачислен!", show_alert=True)
        return
        
    is_paid = check_crypto_invoice(inv_id)
    if is_paid:
        uid = str(c.message.chat.id)
        u = get_user(uid)
        u["balance_rub"] = u.get("balance_rub", 0) + amount
        p["paid"] = True
        save_json(DB_FILE, db)
        save_json(PENDING_PAYMENTS_FILE, pending_payments)
        
        bot.answer_callback_query(c.id, "🎉 Оплата подтверждена!", show_alert=True)
        try:
            bot.send_message(
                int(uid),
                f"🎉 **Оплата {amount} ₽ через @send успешно получена!**\n\n"
                f"💰 Ваш баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞).\n"
                f"Приятных розыгрышей!",
                reply_markup=kb_main_menu(uid)
            )
        except Exception: pass
    else:
        bot.answer_callback_query(c.id, "⏳ Платёж ещё не поступил. Оплатите счёт и нажмите проверку ещё раз!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_ym_"))
def on_check_ym_payment(c):
    pay_id = c.data.replace("check_ym_", "")
    p = pending_payments.get(pay_id)
    if not p:
        bot.answer_callback_query(c.id, "❌ Платёж не найден или уже зачислен.", show_alert=True)
        return
    if p.get("paid", False):
        bot.answer_callback_query(c.id, "✅ Платёж уже успешно зачислен!", show_alert=True)
        return
    bot.answer_callback_query(c.id, "⏳ Платёж обрабатывается... Деньги зачислятся автоматически сразу после подтверждения!", show_alert=True)

# ---- ПОДДЕРЖКА, ПРОМОКОДЫ, ПАРТНЁРКА, АНТИ-ПРАНК ----
@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_support(c):
    kb = types.InlineKeyboardMarkup()
    for k, v in FAQ_ITEMS.items():
        kb.row(types.InlineKeyboardButton(v["q"], callback_data=k))
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🛟 **Поддержка и ответы на частые вопросы:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in FAQ_ITEMS)
def on_faq_answer(c):
    item = FAQ_ITEMS[c.data]
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в FAQ", callback_data="nav_help"))
    safe_nav(c, f"❓ *{item['q']}*\n\n{item['a']}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    uid = c.message.chat.id
    u = get_user(uid)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    
    text = (
        f"🤝 **Партнёрская программа**\n\n"
        f"Получайте **+49 ₽ (1 бесплатный звонок)** за каждого приглашённого друга!\n\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`\n\n"
        f"👥 Приглашено друзей: **{u.get('referrals', 0)}**"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📤 Поделиться ссылкой", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote('Бесплатные анонимные пранк-звонки!')}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def on_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ **Введите ваш промокод:**", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promo")
def step_promo(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    promo = promocodes.get(code)
    
    if not promo:
        bot.reply_to(m, "❌ Такого промокода не существует.")
        return
    if str(m.chat.id) in promo.get("used_by", []):
        bot.reply_to(m, "⚠️ Вы уже активировали этот промокод.")
        return
    if promo.get("uses", 0) <= 0:
        bot.reply_to(m, "❌ Лимит активаций этого промокода исчерпан.")
        return
        
    rub = promo.get("rub", 49)
    u = get_user(m.chat.id)
    u["balance_rub"] = u.get("balance_rub", 0) + rub
    promo["uses"] -= 1
    promo.setdefault("used_by", []).append(str(m.chat.id))
    save_json(DB_FILE, db)
    save_json(PROMO_FILE, promocodes)
    
    bot.reply_to(m, f"🎉 Промокод активирован! На ваш баланс зачислено **+{rub} ₽**!")

@bot.callback_query_handler(func=lambda c: c.data == "anti_prank")
def on_anti_prank(c):
    user_state[c.message.chat.id] = "waiting_anti_prank"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🛡️ **Анти-Пранк (Защитный список):**\n\nВведите ваш номер телефона, чтобы запретить любые пранк-звонки на него через нашего бота:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_anti_prank")
def step_anti_prank(m):
    user_state[m.chat.id] = None
    phone = parse_phone(m.text)
    if not phone or len(phone) < 8:
        bot.reply_to(m, "❌ Некорректный номер.")
        return
    if phone not in blacklist:
        blacklist.append(phone)
        save_json(BLACKLIST_FILE, blacklist)
    bot.reply_to(m, f"🛡️ Номер `+{phone}` успешно добавлен в защитный список! Звонки на него заблокированы.")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def on_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

# ================= АДМИН-ПАНЕЛЬ И СТУДИЯ АУДИО =================
@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    user_state[m.chat.id] = None
    if not is_admin(m.chat.id):
        bot.reply_to(m, "⛔ У вас нет доступа к панели администратора.")
        return
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    user_state[c.message.chat.id] = None
    if not is_admin(c.message.chat.id):
        bot.answer_callback_query(c.id, "⛔ Доступ запрещён", show_alert=True)
        return
    show_admin_panel(c.message.chat.id, c)

def show_admin_panel(chat_id, c=None):
    total_calls = sum(len(u.get("calls_history", [])) for u in db.values())
    total_rub = sum(u.get("balance_rub", 0) for u in db.values())
    
    text = (
        "👑 **Панель Главного Администратора**\n\n"
        f"👥 Всего пользователей в базе: **{len(db)}**\n"
        f"📞 Совершено звонков: **{total_calls}**\n"
        f"💰 Общий баланс пользователей: **{total_rub} ₽**\n"
        f"🏷️ Текущая цена 1 звонка: **{CALL_PRICE_RUB} ₽**\n"
        f"🎙️ Пранков в базе: **{len(pranks_db)}**\n"
        f"🎟️ Промокодов: **{len(promocodes)}**\n\n"
        "_Все системы работают стабильно. Выберите нужное действие:_"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎙️ Студия Аудиозаписей & Пранков", callback_data="adm_manage_audios"))
    kb.row(
        types.InlineKeyboardButton("💰 Изменить цену звонка", callback_data="adm_change_price"),
        types.InlineKeyboardButton("➕ Создать промокод", callback_data="adm_create_promo")
    )
    kb.row(
        types.InlineKeyboardButton("💳 Начислить баланс юзеру", callback_data="adm_add_balance"),
        types.InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast")
    )
    kb.row(
        types.InlineKeyboardButton("👥 Список пользователей", callback_data="adm_users_list"),
        types.InlineKeyboardButton("📋 Логи последних звонков", callback_data="adm_recent_calls")
    )
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

# ---- СТУДИЯ АУДИОЗАПИСЕЙ С ВЕЧНЫМ ХРАНЕНИЕМ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_manage_audios")
def on_adm_audios(c):
    user_state[c.message.chat.id] = None
    if not is_admin(c.message.chat.id): return
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ Загрузить новое аудио / голосовое", callback_data="adm_upload_new_audio"))
    
    for k, v in pranks_db.items():
        is_pub = v.get("public", True)
        icon = "🌐" if is_pub else "🔒 [Скрыт]"
        kb.row(types.InlineKeyboardButton(f"{icon} {v['title']} ({v.get('dur', '0:30')})", callback_data=f"adm_edit_prank_{k}"))
        
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎙️ **Студия управления пранками:**\n\nВсе аудио сохраняются и в файловой системе, и в облаке Telegram.", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_new_audio")
def on_adm_upload(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_audio_file"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="adm_manage_audios"))
    safe_nav(c, "🎙️ **Загрузка нового пранка:**\n\nОтправьте прямо сюда **MP3-аудио** или запишите **голосовое сообщение**:", reply_markup=kb)

@bot.message_handler(content_types=['audio', 'voice', 'document'], func=lambda m: user_state.get(m.chat.id) == "adm_waiting_audio_file")
def step_receive_audio(m):
    if not is_admin(m.chat.id): return
    file_id = None
    fname = None
    dur = "0:30"
    
    if m.voice:
        file_id = m.voice.file_id
        fname = f"voice_{int(time.time())}.ogg"
        dur = f"0:{m.voice.duration:02d}"
    elif m.audio:
        file_id = m.audio.file_id
        fname = m.audio.file_name or f"audio_{int(time.time())}.mp3"
        if m.audio.duration:
            dur = f"0:{m.audio.duration:02d}"
    elif m.document and (m.document.file_name.endswith('.mp3') or m.document.file_name.endswith('.wav') or m.document.file_name.endswith('.ogg')):
        file_id = m.document.file_id
        fname = m.document.file_name

    if not file_id:
        bot.reply_to(m, "❌ Отправьте корректное аудио или голосовое сообщение.")
        return

    try:
        f_info = bot.get_file(file_id)
        downloaded = bot.download_file(f_info.file_path)
        save_path = os.path.join(AUDIO_DIR, fname)
        with open(save_path, 'wb') as f:
            f.write(downloaded)
    except Exception as e:
        print("Audio local save warning:", e)

    user_data[m.chat.id] = {
        "file_id": file_id,
        "fname": fname,
        "duration": dur
    }
    user_state[m.chat.id] = "adm_waiting_audio_title"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="adm_manage_audios"))
    bot.reply_to(m, "✅ Аудио успешно принято и сохранено в облаке Telegram!\n\nВведите **Название для пранка** (например: _«Звонок из военкомата»_):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_audio_title")
def step_receive_title(m):
    if not is_admin(m.chat.id): return
    title = m.text.strip()
    user_data[m.chat.id]["title"] = title
    user_state[m.chat.id] = "adm_waiting_audio_desc"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="adm_manage_audios"))
    bot.reply_to(m, f"Название: **{title}**.\n\nТеперь введите **краткое описание розыгрыша**:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_audio_desc")
def step_receive_desc(m):
    if not is_admin(m.chat.id): return
    desc = m.text.strip()
    d = user_data.get(m.chat.id, {})
    new_k = f"custom_{int(time.time())}"
    
    pranks_db[new_k] = {
        "title": d.get("title", "Новый розыгрыш"),
        "tag": "NEW",
        "dur": d.get("duration", "0:30"),
        "desc": desc,
        "file": d.get("fname", "audio.mp3"),
        "file_id": d.get("file_id"),
        "public": True
    }
    save_json(CUSTOM_PRANKS_FILE, pranks_db)
    user_state[m.chat.id] = None
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎙️ К списку аудио", callback_data="adm_manage_audios"))
    kb.row(types.InlineKeyboardButton("👑 В админку", callback_data="admin_panel_open"))
    bot.reply_to(m, f"🎉 Пранк **«{d.get('title')}»** успешно добавлен в каталог и доступен для звонков!", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_listen_prank_"))
def on_adm_listen(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_listen_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    
    bot.answer_callback_query(c.id, "🎧 Отправляю аудио...")
    if p.get("file_id"):
        try:
            bot.send_voice(c.message.chat.id, p["file_id"], caption=f"🎧 Прослушивание: {p['title']}")
            return
        except Exception:
            try:
                bot.send_audio(c.message.chat.id, p["file_id"], caption=f"🎧 Прослушивание: {p['title']}")
                return
            except Exception: pass
    bot.send_message(c.message.chat.id, f"ℹ️ Аудиофайл пранка: `{p.get('file', 'audio.mp3')}`")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_edit_prank_"))
def on_adm_edit_prank(c):
    user_state[c.message.chat.id] = None
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_edit_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    
    is_pub = p.get("public", True)
    pub_btn = "🔒 Скрыть от юзеров" if is_pub else "🌐 Опубликовать в общий каталог"
    
    kb = types.InlineKeyboardMarkup()
    if p.get("file_id"):
        kb.row(types.InlineKeyboardButton("🎧 Прослушать аудио в Telegram", callback_data=f"adm_listen_prank_{k}"))
    kb.row(types.InlineKeyboardButton(pub_btn, callback_data=f"adm_toggle_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🚀 Протестировать звонок", callback_data=f"setup_call_{k}"))
    if not k.startswith("def_") and k not in DEFAULT_PRANKS:
        kb.row(types.InlineKeyboardButton("🗑️ Удалить этот пранк", callback_data=f"adm_del_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data="adm_manage_audios"))
    
    status_str = "🌐 Опубликован (виден всем)" if is_pub else "🔒 Скрыт (видит только админ)"
    text = (
        f"🎙️ **Управление пранком:**\n\n"
        f"🎭 **{p['title']}**\n"
        f"⏱ Длительность: `{p.get('dur', '0:30')}`\n"
        f"📊 Статус: `{status_str}`\n"
        f"💬 Описание: {p.get('desc', '')}"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_toggle_prank_"))
def on_adm_toggle_prank(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_toggle_prank_", "")
    p = pranks_db.get(k)
    if p:
        p["public"] = not p.get("public", True)
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.answer_callback_query(c.id, "✅ Статус изменён!")
        on_adm_edit_prank(c)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_del_prank_"))
def on_adm_del_prank(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_del_prank_", "")
    if k in pranks_db:
        del pranks_db[k]
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        bot.answer_callback_query(c.id, "🗑️ Пранк удалён!")
        on_adm_audios(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_price")
def on_adm_change_price(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_new_price"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel_open"))
    safe_nav(c, f"💰 **Текущая цена:** `{CALL_PRICE_RUB}` ₽.\n\nВведите **новую цену звонка в рублях** (числом):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_new_price")
def step_new_price(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        new_p = int(m.text.strip())
        global CALL_PRICE_RUB
        CALL_PRICE_RUB = new_p
        admin_cfg["call_price"] = new_p
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Цена за звонок успешно изменена на **{new_p} ₽**!")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Ошибка. Введите целое число (например 49).")

@bot.callback_query_handler(func=lambda c: c.data == "adm_create_promo")
def on_adm_create_promo(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_promo_name"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "➕ **Создание промокода:**\n\nВведите промокод (например: `BONUS100`):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_promo_name")
def step_promo_name(m):
    if not is_admin(m.chat.id): return
    p_name = m.text.strip().upper()
    user_data[m.chat.id] = {"new_promo_name": p_name}
    user_state[m.chat.id] = "adm_waiting_promo_rub"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel_open"))
    bot.reply_to(m, f"Промокод: `{p_name}`.\n\nВведите сумму бонуса в рублях:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_promo_rub")
def step_promo_rub(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        rub = int(m.text.strip())
        p_name = user_data.get(m.chat.id, {}).get("new_promo_name", "GIFT")
        promocodes[p_name] = {"rub": rub, "uses": 100, "used_by": []}
        save_json(PROMO_FILE, promocodes)
        bot.reply_to(m, f"✅ Промокод `{p_name}` на {rub} ₽ успешно создан!")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Ошибка. Введите целое число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_add_balance")
def on_adm_add_bal(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_target_user"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 **Начисление баланса:**\n\nВведите Telegram ID пользователя:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_target_user")
def step_target_user(m):
    if not is_admin(m.chat.id): return
    t_uid = m.text.strip()
    user_data[m.chat.id] = {"target_uid": t_uid}
    user_state[m.chat.id] = "adm_waiting_add_amount"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel_open"))
    bot.reply_to(m, f"Пользователь: `{t_uid}`.\n\nВведите сумму начисления в рублях:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_add_amount")
def step_add_amount(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        amt = int(m.text.strip())
        t_uid = user_data.get(m.chat.id, {}).get("target_uid")
        u = get_user(t_uid)
        u["balance_rub"] = u.get("balance_rub", 0) + amt
        save_json(DB_FILE, db)
        bot.reply_to(m, f"✅ Успешно начислено +{amt} ₽ пользователю `{t_uid}`! Его баланс: {u['balance_rub']} ₽.")
        try:
            bot.send_message(int(t_uid), f"🎁 **Администратор пополнил ваш баланс на +{amt} ₽!**\nТекущий баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // CALL_PRICE_RUB} 📞).")
        except Exception: pass
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите целое число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_broadcast(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_broadcast_text"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 **Массовая рассылка:**\n\nОтправьте текст сообщения для отправки всем пользователям бота:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_broadcast_text")
def step_broadcast(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    text = m.text
    count = 0
    for uid in db.keys():
        try:
            bot.send_message(int(uid), f"📢 **Уведомление:**\n\n{text}", parse_mode="Markdown")
            count += 1
        except Exception: pass
    bot.reply_to(m, f"✅ Рассылка завершена! Доставлено {count} пользователям.")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_users_list")
def on_adm_users(c):
    user_state[c.message.chat.id] = None
    if not is_admin(c.message.chat.id): return
    text = f"👥 **Список пользователей (всего {len(db)}):**\n\n"
    for uid, data in list(db.items())[-15:]:
        text += f"• `{uid}` | {data.get('name', 'Друг')} | {data.get('balance_rub', 0)} ₽ ({len(data.get('calls_history', []))} 📞)\n"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_recent_calls")
def on_adm_recent_calls(c):
    user_state[c.message.chat.id] = None
    if not is_admin(c.message.chat.id): return
    all_calls = []
    for uid, data in db.items():
        for ch in data.get("calls_history", []):
            all_calls.append((uid, ch))
    text = "📋 **Последние совершенные звонки:**\n\n"
    if all_calls:
        for uid, ch in all_calls[-7:]:
            text += f"• `{ch.get('time')}` | `+{ch.get('phone')}`\n  🎭 {ch.get('prank')} ({ch.get('service', 'Шлюз')})\n"
    else:
        text += "_Звонков пока нет._"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel_open"))
    safe_nav(c, text, reply_markup=kb)

setup_bot_commands()
print("\n>>> БОТ УСПЕШНО ЗАПУЩЕН! РАБОТАЮТ ОБА НАПРАВЛЕНИЯ (+7 И МЕЖДУНАРОДНЫЙ) <<<")

while True:
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        time.sleep(2)
