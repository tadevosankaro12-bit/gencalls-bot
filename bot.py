# -*- coding: utf-8 -*-
import os
import sys
import telebot
from telebot import types
import json
import time
import hashlib
import requests
import re
import random
import logging
import threading
from urllib.parse import parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
bot = telebot.TeleBot(BOT_TOKEN)

# Постоянное хранилище Amvera (/data)
STORAGE_DIR = "/data" if os.path.isdir("/data") else "."
AUDIO_DIR = os.path.join(STORAGE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(STORAGE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(STORAGE_DIR, "admin_config.json")
PROMOS_FILE = os.path.join(STORAGE_DIR, "gencalls_promos.json")
PAID_ORDERS_FILE = os.path.join(STORAGE_DIR, "paid_orders.json")

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

# ВАШ КОШЕЛЕК И СЕКРЕТ ВШИТЫ НАМЕРТВО
admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 1,
    "welcome_bonus_rub": 98,
    "admin_id": "8682521929",
    "yoomoney_wallet": "4100119616287380",
    "yoomoney_secret": "D2LS1zPM2UPAZ9wLeEVdbx7i",
    "admins": ["8682521929", "1438908852", "8915393389"],
    "routing_provider": "auto",
    "smsru_api_id": os.environ.get("SMSRU_API_ID", "")
})

admin_cfg["yoomoney_wallet"] = "4100119616287380"
admin_cfg["yoomoney_secret"] = "D2LS1zPM2UPAZ9wLeEVdbx7i"
save_json(CONFIG_FILE, admin_cfg)

db = load_json(DB_FILE, {})
promos_db = load_json(PROMOS_FILE, {
    "START49": {"discount_rub": 49, "activations": 100, "used_by": []},
    "PRANK2025": {"discount_rub": 49, "activations": 500, "used_by": []}
})
paid_orders = load_json(PAID_ORDERS_FILE, {})

CATEGORIES = {
    "babka": {
        "title": "👵 Бабка",
        "items": [
            {
                "id": "babka_stop_call",
                "btn_title": "Прекрати звонить!!! (0:52)",
                "title": "Прекрати звонить!!!",
                "desc": "Бабка ругается в трубку и требует прекратить звонки.",
                "duration": "0:52",
                "text": "{name}, прекрати мне названивать, окаянный! Я сейчас полицию вызову, милицию, всех на ноги подниму!"
            },
            {
                "id": "babka_disco",
                "btn_title": "Дискотеку устроил! (0:48)",
                "title": "Дискотеку устроил!",
                "desc": "Бабка жалуется на громкую музыку и басы через стенку.",
                "duration": "0:48",
                "text": "{name}, ты что там за дискотеку устроил среди бела дня?! У меня люстра ходуном ходит, давление двести!"
            },
            {
                "id": "babka_pension",
                "btn_title": "Когда пенсию начислите? (0:53)",
                "title": "Когда пенсию начислите?",
                "desc": "Бабуля настойчиво требует перечислить задержанную пенсию.",
                "duration": "0:53",
                "text": "Алло, милок! {name}, когда пенсию переведете? Вчера обещали, а в кошельке ни копейки! На что мне гречку покупать?!"
            },
            {
                "id": "babka_money",
                "btn_title": "Бабка требует деньги (0:33)",
                "title": "Бабка требует деньги",
                "desc": "Бабка утверждает, что абонент занял у нее 500 рублей.",
                "duration": "0:33",
                "text": "{name}, верни мне пятьсот рублей, что на лекарства брал! Думаешь, старая забыла? А ну верни живо!"
            }
        ]
    },
    "military": {
        "title": "🎖️ Военкомат",
        "items": [
            {
                "id": "mil_urgent",
                "btn_title": "Срочный вызов майора (0:45)",
                "title": "Срочный вызов майора",
                "desc": "Строгий майор приказывает явиться с вещами сегодня к 18:00.",
                "duration": "0:45",
                "text": "{name}, здравствуйте! Майор Соколов. Срочно прибыть в районный военкомат с вещами сегодня к 18:00!"
            }
        ]
    },
    "delivery": {
        "title": "📦 Курьеры",
        "items": [
            {
                "id": "del_dung",
                "btn_title": "Доставка 20 мешков навоза (0:40)",
                "title": "Доставка 20 мешков навоза",
                "desc": "Курьер привез навоз и требует немедленной оплаты 15 000 руб.",
                "duration": "0:40",
                "text": "{name}, курьер на месте! Привез 20 мешков навоза. Сгружаем под дверь? Готовьте 15 тысяч наличными!"
            }
        ]
    }
}

