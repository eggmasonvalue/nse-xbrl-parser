import sys
import httpx
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoldenTaxonomyBuilder")

def main():
    logger.info("Initializing custom HTTPX client for NSE bypass...")
    
    # Establish base browser headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/118.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=HDFCBANK",
    }
    
    # Needs HTTP/2 for NSE
    client = httpx.Client(http2=True, headers=headers, timeout=15)
    
    try:
        # Step 1: Hit the root to get the session cookies
        logger.info("Step 1: Fetching root session cookies from www.nseindia.com/option-chain")
        res1 = client.get("https://www.nseindia.com/option-chain")
        logger.info(f"Root response status: {res1.status_code}")
        
        # Step 2: Fetch the API endpoint mentioned
        # Test if /api/xbrl-taxonomy exists or if we need to hit the static page
        api_url = "https://www.nseindia.com/api/xbrl-taxonomy"
        logger.info(f"Step 2: Testing {api_url}")
        res2 = client.get(api_url)
        logger.info(f"API response status: {res2.status_code}")
        if res2.status_code == 200:
            logger.info("API exists! Response:")
            logger.info(res2.text[:500])
        else:
            logger.warning(f"API {api_url} failed. We must fall back to crawling the static HTML page.")
            
            static_url = "https://www.nseindia.com/companies-listing/xbrl-information"
            logger.info(f"Step 2B: Falling back to {static_url}")
            res3 = client.get(static_url)
            logger.info(f"Static HTML response: {res3.status_code}")
            
    except Exception as e:
        logger.error(f"Failed HTTP request: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
