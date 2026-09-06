import os, json, telebot, requests, time, threading, logging, uuid
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ================= ГЛАВНЫЕ НАСТРОЙКИ =================
TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
ADMIN_IDS = ["8682521929", "8915393389"]
PRIMARY_ADMIN_ID = "8682521929"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Файлы динамической конфигурации (код менять не нужно, бот сам всё сохраняет)
DB_FILE = os.path.join(BASE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
PROMO_FILE = os.path.join(BASE_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(BASE_DIR, "gencalls_blacklist.json")
CUSTOM_PRANKS_FILE = os.path.join(BASE_DIR, "gencalls_pranks.json")
AUDIO_CACHE_FILE = os.path.join(BASE_DIR, "audio_file_cache.json")

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

# ДИНАМИЧЕСКИЙ КОНФИГ — УПРАВЛЯЕТСЯ ИЗ TELEGRAM
admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 3,
    "admin_id": PRIMARY_ADMIN_ID,
    "sber_card": "2202 2000 1234 5678",
    "sber_phone": "+7 (999) 123-45-67",
    "sber_recipient": "Тадевос К. (Сбербанк)",
    "channel_url": "https://t.me/gencalls_channel",
    "zvonok_key": "d0808ab7450fca32147a9285018fe7a5",
    "campaign_id": "1783540036",
    "smsru_key": "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF",
    "support": "tadevosankaro12"
})
save_json(CONFIG_FILE, admin_cfg)

db = load_json(DB_FILE, {})
promocodes = load_json(PROMO_FILE, {"GEN2026": {"rub": 49, "uses": 100, "used_by": []}})
blacklist = load_json(BLACKLIST_FILE, [])
audio_cloud_vault = load_json(AUDIO_CACHE_FILE, {})

DEFAULT_PRANKS = {
    "babka": {"title": "👵 Бабка Лидия (Долг)", "tag": "ХИТ 🔥", "dur": 35, "desc": "Скандальная пенсионерка обвиняет в краже пенсии и требует вернуть долг с угрозами участковым.", "file": "babka.mp3", "public": True},
    "tulip": {"title": "🌷 Тюльпаны оптом", "tag": "ТОП 🌸", "dur": 40, "desc": "Срочная доставка 500 тюльпанов на свадьбу прямо сейчас: «Выходите забирайте, иначе завянут!»", "file": "tulip.mp3", "public": True},
    "rkn": {"title": "🏛️ Роскомнадзор (Блокировка)", "tag": "ШОК ⚠️", "dur": 45, "desc": "Официальное предупреждение: зафиксирована подозрительная активность, ваш интернет будет заблокирован.", "file": "rkn.mp3", "public": True},
    "django": {"title": "🕺 Джанго стриптизер", "tag": "18+ 🔞", "dur": 38, "desc": "Приватный стриптизер звонит в домофон: «Я уже в костюме с маслом у вашей двери, открывайте!»", "file": "django.mp3", "public": True},
    "govnovoz": {"title": "🚛 Ассенизатор (Шланг)", "tag": "УГАР 😂", "dur": 30, "desc": "Машина приехала откачивать септик прямо во двор: «Куда шланг кидать, открывайте ворота!»", "file": "govnovoz.mp3", "public": True},
    "courier": {"title": "🍕 Голодный курьер", "tag": "НОВОЕ 🍕", "dur": 32, "desc": "Курьер признаётся: «Вы долго не открывали, я не сдержался и съел вашу пиццу, простите...»", "file": "courier.mp3", "public": True}
}

pranks_db = load_json(CUSTOM_PRANKS_FILE, DEFAULT_PRANKS)
for k, v in DEFAULT_PRANKS.items():
    if k not in pranks_db: pranks_db[k] = v
save_json(CUSTOM_PRANKS_FILE, pranks_db)

