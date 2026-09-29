import os
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@kurs_gryvni_ua"

DATA_FILE = "rates.json"
HISTORY_FILE = "history.json"

MORNING_HOUR = 9

# Мінімальна зміна крипти для публікації
CRYPTO_CHANGE_THRESHOLD = 0.005  # 0,5%


# ==================================================
# КРИПТОВАЛЮТИ
# ==================================================

CRYPTO = {
    "btc-bitcoin": "₿ BTC",
    "eth-ethereum": "Ξ ETH",
    "usdt-tether": "💵 USDT",
    "etc-ethereum-classic": "🔷 ETC",
    "zec-zcash": "🛡 ZEC"
}


# ==================================================
# КУРС НБУ
# ==================================================

def get_rate(currency):

    url = (
        "https://bank.gov.ua/NBUStatService/v1/statdirectory/"
        f"exchange?valcode={currency}&json"
    )

    response = requests.get(
        url,
        timeout=10
    )

    response.raise_for_status()

    return float(
        response.json()[0]["rate"]
    )


# ==================================================
# КРИПТОВАЛЮТИ
# ==================================================

def get_crypto_rates():

    url = (
        "https://api.coinpaprika.com/v1/tickers"
        "?quotes=USD"
    )

    try:

        response = requests.get(
            url,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        result = {}

        wanted = set(
            CRYPTO.keys()
        )

        for coin in data:

            coin_id = coin.get("id")

            if coin_id not in wanted:
                continue

            quotes = coin.get(
                "quotes",
                {}
            )

            usd = quotes.get(
                "USD",
                {}
            )

            price = usd.get(
                "price"
            )

            change_24h = usd.get(
                "percent_change_24h",
                0
            )

            if price is None:
                continue

            result[coin_id] = {
                "usd": float(price),
                "change_24h": float(
                    change_24h or 0
                )
            }

        return result

    except Exception as error:

        print(
            "Помилка отримання крипти:",
            error
        )

        return {}


# ==================================================
# TELEGRAM
# ==================================================

def telegram_request(
    method,
    data
):

    url = (
        f"https://api.telegram.org/"
        f"bot{TOKEN}/{method}"
    )

    response = requests.post(
        url,
        data=data,
        timeout=15
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):

        raise Exception(
            result.get(
                "description",
                "Telegram API error"
            )
        )

    return result["result"]


def send_message(text):

    return telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL,
            "text": text
        }
    )


def edit_message(
    message_id,
    text
):

    return telegram_request(
        "editMessageText",
        {
            "chat_id": CHANNEL,
            "message_id": message_id,
            "text": text
        }
    )


def pin_message(message_id):

    return telegram_request(
        "pinChatMessage",
        {
            "chat_id": CHANNEL,
            "message_id": message_id,
            "disable_notification": True
        }
    )


# ==================================================
# ТЕКСТ
# ==================================================

def change_text(change):

    if change > 0:

        return (
            f"📈 +{change:.4f} грн"
        )

    elif change < 0:

        return (
            f"📉 {change:.4f} грн"
        )

    else:

        return "➡️ без змін"


def crypto_change_text(percent):

    if percent > 0:

        return (
            f"📈 +{percent:.2f}%"
        )

    elif percent < 0:

        return (
            f"📉 {percent:.2f}%"
        )

    else:

        return "➡️ без змін"


# ==================================================
# ІСТОРІЯ
# ==================================================

def load_history():

    history = {
        "usd": [],
        "eur": []
    }

    if os.path.exists(
        HISTORY_FILE
    ):

        try:

            with open(
                HISTORY_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                history = json.load(file)

        except Exception:

            pass

    history.setdefault(
        "usd",
        []
    )

    history.setdefault(
        "eur",
        []
    )

    return history


def save_history(history):

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2
        )


# ==================================================
# ПІДГОТОВКА ПРОГНОЗУ
# ==================================================

