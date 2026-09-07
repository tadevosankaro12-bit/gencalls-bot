import os, json, telebot, requests, time, threading, logging
from datetime import datetime
from telebot import types
import urllib3
urllib3.disable_warnings()

logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ================= КОНФИГУРАЦИЯ =================
TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
ADMIN_IDS = ["8682521929", "8915393389"]
PRIMARY_ADMIN_ID = "8682521929"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=8)
user_data = {}
user_state = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "prank_audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "gencalls_db.json")
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
PROMO_FILE = os.path.join(BASE_DIR, "gencalls_promos.json")
BLACKLIST_FILE = os.path.join(BASE_DIR, "gencalls_blacklist.json")
CUSTOM_PRANKS_FILE = os.path.join(BASE_DIR, "gencalls_pranks.json")
AUDIO_STORAGE_FILE = os.path.join(BASE_DIR, "audio_storage_vault.json")

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

admin_cfg = load_json(CONFIG_FILE, {
    "call_price": 49,
    "max_referrals": 3,
    "admin_id": PRIMARY_ADMIN_ID,
    "crystal_auth_login": "dhdhe1728jd",
    "crystal_secret": "c5fdf612bfd5e816a1a7447d2b942a3b03e36c04",
    "crystal_salt": "a7e84e5da09dff11eb7be2ac0c6b83647a28efc1",
    "direct_bank_card": "+7 (999) 000-00-00 (Сбербанк / СБП)",
    "direct_recipient": "Каро Т.",
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

# ================= ВЕЧНОЕ ОБЛАЧНОЕ ХРАНИЛИЩЕ АУДИО =================
# Эти ссылки и file_id никогда не удалятся при перезапуске сервера или обновлении с GitHub!
PERMANENT_CLOUD_AUDIO = {
    "babka": "https://actions.google.com/sounds/v1/human_voices/screaming_female.ogg",
    "tulip": "https://actions.google.com/sounds/v1/human_voices/male_cheering.ogg",
    "rkn": "https://actions.google.com/sounds/v1/emergency/siren_emergency.ogg",
    "django": "https://actions.google.com/sounds/v1/cartoon/whistling_slide.ogg",
    "govnovoz": "https://actions.google.com/sounds/v1/transportation/truck_horn.ogg",
    "courier": "https://actions.google.com/sounds/v1/household/doorbell.ogg"
}

audio_vault = load_json(AUDIO_STORAGE_FILE, {})
for k, v in PERMANENT_CLOUD_AUDIO.items():
    if k not in audio_vault or not audio_vault[k]:
        audio_vault[k] = v
save_json(AUDIO_STORAGE_FILE, audio_vault)

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
            "balance_rub": price * 2,
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

def get_audio_source(key):
    # Сначала проверяем хранилище в памяти
    if key in audio_vault and audio_vault[key]:
        return audio_vault[key]
    # Затем постоянные облачные ссылки
    if key in PERMANENT_CLOUD_AUDIO:
        return PERMANENT_CLOUD_AUDIO[key]
    # Затем локальный файл
    fn = pranks_db.get(key, {}).get("file", f"{key}.mp3")
    local_p = os.path.join(AUDIO_DIR, fn)
    if os.path.exists(local_p):
        return local_p
    return PERMANENT_CLOUD_AUDIO.get("babka")

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
                caption=f"🎉 Звонок завершён! Запись разговора готова!\n\n📞 Номер: +{phone}\n🎭 Розыгрыш: {prank_title}"
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
        try: bot.edit_message_text(f"❌ Не удалось совершить вызов!\n\nОтвет: {call_id}\n💰 Баланс НЕ списан.", chat_id, wait_msg_id, reply_markup=kb_main_menu(chat_id))
        except Exception: pass
        return

    u["balance_rub"] = max(0, u["balance_rub"] - price)
    u.setdefault("calls_history", []).append({
        "time": datetime.now().strftime("%d.%m %H:%M"), "phone": phone, "prank": p_title, "service": service_name, "call_id": str(call_id)
    })
    save_json(DB_FILE, db)

    try:
        bot.edit_message_text(
            f"✅ Звонок запущен!\n\n📞 Номер: +{phone}\n🌐 Канал: {service_name}\n🎭 Розыгрыш: {p_title}\n💰 Остаток: {u['balance_rub']} ₽ ({u['balance_rub'] // price} 📞)\n\n🎙️ Запись разговора придёт в чат сразу после звонка!",
            chat_id, wait_msg_id, reply_markup=kb_main_menu(chat_id)
        )
    except Exception: pass
    threading.Thread(target=track_call_and_send_record, args=(chat_id, call_id, phone, p_title, service_type), daemon=True).start()

def kb_main_menu(uid):
    u, _ = get_user(uid)
    price = admin_cfg.get("call_price", 49)
    bal_rub = u.get("balance_rub", 0)
    bal_calls = bal_rub // price
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🎉 Открыть каталог розыгрышей", callback_data="catalog"))
    kb.row(
        types.InlineKeyboardButton(f"👤 Аккаунт ({bal_rub} ₽ / {bal_calls} 📞)", callback_data="nav_account"),
        types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu")
    )
    kb.row(
        types.InlineKeyboardButton("📜 Правила и Оферта", callback_data="nav_rules"),
        types.InlineKeyboardButton("🛟 Поддержка", callback_data="nav_help")
    )
    kb.row(
        types.InlineKeyboardButton("🎟️ Промокод", callback_data="enter_promo"),
        types.InlineKeyboardButton("🛡️ Анти-Пранк", callback_data="anti_prank")
    )
    kb.row(
        types.InlineKeyboardButton("📢 Telegram-канал", url=admin_cfg.get("channel_url", "https://t.me/gencalls_channel"))
    )
    return kb

def safe_nav(c, text, reply_markup=None):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    try:
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=reply_markup)
    except Exception:
        try: bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception: pass
        bot.send_message(c.message.chat.id, text, reply_markup=reply_markup)

MAIN_TEXT_BANNER = (
    "🎭 GenCalls — Пранк-Звонки с записью реакции!\n\n"
    "🎁 Вам начислено 2 БЕСПЛАТНЫХ ЗВОНКА в подарок!\n\n"
    "🕵️‍♂️ Анонимность 100% — ваш номер скрыт.\n"
    "🎵 MP3-Плеер — слушайте пранки перед звонком!\n"
    "🎙️ Запись реакции — запись разговора прямо в этот чат!\n"
    "⚡ Оплата: Сбербанк Онлайн, СБП и любые карты.\n\n"
    "👇 Выберите действие в меню:"
)

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    user_state[m.chat.id] = None
    u, is_new = get_user(m.chat.id, m.from_user.first_name or "Друг")
    welcome = MAIN_TEXT_BANNER
    if is_new:
        welcome = f"🎉 Добро пожаловать в GenCalls!\n\n🎁 Мы подарили вам 2 БЕСПЛАТНЫХ ЗВОНКА!\n\n" + MAIN_TEXT_BANNER
    bot.send_message(m.chat.id, welcome, reply_markup=kb_main_menu(m.chat.id))

# ================= КАТАЛОГ =================
@bot.callback_query_handler(func=lambda c: c.data == "catalog")
def on_catalog_cb(c):
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        kb.row(types.InlineKeyboardButton(f"🎵 {v['title']} [{v.get('tag', 'ТОП')}]", callback_data=f"open_prank_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "🎭 Каталог голосовых розыгрышей:\nВыберите любой для прослушивания:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_prank_"))
def on_open_prank(c):
    k = c.data.replace("open_prank_", "")
    p = pranks_db.get(k)
    if not p: return
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"🚀 Позвонить жертве ({price} ₽)", callback_data=f"setup_call_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 Каталог", callback_data="catalog"), types.InlineKeyboardButton("🏠 Меню", callback_data="back_main"))
    
    desc_text = f"🎭 {p['title']} [{p.get('tag', 'ТОП')}]\n\n💬 Сценарий: {p.get('desc', '')}\n\n🎙️ После звонка запись разговора придёт в чат!"
    audio_source = get_audio_source(k)
    try:
        bot.answer_callback_query(c.id)
        if str(audio_source).startswith("http") or str(audio_source).startswith("AgAC") or len(str(audio_source)) > 40:
            bot.send_audio(c.message.chat.id, audio_source, title=p['title'], performer="GenCalls", caption=desc_text, reply_markup=kb)
        else:
            with open(audio_source, "rb") as a_file:
                sent = bot.send_audio(c.message.chat.id, a_file, title=p['title'], performer="GenCalls", caption=desc_text, reply_markup=kb)
                if sent.audio:
                    audio_vault[k] = sent.audio.file_id
                    save_json(AUDIO_STORAGE_FILE, audio_vault)
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
        safe_nav(c, f"❌ Недостаточно средств\n\nЦена звонка: {price} ₽\nВаш баланс: {u.get('balance_rub', 0)} ₽", reply_markup=kb)
        return
    k = c.data.replace("setup_call_", "")
    user_data[c.message.chat.id] = {"prank": k}
    user_state[c.message.chat.id] = "waiting_phone"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog"))
    safe_nav(c, "📱 Введите номер телефона жертвы:\n\n• Россия: +79991234567\n• Армения: +374...", reply_markup=kb)

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
    w = bot.send_message(chat_id, f"🚀 Набираем +{phone}...")
    threading.Thread(target=process_call_async, args=(chat_id, phone, prank_key, p["title"], w.message_id), daemon=True).start()

# ================= ОПЛАТА =================
@bot.callback_query_handler(func=lambda c: c.data == "packages_menu")
def cb_packages(c):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.row(types.InlineKeyboardButton(f"{p['title']} — {p['rub']} ₽ ({p['badge']})", callback_data=f"buy_pkg_{pid}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, "💳 Выберите пакет звонков для пополнения:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_pkg_"))
def on_buy_pkg(c):
    pid = c.data.replace("buy_pkg_", "")
    pkg = PACKAGES.get(pid)
    if not pkg: return
    amount = pkg["rub"]
    bank_card = admin_cfg.get("direct_bank_card", "+7 (999) 000-00-00 (Сбербанк)")
    recipient = admin_cfg.get("direct_recipient", "Каро Т.")
    
    text = (
        f"🟢 Оплата пакета «{pkg['title']}»\n\n"
        f"💰 Сумма к переводу: {amount} ₽\n\n"
        f"📌 РЕКВИЗИТЫ ДЛЯ ПЕРЕВОДА:\n"
        f"• Номер / СБП: `{bank_card}`\n"
        f"• Получатель: {recipient}\n\n"
        f"1. Сделайте перевод на сумму {amount} ₽ со своего банка.\n"
        f"2. Нажмите кнопку «📤 Я перевёл (Отправить чек)» ниже и отправьте фото чека в этот чат.\n\n"
        f"⚡ После проверки баланс сразу поступит на ваш счёт!"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.row(types.InlineKeyboardButton("📤 Я перевёл (Отправить чек)", callback_data=f"send_rec_{amount}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к пакетам", callback_data="packages_menu"))
    safe_nav(c, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("send_rec_"))
def on_send_rec(c):
    amount = int(c.data.replace("send_rec_", ""))
    user_state[c.message.chat.id] = "waiting_receipt"
    user_data[c.message.chat.id] = {"amount": amount}
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="packages_menu"))
    safe_nav(c, f"📸 Отправьте фото или скриншот банковского чека на {amount} ₽ сообщением сюда в чат:", reply_markup=kb)

@bot.message_handler(content_types=["photo", "document"], func=lambda m: user_state.get(m.chat.id) == "waiting_receipt")
def on_receipt_uploaded(m):
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
    caption = f"🧾 НОВЫЙ ЧЕК НА ОПЛАТУ!\n\n👤 От: {m.from_user.first_name} (ID: `{chat_id}`)\n💰 Сумма: {amount} ₽"
    try:
        bot.send_photo(int(admin_id), file_id, caption=caption, reply_markup=adm_kb)
        bot.reply_to(m, "✅ Чек отправлен администратору на проверку! Баланс пополнится в течение пары минут.", reply_markup=kb_main_menu(chat_id))
    except Exception:
        bot.reply_to(m, "✅ Чек получен, проверяем.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_appr_"))
def on_adm_appr(c):
    if not is_admin(c.message.chat.id): return
    parts = c.data.split("_")
    uid, amount = parts[2], int(parts[3])
    u, _ = get_user(uid)
    u["balance_rub"] += amount
    save_json(DB_FILE, db)
    bot.answer_callback_query(c.id, "✅ Баланс успешно начислен!", show_alert=True)
    try: bot.edit_message_caption(f"{c.message.caption}\n\n🟢 ПОДТВЕРЖДЕНО (+{amount} ₽) ✅", c.message.chat.id, c.message.message_id)
    except Exception: pass
    try: bot.send_message(int(uid), f"🎉 Оплата подтверждена!\nВам начислено: +{amount} ₽\n💰 Текущий баланс: {u['balance_rub']} ₽ ({u['balance_rub'] // admin_cfg.get('call_price', 49)} 📞)", reply_markup=kb_main_menu(uid))
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_decl_"))
def on_adm_decl(c):
    if not is_admin(c.message.chat.id): return
    uid = c.data.split("_")[2]
    bot.answer_callback_query(c.id, "❌ Чек отклонён", show_alert=True)
    try: bot.edit_message_caption(f"{c.message.caption}\n\n🔴 ОТКЛОНЕНО ❌", c.message.chat.id, c.message.message_id)
    except Exception: pass
    try: bot.send_message(int(uid), f"❌ Ваш чек был отклонён администратором. Свяжитесь с поддержкой: @{admin_cfg.get('support')}")
    except Exception: pass

# ================= МЕНЮ И НАВИГАЦИЯ =================
@bot.callback_query_handler(func=lambda c: c.data == "nav_rules")
def cb_rules(c):
    rules_text = (
        "📜 ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ И ПРАВИЛА (ОФЕРТА)\n\n"
        "1. ОБЩИЕ ПОЛОЖЕНИЯ:\n"
        "Сервис «GenCalls» предоставляет услуги развлекательных голосовых поздравлений и розыгрышей через телефонию.\n\n"
        "2. УСЛОВИЯ ОПЛАТЫ И ОКАЗАНИЯ УСЛУГ:\n"
        "• Все цены на услуги являются фиксированными и указаны в меню пополнения.\n"
        "• После подтверждения оплаты баланс начисляется на аккаунт моментально.\n"
        "• Списание средств происходит только в момент успешного дозвона.\n\n"
        "3. ПРАВИЛА БЕЗОПАСНОСТИ И АНТИ-СПАМ:\n"
        "• Запрещено использовать сервис для угроз, мошенничества или хулиганства.\n"
        "• Каждый пользователь может внести свой номер в бесплатный список защиты «🛡️ Анти-Пранк».\n\n"
        "4. КОНТАКТЫ И ПОДДЕРЖКА:\n"
        f"По всем вопросам и возвратам: @{admin_cfg.get('support')}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, rules_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_account")
def cb_account(c):
    u, _ = get_user(c.message.chat.id)
    price = admin_cfg.get("call_price", 49)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="packages_menu"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"👤 Личный кабинет\n\n🆔 ID: `{c.message.chat.id}`\n💰 Баланс: {u['balance_rub']} ₽ ({u['balance_rub'] // price} 📞)", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "nav_help")
