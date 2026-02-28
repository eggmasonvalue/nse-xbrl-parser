import sys
import httpx
from pathlib import Path
from bs4 import BeautifulSoup
import logging
import urllib.parse
import zipfile
import tempfile
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TaxonomyBuilder")

class NSEXBRLFetcher:
    """A minimal, independent HTTPX client to bypass NSE firewalls and download taxonomies."""
    
    def __init__(self):
        # We must use HTTP/2 and spoof a standard browser to bypass NSE protections
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/118.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=HDFCBANK",
        }
        # Increased timeout to 120s because NSE ZIP files can be large and throttled
        self.client = httpx.Client(http2=True, headers=self.headers, timeout=120.0, follow_redirects=True)
        
    def _init_session(self):
        """Hit the root domain first to acquire the required NSE cookies."""
        logger.info("Initializing NSE Session Cookies...")
        try:
            self.client.get("https://www.nseindia.com/")
        except Exception as e:
            logger.warning(f"Session initialization encountered an error (continuing anyway): {e}")

    def fetch_taxonomy_links(self) -> list[str]:
        """Scrape the static NSE XBRL info page for taxonomy ZIP URLs."""
        self._init_session()
        
        # The URL containing the ZIP files
        url = "https://www.nseindia.com/companies-listing/xbrl-information"
        logger.info(f"Fetching taxonomy links from {url}")
        
        response = self.client.get(url)
        if response.status_code != 200:
            logger.error(f"Failed to fetch {url}. Status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        zip_links = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".zip"):
                full_url = urllib.parse.urljoin(url, href)
                zip_links.append(full_url)
                
        # Deduplicate while preserving order
        unique_links = list(dict.fromkeys(zip_links))
        logger.info(f"Discovered {len(unique_links)} unique ZIP links.")
        return unique_links

    def download_file(self, url: str, dest_path: Path):
        """Stream a file from NSE to the local disk with robust timeout handling."""
        logger.info(f"Downloading: {url}")
        
        for attempt in range(3):
            try:
                with self.client.stream("GET", url) as response:
                    if response.status_code != 200:
                        logger.error(f"Failed to download {url}. Status: {response.status_code}")
                        return
                    
                    with open(dest_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                # Successful download
                return
            except httpx.ReadTimeout:
                logger.warning(f"ReadTimeout on attempt {attempt+1}/3 for {url}. Retrying...")
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
                return
                
        logger.error(f"Exhausted all retries for {url}.")

def main():
    dest_dir = Path(__file__).parent.parent / "src" / "nse_xbrl_parser"/ "taxonomies"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    fetcher = NSEXBRLFetcher()
    zip_links = fetcher.fetch_taxonomy_links()
    
    if not zip_links:
        logger.error("No taxonomy links found. Exiting.")
        sys.exit(1)
        
    # Process within an isolated temporary directory
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        # Download Phase
        for idx, z_url in enumerate(zip_links):
            zip_name = z_url.split("/")[-1]
            temp_zip_path = temp_dir / zip_name
            fetcher.download_file(z_url, temp_zip_path)
            
            # Extract main ZIP
            if temp_zip_path.exists():
                logger.info(f"Extracting main ZIP: {zip_name}")
                try:
                    with zipfile.ZipFile(temp_zip_path, 'r') as z:
                        z.extractall(temp_dir)
                except zipfile.BadZipFile:
                    logger.error(f"Corrupted downloaded ZIP: {zip_name}")
                
        # Nested Extraction Phase
        nested_zips = list(temp_dir.rglob("*.zip"))
        logger.info(f"Extracting {len(nested_zips)} nested ZIPs...")
        for nested_zip in nested_zips:
            try:
                with zipfile.ZipFile(nested_zip, 'r') as z:
                    z.extractall(nested_zip.parent)
            except zipfile.BadZipFile:
                logger.error(f"Corrupted nested ZIP: {nested_zip.name}")

        # Idempotent Copy Phase (Additive Only)
        # We only want .xsd (schema) and .xml (linkbases). Delete Excel Bloat (.xlsx, .xlsm, .xls)
        logger.info(f"Merging valid taxonomies into {dest_dir} (Idempotent Additive)")
        new_files_count = 0
        updated_files_count = 0
        deleted_excel_count = 0
        
        # Walk through the temp extraction directory
        for f in temp_dir.rglob("*"):
            if f.is_file():
                # Explicitly ignore Bloat
                if f.suffix.lower() in [".xlsx", ".xlsm", ".xls", ".pdf"]:
                    deleted_excel_count += 1
                    continue
                    
                # We only want XSDs and XMLs
                if f.suffix.lower() not in [".xsd", ".xml"]:
                    continue
                
                # Maintain relative structure if desired, but classical flat Taxonomy prefers flat
                # However we must avoid namespace collisions, so keeping them exactly as extracted is safest.
                # Actually, NSE schemas internally reference relatives like `../in-role-2023.xsd`, 
                # meaning they must be entirely flattened into a root directory.
                rel_path = f.name
                target_path = dest_dir / rel_path
                
                # Copy idempotently
                if not target_path.exists():
                    shutil.copy2(f, target_path)
                    new_files_count += 1
                else:
                    # Check if file has changed (simple byte size check for speed, or overwrite if strictly newer)
                    # For safety, we'll aggressively overwrite existing schemas to ensure we have the very latest patch
                    shutil.copy2(f, target_path)
                    updated_files_count += 1
                    
        logger.info("Refinement Summary:")
        logger.info(f" - Ignored {deleted_excel_count} bloat files (XLSX, PDF, etc)")
        logger.info(f" - Added {new_files_count} brand new schemas")
        logger.info(f" - Overwrote/Updated {updated_files_count} existing schemas")
        
    logger.info("Taxonomy build complete.")

if __name__ == "__main__":
    main()