def prepare_values(
    items,
    days=7
):

    now = datetime.now(
        timezone.utc
    )

    limit = (
        now -
        timedelta(days=days)
    )

    values = []

    for item in items:

        try:

            item_time = (
                datetime.fromisoformat(
                    item["date"]
                )
            )

            if item_time.tzinfo is None:

                item_time = (
                    item_time.replace(
                        tzinfo=timezone.utc
                    )
                )

            if item_time >= limit:

                values.append(
                    {
                        "date": item_time,
                        "rate": float(
                            item["rate"]
                        )
                    }
                )

        except Exception:

            continue

    values.sort(
        key=lambda x: x["date"]
    )

    return values


def calculate_forecast(
    values
):

    if len(values) < 12:

        return None

    values = values[-336:]

    first_time = (
        values[0]["date"]
    )

    x = []
    y = []

    for item in values:

        minutes = (
            item["date"] -
            first_time
        ).total_seconds() / 60

        x.append(minutes)
        y.append(
            item["rate"]
        )

    average_x = (
        sum(x) / len(x)
    )

    average_y = (
        sum(y) / len(y)
    )

    numerator = 0
    denominator = 0

    for i in range(len(x)):

        numerator += (
            (x[i] - average_x)
            *
            (y[i] - average_y)
        )

        denominator += (
            (x[i] - average_x) ** 2
        )

    if denominator == 0:

        return None

    slope = (
        numerator /
        denominator
    )

    current_rate = (
        values[-1]["rate"]
    )

    forecast = (
        current_rate +
        slope * 1440
    )

    maximum_change = (
        current_rate * 0.02
    )

    if (
        forecast >
        current_rate +
        maximum_change
    ):

        forecast = (
            current_rate +
            maximum_change
        )

    if (
        forecast <
        current_rate -
        maximum_change
    ):

        forecast = (
            current_rate -
            maximum_change
        )

    forecast_change = (
        forecast -
        current_rate
    )

    if forecast_change > 0.005:

        trend = (
            "📈 тенденція до зростання"
        )

    elif forecast_change < -0.005:

        trend = (
            "📉 тенденція до зниження"
        )

    else:

        trend = (
            "➡️ тенденція стабільна"
        )

    return {
        "current": current_rate,
        "forecast": forecast,
        "change": forecast_change,
        "trend": trend,
        "samples": len(values)
    }


# ==================================================
# ПОПЕРЕДНІ ДАНІ
# ==================================================

previous = {}

if os.path.exists(
    DATA_FILE
):

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            previous = json.load(file)

    except Exception:

        pass


previous_usd = previous.get(
    "usd"
)

previous_eur = previous.get(
    "eur"
)

previous_crypto = previous.get(
    "crypto",
    {}
)

last_morning_date = (
    previous.get(
        "last_morning_date"
    )
)

# ID закріпленого повідомлення
pinned_message_id = (
    previous.get(
        "pinned_message_id"
    )
)


# ==================================================
# КУРС НБУ
# ==================================================

usd = get_rate(
    "USD"
)

eur = get_rate(
    "EUR"
)


# ==================================================
# КРИПТО
# ==================================================

crypto_data = (
    get_crypto_rates()
)

crypto_rates = {}


for coin_id in CRYPTO:

    if coin_id not in crypto_data:

        continue

    usd_price = (
        crypto_data[
            coin_id
        ]["usd"]
    )

    change_24h = (
        crypto_data[
            coin_id
        ]["change_24h"]
    )

    uah_price = (
        usd_price * usd
    )

    crypto_rates[coin_id] = {

        "usd": usd_price,

        "uah": uah_price,

        "change_24h":
            change_24h
    }


# ==================================================
# ЧАС
# ==================================================

kyiv_time = datetime.now(
    ZoneInfo("Europe/Kyiv")
)

today = kyiv_time.strftime(
    "%Y-%m-%d"
)

now = datetime.now(
    timezone.utc
).isoformat()


# ==================================================
# ЗМІНА ВАЛЮТ
# ==================================================

