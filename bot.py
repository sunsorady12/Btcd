import os
import time
import threading
import logging
import websocket
import json
from telegram import Bot, error as telegram_error
from flask import Flask
from datetime import datetime

# ------------- CONFIG -------------
TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
REPORT_INTERVAL = 12 * 60 * 60  # 12 hours in seconds
THRESHOLD = 10_000  # USD minimum to consider
# ----------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

@app.route("/")
def ping():
    return "ok", 200

# Initialize Telegram bot
bot = Bot(token=TOKEN)

# Global storage for recent liquidations
recent_liquidations = []

def on_message(ws, message):
    try:
        msg = json.loads(message)
        data = msg.get("data", [])
        for entry in data:
            usd_value = float(entry.get("sz", 0)) * float(entry.get("px", 0))
            if usd_value >= THRESHOLD:
                recent_liquidations.append({
                    "symbol": entry.get("instId", ""),
                    "side": entry.get("side", ""),
                    "executedQty": entry.get("sz", "0"),
                    "price": entry.get("px", "0"),
                    "time": int(entry.get("ts", 0))
                })
    except Exception as e:
        logger.error("Failed to parse liquidation message: %s", e)

def on_open(ws):
    sub_msg = {
        "op": "subscribe",
        "args": [
            {
                "channel": "liquidation-orders",
                "instType": "SWAP",
                "instId": "BTC-USDT-SWAP"
            },
            {
                "channel": "liquidation-orders",
                "instType": "SWAP",
                "instId": "ETH-USDT-SWAP"
            }
        ]
    }
    ws.send(json.dumps(sub_msg))

def start_ws_listener():
    ws = websocket.WebSocketApp(
        "wss://ws.okx.com:8443/ws/v5/public",
        on_message=on_message,
        on_open=on_open
    )
    ws.run_forever()

def find_largest_liquidation():
    if not recent_liquidations:
        return None
    return max(
        recent_liquidations,
        key=lambda x: float(x["executedQty"]) * float(x["price"])
    )

def generate_report():
    largest = find_largest_liquidation()
    if not largest:
        return "\ud83d\udcca *12-Hour Liquidation Report*\n\nNo significant liquidations found"

    usd_value = float(largest["executedQty"]) * float(largest["price"])
    side = "Long" if largest["side"] == "SELL" else "Short"
    liquidation_time = datetime.fromtimestamp(largest["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"\ud83d\udcca *12-Hour Liquidation Report*\n\n"
        f"\ud83d\udd25 *Largest Liquidation*\n"
        f"Symbol: {largest['symbol']}\n"
        f"Side: {side}\n"
        f"Time: {liquidation_time} UTC\n"
        f"Qty: {float(largest['executedQty']):,.0f}\n"
        f"USD Value: ${usd_value:,.0f}\n"
        f"Price: {float(largest['price']):,.2f}"
    )

def report_loop():
    while True:
        try:
            report = generate_report()
            bot.send_message(chat_id=GROUP_ID, text=report, parse_mode="Markdown")
            logger.info("Sent 12-hour liquidation report")
            recent_liquidations.clear()
        except telegram_error.TelegramError as e:
            logger.error(f"Telegram send error: {str(e)}")
        except Exception as e:
            logger.error(f"Error in report_loop: {str(e)}")

        time.sleep(REPORT_INTERVAL)

# Start WebSocket listener
threading.Thread(target=start_ws_listener, daemon=True).start()
# Start report sender
threading.Thread(target=report_loop, daemon=True).start()

# Run Flask app
if __name__ == "__main__":
    logger.info("Starting OKX liquidation reporter...")
    port = int(os.environ.get("PORT", 8443))
    app.run(host="0.0.0.0", port=port)
