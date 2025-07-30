import os
import logging
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Bot, Update, InputFile
from telegram.ext import CommandHandler, Dispatcher, CallbackContext

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PORT = int(os.environ.get('PORT', 5000))
bot = Bot(token=TELEGRAM_TOKEN)

def fetch_crypto_data(symbol: str, days: int = 30) -> pd.DataFrame:
    """Fetch historical OHLC data from CoinGecko"""
    try:
        coin_id = symbol.lower()
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {'vs_currency': 'usd', 'days': days}
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        logger.error(f"Data fetch error: {e}")
        return None

def calculate_trend_indicators(df: pd.DataFrame) -> dict:
    """Calculate technical indicators and trend analysis"""
    analysis = {
        'current_price': df['close'].iloc[-1],
        'support': df['low'].rolling(20).min().iloc[-1],
        'resistance': df['high'].rolling(20).max().iloc[-1],
        'trend': 'neutral',
        'entry_suggestion': 'No clear signal',
        'sma20': df['close'].rolling(20).mean().iloc[-1],
        'sma50': df['close'].rolling(50).mean().iloc[-1]
    }
    
    # Trend detection
    if analysis['sma20'] > analysis['sma50']:
        analysis['trend'] = 'bullish'
    elif analysis['sma20'] < analysis['sma50']:
        analysis['trend'] = 'bearish'
    
    # Entry suggestions
    current_price = analysis['current_price']
    if analysis['trend'] == 'bullish':
        if current_price <= analysis['support'] * 1.02:
            analysis['entry_suggestion'] = 'BUY near support'
        elif current_price <= analysis['sma20']:
            analysis['entry_suggestion'] = 'BUY near 20-day average'
    elif analysis['trend'] == 'bearish':
        if current_price >= analysis['resistance'] * 0.98:
            analysis['entry_suggestion'] = 'SHORT near resistance'
    
    return analysis

def generate_trend_chart(df: pd.DataFrame, analysis: dict, symbol: str) -> BytesIO:
    """Generate price chart with technical markers"""
    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['close'], label='Price', color='blue', linewidth=2)
    plt.plot(df.index, df['close'].rolling(20).mean(), label='20-day SMA', linestyle='--')
    plt.plot(df.index, df['close'].rolling(50).mean(), label='50-day SMA', linestyle='--')
    
    if analysis['support']:
        plt.axhline(y=analysis['support'], color='green', linestyle=':', label='Support')
    if analysis['resistance']:
        plt.axhline(y=analysis['resistance'], color='red', linestyle=':', label='Resistance')
    
    plt.title(f'{symbol.upper()} Price Analysis', fontsize=14)
    plt.ylabel('Price (USD)', fontsize=12)
    plt.legend()
    plt.grid(alpha=0.3)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

def analyze_command(update: Update, context: CallbackContext):
    """Handle /analysis commands in group chats"""
    try:
        symbol = context.args[0].lower() if context.args else 'bitcoin'
        processing_msg = update.message.reply_text(f"🔄 Analyzing {symbol.upper()}...")
        
        df = fetch_crypto_data(symbol)
        if df is None or df.empty:
            update.message.reply_text("❌ Data unavailable. Try /btc or /eth")
            return

        analysis = calculate_trend_indicators(df)
        chart = generate_trend_chart(df, analysis, symbol)
        
        message = (
            f"📈 *{symbol.upper()} Trend Analysis*\n\n"
            f"• Current Price: ${analysis['current_price']:.2f}\n"
            f"• Trend: {analysis['trend'].upper()} "
            f"(20 SMA > 50 SMA)\n"
            f"• Support: ${analysis['support']:.2f}\n"
            f"• Resistance: ${analysis['resistance']:.2f}\n"
            f"• Entry Signal: {analysis['entry_suggestion']}\n\n"
            f"_Data: CoinGecko | {datetime.now().strftime('%Y-%m-%d')}_"
        )
        
        update.message.reply_photo(
            photo=InputFile(chart, filename='chart.png'),
            caption=message,
            parse_mode='Markdown'
        )
        
        bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        update.message.reply_text("⚠️ Use format: /btc or /eth")

# Flask setup for Render.com
@app.route('/')
def home():
    return "Crypto Analysis Bot Online", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(), bot)
        dp = Dispatcher(bot, None, workers=0)
        dp.add_handler(CommandHandler(['btc', 'eth', 'sol', 'analysis'], analyze_command))
        dp.process_update(update)
        return 'ok', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'error', 400

def set_webhook():
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL')}/webhook"
    if webhook_url.startswith('https'):
        bot.set_webhook(webhook_url)

if __name__ == '__main__':
    set_webhook()
    app.run(host='0.0.0.0', port=PORT, debug=False)
