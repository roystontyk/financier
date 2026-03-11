import os
import requests
from bs4 import BeautifulSoup
import certifi
from htmldate import find_date
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re

# --- CONFIGURATION ---
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

def extract_project_details(text):
    """Scans article text for financial metrics."""
    # LVR/LTC Patterns
    ratio_pattern = r'(\d{1,2}(?:\.\d+)?\s?%)\s?(?:LVR|LTC|LCR|ICR)|(?:LVR|LTC|LCR|ICR)\s?(?:of|at)?\s?(\d{1,2}(?:\.\d+)?\s?%)'
    ratios = re.findall(ratio_pattern, text, re.I)
    flat_ratios = [item for sublist in ratios for item in sublist if item]
    
    # Financial Amounts ($50M, $100 million)
    money_pattern = r'(\$\d+(?:\.\d+)?\s?[MmBb]|(?:\$\d+(?:\.\d+)?\s?(?:million|billion)))'
    money = re.findall(money_pattern, text, re.I)

    # GRV Specific
    grv_pattern = r'(?:GRV|Gross Realisation|End Value|Project Value)\s?(?:of|at)?\s?(\$\d+(?:\.\d+)?\s?[MmBb]|(?:\$\d+(?:\.\d+)?\s?(?:million|billion)))'
    grv = re.findall(grv_pattern, text, re.I)

    return {
        "LVR": flat_ratios[0] if flat_ratios else "N/A",
        "Amt": money[0] if money else "N/A",
        "GRV": grv[0] if grv else "N/A"
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
        return pub_date > (datetime.now() - timedelta(days=MAX_DAYS))
    except:
        return True

def send_telegram_batched(lines, title):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    message = f"<b>{title}</b>\n\n" + "\n\n".join(lines)
    # Split into chunks of 4000 chars
    for i in range(0, len(message), 4000):
        requests.post(url, json={
            "chat_id": chat_id, 
            "text": message[i:i+4000], 
            "parse_mode": "HTML", 
            "disable_web_page_preview": True
        })

def main():
    history = get_history()
    active_updates = []
    quiet_sources = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for name, site_url in SOURCES.items():
        print(f"🔍 Checking {name}...")
        try:
            res = requests.get(site_url, headers=headers, timeout=25, verify=certifi.where())
            soup = BeautifulSoup(res.text, 'html.parser')
            found_at_source = False

            for a in soup.find_all('a', href=True):
                link = urljoin(site_url, a['href'])
                if link in history or not link.startswith('http'): continue
                
                if any(x in link.lower() for x in ['/news', '/insight', '/article', '2025', '2026', 'press']):
                    if is_recent(link):
                        # --- NEW: Dig into the article for details ---
                        try:
                            art_res = requests.get(link, headers=headers, timeout=15, verify=certifi.where())
                            details = extract_project_details(art_res.text)
                        except:
                            details = {"LVR": "N/A", "Amt": "N/A", "GRV": "N/A"}

                        # Format the entry with details
                        entry = (f"🏗️ <b>{name}</b>\n"
                                 f"💰 Amt: {details['Amt']} | 📊 LVR: {details['LVR']}\n"
                                 f"🏛️ GRV: {details['GRV']}\n"
                                 f"🔗 <a href='{link}'>Read Full Article</a>")
                        
                        active_updates.append(entry)
                        with open(DB_FILE, "a") as f: f.write(link + "\n")
                        history.add(link)
                        found_at_source = True
            
            if not found_at_source: quiet_sources.append(name)
        except Exception as e:
            quiet_sources.append(f"{name} (Err)")

    if active_updates:
        send_telegram_batched(active_updates, "🚀 NEW MARKET INTELLIGENCE")
    
    summary = f"<b>Quiet Sources:</b> {', '.join(quiet_sources)}"
    send_telegram_batched([summary], "📊 SCAN SUMMARY")

if __name__ == "__main__":
    main()
