import os
import requests
from bs4 import BeautifulSoup
import certifi
from htmldate import find_date
from datetime import datetime, timedelta
from urllib.parse import urljoin

# --- 1. THE COMPLETE SOURCES LIST ---
SOURCES = {
    "MaxCap": "https://maxcapgroup.com.au/category/news/",
    "Qualitas": "https://www.qualitas.com.au/news/",
    "Metrics": "https://www.metrics.com.au/news-insights/",
    "Pallas Capital": "https://www.pallascapital.com.au/news-insights/",
    "Wingate": "https://www.wingate.com.au/news-insights/",
    "Merricks": "https://www.merrickscapital.com/news/",
    "Balmain": "https://www.balmain.com.au/news-insights",
    "La Trobe": "https://www.latrobefinancial.com.au/news-insights/",
    "ICG": "https://www.icgam.com/category/news/",
    "Challenger": "https://www.challenger.com.au/about-us/media-centre",
    "The Urban Developer": "https://www.theurbandeveloper.com/categories/finance",
    "Colliers": "https://www.colliers.com.au/en-au/news",
    "JLL": "https://www.jll.com.au/en-au/newsroom",
    "CBRE": "https://www.cbre.com.au/about-us/newsroom"
}

MAX_DAYS = 14
DB_FILE = "processed_links.txt"

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
        return pub_date > (datetime.now() - timedelta(days=MAX_DAYS))
    except:
        return True

def send_telegram_batched(lines, title):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return

    header = f"<b>{title}</b>\n\n"
    current_chunk = header
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    for line in lines:
        if len(current_chunk) + len(line) > 3800:
            requests.post(url, json={"chat_id": chat_id, "text": current_chunk, "parse_mode": "HTML", "disable_web_page_preview": True})
            current_chunk = header + line + "\n"
        else:
            current_chunk += line + "\n"
    
    requests.post(url, json={"chat_id": chat_id, "text": current_chunk, "parse_mode": "HTML", "disable_web_page_preview": True})

def main():
    history = get_history()
    active_updates = []
    quiet_sources = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for name, url in SOURCES.items():
        print(f"🔍 Checking {name}...")
        try:
            res = requests.get(url, headers=headers, timeout=25, verify=certifi.where())
            soup = BeautifulSoup(res.text, 'html.parser')
            found_at_source = False

            for a in soup.find_all('a', href=True):
                # Fix relative URLs (e.g. /news/article -> https://site.com/news/article)
                link = urljoin(url, a['href'])
                
                if link in history or not link.startswith('http'): 
                    continue
                
                # Broaden filter to ensure we don't miss deals on major newsrooms
                if any(x in link.lower() for x in ['/news', '/insight', '/article', '2025', '2026', 'press']):
                    if is_recent(link):
                        active_updates.append(f"• <b>{name}</b>: <a href='{link}'>View Article</a>")
                        with open(DB_FILE, "a") as f: f.write(link + "\n")
                        history.add(link)
                        found_at_source = True
            
            if not found_at_source: quiet_sources.append(name)
        except Exception as e:
            print(f"⚠️ Error {name}: {e}")
            quiet_sources.append(f"{name} (Err)")

    if active_updates:
        send_telegram_batched(active_updates, "🏗️ NEW MARKET INTELLIGENCE")
    
    summary = f"😴 <b>Quiet Sources:</b>\n{', '.join(quiet_sources)}"
    send_telegram_batched([summary], "📊 SCAN SUMMARY")

if __name__ == "__main__":
    main()