PACKAGES = {
    "pkg_1": {"title": "1 звонок", "rub": 49, "badge": "Старт"},
    "pkg_5": {"title": "5 звонков", "rub": 149, "badge": "🔥 -40%"},
    "pkg_15": {"title": "15 звонков", "rub": 299, "badge": "👑 Хит"},
    "pkg_50": {"title": "50 звонков", "rub": 699, "badge": "VIP"}
}

def is_admin(uid):
    uid_str = str(uid).strip()
    return uid_str in ADMIN_IDS or uid_str == PRIMARY_ADMIN_ID

def get_user(uid, uname="Друг"):
    s_uid = str(uid).strip()
    is_new = False
    if s_uid not in db:
        price = admin_cfg.get("call_price", 49)
        db[s_uid] = {
            "name": uname,
            "balance_rub": price * 2,  # 2 БЕСПЛАТНЫХ ЗВОНКА НА СТАРТЕ
            "calls_history": [],
            "referrals": 0,
            "referred_by": None,
            "reg_date": datetime.now().strftime("%d.%m.%Y"),
            "routing_mode": "auto"
        }
        save_json(DB_FILE, db)
        is_new = True
    return db[s_uid], is_new

def parse_phone(text):
    if not text: return None
    digits = "".join(filter(str.isdigit, text.strip()))
    if not digits: return None
    if len(digits) == 10 and digits.startswith("9"): return "7" + digits
    elif len(digits) == 11 and digits.startswith("8"): return "7" + digits[1:]
    return digits

# ================= АВТОНОМНЫЙ ЦИКЛ АУДИО =================
def ensure_fallback_audio(key, filename):
    path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(path) or os.path.getsize(path) < 100:
        mp3_silence = b'\xff\xfb\x90\x00' + b'\x00' * 1024
        try:
            with open(path, "wb") as f:
                f.write(mp3_silence * 15)
        except Exception: pass
    return path

def get_or_create_audio(key):
    if key in audio_cloud_vault and audio_cloud_vault[key]:
        return audio_cloud_vault[key], "cloud"
    p = pranks_db.get(key, {})
    fn = p.get("file", f"{key}.mp3")
    for fld in [AUDIO_DIR, BASE_DIR]:
        local_p = os.path.join(fld, fn)
        if os.path.exists(local_p) and os.path.getsize(local_p) > 200:
            return local_p, "file"
    return ensure_fallback_audio(key, fn), "file"

# ================= ТЕЛЕФОНИЯ =================
def call_zvonok_campaign(phone):
    url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    params = {
        "campaign_id": admin_cfg.get("campaign_id", "1783540036"),
        "phone": f"+{phone}",
        "public_key": admin_cfg.get("zvonok_key", "d0808ab7450fca32147a9285018fe7a5"),
        "check_duplicate": "0",
        "record": "1"
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=12)
        res = r.json()
        if isinstance(res, dict):
            if res.get("status") == "error" or "error" in res:
                err_msg = res.get("data") or res.get("message") or res.get("error") or str(res)
                return False, f"Zvonok: {err_msg}", None
            call_id = res.get("call_id") or (res.get("data", {}).get("call_id") if isinstance(res.get("data"), dict) else None)
            return True, str(call_id or f"ZV-{int(time.time())}"), "zvonok"
        return False, f"Zvonok: {r.text[:100]}", None
    except Exception as e:
        return False, f"Zvonok: {str(e)}", None

def call_smsru_smart(phone):
    sms_key = admin_cfg.get("smsru_key", "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF")
    for user_ip in ["185.129.100.1", "91.240.85.5", "127.0.0.1"]:
        for url, params in [
            ("https://sms.ru/code/call", {"phone": phone, "api_id": sms_key, "json": 1, "user_ip": user_ip}),
            ("https://sms.ru/callcheck/add", {"phone": phone, "api_id": sms_key, "json": 1, "user_ip": user_ip})
        ]:
            try:
                r = requests.get(url, params=params, timeout=8)
                res = r.json()
                if res.get("status") == "OK":
                    cid = res.get("call_id") or res.get("check_id") or res.get("code") or f"SMS-{int(time.time())}"
                    return True, str(cid), "smsru"
            except Exception: pass
            time.sleep(0.3)
    return False, "SMS.RU: Маршрут временно недоступен", None

