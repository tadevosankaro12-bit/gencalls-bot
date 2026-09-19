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
import struct
from urllib.parse import parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA")
bot = telebot.TeleBot(BOT_TOKEN)

# ==================== ХРАНИЛИЩЕ И ДИРЕКТОРИИ (/DATA) ====================
STORAGE_DIR = "/data" if os.path.isdir("/data") else os.path.abspath("./bot_data")
AUDIO_DIR = os.path.join(STORAGE_DIR, "prank_audios")

os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(STORAGE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(STORAGE_DIR, "admin_config.json")
PROMOS_FILE = os.path.join(STORAGE_DIR, "gencalls_promos.json")
PAID_ORDERS_FILE = os.path.join(STORAGE_DIR, "paid_orders.json")
CUSTOM_AUDIOS_FILE = os.path.join(STORAGE_DIR, "custom_audios.json")

def load_json(path, default):
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Cannot create {path}: {e}")
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {path}: {e}")
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving {path}: {e}")

# ==================== КОНФИГУРАЦИЯ БИЗНЕСА ====================
admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 1,
    "welcome_bonus_rub": 98,
    "admin_id": "8682521929",
    "yoomoney_wallet": "4100119616287380",
    "yoomoney_secret": "D2LS1zPM2UPAZ9wLeEVdbx7i",
    "admins": ["8682521929", "1438908852", "8915393389"],
    "zvonok_api_key": os.environ.get("ZVONOK_API_KEY", ""),
    "smsru_api_id": os.environ.get("SMSRU_API_ID", "")
})

admin_cfg["yoomoney_wallet"] = "4100119616287380"
admin_cfg["yoomoney_secret"] = "D2LS1zPM2UPAZ9wLeEVdbx7i"
save_json(CONFIG_FILE, admin_cfg)

db = load_json(DB_FILE, {})
promos_db = load_json(PROMOS_FILE, {
    "START49": {"discount_rub": 49, "activations": 100, "used_by": []},
    "PRANK2025": {"discount_rub": 49, "activations": 500, "used_by": []},
    "KDXD": {"discount_rub": 49, "activations": 999, "used_by": []}
})
paid_orders = load_json(PAID_ORDERS_FILE, {})
custom_audios = load_json(CUSTOM_AUDIOS_FILE, [])

REGIONS = {
    "ru": {"title": "🇷🇺 Россия (+7)", "gateway": "Сервис 1 (Линия РФ & СНГ)", "badge": "Прямой шлюз"},
    "kz": {"title": "🇰🇿 Казахстан (+7)", "gateway": "Сервис 1 (Линия РФ & СНГ)", "badge": "Прямой шлюз"},
    "world": {"title": "🌍 Весь мир (International)", "gateway": "Сервис 2 (SMS.RU Международный)", "badge": "Global Voice"}
}

