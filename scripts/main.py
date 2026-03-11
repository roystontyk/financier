import os
import requests
from bs4 import BeautifulSoup
import re
import certifi

# --- 1. THE COMPLETE SOURCES LIST ---
# Targeted news/press sub-pages for Top 10 Lenders & Brokers
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

def aggressive_extract(text):
    """Greedy extraction for LVR, LTC, GRV, and Money."""
    # Ratios (LVR/LTC/LCR)
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
        "Metrics": ", ".join(set(flat_ratios)) if flat_ratios else "N/A",
        "Amounts": ", ".join(list(dict.fromkeys(money[:3]))) if money else "N/A",
        "GRV": grv[0] if grv else "N/A"
    }

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ Error: Missing Telegram Secrets")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=15)
        if res.status_code == 200:
            print("✅ Notification sent.")
        else:
            print(f"❌ Telegram Error: {res.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def main():
    processed = get_processed_links()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for name, url in SOURCES.items():
        print(f"🔍 Checking {name}...")
        try:
            # verify=certifi.where() solves the SSLError you saw in the logs
            res = requests.get(url, headers=headers, timeout=20, verify=certifi.where())
            soup = BeautifulSoup(res.text, 'html.parser')
            
            new_deals_found = 0
            for a in soup.find_all('a', href=True):
                href = a['href']
                if not href.startswith('http'): continue
                if href in processed: continue
                
                # Check for article-like keywords
                if any(kw in href.lower() for kw in ['news', 'article', 'press', 'media', 'deal', 'insights']):
                    print(f"✨ New link found: {href}")
                    art_res = requests.get(href, headers=headers, timeout=15, verify=certifi.where())
                    data = aggressive_extract(art_res.text)
                    
                    # Only notify if financial data is detected
                    if data["Amounts"] != "N/A" or data["Metrics"] != "N/A":
                        msg = (
                            f"🏗️ *NEW DEAL: {name}*\n"
                            f"🔗 [Link]({href})\n\n"
                            f"💰 **Facility:** {data['Amounts']}\n"
                            f"📊 **LVR/LTC:** {data['Metrics']}\n"
                            f"🏛️ **GRV:** {data['GRV']}"
                        )
                        send_telegram(msg)
                        save_new_link(href)
                        new_deals_found += 1
                
                if new_deals_found >= 2: break # Limit per site per run
        except Exception as e:
            print(f"⚠️ Failed {name}: {e}")

if __name__ == "__main__":
    main()
