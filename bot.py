import os
import time
import threading
import logging
import requests
from telegram import Bot, error as telegram_error
from flask import Flask

# ------------- CONFIG -------------
TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
INTERVAL = 30  # seconds
THRESHOLD = 10_000  # USD
# ----------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.route("/")
def ping():
    return "ok", 200

def big_liquidations():
    """Return list of liquidations ≥ THRESHOLD in last 30 records."""
    url = "https://fapi.binance.com/fapi/v1/forceOrders"
    try:
        response = requests.get(url, params={"limit": 30}, timeout=15)
        response.raise_for_status()  # Raises HTTPError for bad responses
        data = response.json()
        
        if isinstance(data, dict) and 'code' in data:
            logger.error(f"Binance API error: {data.get('msg', 'Unknown error')}")
            return []
            
        return [
            x for x in data
            if float(x["executedQty"]) * float(x["price"]) >= THRESHOLD
        ]
    except requests.exceptions.RequestException as e:
        logger.error(f"Binance fetch failed: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in big_liquidations: {str(e)}")
        return []

def alert_loop():
    seen = set()
    while True:
        try:
            liquidations = big_liquidations()
            if not liquidations:
                logger.info("No new large liquidations found")
                
            for liq in liquidations:
                key = (liq["symbol"], liq["time"], liq["orderId"])
                if key in seen:
                    continue
                    
                seen.add(key)
                side = "Long" if liq["side"] == "SELL" else "Short"
                usd = float(liq["executedQty"]) * float(liq["price"])
                text = (
                    f"🚨 {liq['symbol']} {side} Liquidation\n"
                    f"Qty: {float(liq['executedQty']):,.0f}\n"
                    f"USD: ${usd:,.0f}\n"
                    f"Price: {float(liq['price']):,.2f}"
                )
                
                try:
                    bot.send_message(chat_id=GROUP_ID, text=text)
                    logger.info(f"Alert sent: {liq['symbol']} - ${usd:,.0f}")
                except telegram_error.TelegramError as e:
                    logger.error(f"Telegram send error: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in alert_loop: {str(e)}")
            
        time.sleep(INTERVAL)

if __name__ == "__main__":
    logger.info("Starting bot...")
    threading.Thread(target=alert_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8443)))
