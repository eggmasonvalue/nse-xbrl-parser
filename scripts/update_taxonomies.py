import sys
import httpx
from pathlib import Path
from bs4 import BeautifulSoup
import logging
import urllib.parse
import zipfile
import tempfile
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nse_xbrl_parser.taxonomy_store import TAXONOMY_DIR, discover_release_units, install_release, release_is_self_contained

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TaxonomyBuilder")


def _safe_archive_dirname(url: str) -> str:
    """Create a stable directory name for an extracted archive."""
    raw_name = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).stem
    safe_name = re.sub(r'[<>:"/\\\\|?*]', "_", raw_name).strip()
    return safe_name or "taxonomy_archive"

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
    TAXONOMY_DIR.mkdir(parents=True, exist_ok=True)

    fetcher = NSEXBRLFetcher()
    zip_links = fetcher.fetch_taxonomy_links()

    if not zip_links:
        logger.error("No taxonomy links found. Exiting.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        added_release_count = 0
        skipped_release_count = 0

        for z_url in zip_links:
            zip_name = urllib.parse.unquote(z_url.split("/")[-1])
            archive_root = temp_dir / _safe_archive_dirname(z_url)
            archive_root.mkdir(parents=True, exist_ok=True)
            temp_zip_path = archive_root / zip_name
            fetcher.download_file(z_url, temp_zip_path)
            
            # Extract main ZIP
            if temp_zip_path.exists():
                logger.info(f"Extracting main ZIP: {zip_name}")
                try:
                    with zipfile.ZipFile(temp_zip_path, 'r') as z:
                        z.extractall(archive_root)
                except zipfile.BadZipFile:
                    logger.error(f"Corrupted downloaded ZIP: {zip_name}")
                    continue

                nested_zips = list(archive_root.rglob("*.zip"))
                logger.info(f"Extracting {len(nested_zips)} nested ZIPs from {archive_root.name}...")
                for nested_zip in nested_zips:
                    if nested_zip == temp_zip_path:
                        continue
                    try:
                        with zipfile.ZipFile(nested_zip, 'r') as z:
                            z.extractall(nested_zip.parent)
                    except zipfile.BadZipFile:
                        logger.error(f"Corrupted nested ZIP: {nested_zip.name}")

                releases = discover_release_units(archive_root)
                logger.info(f"Discovered {len(releases)} release units in {archive_root.name}.")
                for release in releases:
                    if not release_is_self_contained(release):
                        logger.warning(
                            f"Skipping non-self-contained release {release.family}/{release.release_id} from {archive_root.name}"
                        )
                        skipped_release_count += 1
                        continue
                    added, target_dir = install_release(
                        release,
                        destination_root=TAXONOMY_DIR,
                        source_url=z_url,
                        provenance_name=archive_root.name,
                    )
                    if added:
                        added_release_count += 1
                        logger.info(f"Added release {release.family}/{release.release_id} -> {target_dir}")
                    else:
                        skipped_release_count += 1
                        logger.info(f"Skipped existing release {release.family}/{release.release_id}")

        logger.info("Release Summary:")
        logger.info(f" - Added {added_release_count} new canonical releases")
        logger.info(f" - Skipped {skipped_release_count} duplicate releases")

    logger.info("Taxonomy build complete.")

if __name__ == "__main__":
    main()