def track_call_and_send_record(chat_id, call_id, phone, prank_title, service_type):
    time.sleep(30)
    record_url = None
    if service_type == "zvonok":
        for _ in range(3):
            try:
                status_url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call_by_id/"
                params = {"call_id": call_id, "public_key": admin_cfg.get("zvonok_key")}
                r = requests.get(status_url, params=params, verify=False, timeout=8)
                res = r.json()
                record_url = res.get("record_url") or res.get("data", {}).get("record_url")
                if record_url: break
            except Exception: pass
            time.sleep(8)
            
    if record_url:
        try:
            bot.send_audio(
                chat_id, record_url, 
                title=f"Реакция ({prank_title})", performer="GenCalls Запись",
                caption=f"🎉 **Звонок завершён! Запись разговора готова!**\n\n📞 Номер: `+{phone}`\n🎭 Розыгрыш: **{prank_title}**",
                parse_mode="Markdown"
            )
        except Exception: pass

def process_call_async(chat_id, phone, prank_key, p_title, wait_msg_id):
    u, _ = get_user(chat_id)
    price = admin_cfg.get("call_price", 49)
    rmode = u.get("routing_mode", "auto")
    use_service = "zvonok" if (rmode == "zvonok" or (rmode == "auto" and phone.startswith("7"))) else "smsru"
    service_name = "🇷🇺 Zvonok (+7)" if use_service == "zvonok" else "🌍 SMS.RU Voice"

    success = False
    call_id = None
    service_type = "zvonok"

    if use_service == "zvonok":
        success, call_id, service_type = call_zvonok_campaign(phone)
        if not success:
            success_fb, call_id_fb, service_type = call_smsru_smart(phone)
            if success_fb: success, call_id, service_name = True, call_id_fb, "🌍 SMS.RU (Резерв)"
    else:
        success, call_id, service_type = call_smsru_smart(phone)
        if not success and phone.startswith("7"):
            success_zb, call_id_zb, service_type = call_zvonok_campaign(phone)
            if success_zb: success, call_id, service_name = True, call_id_zb, "🇷🇺 Zvonok (Резерв)"

    if not success:
        try: bot.edit_message_text(f"❌ **Не удалось совершить вызов!**\n\nОтвет: `{call_id}`\n💰 Баланс НЕ списан.", chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id))
        except Exception: pass
        return

    u["balance_rub"] = max(0, u["balance_rub"] - price)
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m %H:%M"), "phone": phone, "prank": p_title, "service": service_name, "call_id": str(call_id)
    })
    save_json(DB_FILE, db)

    try:
        bot.edit_message_text(
            f"✅ **Звонок запущен!**\n\n📞 Номер: `+{phone}`\n🌐 Канал: **{service_name}**\n🎭 Розыгрыш: **{p_title}**\n💰 Остаток: **{u['balance_rub']} ₽** ({u['balance_rub'] // price} 📞)\n\n🎙️ _Запись разговора придёт в чат сразу после звонка!_",
            chat_id, wait_msg_id, parse_mode="Markdown", reply_markup=kb_main_menu(chat_id)
        )
    except Exception: pass
    threading.Thread(target=track_call_and_send_record, args=(chat_id, call_id, phone, p_title, service_type), daemon=True).start()

def kb_main_menu(uid):
    u, _ = get_user(uid)
    price = admin_cfg.get("call_price", 49)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // price
    rmode = u.get("routing_mode", "auto")
    rmode_label = "⚙️ Маршрут: 🇷🇺 РФ (+7)" if rmode == "zvonok" else ("⚙️ Маршрут: 🌍 SMS.RU" if rmode == "smsru" else "⚙️ Маршрут: ⚡ Авто-шлюз")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Открыть каталог розыгрышей", callback_data="catalog"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton(rmode_label, callback_data="nav_routing"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🤝 Партнёрам", callback_data="nav_affiliate"),
        types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo")
    )
    kb.row(
        types.InlineKeyboardButton("📢 Наш Telegram-канал", url=admin_cfg.get("channel_url")),
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank")
    )
    return kb

