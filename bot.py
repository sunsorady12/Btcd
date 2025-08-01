import os
import time
import threading
import logging
import requests
from telegram import Bot, error as telegram_error
from flask import Flask
from datetime import datetime, timedelta

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

def fetch_liquidations(hours=1):
    url = f"https://open-api.coinglass.com/public/v2/liquidation?timeType={hours}"
    headers = {
        "accept": "application/json",
        "coinglassSecret": "YOUR_API_KEY"  # Replace with your actual key
    }

    try:
        response = requests.get(url, headers=headers)
        print("Status Code:", response.status_code)
        print("Response:", response.text)

        json_response = response.json()
        data = json_response.get("data")
        if not data:
            print("❌ 'data' key not found in response.")
            return []
        
        # Return or process the data as needed
        return data

    except Exception as e:
        print("🔥 Coinglass fetch failed:", e)
        return []
def find_largest_liquidation(liquidations):
    """Find the largest liquidation by USD value"""
    if not liquidations:
        return None
        
    largest = max(
        liquidations,
        key=lambda x: float(x["executedQty"]) * float(x["price"])
    )
    return largest

def generate_report():
    """Generate 12-hour liquidation report"""
    # Get liquidations from last 12 hours
    liquidations = fetch_liquidations(hours=12)
    
    if not liquidations:
        return "📊 *12-Hour Liquidation Report*\n\nNo significant liquidations found"
    
    # Find the largest liquidation
    largest = find_largest_liquidation(liquidations)
    usd_value = float(largest["executedQty"]) * float(largest["price"])
    side = "Long" if largest["side"] == "SELL" else "Short"
    
    # Format time
    liquidation_time = datetime.fromtimestamp(largest["time"]/1000).strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate report message
    return (
        f"📊 *12-Hour Liquidation Report*\n\n"
        f"🔥 *Largest Liquidation*\n"
        f"Symbol: {largest['symbol']}\n"
        f"Side: {side}\n"
        f"Time: {liquidation_time} UTC\n"
        f"Qty: {float(largest['executedQty']):,.0f}\n"
        f"USD Value: ${usd_value:,.0f}\n"
        f"Price: {float(largest['price']):,.2f}"
    )

def report_loop():
    """Send reports every 12 hours"""
    while True:
        try:
            report = generate_report()
            bot.send_message(chat_id=GROUP_ID, text=report, parse_mode="Markdown")
            logger.info("Sent 12-hour liquidation report")
        except telegram_error.TelegramError as e:
            logger.error(f"Telegram send error: {str(e)}")
        except Exception as e:
            logger.error(f"Error in report_loop: {str(e)}")
            
        # Sleep for 12 hours
        time.sleep(REPORT_INTERVAL)

# Start the report thread
threading.Thread(target=report_loop, daemon=True).start()

# Run Flask app
if __name__ == "__main__":
    logger.info("Starting liquidation reporter...")
    port = int(os.environ.get("PORT", 8443))
    app.run(host="0.0.0.0", port=port)
