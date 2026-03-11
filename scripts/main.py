import os
import requests
from bs4 import BeautifulSoup
import re

# 1. EXPANDED SOURCES: Targeted news/press release sub-pages
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
    """
    Greedy Regex to catch variations: '65% LVR', 'LTC of 70%', '$50 million', '$50M', etc.
    """
    # 1. LVR / LTC / LCR / Interest Coverage (Captures 65%, 65.5%, etc)
    # Looks for any digit + % followed or preceded by finance acronyms
    ratio_pattern = r'(\d{1,2}(?:\.\d+)?\s?%)\s?(?:LVR|LTC|LCR|ICR|Loan-to-Value|Loan-to-Cost)|(?:LVR|LTC|LCR|ICR)\s?(?:of|at)?\s?(\d{1,2}(?:\.\d+)?\s?%)'
    ratios = re.findall(ratio_pattern, text, re.I)
    flat_ratios = [item for sublist in ratios for item in sublist if item]

    # 2. Money amounts (Aggressive: catches $50M, $50m, $50 million, $50.5m)
    money_pattern = r'(\$\d+(?:\.\d+)?\s?[MmBb]|(?:\$\d+(?:\.\d+)?\s?(?:million|billion)))'
    money = re.findall(money_pattern, text, re.I)

    # 3. GRV / End Value / Project Value
    grv_pattern = r'(?:GRV|Gross Realisation|End Value|Project Value|Valued at)\s?(?:of|at|expected to be)?\s?(\$\d+(?:\.\d+)?\s?[MmBb]|(?:\$\d+(?:\.\d+)?\s?(?:million|billion)))'
    grv = re.findall(grv_pattern, text, re.I)

    # 4. Developer / Counterparty Keywords
    # Identifying if a developer name might be near "developed by" or "partnership with"
    dev_pattern = r'(?:developed by|developer|partnership with|builder|client)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)'
    devs = re.findall(dev_pattern, text)

    return {
        "Metrics": ", ".join(set(flat_ratios)) if flat_ratios else "N/A",
        "Amounts": ", ".join(list(dict.fromkeys(money[:4]))) if money else "N/A",
        "GRV": grv[0] if grv else "N/A",
        "Probable_Dev": devs[0] if devs else "N/A"
    }

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # Using a slightly longer timeout for reliable delivery
        requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)

def main():
    processed = get_processed_links()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    for name, url in SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Aggressive Link Hunting: Look for any link that isn't a Nav item or Social link
            links_found = 0
            for a in soup.find_all('a', href=True):
                href = a['href']
                # Clean relative URLs
                if href.startswith('/'):
                    base = "/".join(url.split("/")[:3])
                    href = base + href
                
                if href in processed or not href.startswith('http'):
                    continue

                # Broad filter: If the link contains keywords or the site-name, check it
                if any(kw in href.lower() for kw in ['news', 'article', 'press', 'media', 'deal', 'insights', 'transaction']):
                    art_res = requests.get(href, headers=headers, timeout=15)
                    art_soup = BeautifulSoup(art_res.text, 'html.parser')
                    full_text = art_soup.get_text()
                    
                    # Extract Data
                    data = aggressive_extract(full_text)
                    
                    # ONLY send if we found at least a Dollar Amount or an LVR (filters out "noise")
                    if data["Amounts"] != "N/A" or data["Metrics"] != "N/A":
                        msg = (
                            f"🚨 *NEW DEAL DETECTED: {name}*\n"
                            f"🔗 [Read Article]({href})\n\n"
                            f"💰 **Facility/Loan:** {data['Amounts']}\n"
                            f"📊 **LVR/LTC/ICR:** {data['Metrics']}\n"
                            f"🏛️ **GRV/Value:** {data['GRV']}\n"
                            f"👷 **Ref. Developer:** {data['Probable_Dev']}"
                        )
                        send_telegram(msg)
                        save_new_link(href)
                        links_found += 1
                        
                if links_found >= 2: # Check up to 2 new articles per site per run
                    break
                    
        except Exception as e:
            print(f"Error on {name}: {e}")

if __name__ == "__main__":
    main()
