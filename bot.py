import os, json, telebot, requests, time, threading, urllib3, sys, random
from datetime import datetime
from telebot import types
from urllib.parse import quote
from flask import Flask

# Встроенный веб-сервер для прохождения проверки Render
app = Flask(__name__)

@app.route('/')
def home():
    return "GenCalls Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

urllib3.disable_warnings()

TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
BOT_USERNAME = "Fhhknyjj5bot"
ZVONOK_KEY = "d0808ab7450fca32147a9285018fe7a5"
CAMPAIGN_ID = "1783540036"
SMSRU_KEY = "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF"

MAX_REF_BONUSES = 2

YOOMONEY_WALLET = "4100119616287380"
SBP_PHONE_DISPLAY = "+7 (925) 823-38-98"
SBP_BANKS = "СберБанк / Т-Банк / ЮMoney"
ADMIN_IDS = [8682521929, 8113702580]
SUPPORT_USERNAME = "tadevosankaro12"
CHANNEL_URL = "https://t.me/Grey5g"
CHANNEL_TAG = "@Grey5g"

DATA_DIR = os.path.expanduser("./bot_data")
os.makedirs(DATA_DIR, exist_ok=True)
PRANKS_FILE = os.path.join(DATA_DIR, "permanent_pranks.json")
USERS_FILE = os.path.join(DATA_DIR, "users_v3.json")
PROMOS_FILE = os.path.join(DATA_DIR, "promos_v3.json")

CATEGORIES = {
    "top10": "🏆 ТОП-10",
    "personal": "🗣️ По имени жертвы (ИИ)",
    "voenkom": "🪖 Военкомат",
    "psih": "🤪 Психбольница",
    "armenian": "🇦🇲 Армянские (Հայկական)",
    "babka": "👵 От бабки",
    "avto": "🚗 Автомобилистам",
    "police": "👮‍♂️ От полиции",
    "kavkaz": "🧔 От кавказца",
    "girls": "💅 Для девушек",
    "neighbors": "🏠 Соседи"
}

DEFAULT_PERMANENT_PRANKS = {
    "name_voenkom": {
        "cat": "personal",
        "title": "Военкомат: Личный призыв (по имени)",
        "desc": "Майор называет жертву по имени и требует явиться в военкомат.",
        "text_template": "Алло, здравствуйте! Это {name}? Старший лейтенант Сидоров, военный комиссариат. {name}, почему игнорируете повестку? Завтра в восемь утра явитесь с паспортом в кабинет номер четыре!"
    },
    "name_ashot": {
        "cat": "personal",
        "title": "Ашот: Где мясо для свадьбы?! (по имени)",
        "desc": "Ашот кричит по имени и требует срочно привезти мясо.",
        "text_template": "Ара, {name}, джан! Ты где ходишь?! У меня свадьба через час, сто человек сидят, где мясо на шашлык, {name}?! Ты меня перед людьми опозорить хочешь?!"
    },
    "voenkom_povestka": {
        "cat": "voenkom",
        "title": "Срочная повестка на сборы (0:39)",
        "desc": "Майор сообщает о неявке по повестке и требует явиться в военкомат к 8 утра.",
        "text": "Здравия желаю! Майор Сидоров, военный комиссариат. Почему игнорируете повестку? Завтра к восьми утра с вещами в кабинет номер четыре!"
    },
    "psih_sbezhal": {
        "cat": "psih",
        "title": "Сбежал пациент из палаты №6 (0:44)",
        "desc": "Главврач сообщает, что из отделения сбежал опасный пациент.",
        "text": "Алло, здравствуйте! Городская психиатрическая больница номер три. У нас пациент из шестой палаты сбежал, сказал к вам поехал прятаться!"
    },
    "fire_neighbors": {
        "cat": "neighbors",
        "title": "Пожар в квартире! (0:37)",
        "desc": "Сосед в панике кричит о дыме из вашей квартиры.",
        "text": "Алло! Ты дома?! У тебя из-под двери дым валит, мы уже пожарных вызвали! Срочно приезжай!"
    }
}

def load_json(p, def_val):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: return def_val
    with open(p, "w", encoding="utf-8") as f: json.dump(def_val, f, ensure_ascii=False, indent=2)
    return def_val

def save_json(p, data):
    try:
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

pranks_db = load_json(PRANKS_FILE, DEFAULT_PERMANENT_PRANKS)
for k, v in DEFAULT_PERMANENT_PRANKS.items():
    if k not in pranks_db: pranks_db[k] = v
save_json(PRANKS_FILE, pranks_db)

users_db = load_json(USERS_FILE, {})
promos_db = load_json(PROMOS_FILE, {"FREE1": 49, "GEN2026": 49, "START": 49})

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=16)
user_states = {}

def is_admin(uid): return int(uid) in ADMIN_IDS

def format_phone_display(p):
    p = str(p).strip().replace("+", "")
    if len(p) == 11 and (p.startswith("7") or p.startswith("8")):
        return f"+7 ({p[1:4]}) {p[4:7]}-{p[7:9]}-{p[9:]}"
    elif len(p) == 11 and p.startswith("374"):
        return f"+374 ({p[3:5]}) {p[5:8]}-{p[8:]}"
    return f"+{p}"

def get_user(u_obj, ref_id=None):
    uid = str(u_obj.id)
    is_new = False
    if uid not in users_db:
        is_new = True
        users_db[uid] = {
            "name": u_obj.first_name or "Пользователь",
            "bal": 98,
            "calls": 0,
            "history": [],
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "route": "auto",
            "used_promos": [],
            "invited_by": str(ref_id) if (ref_id and str(ref_id) != uid) else None,
            "ref_count": 0,
            "ref_bonus_count": 0,
            "ref_earned": 0
        }
        if ref_id and str(ref_id) in users_db and str(ref_id) != uid:
            r_uid = str(ref_id)
            cur_bon = users_db[r_uid].get("ref_bonus_count", 0)
            users_db[r_uid]["ref_count"] = users_db[r_uid].get("ref_count", 0) + 1
            if cur_bon < MAX_REF_BONUSES:
                users_db[r_uid]["bal"] = users_db[r_uid].get("bal", 0) + 49
                users_db[r_uid]["ref_bonus_count"] = cur_bon + 1
                users_db[r_uid]["ref_earned"] = users_db[r_uid].get("ref_earned", 0) + 49
                try:
                    bot.send_message(int(r_uid), f"🎉 **Новый реферал ({cur_bon + 1}/{MAX_REF_BONUSES})!**\nВам начислен **+1 бесплатный звонок (+49 ₽)**!", parse_mode="Markdown")
                except: pass
        save_json(USERS_FILE, users_db)
    return users_db[uid], is_new

def make_reliable_call(p, prank_obj, victim_name=None, forced_route="auto"):
    phone_clean = p.replace("+", "").strip()
    txt_speech = prank_obj["text_template"].format(name=victim_name) if (victim_name and "text_template" in prank_obj) else (prank_obj.get("text") or prank_obj.get("title"))
    try:
        url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
        params = {"campaign_id": CAMPAIGN_ID, "phone": f"+{phone_clean}", "public_key": ZVONOK_KEY, "text": txt_speech, "record": "1", "check_duplicate": "0"}
        r = requests.get(url, params=params, verify=False, timeout=8)
        cid = r.json().get("call_id") or r.json().get("data", {}).get("call_id")
        if cid: return True, str(cid), "zvonok"
    except: pass
    try:
        r_sms = requests.get("https://sms.ru/code/call", params={"phone": phone_clean, "api_id": SMSRU_KEY, "json": 1}, timeout=8)
        if r_sms.json().get("status") == "OK":
            cid = str(r_sms.json().get("call_id") or random.randint(4110000, 4119999))
            return True, cid, "smsru"
    except Exception as e:
        return False, str(e), "error"
    return False, "Сбой шлюза дозвона.", "error"

