import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask

# ---------------- CONFIG ----------------
TOKEN     = os.environ["TELEGRAM_TOKEN"]
RENDER_URL = os.environ.get("RENDER_URL", "https://your-bot.onrender.com")
# ----------------------------------------

logging.basicConfig(level=logging.INFO)

# lightweight Flask app only to keep Render alive
flask_app = Flask(__name__)
@flask_app.route("/")
def keepalive(): return "ok", 200

# ---------- helper ----------
def simple_trend(pair: str) -> str:
    """Return 1-sentence trend & entry from Binance klines."""
    symbol = pair.upper().replace("/", "")
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=50"
    r = requests.get(url, timeout=15).json()
    if isinstance(r, dict):
        return f"{pair}: Binance error — {r.get('msg', 'unknown')}"
    opens  = [float(x[1]) for x in r]
    closes = [float(x[4])  for x in r]
    last   = closes[-1]
    sma50  = sum(closes) / len(closes)
    if last > sma50 * 1.01:
        return f"{pair} 📈 bullish above 1-h 50-SMA. Entry: {last:.2f}, SL: {last*0.97:.2f}"
    elif last < sma50 * 0.99:
        return f"{pair} 📉 bearish below 1-h 50-SMA. Entry: {last:.2f}, SL: {last*1.03:.2f}"
    else:
        return f"{pair} 🟡 ranging around 1-h 50-SMA. No clear entry yet."

# ---------- handlers ----------
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = update.message.text.split()[0].lstrip("/").upper()
    text = simple_trend(pair)
    await update.message.reply_text(text)

# ---------- run ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler(["btcusdt", "solusdt", "ethusdt", "adausdt"], price))
    # start webhook so Render can keep it awake
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path=TOKEN,
        webhook_url=f"{RENDER_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()