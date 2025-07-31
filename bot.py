import os
import time
import logging
import requests
from telegram import Bot

# ------------- CONFIG ------------- 
TOKEN    = os.environ["TELEGRAM_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
INTERVAL = 30
THRESHOLD = 10_000  # USD
# ----------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)

def big_liquidations():
    """Return list of liquidations ≥ THRESHOLD in last 5-minute bucket."""
    url = "https://open-api.coinglass.com/public/v2/liquidation_history"
    try:
        r = requests.get(url, params={"time_type": "5m", "symbol": "BTC"}, timeout=15).json()
        data = r.get("data", [])
        # data is a list of dicts: {"symbol","side","qty","price","usdValue",...}
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
            usd  = float(liq["executedQty"]) * float(liq["price"])
            text = (f"🚨 {liq['symbol']}  {side}  Liquidation\n"
                    f"Qty: {float(liq['executedQty']):,.0f}\n"
                    f"USD: ${usd:,.0f}\n"
                    f"Price: {float(liq['price'])}")
            bot.send_message(chat_id=GROUP_ID, text=text)
            logging.info("Alert sent: %s", liq["symbol"])
        time.sleep(INTERVAL)

if __name__ == "__main__":
    alert_loop()