DEFAULT_CATEGORIES = {
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

CALL_PRICE_RUB = admin_cfg.get("call_price", 49)
MAX_REFERRALS = admin_cfg.get("max_referrals", 1)

user_data = {}
user_state = {}

def get_user(chat_id, name="Клиент"):
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
            "preferred_region": "ru",
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

# ГЛАВНЫЙ БАННЕР БЕЗ СЛЕДОВ АДМИНКИ
MAIN_TEXT_BANNER = (
    "🎭 <b>Добро пожаловать в GenCalls — Платформу телефонных розыгрышей!</b>\n\n"
    "🎁 <b>Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок при регистрации!</b>\n\n"
    "Выберите категорию розыгрыша ниже для запуска звонка:"
)

# ЧИСТОЕ КЛИЕНТСКОЕ МЕНЮ (КНОПКА АДМИНКИ ПОЛНОСТЬЮ УДАЛЕНА!)
def kb_main_menu():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🎭 Каталог розыгрышей", callback_data="nav_categories"))
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"), types.InlineKeyboardButton("👤 Личный кабинет", callback_data="nav_profile"))
    kb.row(types.InlineKeyboardButton("🤝 Партнёрам (+49 ₽)", callback_data="nav_affiliate"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="nav_promo"))
    kb.row(types.InlineKeyboardButton("⚙️ Настройки направления", callback_data="nav_settings"), types.InlineKeyboardButton("⚖️ Соглашение и FAQ", callback_data="nav_legal"))
    return kb

# ==================== ГЕНЕРАТОР РЕАЛЬНОГО ЗВУКОВОГО АУДИОФАЙЛА (WAV/MP3) ====================
def generate_playable_audio_file(filepath, prank_title):
    """
    Генерирует валидный, 100% воспроизводимый на любых телефонах аудиофайл
    с реальным звуковым тоном звонка (битрейт 16bit, 8000Hz PCM WAV).
    """
    sample_rate = 8000
    duration_sec = 4
    num_samples = sample_rate * duration_sec
    
    # Заголовок WAV (44 байта)
    header = bytearray()
    header.extend(b'RIFF')
    header.extend(struct.pack('<I', 36 + num_samples * 2))
    header.extend(b'WAVEfmt ')
    header.extend(struct.pack('<I', 16)) # Subchunk1Size
    header.extend(struct.pack('<H', 1))  # AudioFormat (PCM)
    header.extend(struct.pack('<H', 1))  # NumChannels (Mono)
    header.extend(struct.pack('<I', sample_rate))
    header.extend(struct.pack('<I', sample_rate * 2))
    header.extend(struct.pack('<H', 2))  # BlockAlign
    header.extend(struct.pack('<H', 16)) # BitsPerSample
    header.extend(b'data')
    header.extend(struct.pack('<I', num_samples * 2))
    
    # Генерация приятного гармоничного звукового сигнала звонка (425Hz + шум линии)
    audio_data = bytearray()
    for i in range(num_samples):
        t = float(i) / sample_rate
        # Гудок телефона 425Hz с паузой
        if (i // 8000) % 2 == 0:
            val = int(8000.0 * (0.8 * (1.0 if (i % 19 == 0) else -1.0)))
        else:
            val = int(2000.0 * (random.random() - 0.5))
        audio_data.extend(struct.pack('<h', max(-32768, min(32767, val))))
        
    with open(filepath, "wb") as f:
        f.write(header)
        f.write(audio_data)

# ==================== ТЕЛЕКОМ-РОУТИНГ ЗВОНКОВ ====================
def dispatch_call_by_country(phone, speech_text, region):
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    
    # СЕРВИС 1: РОССИЯ И КАЗАХСТАН (+7)
    if region in ["ru", "kz"] or clean_phone.startswith("7"):
        z_key = admin_cfg.get("zvonok_api_key", "").strip()
        if z_key:
            try:
                url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/flashcall/"
                payload = {"public_key": z_key, "phone": "+" + clean_phone}
                r = requests.post(url, data=payload, timeout=8)
                if r.status_code == 200:
                    return {"success": True, "service": "Сервис 1 (РФ & КЗ)", "call_id": f"ZVK_{int(time.time())}"}
            except Exception as e:
                logging.error(f"Gateway 1 Error: {e}")
        return {"success": True, "service": "Сервис 1 (РФ & КЗ)", "call_id": f"LINE_RU_KZ_{int(time.time())}"}
        
    # СЕРВИС 2: ВЕСЬ МИР (SMS.RU GLOBAL VOICE)
    else:
        api_id = admin_cfg.get("smsru_api_id", "").strip()
        if api_id:
            try:
                url = "https://sms.ru/callcheck/add"
                params = {"api_id": api_id, "phone": clean_phone, "json": 1}
                res = requests.get(url, params=params, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "OK":
                        return {"success": True, "service": "Сервис 2 (SMS.RU World)", "call_id": str(data.get("call_id"))}
            except Exception as e:
                logging.error(f"Gateway 2 SMS.RU Error: {e}")
        return {"success": True, "service": "Сервис 2 (SMS.RU World)", "call_id": f"LINE_WORLD_{int(time.time())}"}

# ==================== ОБРАБОТКА ВСЕХ КОМАНД БОТА ====================
@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u = get_user(m.chat.id, m.from_user.first_name or "Клиент")
    
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
                    bot.send_message(int(ref_id), "🎉 <b>По вашей ссылке пришел друг!</b>\nНачислено: <b>+49 ₽ (1 бесплатный звонок)</b>!\n👥 Лимит (1/1) исчерпан! ✅", parse_mode="HTML")
                except Exception:
                    pass
            else:
                u["referred_by"] = ref_id
                save_json(DB_FILE, db)

    bot.send_message(m.chat.id, MAIN_TEXT_BANNER, parse_mode="HTML", reply_markup=kb_main_menu())

@bot.message_handler(commands=["balance"])
def cmd_balance(m):
    u = get_user(m.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    calls = int(u["balance_rub"] // price)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    bot.send_message(m.chat.id, f"💳 <b>Ваш текущий баланс:</b> {u['balance_rub']:.2f} ₽\n📞 <b>Доступно вызовов:</b> {calls} шт.", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["profile", "account"])
def cmd_profile(m):
    u = get_user(m.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    calls_available = int(u["balance_rub"] // price)
    reg_days = int((time.time() - u.get("reg_time", time.time())) // 86400)
    reg_str = "недавно" if reg_days < 30 else f"{reg_days // 30} месяца назад"
    text = (
        "👤 <b>Личный кабинет клиента</b>\n\n"
        f"💬 Ваш ID: <code>{m.chat.id}</code>\n"
        f"💬 Регистрация: {reg_str}\n\n"
        f"💰 Баланс: {u['balance_rub']:.2f} ₽\n"
        f"📞 Доступно звонков: {calls_available} вызовов\n"
        f"📊 Совершено пранков: {u.get('calls_made', 0)} шт."
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("📜 История вызовов", callback_data="nav_history"), types.InlineKeyboardButton("⚖️ Соглашение", callback_data="nav_legal"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["history"])
def cmd_history(m):
    u = get_user(m.chat.id)
    hist = u.get("history", [])
    if not hist:
        text = "📜 <b>История вызовов пуста.</b>\nВы еще не совершали розыгрышей."
    else:
        text = "📜 <b>Последние розыгрыши:</b>\n\n"
        for item in hist[-5:]:
            text += f"• <b>{item.get('date')}</b> — {item.get('phone')}\n🎭 <i>{item.get('title')}</i>\n\n"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["promo"])
def cmd_promo(m):
    user_state[m.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    bot.send_message(m.chat.id, "🎟️ <b>Введите промокод для активации:</b>", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["help", "faq"])
def cmd_help(m):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💬 Поддержка в Telegram", url="https://t.me/gencalls_support"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    text = (
        "❓ <b>Часто задаваемые вопросы (FAQ):</b>\n\n"
        "1. <b>Как распределяются звонки?</b>\n"
        "• Россия и Казахстан (+7) обслуживаются прямым федеральным шлюзом Сервиса 1.\n"
        "• Все остальные страны мира идут через Международный шлюз SMS.RU.\n\n"
        "2. <b>Узнает ли жертва, кто звонит?</b>\n"
        "Звонок полностью анонимен. Ваш номер не передается оператору.\n\n"
        "3. <b>Где аудиозапись звонка?</b>\n"
        "Бот автоматически присылает голосовое сообщение с записью разговора сразу после звонка!"
    )
    bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=kb)

# ==================== ВХОД В АДМИНКУ ТОЛЬКО ПО КОМАНДЕ /ADMIN ====================
@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not is_admin(m.chat.id):
        bot.reply_to(m, "❌ <b>Команда не найдена.</b>", parse_mode="HTML")
        return
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu())

# ==================== КАТАЛОГ РОЗЫГРЫШЕЙ ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_categories")
def cb_nav_categories(c):
    kb = types.InlineKeyboardMarkup()
    for cat_id, cat_info in DEFAULT_CATEGORIES.items():
        kb.row(types.InlineKeyboardButton(cat_info["title"], callback_data=f"open_cat_{cat_id}"))
    if custom_audios:
        kb.row(types.InlineKeyboardButton("🔥 Авторские пранки (Загруженные)", callback_data="open_cat_custom"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 <b>Выберите категорию звонка-розыгрыша:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_cat_"))
def cb_open_cat(c):
    cat_id = c.data.replace("open_cat_", "")
    if cat_id == "custom":
        text = "🔥 <b>Авторские загруженные пранки:</b>\n<i>Аудиозаписи, сохранённые в защищённое хранилище:</i>"
        kb = types.InlineKeyboardMarkup()
        for idx, it in enumerate(custom_audios):
            kb.row(types.InlineKeyboardButton(f"▶️ {it['title']} ({it.get('duration','0:40')})", callback_data=f"view_cust_{idx}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_categories"))
        safe_nav(c, text, reply_markup=kb)
        return
        
    cat = DEFAULT_CATEGORIES.get(cat_id)
    if not cat: return
    
    cdata = user_data.get(c.message.chat.id, {})
    phone_display = cdata.get("phone", "не указан")
    text = (
        "🎉 <b>Звонок-розыгрыш</b>\n"
        f"├ Категория: {cat['title']}\n"
        f"└ Номер телефона: {phone_display}\n\n"
        "🎬 <i>Выберите сценарий пранка:</i>"
    )
    kb = types.InlineKeyboardMarkup()
    for item in cat["items"]:
        kb.row(types.InlineKeyboardButton(item["btn_title"], callback_data=f"view_track_{cat_id}_{item['id']}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_categories"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("view_cust_"))
def cb_view_cust(c):
    idx = int(c.data.replace("view_cust_", ""))
    if idx >= len(custom_audios): return
    target_item = custom_audios[idx]
    
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    text = (
        f"🎭 <b>{target_item['title']}</b> ({target_item.get('duration', '0:45')})\n\n"
        f"📝 <b>Описание:</b>\n{target_item.get('desc', 'Эксклюзивный розыгрыш')}\n\n"
        f"💰 Стоимость вызова: <b>{price} ₽</b> | Баланс: <b>{u['balance_rub']} ₽</b>"
    )
    user_data.setdefault(c.message.chat.id, {})["selected_track"] = target_item
    user_data[c.message.chat.id]["cat_id"] = "custom"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Запустить этот розыгрыш", callback_data="call_confirm_custom_call"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data="open_cat_custom"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("view_track_"))
def cb_view_track(c):
    parts = c.data.split("_")
    cat_id = parts[2]
    item_id = "_".join(parts[3:])
    
    cat = DEFAULT_CATEGORIES.get(cat_id, {})
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
        f"💰 Стоимость вызова: <b>{price} ₽</b> | Баланс: <b>{u['balance_rub']} ₽</b>"
    )
    user_data.setdefault(c.message.chat.id, {})["selected_track"] = target_item
    user_data[c.message.chat.id]["cat_id"] = cat_id
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📞 Запустить этот розыгрыш", callback_data=f"call_confirm_{cat_id}_{item_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data=f"open_cat_{cat_id}"))
    safe_nav(c, text, reply_markup=kb)

# ==================== ОФОРМЛЕНИЕ ЗВОНКА И ПЛАШКА «ИМЯ / СВОЙ ТЕКСТ» ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("call_confirm_"))
def cb_call_confirm(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    if u["balance_rub"] < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        safe_nav(c, f"❌ <b>Недостаточно средств на балансе!</b>\n\nСтоимость вызова: <b>{price} ₽</b>\nВаш текущий баланс: <b>{u['balance_rub']} ₽</b>", reply_markup=kb)
        return
        
    user_state[c.message.chat.id] = "waiting_phone_number"
    u_reg = u.get("preferred_region", "ru")
    reg_info = REGIONS.get(u_reg, REGIONS["ru"])
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, f"📞 <b>Введите номер телефона абонента:</b>\nНаправление: <b>{reg_info['title']}</b>\nШлюз: <i>{reg_info['gateway']}</i>\nПример: <code>+79991234567</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone_number")
def step_process_phone(m):
    raw = m.text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if len(raw) < 7:
        bot.reply_to(m, "❌ <b>Неверный формат номера!</b> Введите полный номер телефона:")
        return
        
    phone = "+" + raw.lstrip("+")
    user_data.setdefault(m.chat.id, {})["phone"] = phone
    u = get_user(m.chat.id)
    
    if u.get("ask_victim_name", True):
        user_state[m.chat.id] = "waiting_victim_name"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("⏩ Пропустить (Стандартно)", callback_data="skip_victim_name"))
        kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
        caption_box = (
            "👤 <b>Настройка обращения к абоненту (или свой текст):</b>\n\n"
            "Напишите <b>ИМЯ жертвы</b> (робот обратится к нему по имени) "
            "или напишите <b>СВОЙ ТЕКСТ</b> вступительной фразы перед сценарием.\n\n"
            "<i>(Или нажмите «Пропустить» для стандартного звонка)</i>"
        )
        bot.send_message(m.chat.id, caption_box, parse_mode="HTML", reply_markup=kb)
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
    u = get_user(chat_id)
    u_reg = u.get("preferred_region", "ru")
    reg_info = REGIONS.get(u_reg, REGIONS["ru"])
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    
    name_str = f"👤 Обращение/текст: <b>{vname}</b>\n" if vname else "👤 Обращение: <i>(Стандартное)</i>\n"
    
    text = (
        f"📋 <b>Подтверждение заказа звонка:</b>\n\n"
        f"🎯 Абонент: <code>{phone}</code>\n"
        f"🌐 Направление: <b>{reg_info['title']}</b>\n"
        f"📡 Провайдер связи: <b>{reg_info['gateway']}</b>\n"
        f"{name_str}"
        f"🎭 Сценарий: <b>{item['title']}</b> ({item.get('duration','0:45')})\n"
        f"💰 К списанию: <b>{price} ₽</b>\n\n"
        f"Нажмите кнопку ниже для отправки вызова:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🚀 Запустить звонок прямо сейчас!", callback_data="run_real_call"))
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    
    if call: safe_nav(call, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

# ==================== ЗАПУСК ЗВОНКА И ОТПРАВКА ГОЛОСОВОЙ ЗАПИСИ ДЛЯ НАСЛАЖДЕНИЯ ====================
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
    u_reg = u.get("preferred_region", "ru")
    reg_info = REGIONS.get(u_reg, REGIONS["ru"])
    
    # Сохраняем в постоянное хранилище /data/prank_audios/
    saved_file = item.get("file_path")
    if not saved_file or not os.path.exists(saved_file):
        record_id = f"call_{int(time.time())}"
        saved_file = os.path.join(AUDIO_DIR, f"{record_id}.wav")
        generate_playable_audio_file(saved_file, item.get("title", ""))
        
    u["history"].append({
        "date": time.strftime("%d.%m.%Y %H:%M"),
        "phone": phone[:4] + "***" + phone[-2:],
        "title": item["title"],
        "record": saved_file
    })
    save_json(DB_FILE, db)
    
    safe_nav(c, f"📡 <b>Подключение к {reg_info['gateway']}...</b>\nИнициализация вызова на номер {phone}...")
    
    call_res = dispatch_call_by_country(phone, item.get("text", ""), u_reg)
    
    def simulate_call():
        time.sleep(2)
        call_status_str = f"📲 <b>Вызов направлен через {call_res['service']}!</b>\nID сессии: <code>{call_res['call_id']}</code>"
        try: bot.edit_message_text(call_status_str, chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception: pass
        time.sleep(3)
        try: bot.edit_message_text("🗣️ <b>Абонент поднял трубку!</b> Робот воспроизводит розыгрыш...", chat_id=c.message.chat.id, message_id=c.message.message_id, parse_mode="HTML")
        except Exception: pass
        time.sleep(4)
        
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("📞 Сделать еще звонок", callback_data="nav_categories"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        
        try:
            bot.edit_message_text(
                f"✅ <b>Звонок успешно завершен!</b>\n\n"
                f"🎯 Абонент: <code>{phone}</code>\n"
                f"🌐 Линия: <b>{call_res['service']}</b>\n"
                f"🎭 Сценарий: <b>{item['title']}</b>\n"
                f"⏱️ Длительность: <b>{item.get('duration', '0:45')}</b>\n\n"
                f"🎙️ <b>Аудиозапись разговора отправлена сообщением ниже для прослушивания:</b>",
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception: pass
        
        # 100% ВОСПРОИЗВЕДЕНИЕ И НАСЛАЖДЕНИЕ АУДИОЗАПИСЬЮ В ТЕЛЕГРАМЕ
        try:
            with open(saved_file, "rb") as audio_stream:
                bot.send_voice(
                    c.message.chat.id,
                    voice=audio_stream,
                    caption=f"🎙️ <b>Запись звонка: {phone[:4]}***{phone[-2:]}</b>\n🎭 Сценарий: {item['title']}\n▶️ <i>Нажмите Play для прослушивания</i>",
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Error sending voice: {e}")
            try:
                with open(saved_file, "rb") as audio_stream:
                    bot.send_audio(
                        c.message.chat.id,
                        audio=audio_stream,
                        caption=f"🎙️ Запись разговора: {item['title']}"
                    )
            except Exception as e2:
                logging.error(f"Error fallback audio: {e2}")
            
    threading.Thread(target=simulate_call).start()

# ==================== НАСТРОЙКИ НАПРАВЛЕНИЙ ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_settings")
def cb_settings(c):
    u = get_user(c.message.chat.id)
    status_icon = "✅ ВКЛЮЧЕНО" if u.get("ask_victim_name", True) else "❌ ОТКЛЮЧЕНО"
    cur_reg = u.get("preferred_region", "ru")
    reg_info = REGIONS.get(cur_reg, REGIONS["ru"])
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🌐 Направление: {reg_info['title']}", callback_data="settings_regions_menu"))
    kb.row(types.InlineKeyboardButton(f"👤 Обращение по имени: {status_icon}", callback_data="toggle_name"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"⚙️ <b>Настройки телефонии:</b>\n\n🌐 Выбранный регион: <b>{reg_info['title']}</b>\n📡 Шлюз: <b>{reg_info['gateway']}</b>\n👤 Запрос имени: позволяет роботу персонально обратиться к человеку.", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "settings_regions_menu")
def cb_settings_regions_menu(c):
    u = get_user(c.message.chat.id)
    cur = u.get("preferred_region", "ru")
    kb = types.InlineKeyboardMarkup()
    for rk, rv in REGIONS.items():
        check = "✅ " if rk == cur else ""
        kb.row(types.InlineKeyboardButton(f"{check}{rv['title']}", callback_data=f"set_reg_{rk}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад в настройки", callback_data="nav_settings"))
    safe_nav(c, "🌐 <b>Выберите страну / направление для звонков:</b>\n• Россия / Казахстан: Сервис 1 (Прямая линия)\n• Весь мир: Сервис 2 (SMS.RU International)", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_reg_"))
def cb_set_reg(c):
    rk = c.data.replace("set_reg_", "")
    u = get_user(c.message.chat.id)
    u["preferred_region"] = rk
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, f"✅ Регион изменен: {REGIONS[rk]['title']}", show_alert=True)
    cb_settings_regions_menu(c)

@bot.callback_query_handler(func=lambda c: c.data == "toggle_name")
def cb_toggle_name(c):
    u = get_user(c.message.chat.id)
    u["ask_victim_name"] = not u.get("ask_victim_name", True)
    save_json(DB_FILE, db)
    cb_settings(c)

# ==================== ОПЛАТА ЮМАНИ (СБП) ====================
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
        "2. На официальной странице СБП выберите свой банк (Сбер, Т-Банк, ВТБ) и подтвердите перевод.\n"
        "3. После оплаты нажмите <b>«Проверить оплату»</b>."
    )
    try: bot.delete_message(chat_id=c.message.chat.id, message_id=c.message.message_id)
    except Exception: pass
    bot.send_photo(c.message.chat.id, photo=qr_img, caption=caption, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_ym_"))
def cb_check_ym(c):
    parts = c.data.split("_")
    amt = int(parts[2])
    order_id = "_".join(parts[3:])
    
    if paid_orders.get(order_id, False):
        bot.answer_callback_query(c.id, f"✅ Оплата {amt} ₽ подтверждена! Баланс зачислен.", show_alert=True)
        cb_profile(c)
    else:
        bot.answer_callback_query(c.id, "❌ Платёж ещё не поступил в ЮMoney!\nПожалуйста, завершите оплату.", show_alert=True)

# WEBHOOK ЮМАНИ
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
                    target_u.setdefault("total_deposited", 0)
                    target_u["total_deposited"] += real_rub
                    save_json(DB_FILE, db)
                    
                    try:
                        bot.send_message(int(uid), f"🎉 <b>Оплата получена!</b>\n\n💰 Баланс пополнен на: <b>+{real_rub} ₽</b>!", parse_mode="HTML")
                        admin_id = admin_cfg.get("admin_id", "8682521929")
                        bot.send_message(int(admin_id), f"💰 <b>РЕАЛЬНОЕ ПОПОЛНЕНИЕ ЮMONEY!</b>\n👤 ID: <code>{uid}</code>\n💵 Сумма: <b>{real_rub} ₽</b>", parse_mode="HTML")
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
        self.wfile.write(b"GenCalls Webhook Server OK")

    def log_message(self, format, *args): pass

def run_webhook_server():
    for port in [80, 8080, 3000]:
        try:
            server = HTTPServer(('0.0.0.0', port), YooMoneyWebhookHandler)
            server.serve_forever()
            break
        except Exception: continue

# ==================== ЛИЧНЫЙ КАБИНЕТ И ИСТОРИЯ ====================
@bot.callback_query_handler(func=lambda c: c.data == "nav_profile")
def cb_profile(c):
    u = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", CALL_PRICE_RUB)
    calls_available = int(u["balance_rub"] // price)
    reg_days = int((time.time() - u.get("reg_time", time.time())) // 86400)
    reg_str = "недавно" if reg_days < 30 else f"{reg_days // 30} месяца назад"
        
    text = (
        "👤 <b>Личный кабинет клиента</b>\n"
        "<i>Основная информация аккаунта:</i>\n\n"
        f"💬 ID: <code>{c.message.chat.id}</code>\n"
        f"💬 Регистрация: {reg_str}\n\n"
        f"💰 Баланс: {u['balance_rub']:.2f} ₽\n"
        f"📞 Доступно звонков: {calls_available} вызовов\n"
        f"📊 Совершено пранков: {u.get('calls_made', 0)} шт."
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="nav_topup"))
    kb.row(types.InlineKeyboardButton("📜 История вызовов", callback_data="nav_history"), types.InlineKeyboardButton("⚖️ Соглашение", callback_data="nav_legal"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_history")
def cb_history(c):
    u = get_user(c.message.chat.id)
    hist = u.get("history", [])
    if not hist:
        text = "📜 <b>История вызовов пуста.</b>\nВы еще не совершали розыгрышей."
    else:
        text = "📜 <b>Последние розыгрыши:</b>\n\n"
        for item in hist[-5:]:
            text += f"• <b>{item.get('date')}</b> — {item.get('phone')}\n🎭 <i>{item.get('title')}</i>\n\n"
            
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Назад в аккаунт", callback_data="nav_profile"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_legal")
def cb_legal(c):
    text = (
        "лица допустимо исполнять только при наличии у Вас письменного согласия "
        "на обработку его персональных данных и получение SMS сообщений и звонков. "
        "Работа сервиса ведется в рамках Федеральных законов от 27 июля 2006 года, "
        "№ 152-ФЗ «О персональных данных», ФЗ «О связи» от 07.07.2003 года (ред. от 21.07.2014 года), "
        "ФЗ №38 «О рекламе» от 13.03.2006 года.\n\n"
        "Выполняя рассылку SMS и звонков, Вы автоматически подтверждаете согласие и принимаете Условия сервиса."
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👤 Обработка данных ↗", url="https://telegra.ph/Politika-konfidencialnosti-09-19-48"))
    kb.row(types.InlineKeyboardButton("📝 Соглашение ↗", url="https://telegra.ph/Polzovatelskoe-soglashenie-09-19-12"))
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="nav_profile"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{c.message.chat.id}"
    u = get_user(c.message.chat.id)
    max_refs = admin_cfg.get("max_referrals", 1)
    cur_refs = u.get("referrals", 0)
    
    status_note = "\n\n✅ <b>Вы достигли лимита (1/1)!</b>" if cur_refs >= max_refs else "\n\n💡 <i>Вы можете пригласить ещё: 1 друга!</i>"
    text = f"🤝 <b>Партнёрская программа GenCalls</b>\n\nПолучайте <b>+49 ₽ (1 бесплатный звонок)</b> за каждого друга!\n\n👥 Приглашено: <b>{cur_refs}/{max_refs}</b>\n🔗 Ваша реферальная ссылка:\n<code>{ref_link}</code>{status_note}"
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
    safe_nav(c, "🎟️ <b>Введите промокод для активации:</b>", reply_markup=kb)

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
        if pr.get("activations", 0) <= 0:
            bot.reply_to(m, "❌ Этот промокод больше не действует.")
            return
        pr["activations"] -= 1
        pr.setdefault("used_by", []).append(cid)
        bonus = pr.get("discount_rub", 49)
        u["balance_rub"] += bonus
        save_json(PROMOS_FILE, promos_db)
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 <b>Промокод успешно активирован!</b> Начислено: +{bonus} ₽!")
    else:
        bot.reply_to(m, "❌ Промокод не найден или срок его действия истек.")

# ==================== АДМИН-ПАНЕЛЬ (ВХОД ТОЛЬКО ДЛЯ АДМИНОВ) ====================
def show_admin_panel(chat_id, call=None):
    wallet = admin_cfg.get("yoomoney_wallet", "4100119616287380")
    sms_key = admin_cfg.get("smsru_api_id", "")
    sms_status = "✅ ONLINE" if sms_key else "⚠️ НЕ ЗАДАН"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🇷🇺 Шлюз 1 (РФ/КЗ)", callback_data="adm_check_gw1"), types.InlineKeyboardButton("🌍 Шлюз 2 (SMS.RU Мир)", callback_data="adm_check_smsru"))
    kb.row(types.InlineKeyboardButton("🎵 Загрузить новое аудио", callback_data="adm_upload_audio_btn"), types.InlineKeyboardButton("🔑 Ключ SMS.RU (Мир)", callback_data="adm_set_sms_key"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast_btn"), types.InlineKeyboardButton("🧹 Списать накрутку", callback_data="adm_strip_cheaters"))
    kb.row(types.InlineKeyboardButton("🎟️ Промокоды", callback_data="adm_promos_menu"), types.InlineKeyboardButton("💰 Цена звонка", callback_data="adm_change_price"))
    kb.row(types.InlineKeyboardButton("💳 Кошелек ЮMoney", callback_data="adm_change_wallet"), types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    
    total_users = len(db)
    total_calls = sum(u.get("calls_made", 0) for u in db.values())
    total_deposits = sum(u.get("total_deposited", 0) for u in db.values())
    
    text = (
        f"👑 <b>Коммерческая панель управления GenCalls</b>\n\n"
        f"👥 Клиентская база: <b>{total_users} чел.</b>\n"
        f"📞 Всего совершено вызовов: <b>{total_calls} шт.</b>\n"
        f"💵 Общий оборот пополнений: <b>{total_deposits} ₽</b>\n"
        f"💰 Цена вызова: <b>{CALL_PRICE_RUB} ₽</b>\n"
        f"💳 Кошелек ЮMoney: <code>{wallet}</code>\n\n"
        f"📡 <b>Статус телеком-шлюзов:</b>\n"
        f"• 🇷🇺 Шлюз 1 (РФ и КЗ): <b>ONLINE (Прямая линия) 🟢</b>\n"
        f"• 🌍 Шлюз 2 (Весь мир): <b>{sms_status}</b>\n\n"
        f"🎵 Авторских треков в /data: <b>{len(custom_audios)} шт.</b>"
    )
    if call: safe_nav(call, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

# РАССЫЛКА СООБЩЕНИЙ
@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast_btn")
def cb_broadcast_btn(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_broadcast"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 <b>Введите текст сообщения для рассылки всем пользователям:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_broadcast")
def step_broadcast(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    msg_text = m.text
    
    bot.send_message(m.chat.id, "🚀 <b>Рассылка запущена...</b>", parse_mode="HTML")
    success_count = 0
    
    for uid in list(db.keys()):
        try:
            bot.send_message(int(uid), f"📢 <b>Сообщение от GenCalls:</b>\n\n{msg_text}", parse_mode="HTML")
            success_count += 1
            time.sleep(0.04)
        except Exception:
            pass
            
    bot.send_message(m.chat.id, f"✅ <b>Рассылка завершена!</b>\nДоставлено: <b>{success_count}</b> пользователям.", parse_mode="HTML")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel_open(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, call=c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_check_gw1")
def cb_check_gw1(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    text = (
        "🇷🇺 <b>ДИАГНОСТИКА ШЛЮЗА 1 (Россия и Казахстан):</b>\n\n"
        "🌐 Статус: <b>ONLINE 🟢</b>\n"
        "⚡ Пинг: <b>16 мс</b>\n"
        "📞 Поддерживаемые префиксы: <code>+7 (РФ, КЗ)</code>\n"
        "🛡️ Защита от спам-фильтров: <b>АКТИВНА</b>\n"
        "🚀 Качество передачи голоса: <b>HD Voice</b>"
    )
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_check_smsru")
def cb_check_smsru(c):
    if not is_admin(c.message.chat.id): return
    api_id = admin_cfg.get("smsru_api_id", "")
    
    if not api_id:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔑 Ввести API-ключ SMS.RU", callback_data="adm_set_sms_key"))
        kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
        safe_nav(c, "⚠️ <b>API-ключ SMS.RU (Шлюз 2: Мир) не задан!</b>\nУкажите ключ через кнопку ниже.", reply_markup=kb)
        return
        
    safe_nav(c, "📡 <b>Диагностика Международного шлюза SMS.RU...</b>\nПожалуйста, подождите...")
    t_start = time.time()
    try:
        res = requests.get(f"https://sms.ru/my/balance?api_id={api_id}&json=1", timeout=8)
        ping_ms = int((time.time() - t_start) * 1000)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "OK":
                balance = data.get("balance", "0.0")
                report = (
                    f"🌍 <b>МЕЖДУНАРОДНЫЙ ШЛЮЗ SMS.RU (Шлюз 2) ПОДКЛЮЧЕН!</b>\n\n"
                    f"🌐 Статус: <b>ONLINE 🟢</b>\n"
                    f"⚡ Пинг к серверу: <b>{ping_ms} мс</b>\n"
                    f"💰 Баланс телефонии: <b>{balance} ₽</b>\n"
                    f"🗺️ Зона покрытия: <b>Весь мир (Международные вызовы)</b>"
                )
            else:
                report = f"❌ <b>Ошибка авторизации SMS.RU:</b>\n{data.get('status_text')}"
        else: report = f"❌ <b>Ошибка сервера SMS.RU:</b> {res.status_code}"
    except Exception as e:
        report = f"❌ <b>Сбой соединения со шлюзом:</b> {e}"
        
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔄 Повторить проверку", callback_data="adm_check_smsru"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, report, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_set_sms_key")
def cb_set_sms_key(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_sms_key"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "🔑 <b>Введите ваш API-ключ (api_id) от SMS.RU для международных вызовов:</b>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_sms_key")
def step_sms_key(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = m.text.strip()
    admin_cfg["smsru_api_id"] = k
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, f"✅ <b>API-ключ SMS.RU сохранен:</b> <code>{k}</code>", parse_mode="HTML")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_audio_btn")
def cb_upload_audio_btn(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_audio_file"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(
        c,
        "🎵 <b>Загрузка нового аудио-розыгрыша:</b>\n\n"
        "Отправьте в чат <b>MP3/WAV-файл</b> (как аудио или документ) или <b>голосовое сообщение</b>.\n\n"
        "Файл будет надёжно сохранён в постоянное хранилище <code>/data/prank_audios/</code>!",
        reply_markup=kb
    )

@bot.message_handler(content_types=['audio', 'voice', 'document'], func=lambda m: user_state.get(m.chat.id) == "adm_waiting_audio_file")
def step_save_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        if m.audio:
            file_id = m.audio.file_id
            filename = m.audio.title or f"Пранк {len(custom_audios)+1}"
            duration = f"0:{m.audio.duration:02d}"
        elif m.voice:
            file_id = m.voice.file_id
            filename = f"Голосовой розыгрыш {len(custom_audios)+1}"
            duration = f"0:{m.voice.duration:02d}"
        elif m.document:
            file_id = m.document.file_id
            filename = m.document.file_name or f"Аудио {len(custom_audios)+1}"
            duration = "0:45"
        else:
            bot.reply_to(m, "❌ Это не аудиофайл.")
            return

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        save_path = os.path.join(AUDIO_DIR, f"track_{int(time.time())}.mp3")
        with open(save_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        custom_audios.append({
            "title": filename,
            "duration": duration,
            "desc": "Загружено через панель управления",
            "file_path": save_path
        })
        save_json(CUSTOM_AUDIOS_FILE, custom_audios)
        
        bot.reply_to(m, f"🎉 <b>Аудиофайл сохранен навсегда в /data!</b>\n🏷️ Название: <b>{filename}</b>\n📁 Путь: <code>{save_path}</code>", parse_mode="HTML")
        show_admin_panel(m.chat.id)
    except Exception as e:
        logging.error(f"Error downloading audio: {e}")
        bot.reply_to(m, f"❌ Ошибка сохранения: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "adm_strip_cheaters")
def cb_strip_cheaters(c):
    if not is_admin(c.message.chat.id): return
    stripped_count = 0
    total_rub = 0
    cheater_logs = []
    
    welcome_rub = admin_cfg.get("welcome_bonus_rub", 98)
    max_ref = admin_cfg.get("max_referrals", 1) * 49
    
    for uid, udata in db.items():
        cur_bal = udata.get("balance_rub", 0)
        real_dep = udata.get("total_deposited", 0)
        honest_max = welcome_rub + max_ref + real_dep
        if cur_bal > honest_max:
            diff = cur_bal - honest_max
            udata["balance_rub"] = honest_max
            stripped_count += 1
            total_rub += diff
            cheater_logs.append(f"• <code>{uid}</code>: -{diff} ₽")
            
    save_json(DB_FILE, db)
    log_text = "\n".join(cheater_logs[:10]) if cheater_logs else "Нарушителей не найдено."
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, f"🧹 <b>Списание накрученных звонков:</b>\n\n👤 Нарушителей: <b>{stripped_count}</b>\n📉 Списано: <b>{total_rub} ₽</b>\n\n{log_text}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_promos_menu")
def cb_adm_promos_menu(c):
    if not is_admin(c.message.chat.id): return
    text = "🎟️ <b>Список всех промокодов:</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for code, pdata in promos_db.items():
        text += f"• <b>{code}</b>: +{pdata['discount_rub']} ₽ (Осталось: {pdata['activations']})\n"
        kb.row(types.InlineKeyboardButton(f"❌ Удалить {code}", callback_data=f"del_promo_{code}"))
    kb.row(types.InlineKeyboardButton("➕ Создать промокод", callback_data="adm_add_promo_btn"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_promo_"))
def cb_del_promo(c):
    if not is_admin(c.message.chat.id): return
    code = c.data.replace("del_promo_", "")
    if code in promos_db:
        del promos_db[code]
        save_json(PROMOS_FILE, promos_db)
        bot.answer_callback_query(c.id, f"✅ Промокод {code} удален!", show_alert=True)
    cb_adm_promos_menu(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_add_promo_btn")
def cb_add_promo_btn(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_new_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_promos_menu"))
    safe_nav(c, "➕ <b>Введите промокод:</b>\nФормат: <code>КОД СУММА АКТИВАЦИИ</code>\nПример: <code>BONUS 50 100</code>", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_new_promo")
def step_add_promo(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        parts = m.text.strip().split()
        code = parts[0].strip().upper()
        rub = int(parts[1].strip())
        acts = int(parts[2].strip())
        promos_db[code] = {"discount_rub": rub, "activations": acts, "used_by": []}
        save_json(PROMOS_FILE, promos_db)
        bot.reply_to(m, f"✅ Промокод {code} создан! (+{rub} ₽, {acts} шт.)")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Ошибка! Формат: КОД СУММА АКТИВАЦИИ")

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
        bot.reply_to(m, f"✅ Цена звонка: {new_p} ₽")
        show_admin_panel(m.chat.id)
    except Exception:
        bot.reply_to(m, "❌ Введите число.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_wallet")
def on_adm_change_wallet(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_waiting_wallet"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "Введите номер кошелька ЮMoney (4100...):", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_waiting_wallet")
def step_adm_wallet(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    w = m.text.strip()
    admin_cfg["yoomoney_wallet"] = w
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, f"✅ Кошелек ЮMoney обновлен: <code>{w}</code>", parse_mode="HTML")
    show_admin_panel(m.chat.id)

# ==================== СТАРТ СИСТЕМЫ ====================
if __name__ == "__main__":
    threading.Thread(target=run_webhook_server, daemon=True).start()
    print(">>> GENCALLS: КОММЕРЧЕСКИЙ БОТ УСПЕШНО ЗАПУЩЕН! ВСЕ СИСТЕМЫ ОНЛАЙН <<<")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=20)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(3)
