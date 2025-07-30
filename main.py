import os, requests, time, schedule
from keep_alive import keep_alive

TOKEN      = "7979844655:AAGIq7SVsrtAKMfpB56zpNXAC6GjdCVKzg8"
CHAT_ID    = -1002782765335
THREAD_ID  = 3

def btc_dominance_gecko() -> float:
    url = "https://api.coingecko.com/api/v3/global"
    return float(
        requests.get(url, timeout=10).json()["data"]["market_cap_percentage"]["btc"]
    )

def send_tg(text: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload, timeout=10)

def job():
    dom = btc_dominance_gecko()
    send_tg(f"📊 *BTC Dominance* {dom:.2f}%")
    if dom < 50:
        send_tg("🚨 *CRITICAL* BTC dominance < 50%")
    elif dom <= 55:
        send_tg("⚠️ *ALERT* BTC dominance ≤ 55%")

# run once on start-up
job()
schedule.every(59).minutes.do(job)

def run_bot():
    while True:
        schedule.run_pending()
        time.sleep(30)

keep_alive()
Thread(target=run_bot).start()