usd_changed = (
    previous_usd is not None
    and usd != previous_usd
)

eur_changed = (
    previous_eur is not None
    and eur != previous_eur
)

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

currency_changed = (
    usd_changed
    or eur_changed
)


# ==================================================
# ЗМІНА КРИПТИ
# ==================================================

crypto_changed = False


if previous_crypto:

    for coin_id, current in (
        crypto_rates.items()
    ):

        old = (
            previous_crypto.get(
                coin_id
            )
        )

        if old is None:

            continue

        old_price = float(
            old.get(
                "usd",
                0
            )
        )

        if old_price <= 0:

            continue

        percent_change = (

            (
                current["usd"]
                -
                old_price
            )
            /
            old_price
        )

        if abs(
            percent_change
        ) >= (
            CRYPTO_CHANGE_THRESHOLD
        ):

            crypto_changed = True

            break


# ==================================================
# ІСТОРІЯ
# ==================================================

history = load_history()


history["usd"].append(
    {
        "date": now,
        "rate": usd
    }
)


history["eur"].append(
    {
        "date": now,
        "rate": eur
    }
)


save_history(
    history
)


# ==================================================
# РАНКОВА ПУБЛІКАЦІЯ
# ==================================================

morning_publish = (

    kyiv_time.hour >=
    MORNING_HOUR

    and

    last_morning_date !=
    today
)


# ==================================================
# ЩО ПУБЛІКУВАТИ
# ==================================================

publish_currency = (

    morning_publish
    or currency_changed
)


publish_crypto = (

    morning_publish
    or crypto_changed
)


should_publish = (

    publish_currency
    or publish_crypto
)


# ==================================================
# ПРОГНОЗ
# ==================================================

usd_values = (
    prepare_values(
        history["usd"],
        days=7
    )
)

eur_values = (
    prepare_values(
        history["eur"],
        days=7
    )
)

usd_forecast = (
    calculate_forecast(
        usd_values
    )
)

eur_forecast = (
    calculate_forecast(
        eur_values
    )
)


# ==================================================
# ЗАКРІПЛЕНИЙ КУРС ГРИВНІ
# ==================================================

pinned_currency_message = (

    "🇺🇦 КУРС ГРИВНІ\n\n"

    f"🇺🇸 USD: {usd:.2f} грн\n"

    f"{change_text(usd_change)}\n\n"

    f"🇪🇺 EUR: {eur:.2f} грн\n"

    f"{change_text(eur_change)}\n\n"

    f"🕐 Оновлено: "
    f"{kyiv_time.strftime('%d.%m.%Y о %H:%M')}\n"

    "📊 Дані: НБУ\n\n"

    "📌 Це повідомлення закріплене "
    "зверху каналу."
)


try:

    if pinned_message_id:

        edit_message(
            pinned_message_id,
            pinned_currency_message
        )

    else:

        result = send_message(
            pinned_currency_message
        )

        pinned_message_id = (
            result["message_id"]
        )

        try:

            pin_message(
                pinned_message_id
            )

            print(
                "Курс гривні закріплено!"
            )

        except Exception as error:

            print(
                "Не вдалося закріпити:",
                error
            )

except Exception as error:

    print(
        "Помилка закріпленого курсу:",
        error
    )


# ==================================================
# ОСНОВНА ПУБЛІКАЦІЯ
# ==================================================