def get_profile_text_and_kb(u_obj):
    uid = str(u_obj.id)
    u, _ = get_user(u_obj)
    name = u.get("name", u_obj.first_name or "Пользователь")
    bal = u.get("bal", 0)
    text = f"👋 **{name}**, это твой профиль:\n\n├ ID: `{uid}`\n├ Баланс: **{bal}₽** ({bal//49} 📞)\n└ Канал: [{CHANNEL_TAG}]({CHANNEL_URL})"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("😂 Заказать розыгрыш (49₽)", callback_data="open_categories"))
    kb.row(types.InlineKeyboardButton("🧾 Пополнить баланс", callback_data="btn_topup_menu"), types.InlineKeyboardButton("📞 Мои розыгрыши", callback_data="btn_history"))
    kb.row(types.InlineKeyboardButton("🤝 Партнерство", callback_data="btn_partnership"), types.InlineKeyboardButton("✅ Бонусный звонок", callback_data="btn_bonus"))
    kb.row(types.InlineKeyboardButton("📢 Наш канал @Grey5g ↗", url=CHANNEL_URL))
    return text, kb

@bot.message_handler(commands=['start', 'menu'])
def handle_start_cmd(m):
    ref_id = m.text.split()[1].replace("ref_", "").strip() if len(m.text.split()) > 1 and m.text.split()[1].startswith("ref_") else None
    get_user(m.from_user, ref_id)
    text, kb = get_profile_text_and_kb(m.from_user)
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c):
    cid = c.message.chat.id
    uid = str(c.from_user.id)
    d = c.data
    try: bot.answer_callback_query(c.id)
    except: pass

    if d == "back_main":
        user_states.pop(cid, None)
        text, kb = get_profile_text_and_kb(c.from_user)
        try: bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)
        except: bot.send_message(cid, text, parse_mode="Markdown", reply_markup=kb)

    elif d == "open_categories":
        kb = types.InlineKeyboardMarkup(row_width=2)
        for k, v in CATEGORIES.items(): kb.add(types.InlineKeyboardButton(v, callback_data=f"showcat_{k}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text("📚 **Каталог розыгрышей:**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d.startswith("showcat_"):
        cat_key = d.replace("showcat_", "")
        pranks = [(k, v) for k, v in pranks_db.items() if v.get("cat") == cat_key] or list(pranks_db.items())
        kb = types.InlineKeyboardMarkup()
        for pk, p in pranks: kb.row(types.InlineKeyboardButton(f"🎭 {p.get('title')}", callback_data=f"callnow_{pk}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад к категориям", callback_data="open_categories"))
        bot.edit_message_text(f"📂 **{CATEGORIES.get(cat_key, 'Розыгрыши')}**\nВыберите розыгрыш:", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d.startswith("callnow_"):
        pk = d.replace("callnow_", "")
        p = pranks_db.get(pk, {})
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="back_main"))
        if "text_template" in p:
            user_states[cid] = {"step": "WAIT_VICTIM_NAME", "prank_key": pk}
            bot.send_message(cid, f"🎭 **{p.get('title')}**\n\n👤 Введите **ИМЯ** жертвы (например `Артём`):", parse_mode="Markdown", reply_markup=kb)
        else:
            user_states[cid] = {"step": "phone", "prank_key": pk}
            bot.send_message(cid, f"🎭 **{p.get('title')}**\n\n📞 Введите **номер телефона** жертвы (например `+79258233898`):", parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_topup_menu":
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("📲 Оплата по СБП (Все банки РФ)", callback_data="topup_sbp_50"))
        kb.row(types.InlineKeyboardButton("💳 Картой / ЮMoney", url=f"https://yoomoney.ru/to/{YOOMONEY_WALLET}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text("💳 **Выберите способ пополнения:**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "topup_sbp_50":
        text = f"📲 **Оплата по СБП (50 ₽ = 1 звонок)**\n\nПереведите **50 ₽** по номеру:\n`{SBP_PHONE_DISPLAY}`\nБанк: **{SBP_BANKS}**\n\nПосле оплаты нажмите кнопку ниже:"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("✅ Я оплатил", callback_data="sbp_done_50"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="btn_topup_menu"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "sbp_done_50":
        bot.send_message(cid, "✅ **Уведомление отправлено администратору!** Баланс будет начислен в течение пары минут.")
        for adm in ADMIN_IDS:
            try:
                kb_adm = types.InlineKeyboardMarkup()
                kb_adm.row(types.InlineKeyboardButton("⚡ Зачислить +50₽", callback_data=f"adm_add_{uid}_50"))
                bot.send_message(adm, f"🔔 **Оплата по СБП!**\nID: `{uid}` ({c.from_user.first_name})\nСумма: 50 ₽", reply_markup=kb_adm)
            except: pass

    elif d.startswith("adm_add_"):
        if is_admin(uid):
            _, _, t_uid, t_sum = d.split("_")
            t_sum = int(t_sum)
            if t_uid in users_db:
                users_db[t_uid]["bal"] += t_sum
                save_json(USERS_FILE, users_db)
                bot.send_message(cid, f"✅ Зачислено **+{t_sum} ₽** для `{t_uid}`!")
                try: bot.send_message(int(t_uid), f"🎉 **Оплата получена!** Вам начислено **+{t_sum} ₽**!")
                except: pass

    elif d == "btn_partnership":
        u, _ = get_user(c.from_user)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        text = f"🤝 **Партнерская программа GenCalls**\n\n🎁 За каждого друга: **+49 ₽ (1 звонок)**\n🛡️ Лимит: 2 друга (98 ₽)\n\n🔗 Ваша ссылка:\n`{ref_link}`"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_bonus":
        user_states[cid] = {"step": "promo"}
        bot.send_message(cid, "🎟️ Введите промокод (например `START`):")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    cid = m.chat.id
    st = user_states.get(cid, {})

    if st.get("step") == "WAIT_VICTIM_NAME":
        user_states[cid] = {"step": "phone", "prank_key": st.get("prank_key"), "victim_name": m.text.strip()}
        bot.send_message(cid, f"✅ Имя: **{m.text.strip()}**\n\n📞 Теперь введите номер телефона жертвы (например `+79258233898`):")
        return

    if st.get("step") == "promo":
        user_states.pop(cid, None)
        code = m.text.strip().upper()
        u, _ = get_user(m.from_user)
        if code in u.get("used_promos", []):
            bot.send_message(cid, "❌ Промокод уже использован!")
            return
        if code in promos_db:
            u["bal"] += promos_db[code]
            u["used_promos"].append(code)
            save_json(USERS_FILE, users_db)
            bot.send_message(cid, f"🎉 Начислено **+{promos_db[code]} ₽**!")
            handle_start_cmd(m)
        else: bot.send_message(cid, "❌ Промокод не найден.")
        return

    if st.get("step") == "phone":
        raw = m.text.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        v_name = st.get("victim_name")
        pk = st.get("prank_key", "fire_neighbors")
        user_states.pop(cid, None)
        u, _ = get_user(m.from_user)
        if u["bal"] < 49:
            bot.send_message(cid, "❌ Недостаточно средств на балансе. Пополните баланс в профиле.")
            return

        p = pranks_db.get(pk, {})
        msg_w = bot.send_message(cid, f"⏳ Соединение со шлюзом для `{format_phone_display(raw)}`...")

        def run():
            ok, cid_res, _ = make_reliable_call(raw, p, v_name, u.get("route", "auto"))
            if not ok:
                bot.edit_message_text(f"❌ Ошибка вызова: {cid_res}", cid, msg_w.message_id)
                return
            u["bal"] -= 49
            save_json(USERS_FILE, users_db)
            bot.edit_message_text(f"🎉 **Звонок успешно запущен!**\n ├ Номер: `{format_phone_display(raw)}`\n └ Сценарий: **{p.get('title')}**", cid, msg_w.message_id, parse_mode="Markdown")

        threading.Thread(target=run, daemon=True).start()

print(">>> БОТ И ВЕБ-СЕРВЕР ЗАПУЩЕНЫ НА СЕРВЕРЕ 24/7! <<<")
while True:
    try:
        bot.remove_webhook()
        bot.infinity_polling(timeout=5, long_polling_timeout=3)
    except Exception as e:
        time.sleep(1)
import os, json, telebot, requests, time, threading, urllib3, sys, random
from datetime import datetime
from telebot import types
from urllib.parse import quote
from flask import Flask

# Фоновый веб-сервер для поддержания статуса Live на сервере 24/7
app = Flask(__name__)

@app.route('/')
def home():
    return "GenCalls Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

urllib3.disable_warnings()

TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
BOT_USERNAME = "Fhhknyjj5bot"
ZVONOK_KEY = "d0808ab7450fca32147a9285018fe7a5"
CAMPAIGN_ID = "1783540036"
SMSRU_KEY = "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF"

MAX_REF_BONUSES = 2

YOOMONEY_WALLET = "4100119616287380"
SBP_PHONE_DISPLAY = "+7 (925) 823-38-98"
SBP_BANKS = "СберБанк / Т-Банк / ЮMoney"
ADMIN_IDS = [8682521929, 8113702580]
SUPPORT_USERNAME = "tadevosankaro12"
CHANNEL_URL = "https://t.me/Grey5g"
CHANNEL_TAG = "@Grey5g"

DATA_DIR = os.path.expanduser("./bot_data")
os.makedirs(DATA_DIR, exist_ok=True)
PRANKS_FILE = os.path.join(DATA_DIR, "permanent_pranks.json")
USERS_FILE = os.path.join(DATA_DIR, "users_v3.json")
PROMOS_FILE = os.path.join(DATA_DIR, "promos_v3.json")

CATEGORIES = {
    "top10": "🏆 ТОП-10",
    "personal": "🗣️ По имени жертвы (ИИ)",
    "voenkom": "🪖 Военкомат",
    "psih": "🤪 Психбольница",
    "armenian": "🇦🇲 Армянские (Հայկական)",
    "babka": "👵 От бабки",
    "avto": "🚗 Автомобилистам",
    "police": "👮‍♂️ От полиции",
    "kavkaz": "🧔 От кавказца",
    "girls": "💅 Для девушек",
    "neighbors": "🏠 Соседи"
}

DEFAULT_PERMANENT_PRANKS = {
    "name_voenkom": {
        "cat": "personal",
        "title": "Военкомат: Личный призыв (по имени)",
        "desc": "Майор называет жертву по имени и требует явиться в военкомат.",
        "text_template": "Алло, здравствуйте! Это {name}? Старший лейтенант Сидоров, военный комиссариат. {name}, почему игнорируете повестку? Завтра в восемь утра явитесь с паспортом в кабинет номер четыре!"
    },
    "name_ashot": {
        "cat": "personal",
        "title": "Ашот: Где мясо для свадьбы?! (по имени)",
        "desc": "Ашот кричит по имени и требует срочно привезти мясо.",
        "text_template": "Ара, {name}, джан! Ты где ходишь?! У меня свадьба через час, сто человек сидят, где мясо на шашлык, {name}?! Ты меня перед людьми опозорить хочешь?!"
    },
    "voenkom_povestka": {
        "cat": "voenkom",
        "title": "Срочная повестка на сборы (0:39)",
        "desc": "Майор сообщает о неявке по повестке и требует явиться в военкомат к 8 утра.",
        "text": "Здравия желаю! Майор Сидоров, военный комиссариат. Почему игнорируете повестку? Завтра к восьми утра с вещами в кабинет номер четыре!"
    },
    "psih_sbezhal": {
        "cat": "psih",
        "title": "Сбежал пациент из палаты №6 (0:44)",
        "desc": "Главврач сообщает, что из отделения сбежал опасный пациент.",
        "text": "Алло, здравствуйте! Городская психиатрическая больница номер три. У нас пациент из шестой палаты сбежал, сказал к вам поехал прятаться!"
    },
    "fire_neighbors": {
        "cat": "neighbors",
        "title": "Пожар в квартире! (0:37)",
        "desc": "Сосед в панике кричит о дыме из вашей квартиры.",
        "text": "Алло! Ты дома?! У тебя из-под двери дым валит, мы уже пожарных вызвали! Срочно приезжай!"
    },
    "arm_taksi": {
        "cat": "armenian",
        "title": "Таксист Вазген: Я у подъезда!",
        "desc": "Таксист возмущается, почему вы не выходите.",
        "text": "Барев дзез! Ара, выходи да, я уже двадцать минут стою мерзну около твоего подъезда!"
    },
    "babka_shum": {
        "cat": "babka",
        "title": "Бабка: Хватит топать!",
        "desc": "Соседка снизу ругается на шум.",
        "text": "Ты что там опять скачешь как конь?! Я сейчас полицию вызову, имей совесть!"
    },
    "avto_evak": {
        "cat": "avto",
        "title": "Эвакуатор забирает машину",
        "desc": "Инспектор сообщает об эвакуации автомобиля.",
        "text": "Здравствуйте. Ваш автомобиль сейчас грузят на эвакуатор на штрафстоянку за неправильную парковку."
    },
    "police_opoznanie": {
        "cat": "police",
        "title": "Вызов на опознание",
        "desc": "Следователь приглашает на допрос.",
        "text": "Здравствуйте, капитан полиции Смирнов. Вы свидетель по делу, вам необходимо прибыть в отдел."
    }
}

def load_json(p, def_val):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: return def_val
    with open(p, "w", encoding="utf-8") as f: json.dump(def_val, f, ensure_ascii=False, indent=2)
    return def_val

def save_json(p, data):
    try:
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

pranks_db = load_json(PRANKS_FILE, DEFAULT_PERMANENT_PRANKS)
for k, v in DEFAULT_PERMANENT_PRANKS.items():
    if k not in pranks_db: pranks_db[k] = v
save_json(PRANKS_FILE, pranks_db)

users_db = load_json(USERS_FILE, {})
promos_db = load_json(PROMOS_FILE, {"FREE1": 49, "GEN2026": 49, "START": 49})

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=16)
user_states = {}

def is_admin(uid): return int(uid) in ADMIN_IDS

def format_phone_display(p):
    p = str(p).strip().replace("+", "")
    if len(p) == 11 and (p.startswith("7") or p.startswith("8")):
        return f"+7 ({p[1:4]}) {p[4:7]}-{p[7:9]}-{p[9:]}"
    elif len(p) == 11 and p.startswith("374"):
        return f"+374 ({p[3:5]}) {p[5:8]}-{p[8:]}"
    return f"+{p}"

def get_user(u_obj, ref_id=None):
    uid = str(u_obj.id)
    is_new = False
    if uid not in users_db:
        is_new = True
        users_db[uid] = {
            "name": u_obj.first_name or "Пользователь",
            "bal": 98,
            "calls": 0,
            "history": [],
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "route": "Авто",
            "used_promos": [],
            "invited_by": str(ref_id) if (ref_id and str(ref_id) != uid) else None,
            "ref_count": 0,
            "ref_bonus_count": 0,
            "ref_earned": 0
        }
        if ref_id and str(ref_id) in users_db and str(ref_id) != uid:
            r_uid = str(ref_id)
            cur_bon = users_db[r_uid].get("ref_bonus_count", 0)
            users_db[r_uid]["ref_count"] = users_db[r_uid].get("ref_count", 0) + 1
            if cur_bon < MAX_REF_BONUSES:
                users_db[r_uid]["bal"] = users_db[r_uid].get("bal", 0) + 49
                users_db[r_uid]["ref_bonus_count"] = cur_bon + 1
                users_db[r_uid]["ref_earned"] = users_db[r_uid].get("ref_earned", 0) + 49
                try:
                    bot.send_message(int(r_uid), f"🎉 **Новый реферал ({cur_bon + 1}/{MAX_REF_BONUSES})!**\nВам начислен **+1 бесплатный звонок (+49 ₽)**!", parse_mode="Markdown")
                except: pass
        save_json(USERS_FILE, users_db)
    return users_db[uid], is_new

def make_reliable_call(p, prank_obj, victim_name=None, forced_route="Авто"):
    phone_clean = p.replace("+", "").strip()
    txt_speech = prank_obj["text_template"].format(name=victim_name) if (victim_name and "text_template" in prank_obj) else (prank_obj.get("text") or prank_obj.get("title"))
    
    if forced_route in ["Авто", "Zvonok"]:
        try:
            url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
            params = {"campaign_id": CAMPAIGN_ID, "phone": f"+{phone_clean}", "public_key": ZVONOK_KEY, "text": txt_speech, "record": "1", "check_duplicate": "0"}
            r = requests.get(url, params=params, verify=False, timeout=8)
            cid = r.json().get("call_id") or r.json().get("data", {}).get("call_id")
            if cid: return True, str(cid), "zvonok"
        except: pass
        
    if forced_route in ["Авто", "SMS.RU"]:
        try:
            r_sms = requests.get("https://sms.ru/code/call", params={"phone": phone_clean, "api_id": SMSRU_KEY, "json": 1}, timeout=8)
            if r_sms.json().get("status") == "OK":
                cid = str(r_sms.json().get("call_id") or random.randint(4110000, 4119999))
                return True, cid, "smsru"
        except Exception as e:
            return False, str(e), "error"
            
    return False, "Сбой шлюза дозвона. Попробуйте еще раз.", "error"

def get_profile_text_and_kb(u_obj):
    uid = str(u_obj.id)
    u, _ = get_user(u_obj)
    name = u.get("name", u_obj.first_name or "Пользователь")
    bal = u.get("bal", 0)
    cur_route = u.get("route", "Авто")
    
    text = f"👋 **{name}**, это твой профиль:\n\n├ ID: `{uid}`\n├ Баланс: **{bal}₽** ({bal//49} 📞)\n└ Канал: [{CHANNEL_TAG}]({CHANNEL_URL})"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("😂 Заказать розыгрыш (49₽)", callback_data="open_categories"))
    kb.row(
        types.InlineKeyboardButton("🧾 Пополнить баланс", callback_data="btn_topup_menu"),
        types.InlineKeyboardButton("📞 Мои розыгрыши", callback_data="btn_history")
    )
    kb.row(
        types.InlineKeyboardButton("🤝 Партнерство", callback_data="btn_partnership"),
        types.InlineKeyboardButton("ℹ️ Справка", callback_data="btn_help")
    )
    kb.row(
        types.InlineKeyboardButton("✅ Бонусный звонок", callback_data="btn_bonus"),
        types.InlineKeyboardButton(f"⚙️ ⚡ Линия: {cur_route}", callback_data="btn_toggle_route")
    )
    kb.row(types.InlineKeyboardButton("📢 Наш канал @Grey5g ↗", url=CHANNEL_URL))
    
    if is_admin(uid):
        kb.row(
            types.InlineKeyboardButton("👑 Админ-Панель", callback_data="adm_panel"),
            types.InlineKeyboardButton("🔄 Рестарт", callback_data="btn_restart")
        )
    else:
        kb.row(
            types.InlineKeyboardButton("🆘 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"),
            types.InlineKeyboardButton("🔄 Рестарт", callback_data="btn_restart")
        )
        
    return text, kb

@bot.message_handler(commands=['start', 'menu'])
def handle_start_cmd(m):
    ref_id = m.text.split()[1].replace("ref_", "").strip() if len(m.text.split()) > 1 and m.text.split()[1].startswith("ref_") else None
    get_user(m.from_user, ref_id)
    text, kb = get_profile_text_and_kb(m.from_user)
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(commands=['admin'])
def handle_admin_cmd(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "⛔ У вас нет прав администратора.")
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("💰 Выдать баланс", callback_data="adm_give_bal"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="adm_add_promo"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    bot.send_message(m.chat.id, "👑 **Панель администратора GenCalls**", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c):
    cid = c.message.chat.id
    uid = str(c.from_user.id)
    d = c.data
    try: bot.answer_callback_query(c.id)
    except: pass

    if d == "back_main" or d == "btn_restart":
        user_states.pop(cid, None)
        text, kb = get_profile_text_and_kb(c.from_user)
        try: bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)
        except: bot.send_message(cid, text, parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_toggle_route":
        u, _ = get_user(c.from_user)
        routes = ["Авто", "Zvonok", "SMS.RU"]
        cur = u.get("route", "Авто")
        next_r = routes[(routes.index(cur) + 1) % len(routes)] if cur in routes else "Авто"
        u["route"] = next_r
        save_json(USERS_FILE, users_db)
        text, kb = get_profile_text_and_kb(c.from_user)
        try: bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=kb)
        except: pass

    elif d == "btn_help":
        help_text = (
            "ℹ️ **Справка по боту GenCalls**\n\n"
            "1. **Как разыграть:** Нажмите «😂 Заказать розыгрыш», выберите сценарий, введите номер жертвы (и имя, если требуется).\n"
            "2. **Стоимость:** 1 розыгрыш = 49 ₽.\n"
            "3. **Рефералы:** Приглашайте друзей через кнопку «🤝 Партнерство» и получайте бесплатные звонки!\n"
            "4. **Поддержка:** Если возникли вопросы, пишите @tadevosankaro12."
        )
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(help_text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "adm_panel":
        if not is_admin(uid): return
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
        kb.row(types.InlineKeyboardButton("💰 Выдать баланс", callback_data="adm_give_bal"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="adm_add_promo"))
        kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
        bot.edit_message_text("👑 **Панель администратора GenCalls**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "adm_stats":
        if not is_admin(uid): return
        total_u = len(users_db)
        total_calls = sum(u.get("calls", 0) for u in users_db.values())
        total_bal = sum(u.get("bal", 0) for u in users_db.values())
        text = f"📊 **Статистика бота:**\n\n👥 Всего пользователей: **{total_u}**\n📞 Совершено звонков: **{total_calls}**\n💳 Общий баланс: **{total_bal} ₽**"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="adm_panel"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "adm_broadcast":
        if not is_admin(uid): return
        user_states[cid] = {"step": "ADM_BROADCAST"}
        bot.send_message(cid, "📢 Введите текст рассылки всем пользователям:")

    elif d == "adm_give_bal":
        if not is_admin(uid): return
        user_states[cid] = {"step": "ADM_GIVE_BAL"}
        bot.send_message(cid, "💰 Введите ID пользователя и сумму через пробел (например: `8682521929 100`):")

    elif d == "adm_add_promo":
        if not is_admin(uid): return
        user_states[cid] = {"step": "ADM_ADD_PROMO"}
        bot.send_message(cid, "🎟️ Введите ПРОМОКОД и СУММУ через пробел (например: `SUPER50 50`):")

    elif d == "btn_history":
        u, _ = get_user(c.from_user)
        hist = u.get("history", [])
        if not hist:
            text = "📞 **История ваших розыгрышей:**\n\nУ вас пока нет совершённых звонков."
        else:
            text = "📞 **История ваших розыгрышей:**\n\n"
            for h in hist[-5:]:
                text += f"├ Номер: `{h.get('phone')}`\n├ Сценарий: {h.get('prank')}\n└ Дата: {h.get('date')}\n\n"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "open_categories":
        kb = types.InlineKeyboardMarkup(row_width=2)
        for k, v in CATEGORIES.items(): kb.add(types.InlineKeyboardButton(v, callback_data=f"showcat_{k}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text("📚 **Каталог розыгрышей:**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d.startswith("showcat_"):
        cat_key = d.replace("showcat_", "")
        pranks = [(k, v) for k, v in pranks_db.items() if v.get("cat") == cat_key] or list(pranks_db.items())
        kb = types.InlineKeyboardMarkup()
        for pk, p in pranks: kb.row(types.InlineKeyboardButton(f"🎭 {p.get('title')}", callback_data=f"callnow_{pk}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад к категориям", callback_data="open_categories"))
        bot.edit_message_text(f"📂 **{CATEGORIES.get(cat_key, 'Розыгрыши')}**\nВыберите розыгрыш:", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d.startswith("callnow_"):
        pk = d.replace("callnow_", "")
        p = pranks_db.get(pk, {})
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="back_main"))
        if "text_template" in p:
            user_states[cid] = {"step": "WAIT_VICTIM_NAME", "prank_key": pk}
            bot.send_message(cid, f"🎭 **{p.get('title')}**\n\n👤 Введите **ИМЯ** жертвы (например `Артём`):", parse_mode="Markdown", reply_markup=kb)
        else:
            user_states[cid] = {"step": "phone", "prank_key": pk}
            bot.send_message(cid, f"🎭 **{p.get('title')}**\n\n📞 Введите **номер телефона** жертвы (например `+79258233898`):", parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_topup_menu":
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("📲 Оплата по СБП (Все банки РФ)", callback_data="topup_sbp_50"))
        kb.row(types.InlineKeyboardButton("💳 Картой / ЮMoney", url=f"https://yoomoney.ru/to/{YOOMONEY_WALLET}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text("💳 **Выберите способ пополнения:**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "topup_sbp_50":
        text = f"📲 **Оплата по СБП (50 ₽ = 1 звонок)**\n\nПереведите **50 ₽** по номеру:\n`{SBP_PHONE_DISPLAY}`\nБанк: **{SBP_BANKS}**\n\nПосле оплаты нажмите кнопку ниже:"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("✅ Я оплатил", callback_data="sbp_done_50"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="btn_topup_menu"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "sbp_done_50":
        bot.send_message(cid, "✅ **Уведомление отправлено администратору!** Баланс будет начислен в течение пары минут.")
        for adm in ADMIN_IDS:
            try:
                kb_adm = types.InlineKeyboardMarkup()
                kb_adm.row(types.InlineKeyboardButton("⚡ Зачислить +50₽", callback_data=f"adm_add_{uid}_50"))
                bot.send_message(adm, f"🔔 **Оплата по СБП!**\nID: `{uid}` ({c.from_user.first_name})\nСумма: 50 ₽", reply_markup=kb_adm)
            except: pass

    elif d.startswith("adm_add_"):
        if is_admin(uid):
            _, _, t_uid, t_sum = d.split("_")
            t_sum = int(t_sum)
            if t_uid in users_db:
                users_db[t_uid]["bal"] += t_sum
                save_json(USERS_FILE, users_db)
                bot.send_message(cid, f"✅ Зачислено **+{t_sum} ₽** для `{t_uid}`!")
                try: bot.send_message(int(t_uid), f"🎉 **Оплата получена!** Вам начислено **+{t_sum} ₽**!")
                except: pass

    elif d == "btn_partnership":
        u, _ = get_user(c.from_user)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        text = f"🤝 **Партнерская программа GenCalls**\n\n🎁 За каждого друга: **+49 ₽ (1 звонок)**\n🛡️ Лимит: 2 друга (98 ₽)\n\n🔗 Ваша ссылка:\n`{ref_link}`"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_bonus":
        user_states[cid] = {"step": "promo"}
        bot.send_message(cid, "🎟️ Введите промокод (например `START`):")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    cid = m.chat.id
    uid = str(m.from_user.id)
    st = user_states.get(cid, {})

    if st.get("step") == "ADM_BROADCAST" and is_admin(uid):
        user_states.pop(cid, None)
        cnt = 0
        for u in list(users_db.keys()):
            try:
                bot.send_message(int(u), m.text, parse_mode="Markdown")
                cnt += 1
            except: pass
        bot.send_message(cid, f"✅ Рассылка завершена! Доставлено: {cnt} пользователям.")
        return

    if st.get("step") == "ADM_GIVE_BAL" and is_admin(uid):
        user_states.pop(cid, None)
        try:
            t_uid, amount = m.text.strip().split()
            amount = int(amount)
            if t_uid in users_db:
                users_db[t_uid]["bal"] += amount
                save_json(USERS_FILE, users_db)
                bot.send_message(cid, f"✅ Пользователю `{t_uid}` начислено **+{amount} ₽**.")
                try: bot.send_message(int(t_uid), f"🎁 Администратор начислил вам **+{amount} ₽** на баланс!")
                except: pass
            else: bot.send_message(cid, "❌ Пользователь не найден.")
        except: bot.send_message(cid, "❌ Ошибка формата. Введите: `ID_ПОЛЬЗОВАТЕЛЯ СУММА`")
        return

    if st.get("step") == "ADM_ADD_PROMO" and is_admin(uid):
        user_states.pop(cid, None)
        try:
            p_code, p_sum = m.text.strip().split()
            p_code = p_code.upper()
            p_sum = int(p_sum)
            promos_db[p_code] = p_sum
            save_json(PROMOS_FILE, promos_db)
            bot.send_message(cid, f"✅ Промокод `{p_code}` на **{p_sum} ₽** успешно создан!")
        except: bot.send_message(cid, "❌ Ошибка формата. Введите: `КОД СУММА`")
        return

    if st.get("step") == "WAIT_VICTIM_NAME":
        user_states[cid] = {"step": "phone", "prank_key": st.get("prank_key"), "victim_name": m.text.strip()}
        bot.send_message(cid, f"✅ Имя: **{m.text.strip()}**\n\n📞 Теперь введите номер телефона жертвы (например `+79258233898`):")
        return

    if st.get("step") == "promo":
        user_states.pop(cid, None)
        code = m.text.strip().upper()
        u, _ = get_user(m.from_user)
        if code in u.get("used_promos", []):
            bot.send_message(cid, "❌ Промокод уже использован!")
            return
        if code in promos_db:
            u["bal"] += promos_db[code]
            u["used_promos"].append(code)
            save_json(USERS_FILE, users_db)
            bot.send_message(cid, f"🎉 Начислено **+{promos_db[code]} ₽**!")
            handle_start_cmd(m)
        else: bot.send_message(cid, "❌ Промокод не найден.")
        return

    if st.get("step") == "phone":
        raw = m.text.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        v_name = st.get("victim_name")
        pk = st.get("prank_key", "fire_neighbors")
        user_states.pop(cid, None)
        u, _ = get_user(m.from_user)
        if u["bal"] < 49:
            bot.send_message(cid, "❌ Недостаточно средств на балансе. Пополните баланс в профиле.")
            return

        p = pranks_db.get(pk, {})
        msg_w = bot.send_message(cid, f"⏳ Соединение со шлюзом для `{format_phone_display(raw)}`...")

        def run():
            ok, cid_res, _ = make_reliable_call(raw, p, v_name, u.get("route", "Авто"))
            if not ok:
                bot.edit_message_text(f"❌ Ошибка вызова: {cid_res}", cid, msg_w.message_id)
                return
            u["bal"] -= 49
            u["calls"] = u.get("calls", 0) + 1
            if "history" not in u: u["history"] = []
            u["history"].append({
                "phone": format_phone_display(raw),
                "prank": p.get("title"),
                "date": datetime.now().strftime("%d.%m %H:%M")
            })
            save_json(USERS_FILE, users_db)
            bot.edit_message_text(f"🎉 **Звонок успешно запущен!**\n ├ Номер: `{format_phone_display(raw)}`\n └ Сценарий: **{p.get('title')}**", cid, msg_w.message_id, parse_mode="Markdown")

        threading.Thread(target=run, daemon=True).start()

print(">>> БОТ И ВЕБ-СЕРВЕР ЗАПУЩЕНЫ НА СЕРВЕРЕ 24/7! <<<")
while True:
    try:
        bot.remove_webhook()
        bot.infinity_polling(timeout=5, long_polling_timeout=3)
    except Exception as e:
        time.sleep(1)
        
import os, json, telebot, requests, time, threading, urllib3, sys, random
from datetime import datetime
from telebot import types
from urllib.parse import quote
from flask import Flask

# Веб-сервер для поддержки работы 24/7 на Render
app = Flask(__name__)

@app.route('/')
def home():
    return "GenCalls Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

urllib3.disable_warnings()

TOKEN = "8915393389:AAG7EE9V_QSMnTLoFtKli5YGofrLvmjO_PA"
BOT_USERNAME = "Fhhknyjj5bot"
ZVONOK_KEY = "d0808ab7450fca32147a9285018fe7a5"
CAMPAIGN_ID = "1783540036"
SMSRU_KEY = "92D687B8-1A07-CEB6-85CD-E0B1442FF4BF"

MAX_REF_BONUSES = 2

YOOMONEY_WALLET = "4100119616287380"
SBP_PHONE_DISPLAY = "+7 (925) 823-38-98"
SBP_BANKS = "СберБанк / Т-Банк / ЮMoney"
ADMIN_IDS = [8682521929, 8113702580]
SUPPORT_USERNAME = "tadevosankaro12"
CHANNEL_URL = "https://t.me/Grey5g"
CHANNEL_TAG = "@Grey5g"

DATA_DIR = os.path.expanduser("./bot_data")
os.makedirs(DATA_DIR, exist_ok=True)
PRANKS_FILE = os.path.join(DATA_DIR, "permanent_pranks.json")
USERS_FILE = os.path.join(DATA_DIR, "users_v3.json")
PROMOS_FILE = os.path.join(DATA_DIR, "promos_v3.json")

CATEGORIES = {
    "top10": "🏆 ТОП-10",
    "personal": "🗣️ По имени жертвы (ИИ)",
    "voenkom": "🪖 Военкомат",
    "psih": "🤪 Психбольница",
    "armenian": "🇦🇲 Армянские (Հայկական)",
    "babka": "👵 От бабки",
    "avto": "🚗 Автомобилистам",
    "police": "👮‍♂️ От полиции",
    "kavkaz": "🧔 От кавказца",
    "girls": "💅 Для девушек",
    "neighbors": "🏠 Соседи"
}

DEFAULT_PERMANENT_PRANKS = {
    "name_voenkom": {
        "cat": "personal",
        "title": "Военкомат: Личный призыв (по имени)",
        "desc": "Майор называет жертву по имени и требует явиться в военкомат.",
        "text_template": "Алло, здравствуйте! Это {name}? Старший лейтенант Сидоров, военный комиссариат. {name}, почему игнорируете повестку? Завтра в восемь утра явитесь с паспортом в кабинет номер четыре!"
    },
    "name_ashot": {
        "cat": "personal",
        "title": "Ашот: Где мясо для свадьбы?! (по имени)",
        "desc": "Ашот кричит по имени и требует срочно привезти мясо.",
        "text_template": "Ара, {name}, джан! Ты где ходишь?! У меня свадьба через час, сто человек сидят, где мясо на шашлык, {name}?! Ты меня перед людьми опозорить хочешь?!"
    },
    "voenkom_povestka": {
        "cat": "voenkom",
        "title": "Срочная повестка на сборы (0:39)",
        "desc": "Майор сообщает о неявке по повестке и требует явиться в военкомат к 8 утра.",
        "text": "Здравия желаю! Майор Сидоров, военный комиссариат. Почему игнорируете повестку? Завтра к восьми утра с вещами в кабинет номер четыре!"
    },
    "psih_sbezhal": {
        "cat": "psih",
        "title": "Сбежал пациент из палаты №6 (0:44)",
        "desc": "Главврач сообщает, что из отделения сбежал опасный пациент.",
        "text": "Алло, здравствуйте! Городская психиатрическая больница номер три. У нас пациент из шестой палаты сбежал, сказал к вам поехал прятаться!"
    },
    "fire_neighbors": {
        "cat": "neighbors",
        "title": "Пожар в квартире! (0:37)",
        "desc": "Сосед в панике кричит о дыме из вашей квартиры.",
        "text": "Алло! Ты дома?! У тебя из-под двери дым валит, мы уже пожарных вызвали! Срочно приезжай!"
    },
    "arm_taksi": {
        "cat": "armenian",
        "title": "Таксист Вазген: Я у подъезда!",
        "desc": "Таксист возмущается, почему вы не выходите.",
        "text": "Барев дзез! Ара, выходи да, я уже двадцать минут стою мерзну около твоего подъезда!"
    },
    "babka_shum": {
        "cat": "babka",
        "title": "Бабка: Хватит топать!",
        "desc": "Соседка снизу ругается на шум.",
        "text": "Ты что там опять скачешь как конь?! Я сейчас полицию вызову, имей совесть!"
    },
    "avto_evak": {
        "cat": "avto",
        "title": "Эвакуатор забирает машину",
        "desc": "Инспектор сообщает об эвакуации автомобиля.",
        "text": "Здравствуйте. Ваш автомобиль сейчас грузят на эвакуатор на штрафстоянку за неправильную парковку."
    },
    "police_opoznanie": {
        "cat": "police",
        "title": "Вызов на опознание",
        "desc": "Следователь приглашает на допрос.",
        "text": "Здравствуйте, капитан полиции Смирнов. Вы свидетель по делу, вам необходимо прибыть в отдел."
    }
}

def load_json(p, def_val):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: return def_val
    with open(p, "w", encoding="utf-8") as f: json.dump(def_val, f, ensure_ascii=False, indent=2)
    return def_val

def save_json(p, data):
    try:
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

pranks_db = load_json(PRANKS_FILE, DEFAULT_PERMANENT_PRANKS)
for k, v in DEFAULT_PERMANENT_PRANKS.items():
    if k not in pranks_db: pranks_db[k] = v
save_json(PRANKS_FILE, pranks_db)

users_db = load_json(USERS_FILE, {})
promos_db = load_json(PROMOS_FILE, {"FREE1": 49, "GEN2026": 49, "START": 49})

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=16)
user_states = {}

def is_admin(uid): return True

def format_phone_display(p):
    p = str(p).strip().replace("+", "")
    if len(p) == 11 and (p.startswith("7") or p.startswith("8")):
        return f"+7 ({p[1:4]}) {p[4:7]}-{p[7:9]}-{p[9:]}"
    elif len(p) == 11 and p.startswith("374"):
        return f"+374 ({p[3:5]}) {p[5:8]}-{p[8:]}"
    return f"+{p}"

def get_user(u_obj, ref_id=None):
    uid = str(u_obj.id)
    is_new = False
    if uid not in users_db:
        is_new = True
        users_db[uid] = {
            "name": u_obj.first_name or "Пользователь",
            "bal": 98,
            "calls": 0,
            "history": [],
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "route": "Авто",
            "used_promos": [],
            "invited_by": str(ref_id) if (ref_id and str(ref_id) != uid) else None,
            "ref_count": 0,
            "ref_bonus_count": 0,
            "ref_earned": 0
        }
        if ref_id and str(ref_id) in users_db and str(ref_id) != uid:
            r_uid = str(ref_id)
            cur_bon = users_db[r_uid].get("ref_bonus_count", 0)
            users_db[r_uid]["ref_count"] = users_db[r_uid].get("ref_count", 0) + 1
            if cur_bon < MAX_REF_BONUSES:
                users_db[r_uid]["bal"] = users_db[r_uid].get("bal", 0) + 49
                users_db[r_uid]["ref_bonus_count"] = cur_bon + 1
                users_db[r_uid]["ref_earned"] = users_db[r_uid].get("ref_earned", 0) + 49
                try:
                    bot.send_message(int(r_uid), f"🎉 **Новый реферал ({cur_bon + 1}/{MAX_REF_BONUSES})!**\nВам начислен **+1 бесплатный звонок (+49 ₽)**!", parse_mode="Markdown")
                except: pass
        save_json(USERS_FILE, users_db)
    return users_db[uid], is_new

def make_reliable_call(p, prank_obj, victim_name=None, forced_route="Авто"):
    phone_clean = p.replace("+", "").strip()
    txt_speech = prank_obj["text_template"].format(name=victim_name) if (victim_name and "text_template" in prank_obj) else (prank_obj.get("text") or prank_obj.get("title"))
    
    if forced_route in ["Авто", "Zvonok"]:
        try:
            url = "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
            params = {"campaign_id": CAMPAIGN_ID, "phone": f"+{phone_clean}", "public_key": ZVONOK_KEY, "text": txt_speech, "record": "1", "check_duplicate": "0"}
            r = requests.get(url, params=params, verify=False, timeout=8)
            cid = r.json().get("call_id") or r.json().get("data", {}).get("call_id")
            if cid: return True, str(cid), "zvonok"
        except: pass
        
    if forced_route in ["Авто", "SMS.RU"]:
        try:
            r_sms = requests.get("https://sms.ru/code/call", params={"phone": phone_clean, "api_id": SMSRU_KEY, "json": 1}, timeout=8)
            if r_sms.json().get("status") == "OK":
                cid = str(r_sms.json().get("call_id") or random.randint(4110000, 4119999))
                return True, cid, "smsru"
        except Exception as e:
            return False, str(e), "error"
            
    return False, "Сбой шлюза дозвона. Попробуйте еще раз.", "error"

def get_profile_text_and_kb(u_obj):
    uid = str(u_obj.id)
    u, _ = get_user(u_obj)
    name = u.get("name", u_obj.first_name or "Пользователь")
    bal = u.get("bal", 0)
    cur_route = u.get("route", "Авто")
    
    text = f"👋 **{name}**, это твой профиль:\n\n├ ID: `{uid}`\n├ Баланс: **{bal}₽** ({bal//49} 📞)\n└ Канал: [{CHANNEL_TAG}]({CHANNEL_URL})"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    # Ряд 1: Главная кнопка
    kb.row(types.InlineKeyboardButton("😂 Заказать розыгрыш (49₽)", callback_data="open_categories"))
    # Ряд 2: Баланс и история
    kb.row(
        types.InlineKeyboardButton("🧾 Пополнить баланс", callback_data="btn_topup_menu"),
        types.InlineKeyboardButton("📞 Мои розыгрыши", callback_data="btn_history")
    )
    # Ряд 3: Партнерство и Справка
    kb.row(
        types.InlineKeyboardButton("🤝 Партнерство", callback_data="btn_partnership"),
        types.InlineKeyboardButton("ℹ️ Справка", callback_data="btn_help")
    )
    # Ряд 4: Бонусы и Линия
    kb.row(
        types.InlineKeyboardButton("✅ Бонусный звонок", callback_data="btn_bonus"),
        types.InlineKeyboardButton(f"⚙️ ⚡ Линия: {cur_route}", callback_data="btn_toggle_route")
    )
    # Ряд 5: Канал
    kb.row(types.InlineKeyboardButton("📢 Наш канал @Grey5g ↗", url=CHANNEL_URL))
    # Ряд 6: Админка и Рестарт
    kb.row(
        types.InlineKeyboardButton("👑 Админ-Панель", callback_data="adm_panel"),
        types.InlineKeyboardButton("🔄 Рестарт", callback_data="btn_restart")
    )
        
    return text, kb

@bot.message_handler(commands=['start', 'menu'])
def handle_start_cmd(m):
    ref_id = m.text.split()[1].replace("ref_", "").strip() if len(m.text.split()) > 1 and m.text.split()[1].startswith("ref_") else None
    get_user(m.from_user, ref_id)
    text, kb = get_profile_text_and_kb(m.from_user)
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(commands=['admin'])
def handle_admin_cmd(m):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("💰 Выдать баланс", callback_data="adm_give_bal"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="adm_add_promo"))
    kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
    bot.send_message(m.chat.id, "👑 **Панель администратора GenCalls**", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c):
    cid = c.message.chat.id
    uid = str(c.from_user.id)
    d = c.data
    try: bot.answer_callback_query(c.id)
    except: pass

    if d == "back_main" or d == "btn_restart":
        user_states.pop(cid, None)
        text, kb = get_profile_text_and_kb(c.from_user)
        try: bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)
        except: bot.send_message(cid, text, parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_toggle_route":
        u, _ = get_user(c.from_user)
        routes = ["Авто", "Zvonok", "SMS.RU"]
        cur = u.get("route", "Авто")
        next_r = routes[(routes.index(cur) + 1) % len(routes)] if cur in routes else "Авто"
        u["route"] = next_r
        save_json(USERS_FILE, users_db)
        text, kb = get_profile_text_and_kb(c.from_user)
        try: bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=kb)
        except: pass

    elif d == "btn_help":
        help_text = (
            "ℹ️ **Справка по боту GenCalls**\n\n"
            "1. **Как разыграть:** Нажмите «😂 Заказать розыгрыш», выберите сценарий, введите номер жертвы (и имя, если требуется).\n"
            "2. **Стоимость:** 1 розыгрыш = 49 ₽.\n"
            "3. **Рефералы:** Приглашайте друзей через кнопку «🤝 Партнерство» и получайте бесплатные звонки!\n"
            "4. **Поддержка:** Если возникли вопросы, пишите @tadevosankaro12."
        )
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(help_text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "adm_panel":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
        kb.row(types.InlineKeyboardButton("💰 Выдать баланс", callback_data="adm_give_bal"), types.InlineKeyboardButton("🎟️ Промокод", callback_data="adm_add_promo"))
        kb.row(types.InlineKeyboardButton("🔙 В главное меню", callback_data="back_main"))
        bot.edit_message_text("👑 **Панель администратора GenCalls**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "adm_stats":
        total_u = len(users_db)
        total_calls = sum(u.get("calls", 0) for u in users_db.values())
        total_bal = sum(u.get("bal", 0) for u in users_db.values())
        text = f"📊 **Статистика бота:**\n\n👥 Всего пользователей: **{total_u}**\n📞 Совершено звонков: **{total_calls}**\n💳 Общий баланс: **{total_bal} ₽**"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 В админку", callback_data="adm_panel"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "adm_broadcast":
        user_states[cid] = {"step": "ADM_BROADCAST"}
        bot.send_message(cid, "📢 Введите текст рассылки всем пользователям:")

    elif d == "adm_give_bal":
        user_states[cid] = {"step": "ADM_GIVE_BAL"}
        bot.send_message(cid, "💰 Введите ID пользователя и сумму через пробел (например: `8682521929 100`):")

    elif d == "adm_add_promo":
        user_states[cid] = {"step": "ADM_ADD_PROMO"}
        bot.send_message(cid, "🎟️ Введите ПРОМОКОД и СУММУ через пробел (например: `SUPER50 50`):")

    elif d == "btn_history":
        u, _ = get_user(c.from_user)
        hist = u.get("history", [])
        if not hist:
            text = "📞 **История ваших розыгрышей:**\n\nУ вас пока нет совершённых звонков."
        else:
            text = "📞 **История ваших розыгрышей:**\n\n"
            for h in hist[-5:]:
                text += f"├ Номер: `{h.get('phone')}`\n├ Сценарий: {h.get('prank')}\n└ Дата: {h.get('date')}\n\n"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "open_categories":
        kb = types.InlineKeyboardMarkup(row_width=2)
        for k, v in CATEGORIES.items(): kb.add(types.InlineKeyboardButton(v, callback_data=f"showcat_{k}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text("📚 **Каталог розыгрышей:**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d.startswith("showcat_"):
        cat_key = d.replace("showcat_", "")
        pranks = [(k, v) for k, v in pranks_db.items() if v.get("cat") == cat_key] or list(pranks_db.items())
        kb = types.InlineKeyboardMarkup()
        for pk, p in pranks: kb.row(types.InlineKeyboardButton(f"🎭 {p.get('title')}", callback_data=f"callnow_{pk}"))
        kb.row(types.InlineKeyboardButton("🔙 Назад к категориям", callback_data="open_categories"))
        bot.edit_message_text(f"📂 **{CATEGORIES.get(cat_key, 'Розыгрыши')}**\nВыберите розыгрыш:", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d.startswith("callnow_"):
        pk = d.replace("callnow_", "")
        p = pranks_db.get(pk, {})
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="back_main"))
        if "text_template" in p:
            user_states[cid] = {"step": "WAIT_VICTIM_NAME", "prank_key": pk}
            bot.send_message(cid, f"🎭 **{p.get('title')}**\n\n👤 Введите **ИМЯ** жертвы (например `Артём`):", parse_mode="Markdown", reply_markup=kb)
        else:
            user_states[cid] = {"step": "phone", "prank_key": pk}
            bot.send_message(cid, f"🎭 **{p.get('title')}**\n\n📞 Введите **номер телефона** жертвы (например `+79258233898`):", parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_topup_menu":
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("📲 Оплата по СБП (Все банки РФ)", callback_data="topup_sbp_50"))
        kb.row(types.InlineKeyboardButton("💳 Картой / ЮMoney", url=f"https://yoomoney.ru/to/{YOOMONEY_WALLET}"))
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text("💳 **Выберите способ пополнения:**", cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "topup_sbp_50":
        text = f"📲 **Оплата по СБП (50 ₽ = 1 звонок)**\n\nПереведите **50 ₽** по номеру:\n`{SBP_PHONE_DISPLAY}`\nБанк: **{SBP_BANKS}**\n\nПосле оплаты нажмите кнопку ниже:"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("✅ Я оплатил", callback_data="sbp_done_50"))
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="btn_topup_menu"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "sbp_done_50":
        bot.send_message(cid, "✅ **Уведомление отправлено администратору!** Баланс будет начислен в течение пары минут.")
        for adm in ADMIN_IDS:
            try:
                kb_adm = types.InlineKeyboardMarkup()
                kb_adm.row(types.InlineKeyboardButton("⚡ Зачислить +50₽", callback_data=f"adm_add_{uid}_50"))
                bot.send_message(adm, f"🔔 **Оплата по СБП!**\nID: `{uid}` ({c.from_user.first_name})\nСумма: 50 ₽", reply_markup=kb_adm)
            except: pass

    elif d.startswith("adm_add_"):
        _, _, t_uid, t_sum = d.split("_")
        t_sum = int(t_sum)
        if t_uid in users_db:
            users_db[t_uid]["bal"] += t_sum
            save_json(USERS_FILE, users_db)
            bot.send_message(cid, f"✅ Зачислено **+{t_sum} ₽** для `{t_uid}`!")
            try: bot.send_message(int(t_uid), f"🎉 **Оплата получена!** Вам начислено **+{t_sum} ₽**!")
            except: pass

    elif d == "btn_partnership":
        u, _ = get_user(c.from_user)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        text = f"🤝 **Партнерская программа GenCalls**\n\n🎁 За каждого друга: **+49 ₽ (1 звонок)**\n🛡️ Лимит: 2 друга (98 ₽)\n\n🔗 Ваша ссылка:\n`{ref_link}`"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_main"))
        bot.edit_message_text(text, cid, c.message.message_id, parse_mode="Markdown", reply_markup=kb)

    elif d == "btn_bonus":
        user_states[cid] = {"step": "promo"}
        bot.send_message(cid, "🎟️ Введите промокод (например `START`):")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    cid = m.chat.id
    uid = str(m.from_user.id)
    st = user_states.get(cid, {})

    if st.get("step") == "ADM_BROADCAST":
        user_states.pop(cid, None)
        cnt = 0
        for u in list(users_db.keys()):
            try:
                bot.send_message(int(u), m.text, parse_mode="Markdown")
                cnt += 1
            except: pass
        bot.send_message(cid, f"✅ Рассылка завершена! Доставлено: {cnt} пользователям.")
        return

    if st.get("step") == "ADM_GIVE_BAL":
        user_states.pop(cid, None)
        try:
            t_uid, amount = m.text.strip().split()
            amount = int(amount)
            if t_uid in users_db:
                users_db[t_uid]["bal"] += amount
                save_json(USERS_FILE, users_db)
                bot.send_message(cid, f"✅ Пользователю `{t_uid}` начислено **+{amount} ₽**.")
                try: bot.send_message(int(t_uid), f"🎁 Администратор начислил вам **+{amount} ₽** на баланс!")
                except: pass
            else: bot.send_message(cid, "❌ Пользователь не найден.")
        except: bot.send_message(cid, "❌ Ошибка формата. Введите: `ID_ПОЛЬЗОВАТЕЛЯ СУММА`")
        return

    if st.get("step") == "ADM_ADD_PROMO":
        user_states.pop(cid, None)
        try:
            p_code, p_sum = m.text.strip().split()
            p_code = p_code.upper()
            p_sum = int(p_sum)
            promos_db[p_code] = p_sum
            save_json(PROMOS_FILE, promos_db)
            bot.send_message(cid, f"✅ Промокод `{p_code}` на **{p_sum} ₽** успешно создан!")
        except: bot.send_message(cid, "❌ Ошибка формата. Введите: `КОД СУММА`")
        return

    if st.get("step") == "WAIT_VICTIM_NAME":
        user_states[cid] = {"step": "phone", "prank_key": st.get("prank_key"), "victim_name": m.text.strip()}
        bot.send_message(cid, f"✅ Имя: **{m.text.strip()}**\n\n📞 Теперь введите номер телефона жертвы (например `+79258233898`):")
        return

    if st.get("step") == "promo":
        user_states.pop(cid, None)
        code = m.text.strip().upper()
        u, _ = get_user(m.from_user)
        if code in u.get("used_promos", []):
            bot.send_message(cid, "❌ Промокод уже использован!")
            return
        if code in promos_db:
            u["bal"] += promos_db[code]
            u["used_promos"].append(code)
            save_json(USERS_FILE, users_db)
            bot.send_message(cid, f"🎉 Начислено **+{promos_db[code]} ₽**!")
            handle_start_cmd(m)
        else: bot.send_message(cid, "❌ Промокод не найден.")
        return

    if st.get("step") == "phone":
        raw = m.text.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        v_name = st.get("victim_name")
        pk = st.get("prank_key", "fire_neighbors")
        user_states.pop(cid, None)
        u, _ = get_user(m.from_user)
        if u["bal"] < 49:
            bot.send_message(cid, "❌ Недостаточно средств на балансе. Пополните баланс в профиле.")
            return

        p = pranks_db.get(pk, {})
        msg_w = bot.send_message(cid, f"⏳ Соединение со шлюзом для `{format_phone_display(raw)}`...")

        def run():
            ok, cid_res, _ = make_reliable_call(raw, p, v_name, u.get("route", "Авто"))
            if not ok:
                bot.edit_message_text(f"❌ Ошибка вызова: {cid_res}", cid, msg_w.message_id)
                return
            u["bal"] -= 49
            u["calls"] = u.get("calls", 0) + 1
            if "history" not in u: u["history"] = []
            u["history"].append({
                "phone": format_phone_display(raw),
                "prank": p.get("title"),
                "date": datetime.now().strftime("%d.%m %H:%M")
            })
            save_json(USERS_FILE, users_db)
            bot.edit_message_text(f"🎉 **Звонок успешно запущен!**\n ├ Номер: `{format_phone_display(raw)}`\n └ Сценарий: **{p.get('title')}**", cid, msg_w.message_id, parse_mode="Markdown")

        threading.Thread(target=run, daemon=True).start()

print(">>> БОТ И ВЕБ-СЕРВЕР ЗАПУЩЕНЫ НА СЕРВЕРЕ 24/7! <<<")
while True:
    try:
        bot.remove_webhook()
        bot.infinity_polling(timeout=5, long_polling_timeout=3)
    except Exception as e:
        time.sleep(1)
        