def safe_nav(c, text, reply_markup=None):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    try: bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        try: bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception: pass
        bot.send_message(c.message.chat.id, text, parse_mode="Markdown", reply_markup=reply_markup)

MAIN_TEXT_BANNER = (
    "🎭 **GenCalls — Пранк-Звонки с записью реакции!**\n\n"
    "🎁 **Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!**\n\n"
    "🕵️‍♂️ **Анонимность 100%** — ваш номер скрыт.\n"
    "🎵 **MP3-Плеер** — слушайте пранки перед звонком!\n"
    "🎙️ **Запись реакции** — запись разговора прямо в этот чат!\n"
    "💳 **Оплата Сбербанк / СБП** без комиссии по чекам.\n\n"
    "👇 _Выберите пранк и разыграйте друга:_"
)

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u, is_new = get_user(m.chat.id, m.from_user.first_name or "Друг")
    welcome = MAIN_TEXT_BANNER
    if is_new:
        welcome = f"🎉 **Добро пожаловать в GenCalls!**\n\n🎁 Мы подарили вам **2 БЕСПЛАТНЫХ ЗВОНКА**!\n\n" + MAIN_TEXT_BANNER
    bot.send_message(m.chat.id, welcome, parse_mode="Markdown", reply_markup=kb_main_menu(m.chat.id))

@bot.message_handler(commands=["catalog", "pranks"])
def cmd_catalog(m):
    admin_mode = is_admin(m.chat.id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        if v.get("public", True) or admin_mode:
            kb.row(types.InlineKeyboardButton(f"🎵 {v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    bot.send_message(m.chat.id, "🎭 **Каталог голосовых розыгрышей:**", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog_cb(c):
    admin_mode = is_admin(c.message.chat.id)
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        if v.get("public", True) or admin_mode:
            kb.row(types.InlineKeyboardButton(f"🎵 {v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 **Каталог голосовых розыгрышей:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({price} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    desc_text = f"🎭 **{p['title']}** [{p.get('tag', 'ТОП')}]\n\n💬 **Сценарий:** {p.get('desc', '')}\n\n🎙️ _После звонка запись разговора придёт в чат!_"
    audio_source, source_type = get_or_create_audio(k)
    try:
        bot.answer_callback_query(c.id)
        if source_type == "cloud":
            bot.send_audio(c.message.chat.id, audio_source, title=p['title'], performer="GenCalls", caption=desc_text, parse_mode="Markdown", reply_markup=kb)
        else:
            with open(audio_source, "rb") as a_file:
                sent = bot.send_audio(c.message.chat.id, a_file, title=p['title'], performer="GenCalls", caption=desc_text, parse_mode="Markdown", reply_markup=kb)
                if sent.audio:
                    audio_cloud_vault[k] = sent.audio.file_id
                    save_json(AUDIO_CACHE_FILE, audio_cloud_vault)
        return
    except Exception:
        safe_nav(c, desc_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_call_"))
def on_setup_call(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    if u.get("balance_rub", 0) < price:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
        safe_nav(c, f"❌ **Недостаточно средств**\n\nЦена: **{price} ₽**\nБаланс: **{u.get('balance_rub', 0)} ₽**", reply_markup=kb)
        return
    k = c.data.replace("setup_call_", "")
    user_data[c.message.chat.id] = {"prank": k}
    user_state[c.message.chat.id] = "waiting_phone"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📱 **Введите номер телефона жертвы:**\n\n• Россия: `+79991234567`\n• Армения: `+374...`", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def step_phone_input(m):
    chat_id = m.chat.id
    phone = parse_phone(m.text)
    if not phone or len(phone) < 8 or phone in blacklist:
        bot.reply_to(m, "❌ Номер некорректен или находится в защитном списке бота.")
        return
    user_state[chat_id] = None
    prank_key = user_data.get(chat_id, {}).get("prank", "babka")
    p = pranks_db.get(prank_key, pranks_db["babka"])
    w = bot.send_message(chat_id, f"🚀 _Набираем +{phone}..._")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, p["title"], w.message_id), daemon=True).start()

# ================= ОПЛАТА СБЕРБАНК =================
@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['title']} — {p['rub']} ₽ ({p['badge']})", callback_data=f"pay_sber_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "💳 **Пополнение баланса через Сбербанк / СБП:**\n\nВыберите пакет:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_sber_"))
def on_pay_sber(c):
    pid = c.data.replace("pay_sber_", "")
    pkg = PACKAGES.get(pid)
    if not pkg: return
    uid = c.message.chat.id
    user_data[uid] = {"pending_amount": pkg["rub"]}
    
    text = (
        f"🟢 **Оплата Сбербанк / СБП**\n\n"
        f"📦 Пакет: **{pkg['title']}** ({pkg['rub']} ₽)\n\n"
        f"💳 **Реквизиты:**\n"
        f"• Номер карты: `{admin_cfg.get('sber_card')}`\n"
        f"• По номеру телефона (СБП): `{admin_cfg.get('sber_phone')}`\n"
        f"• Банк: **Сбербанк**\n"
        f"• Получатель: **{admin_cfg.get('sber_recipient')}**\n\n"
        f"После перевода нажмите кнопку ниже и отправьте фото чека!"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📤 Отправить чек об оплате", callback_data=f"send_receipt_{pkg['rub']}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("send_receipt_"))
def on_req_receipt(c):
    amount = c.data.replace("send_receipt_", "")
    user_state[c.message.chat.id] = "waiting_receipt_photo"
    user_data[c.message.chat.id] = {"amount": int(amount)}
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="packages_menu"))
    safe_nav(c, f"📸 **Отправьте скриншот чека на {amount} ₽ в чат:**", reply_markup=kb)

