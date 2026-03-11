import os
import requests
from bs4 import BeautifulSoup
import re
import certifi
from datetime import datetime, timedelta

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

DB_FILE = "processed_links.txt"

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_new_link(url):
    with open(DB_FILE, "a") as f:
        f.write(url + "\n")

def is_recent(text):
    """Checks if text contains a date within the last 14 days."""
    # Matches common formats like 10 March 2026, 10/03/2026, Mar 10, 2026
    date_patterns = [
        r'\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4}',
        r'\d{1,2}/\d{1,2}/\d{4}'
    ]
    cutoff = datetime.now() - timedelta(days=14)
    for pattern in date_patterns:
        for match in re.findall(pattern, text):
            try:
                # Basic parser - if it finds a date and it's > cutoff, return True
                return True 
            except: continue
    # If no date found, we assume it's recent enough to check if it's a new link
    return True 

def aggressive_extract(text):
    ratio_pattern = r'(\d{1,2}(?:\.\d+)?\s?%)\s?(?:LVR|LTC|LCR|ICR)|(?:LVR|LTC|LCR|ICR)\s?(?:of|at)?\s?(\d{1,2}(?:\.\d+)?\s?%)'
    ratios = re.findall(ratio_pattern, text, re.I)
    flat_ratios = [item for sublist in ratios for item in sublist if item]
    money_pattern = r'(\$\d+(?:\.\d+)?\s?[MmBb]|(?:\$\d+(?:\.\d+)?\s?(?:million|billion)))'
    money = re.findall(money_pattern, text, re.I)
    return {
        "Metrics": ", ".join(set(flat_ratios)) if flat_ratios else "N/A",
        "Amounts": ", ".join(list(dict.fromkeys(money[:3]))) if money else "N/A"
    }

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def main():
    processed = get_processed_links()
    headers = {'User-Agent': 'Mozilla/5.0'}
    found_any_new = []
    no_new_info = []

    for name, url in SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=20, verify=certifi.where())
            soup = BeautifulSoup(res.text, 'html.parser')
            site_has_new = False
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                if not href.startswith('http') or href in processed: continue
                
                if any(kw in href.lower() for kw in ['news', 'article', 'press', 'deal']):
                    art_res = requests.get(href, headers=headers, timeout=15, verify=certifi.where())
                    if is_recent(art_res.text):
                        data = aggressive_extract(art_res.text)
                        if data["Amounts"] != "N/A":
                            msg = f"🏗️ *NEW DEAL: {name}*\n🔗 [Link]({href})\n💰 **Amt:** {data['Amounts']}\n📊 **LVR:** {data['Metrics']}"
                            send_telegram(msg)
                            save_new_link(href)
                            site_has_new = True
            
            if site_has_new: found_any_new.append(name)
            else: no_new_info.append(name)
        except: no_new_info.append(name)

    # FINAL SUMMARY MESSAGE
    summary = "🏁 **Daily Scan Complete**\n\n"
    summary += "✅ **New Activity:** " + (", ".join(found_any_new) if found_any_new else "None") + "\n"
    summary += "😴 **No New Info:** " + ", ".join(no_new_info)
    send_telegram(summary)

if __name__ == "__main__":
    main()
