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
        return f"📈 +{change:.4f} грн"
    elif change < 0:
        return f"📉 {change:.4f} грн"
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


def prepare_values(items, days=7):
    now = datetime.now(timezone.utc)
    limit = now - timedelta(days=days)

    values = []

    for item in items:
        try:
            item_time = datetime.fromisoformat(item["date"])

            if item_time.tzinfo is None:
                item_time = item_time.replace(
                    tzinfo=timezone.utc
                )

            if item_time >= limit:
                values.append({
                    "date": item_time,
                    "rate": float(item["rate"])
                })

        except Exception:
            continue

    values.sort(key=lambda x: x["date"])

    return values


def calculate_forecast(values):
    """
    Статистичний прогноз на наступні 24 години.

    Використовує лінійну тенденцію історичних значень.
    """

    if len(values) < 12:
        return None

    # Беремо максимум 336 останніх точок
    # (7 днів при запуску кожні 30 хвилин)
    values = values[-336:]

    first_time = values[0]["date"]

    x = []
    y = []

    for item in values:
        minutes = (
            item["date"] - first_time
        ).total_seconds() / 60

        x.append(minutes)
        y.append(item["rate"])

    if len(x) < 2:
        return None

    average_x = sum(x) / len(x)
    average_y = sum(y) / len(y)

    numerator = 0
    denominator = 0

    for i in range(len(x)):
        numerator += (
            (x[i] - average_x)
            * (y[i] - average_y)
        )

        denominator += (
            (x[i] - average_x) ** 2
        )

    if denominator == 0:
        return None

    slope = numerator / denominator

    current_rate = values[-1]["rate"]

    # Прогноз на 24 години
    forecast = current_rate + (
        slope * 1440
    )

    # Захист від нереалістичного стрибка.
    # Максимум ±2% від поточного курсу.
    maximum_change = current_rate * 0.02

    if forecast > current_rate + maximum_change:
        forecast = current_rate + maximum_change

    if forecast < current_rate - maximum_change:
        forecast = current_rate - maximum_change

    forecast_change = forecast - current_rate

    if forecast_change > 0.005:
        trend = "📈 тенденція до зростання"
    elif forecast_change < -0.005:
        trend = "📉 тенденція до зниження"
    else:
        trend = "➡️ тенденція стабільна"

    return {
        "current": current_rate,
        "forecast": forecast,
        "change": forecast_change,
        "trend": trend,
        "samples": len(values)
    }


# -----------------------------------
# Попередній курс
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
# Історія
# -----------------------------------

history = load_history()

history["usd"].append({
    "date": now,
    "rate": usd
})

history["eur"].append({
    "date": now,
    "rate": eur
})

save_history(history)


# -----------------------------------
# Поточний курс
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
# Готуємо дані для прогнозу
# -----------------------------------

usd_values = prepare_values(
    history["usd"],
    days=7
)

eur_values = prepare_values(
    history["eur"],
    days=7
)

usd_forecast = calculate_forecast(
    usd_values
)

eur_forecast = calculate_forecast(
    eur_values
)


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
# Прогноз
# -----------------------------------

if usd_forecast is not None or eur_forecast is not None:

    message += (
        "\n\n"
        "🔮 ОРІЄНТОВНИЙ ПРОГНОЗ НА 24 ГОДИНИ"
    )

    if usd_forecast is not None:

        message += (
            "\n\n"
            "🇺🇸 USD\n"
            f"Поточний: {usd:.2f} грн\n"
            f"Прогноз: ≈ "
            f"{usd_forecast['forecast']:.2f} грн\n"
            f"{change_text(usd_forecast['change'])}\n"
            f"{usd_forecast['trend']}\n"
            f"📊 Даних використано: "
            f"{usd_forecast['samples']}"
        )

    if eur_forecast is not None:

        message += (
            "\n\n"
            "🇪🇺 EUR\n"
            f"Поточний: {eur:.2f} грн\n"
            f"Прогноз: ≈ "
            f"{eur_forecast['forecast']:.2f} грн\n"
            f"{change_text(eur_forecast['change'])}\n"
            f"{eur_forecast['trend']}\n"
            f"📊 Даних використано: "
            f"{eur_forecast['samples']}"
        )

    message += (
        "\n\n"
        "⚠️ Це статистична оцінка, "
        "а не гарантований майбутній курс."
    )

else:

    message += (
        "\n\n"
        "🔮 ПРОГНОЗ\n"
        "⏳ Поки недостатньо історичних даних "
        "для статистичного прогнозу."
    )


# -----------------------------------
# Відправляємо повідомлення
# -----------------------------------

send_message(message)


print("Опубліковано успішно!")
print("Історію збережено!")
print("Статистичний прогноз розраховано.")
