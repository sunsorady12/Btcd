from flask import Flask
app = Flask(__name__)
@app.route("/")
def ping(): return "ok", 200
import os
import time
import logging
import requests
from telegram import Bot
from flask import Flask

# ------------- CONFIG -------------
TOKEN    = os.environ["TELEGRAM_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])   # numeric group id (negative)
INTERVAL = 30                            # seconds between checks
# ----------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)
flask_app = Flask(__name__)
@flask_app.route("/")
def keepalive(): return "ok", 200

def big_liquidations():
    """Return list of large liquidations (last 30 s)."""
    url = "https://fapi.binance.com/fapi/v1/forceOrders"
    params = {"limit": 30}
    try:
        r = requests.get(url, params=params, timeout=15).json()
        if isinstance(r, dict):
            return []  # API error
       return [x for x in r if float(x["executedQty"]) * float(x["price"]) >= 10_000]
    except Exception as e:
        logging.warning("Binance liquidations fetch failed: %s", e)
        return []

def alert_loop():
    """Poll every INTERVAL seconds and push alerts to Telegram."""
    seen = set()
    while True:
        for liq in big_liquidations():
            key = (liq["symbol"], liq["time"], liq["orderId"])
            if key in seen:
                continue
            seen.add(key)
            side  = "Long" if liq["side"] == "SELL" else "Short"
            usd   = float(liq["executedQty"]) * float(liq["price"])
            text  = (f"🚨 {liq['symbol']}  {side}  Liquidation\n"
                     f"Qty: {float(liq['executedQty']):,.0f}\n"
                     f"USD: ${usd:,.0f}\n"
                     f"Price: {float(liq['price'])}")
            bot.send_message(chat_id=GROUP_ID, text=text)
            logging.info("Alert sent: %s", liq["symbol"])
        time.sleep(INTERVAL)

if __name__ == "__main__":
    threading.Thread(target=alert_loop, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=PORT)
