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
    """Checks if the article was published within the last 14 days."""
    try:
        date_str = find_date(url) # Returns YYYY-MM-DD
        if not date_str: return True # If we can't find a date, we take a chance
        pub_date = datetime.strptime(date_str, '%Y-%m-%d')
        cutoff = datetime.now() - timedelta(days=MAX_DAYS)
        return pub_date > cutoff
    except:
        return True

def main():
    history = get_history()
    active_updates = []
    quiet_sources = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for name, url in SOURCES.items():
        print(f"🔍 Checking {name}...")
        try:
            res = requests.get(url, headers=headers, timeout=15, verify=certifi.where())
            soup = BeautifulSoup(res.text, 'html.parser')
            found_at_source = False

            # We only look for links that likely point to actual articles
            for a in soup.find_all('a', href=True):
                link = a['href']
                if not link.startswith('http') or link in history: continue
                
                # Filter for typical news URL patterns to avoid "Contact Us" etc.
                if any(x in link.lower() for x in ['/news/', '/insights/', '/article/', '2026', '2025']):
                    if is_recent(link):
                        # Simple extraction for the alert
                        active_updates.append(f"✅ *{name}*: {link}")
                        with open(DB_FILE, "a") as f: f.write(link + "\n")
                        history.add(link)
                        found_at_source = True
            
            if not found_at_source:
                quiet_sources.append(name)
        except Exception as e:
            quiet_sources.append(f"{name} (Error)")

    # Construct the summary message
    message = "🏁 **Market Intelligence Scan**\n\n"
    if active_updates:
        message += "🚀 **New Deals/Insights Found:**\n" + "\n".join(active_updates)
    else:
        message += "😴 No new deals found in the last 14 days."
    
    message += "\n\n🔇 **No Changes:** " + ", ".join(quiet_sources)
    
    # Send to Telegram
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()