@bot.message_handler(content_types=["photo", "document"], func=lambda m: user_state.get(m.chat.id) == "waiting_receipt_photo")
def on_receive_receipt(m):
    chat_id = m.chat.id
    user_state[chat_id] = None
    amount = user_data.get(chat_id, {}).get("amount", 49)
    file_id = m.photo[-1].file_id if m.photo else m.document.file_id
    admin_id = admin_cfg.get("admin_id", PRIMARY_ADMIN_ID)
    
    adm_kb = types.InlineKeyboardMarkup(row_width=2)
    adm_kb.row(
        types.InlineKeyboardButton(f"✅ Подтвердить (+{amount} ₽)", callback_data=f"adm_appr_{chat_id}_{amount}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_decl_{chat_id}")
    )
    caption = f"🧾 **НОВЫЙ ЧЕК!**\n\n👤 От: {m.from_user.first_name} (`{chat_id}`)\n💰 Сумма: **{amount} ₽**"
    try:
        bot.send_photo(int(admin_id), file_id, caption=caption, parse_mode="Markdown", reply_markup=adm_kb)
        bot.reply_to(m, "✅ **Чек отправлен! Баланс пополнится через 1–2 минуты.**", reply_markup=kb_main_menu(chat_id))
    except Exception:
        bot.reply_to(m, "✅ Чек принят.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_appr_"))
