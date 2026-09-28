import os
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@kurs_gryvni_ua"

DATA_FILE = "rates.json"
HISTORY_FILE = "history.json"


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


def load_history():
    history = {
        "usd": [],
        "eur": []
    }

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as file:
                history = json.load(file)
        except Exception:
            pass

    history.setdefault("usd", [])
    history.setdefault("eur", [])

    return history


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2
        )


def get_recent_values(items, hours=24):
    now = datetime.now(timezone.utc)
    limit = now - timedelta(hours=hours)

    values = []

    for item in items:
        try:
            item_time = datetime.fromisoformat(item["date"])

            if item_time.tzinfo is None:
                item_time = item_time.replace(tzinfo=timezone.utc)

            if item_time >= limit:
                values.append({
                    "date": item_time,
                    "rate": float(item["rate"])
                })

        except Exception:
            continue

    values.sort(key=lambda x: x["date"])

    return values


def make_forecast(values):
    """
    Простий статистичний прогноз.

    Використовуємо середню зміну між вимірюваннями
    за останні 24 години.

    Потрібно мінімум 3 вимірювання.
    """

    if len(values) < 3:
        return None

    changes = []

    for i in range(1, len(values)):
        change = values[i]["rate"] - values[i - 1]["rate"]
        changes.append(change)

    if not changes:
        return None

    average_change = sum(changes) / len(changes)

    current_rate = values[-1]["rate"]

    forecast = current_rate + average_change

    return {
        "current": current_rate,
        "forecast": forecast,
        "change": forecast - current_rate,
        "samples": len(values)
    }


# -----------------------------------
# Отримуємо попередній курс
# -----------------------------------

previous = {}

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            previous = json.load(file)
    except Exception:
        pass


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
# Час
# -----------------------------------

kyiv_time = datetime.now(
    ZoneInfo("Europe/Kyiv")
)

now = datetime.now(timezone.utc).isoformat()


# -----------------------------------
# Завантажуємо історію
# -----------------------------------

history = load_history()


# -----------------------------------
# Додаємо нові значення
# -----------------------------------

history["usd"].append({
    "date": now,
    "rate": usd
})

history["eur"].append({
    "date": now,
    "rate": eur
})


# -----------------------------------
# Зберігаємо історію
# -----------------------------------

save_history(history)


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
# Розрахунок прогнозу
# -----------------------------------

usd_recent = get_recent_values(
    history["usd"],
    24
)

eur_recent = get_recent_values(
    history["eur"],
    24
)

usd_forecast = make_forecast(usd_recent)
eur_forecast = make_forecast(eur_recent)


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


# -----------------------------------
# Додаємо прогноз
# -----------------------------------

if usd_forecast is not None or eur_forecast is not None:

    message += "\n\n🔮 ОРІЄНТОВНИЙ ПРОГНОЗ\n"

    if usd_forecast is not None:
        message += (
            "\n🇺🇸 USD на наступну добу:\n"
            f"≈ {usd_forecast['forecast']:.2f} грн\n"
            f"{change_text(usd_forecast['change'])}\n"
            f"📊 Вимірювань: {usd_forecast['samples']}"
        )

    if eur_forecast is not None:
        message += (
            "\n\n🇪🇺 EUR на наступну добу:\n"
            f"≈ {eur_forecast['forecast']:.2f} грн\n"
            f"{change_text(eur_forecast['change'])}\n"
            f"📊 Вимірювань: {eur_forecast['samples']}"
        )

    message += (
        "\n\n⚠️ Прогноз статистичний і не гарантує "
        "майбутній курс."
    )

else:

    message += (
        "\n\n🔮 ПРОГНОЗ\n"
        "⏳ Поки недостатньо історичних даних."
    )


# -----------------------------------
# Відправляємо повідомлення
# -----------------------------------

send_message(message)


print("Опубліковано успішно!")
print("Історію збережено!")
print("Прогноз розраховано.")
