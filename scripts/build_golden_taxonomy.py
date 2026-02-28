import sys
from pathlib import Path

# Add src to Python path so we can import knowledgelm
src_path = Path(__file__).parent.parent / "src"
sys.path.append(str(src_path))

from knowledgelm.data.nse_adapter import NSEAdapter
from bs4 import BeautifulSoup
import logging
import urllib.parse
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoldenTaxonomyBuilder")

def main():
    dest_dir = Path(__file__).parent.parent / "golden_taxonomy_v1"
    temp_download_dir = Path(__file__).parent.parent / ".temp_taxonomies"
    
    # Initialize NSEAdapter
    adapter = NSEAdapter(download_folder=temp_download_dir)
    url = "https://www.nseindia.com/static/companies-listing/xbrl-information"
    
    logger.info(f"Fetching HTML from {url}...")
    response = adapter.nse._req(url)
    if response.status_code != 200:
        logger.error(f"Failed to fetch {url}, status code: {response.status_code}")
        return
        
    soup = BeautifulSoup(response.content, "html.parser")
    zip_links = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".zip"):
            full_url = urllib.parse.urljoin(url, href)
            zip_links.append(full_url)
            
    logger.info(f"Found {len(zip_links)} ZIP links.")
    
    # Prepare destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_download_dir.mkdir(parents=True, exist_ok=True)
    
    for z_url in zip_links:
        logger.info(f"Downloading and extracting {z_url}...")
        adapter.download_and_extract(z_url, dest_dir)
        
    logger.info("Extracting any nested zip files found inside the taxonomy directory...")
    import zipfile
    import os
    import glob
    
    nested_zips = glob.glob(str(dest_dir / "**/*.zip"), recursive=True)
    for nested_zip in nested_zips:
        logger.info(f"Extracting nested zip: {nested_zip}")
        try:
            with zipfile.ZipFile(nested_zip) as z:
                z.extractall(os.path.dirname(nested_zip))
            os.remove(nested_zip)
        except Exception as e:
            logger.error(f"Failed to extract nested zip {nested_zip}: {e}")

    logger.info("Finished downloading and extracting all taxonomies into golden_taxonomy_v1.")

if __name__ == "__main__":
    main()