def on_admin_approve(c):
    if not is_admin(c.message.chat.id): return
    parts = c.data.split("_")
    uid, amount = parts[2], int(parts[3])
    u, _ = get_user(uid)
    u["balance_rub"] += amount
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Оплата подтверждена!")
    try: bot.edit_message_caption(f"{c.message.caption}\n\n🟢 **ОПЛАЧЕНО (+{amount} ₽) ✅**", c.message.chat.id, c.message.message_id)
    except Exception: pass
    try: bot.send_message(int(uid), f"🎉 **Оплата подтверждена! Начислено: +{amount} ₽**\nБаланс: **{u['balance_rub']} ₽**", reply_markup=kb_main_menu(uid))
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_decl_"))
def on_admin_decline(c):
    if not is_admin(c.message.chat.id): return
    uid = c.data.split("_")[2]
    bot.answer_callback_query(c.id, "❌ Отклонено")
    try: bot.edit_message_caption(f"{c.message.caption}\n\n🔴 **ОТКЛОНЕНО ❌**", c.message.chat.id, c.message.message_id)
    except Exception: pass
    try: bot.send_message(int(uid), f"❌ Чек отклонён. Напишите в поддержку: @{admin_cfg.get('support')}")
    except Exception: pass

# ================= МЕНЮ И НАВИГАЦИЯ =================
@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"👤 **Личный кабинет**\n\n🆔 ID: `{c.message.chat.id}`\n💰 Баланс: **{u['balance_rub']} ₽** ({u['balance_rub'] // price} 📞)", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_help(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Поддержка", url=f"https://t.me/{admin_cfg.get('support')}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🛟 **Поддержка:** Нажмите кнопку ниже для связи с создателем:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_affiliate")
def cb_affiliate(c):
    binfo = bot.get_me()
    link = f"https://t.me/{binfo.username}?start=ref_{c.message.chat.id}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={link}&text=Пранк-звонки+🔥"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"🤝 **Партнёрка:** Приглашайте друзей и получайте +49 ₽!\n\n🔗 Ссылка:\n`{link}`", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def on_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ **Введите промокод:**", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_promo")
def step_promo(m):
    user_state[m.chat.id] = None
    code = m.text.strip().upper()
    u, _ = get_user(m.chat.id)
    if code in promocodes and str(m.chat.id) not in promocodes[code].get("used_by", []):
        promocodes[code].setdefault("used_by", []).append(str(m.chat.id))
        bonus = promocodes[code].get("rub", 49)
        save_json(PROMO_FILE, promocodes)
        u["balance_rub"] += bonus
        save_json(DB_FILE, db)
        bot.reply_to(m, f"🎉 Промокод активирован! +{bonus} ₽ начислено.", reply_markup=kb_main_menu(m.chat.id))
    else:
        bot.reply_to(m, "❌ Промокод недействителен.", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "anti_prank")
def on_anti_prank(c):
    user_state[c.message.chat.id] = "waiting_bl"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🛡️ Введите номер телефона для защиты от звонков:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_bl")
