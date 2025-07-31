from flask import Flask
import logging
import requests
from telegram import Bot
import time

TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
THRESHOLD = 10_000
INTERVAL = 30

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)

@app.route("/")
def ping():
    return "ok", 200

def big_liquidations():
    url = "https://open-api.coinglass.com/public/v2/liquidation_history"
    try:
        r = requests.get(url, params={"time_type": "5m", "symbol": "BTC"}, timeout=15).json()
        data = r.get("data", [])
        return [x for x in data if float(x.get("usdValue", 0)) >= THRESHOLD]
    except Exception as e:
        logging.warning("CoinGlass fetch failed: %s", e)
        return []

def alert_loop():
    seen = set()
    while True:
        for liq in big_liquidations():
            key = (liq["symbol"], liq["time"], liq["orderId"])
            if key in seen:
                continue
            seen.add(key)
            side = "Long" if liq["side"] == "SELL" else "Short"
            usd = float(liq["executedQty"]) * float(liq["price"])
            text = (f"🚨 {liq['symbol']}  {side}  Liquidation\n"
                    f"Qty: {float(liq['executedQty']):,.0f}\n"
                    f"USD: ${usd:,.0f}\n"
                    f"Price: {float(liq['price'])}")
            bot.send_message(chat_id=GROUP_ID, text=text)
            logging.info("Alert sent: %s", liq["symbol"])
        time.sleep(INTERVAL)

if __name__ == "__main__":
    threading.Thread(target=alert_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8443)))
