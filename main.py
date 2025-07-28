import os, requests, time, schedule

TOKEN      = os.getenv("TELEGRAM_TOKEN")
CHAT_ID    = int(os.getenv("CHAT_ID"))
THREAD_ID  = int(os.getenv("THREAD_ID"))

def btc_dominance_gecko() -> float:
    url = "https://api.coingecko.com/api/v3/global"
    return float(requests.get(url, timeout=10).json()["data"]["market_cap_percentage"]["btc"])

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

job()
schedule.every(59).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(30)