def step_bl(m):
    user_state[m.chat.id] = None
    num = parse_phone(m.text)
    if num and num not in blacklist:
        blacklist.extend([num, f"+{num}"])
        save_json(BLACKLIST_FILE, blacklist)
    bot.reply_to(m, f"🛡️ Номер +{num} защищён от розыгрышей!", reply_markup=kb_main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def on_back(c):
    user_state[c.message.chat.id] = None
    safe_nav(c, MAIN_TEXT_BANNER, reply_markup=kb_main_menu(c.message.chat.id))

# ================= ВСЯ АДМИНКА БЕЗ ПРАВОК В КОДЕ (/admin) =================
@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel_open")
def cb_admin_panel(c):
    if not is_admin(c.message.chat.id): return
    show_admin_panel(c.message.chat.id, c)

def show_admin_panel(chat_id, c=None):
    text = (
        "👑 **Панель Управления БЕЗ Правок Кода**\n\n"
        f"🟢 Сбербанк: `{admin_cfg.get('sber_card')}`\n"
        f"📱 СБП телефон: `{admin_cfg.get('sber_phone')}`\n"
        f"👤 Получатель: `{admin_cfg.get('sber_recipient')}`\n"
        f"🏷️ Цена звонка: **{admin_cfg.get('call_price')} ₽**\n"
        f"🎵 Сохранено аудио: **{len(audio_cloud_vault)}/6**\n"
        f"👥 Пользователей в базе: **{len(db)}**"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("💳 Изменить карту Сбербанка", callback_data="adm_change_sber"))
    kb.row(types.InlineKeyboardButton("🎵 Загрузить аудио в облако", callback_data="adm_upload_audio_menu"))
    kb.row(types.InlineKeyboardButton("🏷️ Изменить цену звонка", callback_data="adm_change_price"))
    kb.row(types.InlineKeyboardButton("💳 Выдать баланс юзеру", callback_data="adm_add_balance"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка сообщений", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_sber")
def on_adm_sber(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_sber"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 **Введите новые реквизиты через запятую:**\n\n_Формат:_ `Карта, Телефон_СБП, ФИО`\n_Пример:_ `2202 2000 1234 5678, +79991234567, Иван И.`", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_sber")
def step_adm_sber(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    parts = [p.strip() for p in m.text.split(",")]
    if len(parts) >= 1: admin_cfg["sber_card"] = parts[0]
    if len(parts) >= 2: admin_cfg["sber_phone"] = parts[1]
    if len(parts) >= 3: admin_cfg["sber_recipient"] = parts[2]
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, "✅ Новые реквизиты сохранены без правок кода!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_price")
def on_adm_price(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_price"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "🏷️ **Введите новую стоимость 1 звонка в рублях:**", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_price")
def step_adm_price(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        p = int("".join(filter(str.isdigit, m.text)))
        admin_cfg["call_price"] = p
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Цена звонка изменена на {p} ₽!")
    except Exception: pass
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_audio_menu")
def on_upload_menu(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        kb.row(types.InlineKeyboardButton(f"🎵 {v['title']}", callback_data=f"adm_up_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎵 **Выберите розыгрыш для прикрепления аудио:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_up_"))
def on_sel_up(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_up_", "")
    user_data[c.message.chat.id] = {"prank_up": k}
    user_state[c.message.chat.id] = "adm_audio_file"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_upload_audio_menu"))
    safe_nav(c, f"🎵 **Просто скиньте аудиофайл или голосовое в чат:**", reply_markup=kb)

@bot.message_handler(content_types=["audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_audio_file")
def step_adm_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("prank_up")
    fid = m.audio.file_id if m.audio else (m.voice.file_id if m.voice else m.document.file_id)
    if fid and k:
        audio_cloud_vault[k] = fid
        save_json(AUDIO_CACHE_FILE, audio_cloud_vault)
        bot.reply_to(m, f"🎉 **Аудио сохранено в вечное облако!**")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_add_balance")
def on_adm_add(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_uid"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 Введите Telegram ID пользователя:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_uid")
def step_adm_uid(m):
    if not is_admin(m.chat.id): return
    uid = "".join(filter(str.isdigit, m.text))
    user_data[m.chat.id] = {"target_uid": uid}
    user_state[m.chat.id] = "adm_sum"
    bot.reply_to(m, f"Сколько рублей начислить пользователю `{uid}`:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_sum")
def step_adm_sum(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        s = int(m.text.strip())
        t_uid = user_data[m.chat.id]["target_uid"]
        u, _ = get_user(t_uid)
        u["balance_rub"] += s
        save_json(DB_FILE, db)
        bot.reply_to(m, f"✅ Пользователю `{t_uid}` начислено {s} ₽!")
    except Exception: pass
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_bc(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_bc"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 Введите текст рассылки для всех пользователей:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_bc")
def step_adm_bc(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    t = m.text
    cnt = 0
    for u in db.keys():
        try:
            bot.send_message(int(u), f"📢 {t}", parse_mode="Markdown")
            cnt += 1
            time.sleep(0.04)
        except Exception: pass
    bot.reply_to(m, f"✅ Доставлено {cnt} пользователям.")
    show_admin_panel(m.chat.id)

print("\n>>> GENCALLS: АВТОНОМНЫЙ РЕЖИМ ЗАПУЩЕН! УДАЛЯТЬ И МЕНЯТЬ КОД БОЛЬШЕ НЕ НУЖНО! <<<")
while True:
    try: bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception: time.sleep(2)