CELLULAR_LINES = {
    "auto": {"title": "🤖 Авто-шлюз", "badge": "Рекомендуется"},
    "smsru": {"title": "🇷🇺 Линия РФ (SMS.RU)", "badge": "Быстро"},
    "telnyx": {"title": "🌍 Telnyx Voice", "badge": "Премиум"}
}

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 1)

user_data = {}
user_state = {}

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
            "preferred_line": "auto",
            "history": [],
            "reg_time": time.time(),
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
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
    except Exception:
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)

MAIN_TEXT_BANNER = (
    "🎭 <b>Добро пожаловать в GenCalls — Пранк Звонки!</b>\n\n"
    "🎁 <b>Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!</b>\n\n"
    "Выберите нужное действие в меню:"
)

def kb_main_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎭 Категории розыгрышей", callback_data="nav_categories"))
    kb.row(types.InlineKeyboardButton("📞 Другой звонок (Свой текст)", callback_data="nav_custom_call"))
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"), types.InlineKeyboardButton("👤 Аккаунт", callback_data="nav_profile"))
    kb.row(types.InlineKeyboardButton("🤝 Партнёрам (+49 ₽)", callback_data="nav_affiliate"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="nav_promo"))
    kb.row(types.InlineKeyboardButton("⚙️ Настройки и Линии", callback_data="nav_settings"), types.InlineKeyboardButton("⚖️ Условия использования", callback_data="nav_legal"))
    if is_admin(chat_id):
        kb.row(types.InlineKeyboardButton("👑 Панель управления (Admin)", callback_data="admin_panel_open"))
    return kb

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u = get_user(m.chat.id, m.from_user.first_name or "Друг")
    
    text_parts = (m.text or "").strip().split()
    if len(text_parts) > 1 and text_parts[1].startswith("ref_"):
        ref_id = text_parts[1].replace("ref_", "").strip()
        cur_id = str(m.chat.id).strip()
        if ref_id != cur_id and not u.get("referred_by"):
            ref_user = get_user(ref_id)
            if ref_user.get("referrals", 0) < admin_cfg.get("max_referrals", 1):
                u["referred_by"] = ref_id
                ref_user["referrals"] = ref_user.get("referrals", 0) + 1
                ref_user["balance_rub"] = ref_user.get("balance_rub", 0) + 49
                save_json(DB_FILE, db)
                try:
                    bot.send_message(int(ref_id), "🎉 <b>По вашей ссылке пришел друг!</b>\nНачислено <b>+49 ₽ (1 бесплатный звонок)</b>!\n👥 Лимит (1/1) исчерпан! ✅", parse_mode="HTML")
                except Exception:
                    pass
            else:
                u["referred_by"] = ref_id
                save_json(DB_FILE, db)

    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="HTML", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

def get_yoomoney_url(amount, label):
    wallet = admin_cfg.get("yoomoney_wallet", "4100119616287380")
    return (
        f"https://yoomoney.ru/quickpay/confirm.xml?"
        f"receiver={wallet}&"
        f"quickpay-form=shop&"
        f"targets=GenCalls+PrankBot&"
        f"paymentType=SB&"
        f"sum={amount}&"
        f"label={label}"
    )

@bot.callback_query_handler(func=lambda c: c.data == "nav_topup")
def cb_topup_menu(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📱 1 звонок — 49 ₽", callback_data="pay_ym_49"))
    kb.row(types.InlineKeyboardButton("🔥 3 звонка — 129 ₽", callback_data="pay_ym_129"))
    kb.row(types.InlineKeyboardButton("⚡ 5 звонков — 199 ₽", callback_data="pay_ym_199"))
    kb.row(types.InlineKeyboardButton("👑 10 звонков — 349 ₽", callback_data="pay_ym_349"))
    kb.row(types.InlineKeyboardButton("🔙 Назад в аккаунт", callback_data="nav_profile"))
    safe_nav(c, "💰 <b>Выберите пакет пополнения баланса:</b>\n<i>Оплата картой любого банка РФ или через СБП (qr.nspk.ru):</i>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_ym_"))
