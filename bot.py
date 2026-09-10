import os
import hashlib
import telebot
from telebot import types

# ---------------------------------------------
# НАСТРОЙКИ ПЛАТЕЖЕЙ И БОТА
# ---------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "7963495471:AAFLR2L1R88ZqK-4X-T9fU-h5H6A8m-o") # ваш токен
ADMIN_ID = 1438908852  # ваш Telegram ID

# Реквизиты ЮMoney (автоматическое зачисление по секрету)
YOOMONEY_WALLET = "4100119616287380"
YOOMONEY_SECRET = "D2LS1zPM2UPAZ9wLeEVdbx7i"

# Ссылка на оплату через СБП (Lava)
LAVA_PAY_URL = "https://app.lava.top/products/a86f2412-debe-42a3-83fc-ab3abdc5a967"

# Тарифные пакеты
PACKAGES = {
    "pkg_1": {"title": "3 звонка", "price": "49 ₽", "rub": 49, "calls": 3},
    "pkg_2": {"title": "10 звонков", "price": "149 ₽", "rub": 149, "calls": 10},
    "pkg_3": {"title": "25 звонков", "price": "299 ₽", "rub": 299, "calls": 25},
    "pkg_4": {"title": "Безлимит на 24 часа", "price": "499 ₽", "rub": 499, "calls": 999}
}

# Генератор быстрой ссылки ЮMoney
def create_yoomoney_payment(user_id, amount_rub, comment=""):
    import uuid
    pay_id = f"pay_{user_id}_{uuid.uuid4().hex[:8]}"
    base_url = "https://yoomoney.ru/quickpay/confirm.xml"
    params = {
        "receiver": YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": f"GenCalls: {comment}",
        "paymentType": "SB",  # SberPay / Карты
        "sum": str(amount_rub),
        "label": f"{user_id}:{amount_rub}:{pay_id}"
    }
    from urllib.parse import urlencode
    pay_url = f"{base_url}?{urlencode(params)}"
    return pay_id, pay_url

# Обработчик выбора пакета с двумя кнопками оплаты (СБП и ЮMoney)
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_pkg_"))
def on_buy_package(c):
    pid = c.data.replace("buy_", "")
    pkg = PACKAGES.get(pid, {})
    user_id = c.message.chat.id
    rub = pkg.get("rub", 49)
    pay_id, ym_url = create_yoomoney_payment(user_id, rub, f"{pkg.get('title')} ({rub} ₽)")
    
    text = (
        f"📦 *{pkg.get('title')} ({pkg.get('price')})*\n\n"
        f"Выберите удобный способ оплаты:\n\n"
        f"1️⃣ 📲 *СБП / Карты / Сбербанк (Lava)*\n"
        f"• Любой банк РФ (Сбер, Т-Банк, ВТБ, Альфа)\n\n"
        f"2️⃣ 🟣 *ЮMoney / SberPay / Карты*\n"
        f"• В 1 клик через ЮMoney"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"📲 Оплатить через СБП ({pkg.get('price')})", url=LAVA_PAY_URL))
    kb.row(types.InlineKeyboardButton(f"🟣 Оплатить через ЮMoney / SberPay", url=ym_url))
    kb.row(types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_ym_{pay_id}"))
    kb.row(types.InlineKeyboardButton("🔙 Назад к тарифам", callback_data="packages_menu"))
    
    safe_nav(c, text, reply_markup=kb)
