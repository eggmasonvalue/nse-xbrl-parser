import sys
import httpx
from bs4 import BeautifulSoup

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/118.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=HDFCBANK",
    }
    client = httpx.Client(http2=True, headers=headers, timeout=30.0, follow_redirects=True)
    
    # Init exactly like nse.py
    res1 = client.get("https://www.nseindia.com/option-chain")
    print(f"Cookie Init Status: {res1.status_code}")
    
    # 2. Try fetching
    res2 = client.get("https://www.nseindia.com/companies-listing/xbrl-information")
    print(f"HTML Fetch Status: {res2.status_code}")
    
    with open("debug_nse2.html", "w", encoding="utf-8") as f:
        f.write(res2.text)
        
    soup = BeautifulSoup(res2.text, "html.parser")
    links = soup.find_all("a", href=True)
    
    zips = [a["href"] for a in links if a["href"].endswith(".zip")]
    print(f"Total links: {len(links)}")
    print(f"ZIP links: {len(zips)}")
    
if __name__ == "__main__":
    main()
