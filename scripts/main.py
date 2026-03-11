import os
import requests
from bs4 import BeautifulSoup
import certifi
from htmldate import find_date
from datetime import datetime, timedelta

# Settings
MAX_DAYS = 14
DB_FILE = "processed_links.txt"
SOURCES = {
    "MaxCap": "https://maxcapgroup.com.au/category/news/",
    "Qualitas": "https://www.qualitas.com.au/news/",
    "Metrics": "https://www.metrics.com.au/news-insights/",
    "Pallas Capital": "https://www.pallascapital.com.au/news-insights/",
    "Wingate": "https://www.wingate.com.au/news-insights/",
    "Merricks": "https://www.merrickscapital.com/news/",
    "ICG": "https://www.icgam.com/category/news/",
    "Challenger": "https://www.challenger.com.au/about-us/media-centre",
}

def get_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def is_recent(url):
    try:
        date_str = find_date(url)
        if not date_str: return True
        pub_date = datetime.strptime(date_str, '%Y-%m-%d')
        cutoff = datetime.now() - timedelta(days=MAX_DAYS)
        return pub_date > cutoff
    except:
        return True

def send_telegram(text):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ Telegram credentials missing")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def main():
    history = get_history()
    active_updates = []
    quiet_sources = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    print("🚀 Starting Scan...")
    
    for name, url in SOURCES.items():
        print(f"🔍 Checking {name}...")
        try:
            res = requests.get(url, headers=headers, timeout=20, verify=certifi.where())
            soup = BeautifulSoup(res.text, 'html.parser')
            found_at_source = False

            for a in soup.find_all('a', href=True):
                link = a['href']
                if not link.startswith('http') or link in history: continue
                
                # Filter for likely news articles
                if any(x in link.lower() for x in ['/news/', '/insights/', '/article/', '2026', '2025']):
                    if is_recent(link):
                        active_updates.append(f"✅ *{name}*: {link}")
                        with open(DB_FILE, "a") as f: f.write(link + "\n")
                        history.add(link)
                        found_at_source = True
            
            if not found_at_source:
                quiet_sources.append(name)
        except Exception as e:
            print(f"⚠️ Error checking {name}: {e}")
            quiet_sources.append(f"{name} (Err)")

    # Construct the final summary
    summary = "🏁 **Market Intelligence Scan**\n\n"
    if active_updates:
        summary += "🚀 **New Deals/Insights Found:**\n" + "\n".join(active_updates)
    else:
        summary += "😴 No new news found in the last 14 days."
    
    summary += "\n\n🔇 **Quiet Sources:** " + ", ".join(quiet_sources)
    
    print("📤 Sending summary to Telegram...")
    send_telegram(summary)

if __name__ == "__main__":
    main()