def cb_help(c):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("👨‍💻 Написать администратору", url=f"https://t.me/{admin_cfg.get('support')}"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    safe_nav(c, f"🛟 Служба заботы и поддержки:\n\nПо любым вопросам пишите: @{admin_cfg.get('support')}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "enter_promo")
def on_enter_promo(c):
    user_state[c.message.chat.id] = "waiting_promo"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="back_main"))
    safe_nav(c, "🎟️ Введите промокод в чат:", reply_markup=kb)

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
    safe_nav(c, "🛡️ Введите номер для защиты от розыгрышей:", reply_markup=kb)

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

# ================= АДМИНКА (/admin) =================
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
    active_audios = len(audio_vault)
    text = (
        "👑 Панель Управления GenCalls\n\n"
        f"💳 Реквизиты для оплаты: `{admin_cfg.get('direct_bank_card')}`\n"
        f"👤 Получатель: {admin_cfg.get('direct_recipient')}\n"
        f"🎭 Розыгрышей в базе: {len(pranks_db)} шт.\n"
        f"☁️ Облачных аудио: {active_audios} шт. (ЗАЩИЩЕНО НАВСЕГДА)\n"
        f"🏷️ Цена звонка: {admin_cfg.get('call_price')} ₽\n"
        f"👥 Пользователей: {len(db)}"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("💳 Изменить реквизиты Сбера", callback_data="adm_change_direct_bank"))
    kb.row(types.InlineKeyboardButton("🎭 Редактор розыгрышей", callback_data="adm_pranks_manager"))
    kb.row(types.InlineKeyboardButton("🎵 Загрузить аудио к пранку", callback_data="adm_upload_audio_menu"))
    kb.row(types.InlineKeyboardButton("🏷️ Изменить цену звонка", callback_data="adm_change_price"))
    kb.row(types.InlineKeyboardButton("💳 Выдать баланс юзеру", callback_data="adm_add_balance"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
    if c: safe_nav(c, text, reply_markup=kb)
    else: bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_direct_bank")
def on_adm_cdb(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_direct_bank"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 Введите номер телефона/карты и имя получателя через запятую:\n\nПример: +79991234567 (Сбербанк), Каро Т.", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_direct_bank")
def step_adm_direct_bank(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    parts = [p.strip() for p in m.text.split(",")]
    if len(parts) >= 1: admin_cfg["direct_bank_card"] = parts[0]
    if len(parts) >= 2: admin_cfg["direct_recipient"] = parts[1]
    save_json(CONFIG_FILE, admin_cfg)
    bot.reply_to(m, "✅ Реквизиты для оплаты успешно обновлены!")
    show_admin_panel(m.chat.id)

# ---- РЕДАКТОР РОЗЫГРЫШЕЙ С ВЕЧНЫМ ХРАНЕНИЕМ ----
@bot.callback_query_handler(func=lambda c: c.data == "adm_pranks_manager")
def on_pranks_manager(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ ДОБАВИТЬ НОВЫЙ РОЗЫГРЫШ", callback_data="adm_prank_create_new"))
    for k, v in pranks_db.items():
        kb.row(
            types.InlineKeyboardButton(f"🎵 {v['title']}", callback_data=f"adm_up_{k}"),
            types.InlineKeyboardButton("❌ Удалить", callback_data=f"adm_del_prank_{k}")
        )
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎭 Управление каталогом розыгрышей:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_prank_create_new")
def on_create_prank_start(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_prank_new_title"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_pranks_manager"))
    safe_nav(c, "➕ Шаг 1 из 3: Введите название нового розыгрыша:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_title")
def step_prank_new_title(m):
    if not is_admin(m.chat.id): return
    user_data[m.chat.id] = {"new_title": m.text.strip(), "new_key": f"prank_{int(time.time())}"}
    user_state[m.chat.id] = "adm_prank_new_desc"
    bot.reply_to(m, "📝 Шаг 2 из 3: Введите краткое описание сценария:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_desc")
def step_prank_new_desc(m):
    if not is_admin(m.chat.id): return
    user_data[m.chat.id]["new_desc"] = m.text.strip()
    user_state[m.chat.id] = "adm_prank_new_audio"
    bot.reply_to(m, "🎵 Шаг 3 из 3: Отправьте сюда MP3-аудиофайл или голосовое (сохранится в облако навсегда):")

@bot.message_handler(content_types=["audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_prank_new_audio")
def step_prank_new_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    d = user_data.get(m.chat.id, {})
    k = d.get("new_key")
    fid = m.audio.file_id if m.audio else (m.voice.file_id if m.voice else m.document.file_id)
    
    if k and fid:
        pranks_db[k] = {
            "title": d.get("new_title", "Новый розыгрыш"),
            "tag": "NEW 🔥",
            "dur": 30,
            "desc": d.get("new_desc", ""),
            "file": f"{k}.mp3",
            "public": True
        }
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        audio_vault[k] = fid
        save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.reply_to(m, f"🎉 Розыгрыш «{d.get('new_title')}» сохранен в облако навсегда!")
        show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_del_prank_"))
def on_del_prank(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_del_prank_", "")
    if k in pranks_db:
        del pranks_db[k]
        save_json(CUSTOM_PRANKS_FILE, pranks_db)
        if k in audio_vault:
            del audio_vault[k]
            save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.answer_callback_query(c.id, "✅ Розыгрыш удален!")
    on_pranks_manager(c)

@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_audio_menu")
def on_upload_menu(c):
    if not is_admin(c.message.chat.id): return
    kb = types.InlineKeyboardMarkup()
    for k, v in pranks_db.items():
        status = "☁️ " if k in audio_vault else "⚪ "
        kb.row(types.InlineKeyboardButton(f"{status}{v['title']}", callback_data=f"adm_up_{k}"))
    kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="admin_panel_open"))
    safe_nav(c, "🎵 Выберите розыгрыш для обновления аудио в облаке:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_up_"))
def on_sel_up(c):
    if not is_admin(c.message.chat.id): return
    k = c.data.replace("adm_up_", "")
    user_data[c.message.chat.id] = {"prank_up": k}
    user_state[c.message.chat.id] = "adm_audio_file"
    p = pranks_db.get(k, {})
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="adm_upload_audio_menu"))
    safe_nav(c, f"🎵 Отправьте аудио (.mp3 или голосовое) для:\n\n🎭 {p.get('title', k)}\n\n(Оно зафиксируется в облаке и больше никогда не удалится)", reply_markup=kb)

@bot.message_handler(content_types=["audio", "voice", "document"], func=lambda m: user_state.get(m.chat.id) == "adm_audio_file")
def step_adm_audio(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    k = user_data.get(m.chat.id, {}).get("prank_up")
    fid = m.audio.file_id if m.audio else (m.voice.file_id if m.voice else m.document.file_id)
    if fid and k:
        audio_vault[k] = fid
        save_json(AUDIO_STORAGE_FILE, audio_vault)
        bot.reply_to(m, f"🎉 УСПЕХ! Аудио навечно привязано в облаке к «{pranks_db.get(k, {}).get('title', k)}»!")
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_change_price")
def on_adm_price(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_price"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "🏷️ Введите цену 1 звонка в рублях:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_price")
def step_adm_price(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    try:
        p = int("".join(filter(str.isdigit, m.text)))
        admin_cfg["call_price"] = p
        save_json(CONFIG_FILE, admin_cfg)
        bot.reply_to(m, f"✅ Цена звонка: {p} ₽!")
    except Exception: pass
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_add_balance")
def on_adm_add(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_uid"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "💳 Введите ID пользователя:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_uid")
def step_adm_uid(m):
    if not is_admin(m.chat.id): return
    uid = "".join(filter(str.isdigit, m.text))
    user_data[m.chat.id] = {"target_uid": uid}
    user_state[m.chat.id] = "adm_sum"
    bot.reply_to(m, f"Сколько рублей начислить пользователю {uid}:")

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
        bot.reply_to(m, f"✅ Начислено {s} ₽!")
    except Exception: pass
    show_admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
def on_adm_bc(c):
    if not is_admin(c.message.chat.id): return
    user_state[c.message.chat.id] = "adm_bc"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel_open"))
    safe_nav(c, "📢 Введите текст рассылки:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "adm_bc")
def step_adm_bc(m):
    if not is_admin(m.chat.id): return
    user_state[m.chat.id] = None
    t = m.text
    cnt = 0
    for u in db.keys():
        try:
            bot.send_message(int(u), f"📢 {t}")
            cnt += 1
            time.sleep(0.04)
        except Exception: pass
    bot.reply_to(m, f"✅ Доставлено {cnt} пользователям.")
    show_admin_panel(m.chat.id)

print("\n>>> GENCALLS: ВЕЧНОЕ ОБЛАЧНОЕ ХРАНИЛИЩЕ АУДИО АКТИВИРОВАНО! <<<")
while True:
    try: bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception: time.sleep(2)