if should_publish:

    message_parts = []


    # ----------------------------------------------
    # ВАЛЮТИ
    # ----------------------------------------------

    if publish_currency:

        currency_message = (

            "💰 КУРС ВАЛЮТ\n\n"

            f"🇺🇸 USD: "
            f"{usd:.2f} грн\n"

            f"{change_text(usd_change)}\n\n"

            f"🇪🇺 EUR: "
            f"{eur:.2f} грн\n"

            f"{change_text(eur_change)}\n\n"

            f"🕐 Оновлено: "
            f"{kyiv_time.strftime('%d.%m.%Y о %H:%M')}\n"

            "📊 Дані: НБУ"
        )


        if morning_publish:

            if (
                usd_forecast is not None
                or
                eur_forecast is not None
            ):

                currency_message += (

                    "\n\n"
                    "🔮 ОРІЄНТОВНИЙ ПРОГНОЗ "
                    "НА 24 ГОДИНИ"
                )


                if usd_forecast is not None:

                    usd_forecast_text = (
                        change_text(
                            usd_forecast[
                                "change"
                            ]
                        )
                    )

                    currency_message += (

                        "\n\n"
                        "🇺🇸 USD\n"

                        f"Поточний: "
                        f"{usd:.2f} грн\n"

                        f"Прогноз: ≈ "
                        f"{usd_forecast['forecast']:.2f} грн\n"

                        f"{usd_forecast_text}\n"

                        f"{usd_forecast['trend']}\n"

                        f"📊 Даних використано: "
                        f"{usd_forecast['samples']}"
                    )


                if eur_forecast is not None:

                    eur_forecast_text = (
                        change_text(
                            eur_forecast[
                                "change"
                            ]
                        )
                    )

                    currency_message += (

                        "\n\n"
                        "🇪🇺 EUR\n"

                        f"Поточний: "
                        f"{eur:.2f} грн\n"

                        f"Прогноз: ≈ "
                        f"{eur_forecast['forecast']:.2f} грн\n"

                        f"{eur_forecast_text}\n"

                        f"{eur_forecast['trend']}\n"

                        f"📊 Даних використано: "
                        f"{eur_forecast['samples']}"
                    )


                currency_message += (

                    "\n\n"
                    "⚠️ Це статистична оцінка, "
                    "а не гарантований майбутній курс."
                )

            else:

                currency_message += (

                    "\n\n"
                    "🔮 ПРОГНОЗ\n"
                    "⏳ Поки недостатньо "
                    "історичних даних."
                )


        message_parts.append(
            currency_message
        )


    # ----------------------------------------------
    # КРИПТО
    # ----------------------------------------------

    if publish_crypto:

        crypto_message = (

            "🪙 КУРС КРИПТОВАЛЮТ\n\n"
        )


        for coin_id, name in (
            CRYPTO.items()
        ):

            if coin_id not in crypto_rates:

                continue

            coin = (
                crypto_rates[
                    coin_id
                ]
            )

            crypto_change = (
                coin["change_24h"]
            )

            crypto_change_display = (
                crypto_change_text(
                    crypto_change
                )
            )

            crypto_message += (

                f"{name}: "
                f"${coin['usd']:,.2f} / "
                f"{coin['uah']:,.2f} грн\n"

                f"{crypto_change_display}\n\n"
            )


        if crypto_rates:

            crypto_message += (

                f"🕐 Оновлено: "
                f"{kyiv_time.strftime('%d.%m.%Y о %H:%M')}\n"

                "📊 Дані: CoinPaprika\n"

                "ℹ️ Публікація при зміні від 0,5%"
            )

            message_parts.append(
                crypto_message
            )


    # ----------------------------------------------
    # ПОВІДОМЛЕННЯ
    # ----------------------------------------------

    if message_parts:

        message = (
            "\n\n━━━━━━━━━━━━━━\n\n"
            .join(
                message_parts
            )
        )

        send_message(
            message
        )

        print(
            "Повідомлення опубліковано!"
        )


    if morning_publish:

        last_morning_date = today


else:

    print(
        "Змін для публікації немає."
    )


# ==================================================
# ЗБЕРІГАЄМО ДАНІ
# ==================================================

data = {

    "usd": usd,

    "eur": eur,

    "crypto":
        crypto_rates,

    "updated":
        now,

    "last_morning_date":
        last_morning_date,

    "pinned_message_id":
        pinned_message_id
}


with open(
    DATA_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        data,
        file,
        ensure_ascii=False,
        indent=2
    )


print(
    "Перевірку завершено."
)
