import os
import json
import requests
from datetime import datetime, timezone

TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@kurs_gryvni_ua"
DATA_FILE = "rates.json"


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
        data={"chat_id": CHANNEL, "text": text},
        timeout=10
    )
    response.raise_for_status()


# Завантажуємо попередній курс
previous = {}

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            previous = json.load(file)
    except Exception:
        previous = {}


# Отримуємо актуальний курс
usd = get_rate("USD")
eur = get_rate("EUR")

previous_usd = previous.get("usd")
previous_eur = previous.get("eur")

# Розраховуємо зміну
usd_change = usd - previous_usd if previous_usd is not None else 0
eur_change = eur - previous_eur if previous_eur is not None else 0


# Напрямок зміни
if usd_change > 0:
    usd_signal = "📈 USD росте"
elif usd_change < 0:
    usd_signal = "📉 USD падає"
else:
    usd_signal = "➡️ USD без змін"

if eur_change > 0:
    eur_signal = "📈 EUR росте"
elif eur_change < 0:
    eur_signal = "📉 EUR падає"
else:
    eur_signal = "➡️ EUR без змін"


message = (
    "💰 Курс гривні\n\n"
    f"🇺🇸 USD: {usd:.2f} грн ({usd_change:+.2f})\n"
    f"{usd_signal}\n\n"
    f"🇪🇺 EUR: {eur:.2f} грн ({eur_change:+.2f})\n"
    f"{eur_signal}\n\n"
    "📊 Дані: НБУ"
)

send_message(message)


# Зберігаємо актуальний курс
data = {
    "usd": usd,
    "eur": eur,
    "updated": datetime.now(timezone.utc).isoformat()
}

with open(DATA_FILE, "w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=2)

print("Опубліковано успішно!")
print("USD:", usd, "зміна:", usd_change)
print("EUR:", eur, "зміна:", eur_change)