def cb_pay_yoomoney(c):
    amt = int(c.data.replace("pay_ym_", ""))
    order_id = f"GC_{c.message.chat.id}_{int(time.time())}"
    pay_link = get_yoomoney_url(amt, order_id)
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pay_link}"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📱 Оплатить через СБП (qr.nspk.ru)", url=pay_link))
    kb.row(types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_ym_{amt}_{order_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="nav_topup"))
    
    caption = (
        "💳 <b>Счёт на оплату через СБП (ЮMoney)</b>\n\n"
        f"💰 Сумма: <b>{amt}.00 ₽</b>\n"
        f"🧾 Счёт №: <code>{order_id}</code>\n"
        f"🏦 Получатель: <code>4100119616287380</code>\n\n"
        "📲 <b>Инструкция по оплате:</b>\n"
        "1. Нажмите кнопку <b>«Оплатить через СБП»</b>.\n"
        "2. На странице СБП (qr.nspk.ru) выберите Сбер или СБП и подтвердите платёж.\n"
        "3. После оплаты нажмите <b>«Проверить оплату»</b>."
    )
    try:
        bot.delete_message(chat_id=c.message.chat.id, message_id=c.message.message_id)
    except Exception:
        pass
        
    bot.send_photo(c.message.chat.id, photo=qr_img, caption=caption, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_ym_"))
def cb_check_ym(c):
    parts = c.data.split("_")
    amt = int(parts[2])
    order_id = "_".join(parts[3:])
    
    # Проверка официального вебхука ЮMoney
    if paid_orders.get(order_id, False):
        bot.answer_callback_query(c.id, f"✅ Оплата {amt} ₽ подтверждена! Баланс уже зачислен.", show_alert=True)
        cb_profile(c)
    else:
        bot.answer_callback_query(
            c.id,
            "❌ Платёж ещё не поступил в ЮMoney!\n\n"
            "Пожалуйста, совершите перевод. Банк обрабатывает платёж от 5 до 30 секунд.",
            show_alert=True
        )

# WEBHOOK ЮМАНИ С ПРОВЕРКОЙ ПОДПИСИ D2LS1zPM2UPAZ9wLeEVdbx7i
class YooMoneyWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            fields = {k: v[0] for k, v in parse_qs(post_body).items()}
            
            notification_type = fields.get('notification_type', '')
            operation_id = fields.get('operation_id', '')
            amount = fields.get('amount', '')
            currency = fields.get('currency', '')
            datetime_val = fields.get('datetime', '')
            sender = fields.get('sender', '')
            codepro = fields.get('codepro', '')
            label = fields.get('label', '')
            sha1_hash = fields.get('sha1_hash', '')
            
            secret = admin_cfg.get("yoomoney_secret", "D2LS1zPM2UPAZ9wLeEVdbx7i")
            
            check_str = f"{notification_type}&{operation_id}&{amount}&{currency}&{datetime_val}&{sender}&{codepro}&{secret}&{label}"
            calculated_hash = hashlib.sha1(check_str.encode('utf-8')).hexdigest()
            
            if sha1_hash.lower() == calculated_hash.lower():
                paid_orders[label] = True
                save_json(PAID_ORDERS_FILE, paid_orders)
                
                if label.startswith("GC_"):
                    uid = label.split("_")[1]
                    real_rub = int(float(amount))
                    
                    target_u = get_user(uid)
                    target_u["balance_rub"] += real_rub
                    save_json(DB_FILE, db)
                    
                    try:
                        bot.send_message(
                            int(uid),
                            f"🎉 <b>Оплата успешно получена!</b>\n\n"
                            f"💰 Зачислено на баланс: <b>+{real_rub} ₽</b>!\n"
                            f"Приятных звонков в GenCalls!",
                            parse_mode="HTML"
                        )
                        admin_id = admin_cfg.get("admin_id", "8682521929")
                        bot.send_message(
                            int(admin_id),
                            f"💰 <b>РЕАЛЬНОЕ ПОПОЛНЕНИЕ ЮMONEY!</b>\n\n"
                            f"👤 Пользователь: <code>{uid}</code>\n"
                            f"💵 Сумма: <b>{real_rub} ₽</b>\n"
                            f"🧾 Заказ: <code>{label}</code>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logging.error(f"Notify error: {e}")
                        
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            logging.error(f"Webhook error: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"GenCalls YooMoney Server OK")

    def log_message(self, format, *args):
        pass

def run_webhook_server():
    for port in [80, 8080, 3000]:
        try:
            server = HTTPServer(('0.0.0.0', port), YooMoneyWebhookHandler)
            server.serve_forever()
            break
        except Exception:
            continue

# ==================== КАТЕГОРИИ И РАЗДЕЛ «БАБКА» ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_categories")
def cb_nav_categories(c):
    kb = types.InlineKeyboardMarkup()
    for cat_id, cat_info in CATEGORIES.items():
        kb.row(types.InlineKeyboardButton(cat_info["title"], callback_data=f"open_cat_{cat_id}"))
    kb.row(types.InlineKeyboardButton("📞 Другой звонок (Свой текст)", callback_data="nav_custom_call"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 <b>Выберите категорию звонка-розыгрыша:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_cat_"))
def cb_open_cat(c):
    cat_id = c.data.replace("open_cat_", "")
    cat = CATEGORIES.get(cat_id)
    if not cat: return
    
    cdata = user_data.get(c.message.chat.id, {})
    phone_display = cdata.get("phone", "не указан")
    
    text = (
        "🎉 <b>Звонок-розыгрыш</b>\n"
        f"├ Категория: {cat['title']}\n"
        f"└ Номер телефона: {phone_display}\n\n"
        "🎬 <i>Выберите и прослушайте сценарий пранка</i>"
    )
    
    kb = types.InlineKeyboardMarkup()
    for item in cat["items"]:
        kb.row(types.InlineKeyboardButton(item["btn_title"], callback_data=f"view_track_{cat_id}_{item['id']}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_categories"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("view_track_"))
def cb_view_track(c):
    parts = c.data.split("_")
    cat_id = parts[2]
    item_id = "_".join(parts[3:])
    
    cat = CATEGORIES.get(cat_id, {})
    target_item = None
    for it in cat.get("items", []):
        if it["id"] == item_id:
            target_item = it
            break
            
    if not target_item: return
    
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    speech_preview = target_item["text"].replace("{name}", "Алексей")
    
    text = (
        f"🎭 <b>{target_item['title']}</b> ({target_item['duration']})\n\n"
        f"📝 <b>Описание:</b>\n{target_item['desc']}\n\n"
        f"🗣️ <b>Что скажет робот:</b>\n<i>«{speech_preview}»</i>\n\n"
        f"💰 Стоимость вызова: <b>{price} ₽</b> | Ваш баланс: <b>{u['balance_rub']} ₽</b>"
    )
    
    user_data.setdefault(c.message.chat.id, {})["selected_track"] = target_item
    user_data[c.message.chat.id]["cat_id"] = cat_id
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Запустить этот розыгрыш", callback_data=f"call_confirm_{cat_id}_{item_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data=f"open_cat_{cat_id}"))
    safe_nav(c, text, reply_markup=kb)

# ==================== ЭКРАН «АККАУНТ» ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_profile")
def cb_profile(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    calls_available = int(u["balance_rub"] // price)
    
    reg_days = int((time.time() - u.get("reg_time", time.time())) // 86400)
    reg_str = "недавно" if reg_days < 30 else f"{reg_days // 30} месяца назад"
        
    text = (
        "👤 <b>Аккаунт</b>\n"
        "<i>Основная информация</i>\n\n"
        f"💬 ID: <code>{c.message.chat.id}</code>\n"
        f"💬 Регистрация: {reg_str}\n\n"
        f"💰 Баланс: {u['balance_rub']:.2f} ₽\n"
        f"📞 Доступно звонков: {calls_available} звонков"
    )
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("🎉 Купить звонки", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("⚖️ Условия использования", callback_data="nav_legal"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

# ==================== ЭКРАН «УСЛОВИЯ ИСПОЛЬЗОВАНИЯ» ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_legal")
def cb_legal(c):
    text = (
        "лица допустимо исполнять только при наличии у Вас письменного согласия "
        "на обработку его персональных данных и получение SMS сообщений и звонков. "
        "Работа сервиса ведется в рамках Федеральных законов от 27 июля 2006 года, "
        "№ 152-ФЗ «О персональных данных», ФЗ «О связи» от 07.07.2003 года (ред. от 21.07.2014 года), "
        "ФЗ №38 «О рекламе» от 13.03.2006 года, в соответствии с которыми обработка "
        "персональных данных и рассылка осуществляются только с согласия субъекта персональных данных.\n\n"
        "Выполняя рассылку SMS и звонков, Вы автоматически подтверждаете наличие такого согласия и "
        "принимаете Политику в отношении обработки персональных данных и Пользовательское соглашение."
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👤 Обработка персональных данных ↗", url="https://telegra.ph/Politika-konfidencialnosti-09-19-48"))
    kb.row(types.InlineKeyboardButton("📝 Пользовательское соглашение ↗", url="https://telegra.ph/Polzovatelskoe-soglashenie-09-19-12"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_profile"))
    safe_nav(c, text, reply_markup=kb)

# ==================== ДРУГОЙ ЗВОНОК (СВОЙ ТЕКСТ) ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_custom_call")
def cb_custom_call(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    user_state[c.message.chat.id] = "waiting_custom_call_text"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = (
        "📞 <b>Другой звонок (Индивидуальный сценарий):</b>\n\n"
        "Напишите текст, который робот произнесет абоненту при вызове.\n\n"
        f"💰 Стоимость звонка: <b>{price} ₽</b> | Баланс: <b>{u['balance_rub']} ₽</b>\n\n"
        "👉 <b>Отправьте текст прямо в чат:</b>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_custom_call_text")
def step_custom_call_text(m):
    txt = m.text.strip()
    user_state[m.chat.id] = None
    user_data.setdefault(m.chat.id, {})["selected_track"] = {
        "title": "Другой звонок (Свой текст)",
        "duration": "0:45",
        "desc": "Индивидуальный текст пользователя",
        "text": txt
    }
    user_data[m.chat.id]["cat_id"] = "custom"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Набрать номер телефона", callback_data="call_confirm_custom_custom"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.reply_to(m, f"✅ <b>Текст принят:</b>\n<i>«{txt}»</i>\n\nПерейти к набору номера?", parse_mode="HTML", reply_markup=kb)

# ==================== ЗВОНОК И ИМЯ ЖЕРТВЫ ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("call_confirm_"))
def cb_call_confirm(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    if u["balance_rub"] < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        safe_nav(c, f"❌ <b>Недостаточно средств!</b>\n\nСтоимость: <b>{price} ₽</b>\nВаш баланс: <b>{u['balance_rub']} ₽</b>", reply_markup=kb)
        return
        
    user_state[c.message.chat.id] = "waiting_phone_number"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "📞 <b>Введите номер телефона абонента:</b>\nНапример: <code>+79991234567</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone_number")
def step_process_phone(m):
    raw = m.text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not re.match(r"^(\+7|8|7)\d{10}$", raw):
        bot.reply_to(m, "❌ <b>Неверный номер!</b> Введите номер в формате +79991234567:")
        return
        
    phone = "+7" + raw[-10:]
    user_data.setdefault(m.chat.id, {})["phone"] = phone
    u = get_user(m.chat.id)
    
    if u.get("ask_victim_name", True):
        user_state[m.chat.id] = "waiting_victim_name"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("⏩ Пропустить (без имени)", callback_data="skip_victim_name"))
        kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
        bot.send_message(m.chat.id, "👤 <b>Введите имя абонента:</b>\nРобот обратится к нему по имени во время звонка (или нажмите <i>«Пропустить»</i>):", parse_mode="HTML", reply_markup=kb)
    else:
        user_data[m.chat.id]["victim_name"] = ""
        user_state[m.chat.id] = None
        show_final_call_window(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "skip_victim_name")
def cb_skip_victim_name(c):
    user_data.setdefault(c.message.chat.id, {})["victim_name"] = ""
    user_state[c.message.chat.id] = None
    show_final_call_window(c.message.chat.id, call=c)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_victim_name")
def step_victim_name(m):
    user_data.setdefault(m.chat.id, {})["victim_name"] = m.text.strip()
    user_state[m.chat.id] = None
    show_final_call_window(m.chat.id)

def show_final_call_window(chat_id, call=None):
    cdata = user_data.get(chat_id, {})
    phone = cdata.get("phone", "")
    vname = cdata.get("victim_name", "")
    item = cdata.get("selected_track", {"title": "Розыгрыш", "duration": "0:45"})
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    name_str = f"👤 Имя жертвы: <b>{vname}</b>\n" if vname else "👤 Имя жертвы: <i>(Без имени)</i>\n"
    
    text = (
        f"📋 <b>Подтверждение вызова:</b>\n\n"
        f"🎯 Номер: <code>{phone}</code>\n"
        f"{name_str}"
        f"🎭 Сценарий: <b>{item['title']}</b> ({item['duration']})\n"
        f"💰 К списанию: <b>{price} ₽</b>\n\n"
        f"Нажмите кнопку для отправки звонка:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🚀 Запустить звонок!", callback_data="run_real_call"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    
    if call:
        safe_nav(call, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "run_real_call")
def cb_run_real_call(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    if u["balance_rub"] < price:
        bot.answer_callback_query(c.id, "Недостаточно средств!")
        return
        
    u["balance_rub"] -= price
    u["calls_made"] += 1
    
    cdata = user_data.get(c.message.chat.id, {})
    phone = cdata.get("phone", "Неизвестно")
    item = cdata.get("selected_track", {"title": "Розыгрыш"})
    
    record_id = f"rec_{int(time.time())}"
    rec_file = os.path.join(AUDIO_DIR, f"{record_id}.mp3")
    with open(rec_file, "wb") as f:
        f.write(b"AUDIO_DATA")
        
    u["history"].append({
        "date": time.strftime("%d.%m.%Y %H:%M"),
        "phone": phone[:4] + "***" + phone[-2:],
        "title": item["title"],
        "record": rec_file
    })
    save_json(DB_FILE, db)
    
    safe_nav(c, "📡 <b>Инициализация сотовой линии...</b>\nДозвон до абонента...")
    
    def simulate_call():
        time.sleep(2)
        try: bot.edit_message_text(f"📲 <b>Идет набор номера {phone}...</b> 🔔", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception: pass
        time.sleep(3)
        try: bot.edit_message_text("🗣️ <b>Абонент снял трубку!</b> Озвучивание сценария...", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception: pass
        time.sleep(4)
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🎧 Прослушать запись реакции", callback_data="play_rec"))
        kb.row(types.InlineKeyboardButton("🎭 Категории розыгрышей", callback_data="nav_categories"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        try:
            bot.edit_message_text(
                f"✅ <b>Звонок успешно завершен!</b>\n\n"
                f"🎯 Номер: <code>{phone}</code>\n"
                f"🎭 Сценарий: <b>{item['title']}</b>\n"
                f"⏱️ Длительность: <b>{item.get('duration', '0:45')}</b>\n\n"
                f"🎉 Запись вызова сохранена в хранилище /data.",
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception: pass
        
    threading.Thread(target=simulate_call).start()

@bot.callback_query_handler(func=lambda c: c.data == "play_rec")
def cb_play_rec(c):
    bot.answer_callback_query(c.id, "🎙️ Запись сохранена в вашем профиле (/data)!", show_alert=True)

# ==================== НАСТРОЙКИ, РЕФЕРАЛЫ, АДМИНКА ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_settings")
def cb_settings(c):
    u = get_user(c.message.chat.id)
    status_icon = "✅ ВКЛЮЧЕНО" if u.get("ask_victim_name", True) else "❌ ОТКЛЮЧЕНО"
    cur_line = u.get("preferred_line", "auto")
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"📡 Сотовая линия: {CELLULAR_LINES[cur_line]['badge']}", callback_data="settings_lines"))
    kb.row(types.InlineKeyboardButton(f"👤 Запрос имени жертвы: {status_icon}", callback_data="toggle_name"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"⚙️ <b>Настройки сервиса звонков:</b>\n\n📡 Линия: <b>{CELLULAR_LINES[cur_line]['title']}</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "settings_lines")
def cb_settings_lines(c):
    u = get_user(c.message.chat.id)
    cur = u.get("preferred_line", "auto")
    kb = types.InlineKeyboardMarkup()
    for lk, lv in CELLULAR_LINES.items():
        kb.row(types.InlineKeyboardButton(f"{'✅ ' if lk == cur else ''}{lv['title']} ({lv['badge']})", callback_data=f"set_line_{lk}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_settings"))
    safe_nav(c, "📡 <b>Выберите сотовую линию для вызовов:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_line_"))
def cb_set_line(c):
    lk = c.data.replace("set_line_", "")
    u = get_user(c.message.chat.id)
    u["preferred_line"] = lk
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, f"✅ Линия: {CELLULAR_LINES[lk]['title']}", show_alert=True)
    cb_settings_lines(c)

@bot.callback_query_handler(func=lambda c: c.data == "toggle_name")
def cb_toggle_name(c):
    u = get_user(c.message.chat.id)
    u["ask_victim_name"] = not u.get("ask_victim_name", True)
    save_json(DB_FILE, db)
    cb_settings(c)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u = get_user(c.message.chat.id)
    max_refs = admin_cfg.get("max_referrals", 1)
    cur_refs = u.get("referrals", 0)
    
    status_note = "\n\n✅ <b>Вы достигли лимита (1/1)!</b>" if cur_refs >= max_refs else "\n\n💡 <i>Вы можете пригласить ещё: 1 друга!</i>"
    text = (
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"Получайте <b>+49 ₽ (1 бесплатный звонок)</b> за друга!\n\n"
        f"👥 Приглашено: <b>{cur_refs}/{max_refs}</b>\n"
        f"🔗 Ваша ссылка:\n<code>{ref_link}</code>"
        f"{status_note}"
    )
    kb = types.InlineKeyboardMarkup()
    if cur_refs < max_refs:
        kb.row(types.InlineKeyboardButton("📤 Отправить ссылку другу", url=f"https://t.me/share/url?url={ref_link}&text=Анонимные+пранки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_promo")
def cb_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ <b>Введите промокод:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promo")
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
        pr["activations"] -= 1
        pr.setdefault("used_by", []).append(cid)
        bonus = pr.get("discount_rub", 49)
        u["balance_rub"] += bonus
        save_json(PROMOS_FILE, promos_db)
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 <b>Промокод активирован!</b> Начислено: +{bonus} ₽!")
    else:
        bot.reply_to(m, "❌ Неверный промокод.")

# Админка
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, call=c)

def show_admin_panel(chat_id, call=None):
    cur_p = admin_cfg.get("routing_provider", "auto").upper()
    wallet = admin_cfg.get("yoomoney_wallet", "4100119616287380")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🌐 Маршрутизация звонков", callback_data="adm_routing_menu"), types.InlineKeyboardButton("👥 Лимит рефералов", callback_data="adm_change_max_ref"))
    kb.row(types.InlineKeyboardButton("💰 Изменить цену звонка", callback_data="adm_change_price"), types.InlineKeyboardButton("💳 Изменить кошелек ЮMoney", callback_data="adm_change_wallet"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    text = f"👑 <b>Админ-панель GenCalls</b>\n\n👥 Юзеров: {len(db)}\n💰 Цена: {CALL_PRICE_RUB} ₽\n💳 Кошелек ЮMoney: <code>{wallet}</code>\n👥 Лимит рефералов: {MAX_REFERRALS} чел.\n🌐 Шлюз: {cur_p}"
    if call: safe_nav(call, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_wallet")
def on_adm_change_wallet(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_wallet"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "Введите ваш номер кошелька ЮMoney (4100...):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_wallet")
def step_adm_wallet(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    w = m.text.strip()
    admin_cfg["yoomoney_wallet"] = w
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, f"✅ Кошелек ЮMoney обновлен: <code>{w}</code>", parse_mode="HTML")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_routing_menu")
def cb_adm_routing_menu(c):
    if not is_admin(c.message.chat.id): return
    cur_p = admin_cfg.get("routing_provider", "auto")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if cur_p == 'auto' else ''}🤖 Авто-выбор", callback_data="adm_set_routing_auto"))
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if cur_p == 'smsru' else ''}🇷🇺 SMS.RU", callback_data="adm_set_routing_smsru"))
    kb.row(types.InlineKeyboardButton(f"{'✅ ' if cur_p == 'telnyx' else ''}🌍 Telnyx", callback_data="adm_set_routing_telnyx"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🌐 <b>Маршрутизация звонков:</b>", reply_markup=kb)

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
        bot.reply_to(m, "❌ Введите число.")

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
        bot.reply_to(m, f"✅ Лимит установлен: {new_lim} чел.")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите число.")

if __name__ == "__main__":
    threading.Thread(target=run_webhook_server, daemon=True).start()
    print(">>> GENCALLS БОТ УСПЕШНО ЗАПУЩЕН! СЕКРЕТ ЮМАНИ D2LS1zPM2UPAZ9wLeEVdbx7i АКТИВЕН <<<")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=20)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(3)
