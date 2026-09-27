import os
import requests

TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@kurs_gryvni_ua"

def get_rate(currency):
    url = f"https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode={currency}&json"
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

usd = get_rate("USD")
eur = get_rate("EUR")

message = (
    "💰 Курс гривні\n\n"
    f"🇺🇸 USD: {usd:.2f} грн\n"
    f"🇪🇺 EUR: {eur:.2f} грн\n\n"
    "📊 Дані: НБУ"
)

send_message(message)

print("Опубліковано успішно!")
