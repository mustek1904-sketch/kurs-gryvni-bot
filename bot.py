import os
import json
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@kurs_gryvni_ua"

DATA_FILE = "rates.json"
HISTORY_FILE = "history.json"
SUMMARY_FILE = "daily_summary.json"


def get_rate(currency):
    url = (
        "https://bank.gov.ua/NBUStatService/v1/statdirectory/"
        f"exchange?valcode={currency}&json"
    )

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    return float(response.json()[0]["rate"])


def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL,
            "text": text
        },
        timeout=10
    )

    response.raise_for_status()


def change_text(change):
    if change > 0:
        return f"🔺 +{change:.4f} грн"
    elif change < 0:
        return f"🔻 {change:.4f} грн"
    else:
        return "➡️ без змін"


# -----------------------------------
# Попередній курс
# -----------------------------------

previous = {}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        previous = json.load(file)


# -----------------------------------
# Отримуємо курс НБУ
# -----------------------------------

usd = get_rate("USD")
eur = get_rate("EUR")

previous_usd = previous.get("usd")
previous_eur = previous.get("eur")

usd_change = (
    usd - previous_usd
    if previous_usd is not None
    else 0
)

eur_change = (
    eur - previous_eur
    if previous_eur is not None
    else 0
)


# -----------------------------------
# Київський час
# -----------------------------------

kyiv_time = datetime.now(
    ZoneInfo("Europe/Kyiv")
)

now = datetime.now(timezone.utc).isoformat()


# -----------------------------------
# Основне повідомлення
# -----------------------------------

message = (
    "💰 КУРС ГРИВНІ\n\n"
    f"🇺🇸 USD: {usd:.2f} грн\n"
    f"{change_text(usd_change)}\n\n"
    f"🇪🇺 EUR: {eur:.2f} грн\n"
    f"{change_text(eur_change)}\n\n"
    f"🕐 Оновлено: "
    f"{kyiv_time.strftime('%d.%m.%Y о %H:%M')}\n"
    "📊 Дані: НБУ"
)

send_message(message)


# -----------------------------------
# Історія
# -----------------------------------

history = {
    "usd": [],
    "eur": []
}

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as file:
        history = json.load(file)

history.setdefault("usd", [])
history.setdefault("eur", [])


history["usd"].append({
    "date": now,
    "rate": usd
})

history["eur"].append({
    "date": now,
    "rate": eur
})


with open(HISTORY_FILE, "w", encoding="utf-8") as file:
    json.dump(
        history,
        file,
        ensure_ascii=False,
        indent=2
    )


# -----------------------------------
# Зберігаємо останній курс
# -----------------------------------

data = {
    "usd": usd,
    "eur": eur,
    "updated": now
}

with open(DATA_FILE, "w", encoding="utf-8") as file:
    json.dump(
        data,
        file,
        ensure_ascii=False,
        indent=2
    )


# -----------------------------------
# ЩОДЕННИЙ ПІДСУМОК
# -----------------------------------

today = kyiv_time.strftime("%Y-%m-%d")

# Завантажуємо інформацію про останній підсумок
summary_data = {}

if os.path.exists(SUMMARY_FILE):
    with open(SUMMARY_FILE, "r", encoding="utf-8") as file:
        summary_data = json.load(file)

last
