
import os
import json
import logging
from typing import List, Dict, Optional
from firecrawl import FirecrawlApp
from urllib.parse import urlparse
from datetime import datetime
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SCRAPE_DIR = "scraped_content"

mcp = FastMCP("llm_inference")

def _resolve_api_key(api_key: Optional[str]) -> str:
    """Return the given API key, falling back to the FIRECRAWL_API_KEY environment variable."""
    api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        raise ValueError("API key must be provided or set as FIRECRAWL_API_KEY environment variable")
    return api_key


def _load_metadata(metadata_file: str) -> Dict[str, dict]:
    """Load the scraped metadata file, returning an empty dict if it is missing or invalid."""
    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_metadata(metadata_file: str, scraped_metadata: Dict[str, dict]) -> None:
    with open(metadata_file, 'w') as f:
        json.dump(scraped_metadata, f, indent=4)


def _base_metadata(provider_name: str, url: str, formats: List[str]) -> dict:
    return {
        "provider_name": provider_name,
        "url": url,
        "domain": urlparse(url).netloc,
        "scraped_at": datetime.now().isoformat(),
        "formats": formats,
    }


def _save_content_files(provider_name: str, scrape_result: dict, formats: List[str]) -> Dict[str, str]:
    """Write each requested format's content to SCRAPE_DIR and return format -> filename."""
    content_files = {}
    for format_type in formats:
        content = scrape_result.get(format_type)
        if content:
            filename = f"{provider_name}_{format_type}.txt"
            with open(os.path.join(SCRAPE_DIR, filename), 'w', encoding='utf-8') as f:
                f.write(content)
            content_files[format_type] = filename
    return content_files


def _scrape_provider(app: FirecrawlApp, provider_name: str, url: str, formats: List[str]) -> dict:
    """Scrape one website, save its content and return its metadata entry."""
    metadata = _base_metadata(provider_name, url, formats)
    try:
        logger.info(f"Scraping {provider_name}: {url}")
        scrape_result = app.scrape(url, formats=formats).model_dump()

        # Newer Firecrawl versions return a Document without a 'success' key,
        # so fall back to whether any requested content came back.
        success = scrape_result.get('success', any(scrape_result.get(fmt) for fmt in formats))

        if success:
            page_metadata = scrape_result.get('metadata') or {}
            metadata["success"] = "true"
            metadata["content_files"] = _save_content_files(provider_name, scrape_result, formats)
            metadata["title"] = page_metadata.get('title', '')
            metadata["description"] = page_metadata.get('description', '')
            logger.info(f"Successfully scraped {provider_name}")
        else:
            metadata["success"] = "false"
            metadata["error"] = scrape_result.get('error', 'Unknown error')
            logger.error(f"Failed to scrape {provider_name}: {metadata['error']}")
    except Exception as e:
        logger.error(f"Error scraping {provider_name}: {e}")
        metadata["success"] = "false"
        metadata["error"] = str(e)
    return metadata


@mcp.tool()
def scrape_websites(
    websites: Dict[str, str],
    formats: List[str] = ['markdown', 'html'],
    api_key: Optional[str] = None
) -> List[str]:
    """
    Scrape multiple websites using Firecrawl and store their content.
    
    Args:
        websites: Dictionary of provider_name -> URL mappings
        formats: List of formats to scrape ['markdown', 'html'] (default: both)
        api_key: Firecrawl API key (if None, expects environment variable)
        
    Returns:
        List of provider names for successfully scraped websites
    """
    app = FirecrawlApp(api_key=_resolve_api_key(api_key))
    os.makedirs(SCRAPE_DIR, exist_ok=True)

    metadata_file = os.path.join(SCRAPE_DIR, "scraped_metadata.json")
    scraped_metadata = _load_metadata(metadata_file)

    for provider_name, url in websites.items():
        scraped_metadata[provider_name] = _scrape_provider(app, provider_name, url, formats)

    _save_metadata(metadata_file, scraped_metadata)

    successful_scrapes = [name for name in websites if scraped_metadata[name]["success"] == "true"]
    logger.info(f"Scraped {len(successful_scrapes)}/{len(websites)} websites successfully: {successful_scrapes}")
    return successful_scrapes

def _find_metadata(scraped_metadata: Dict[str, dict], identifier: str) -> Optional[dict]:
    """Return the entry whose provider name, URL or domain matches the identifier."""
    for provider_name, metadata in scraped_metadata.items():
        if identifier in (provider_name, metadata.get('url', ''), metadata.get('domain', '')):
            return metadata
    return None


def _load_content(content_files: Dict[str, str]) -> Dict[str, str]:
    """Read each saved content file from SCRAPE_DIR, keyed by format."""
    content = {}
    for format_type, filename in content_files.items():
        with open(os.path.join(SCRAPE_DIR, filename), 'r', encoding='utf-8') as f:
            content[format_type] = f.read()
    return content


@mcp.tool()
def extract_scraped_info(identifier: str) -> str:
    """
    Extract information about a scraped website.
    
    Args:
        identifier: The provider name, full URL, or domain to look for
        
    Returns:
        Formatted JSON string with the scraped information
    """
    
    logger.info(f"Extracting information for identifier: {identifier}")
    logger.info(f"Files in {SCRAPE_DIR}: {os.listdir(SCRAPE_DIR)}")

    metadata_file = os.path.join(SCRAPE_DIR, "scraped_metadata.json")
    logger.info(f"Checking metadata file: {metadata_file}")

    not_found = f"There's no saved information related to identifier '{identifier}'."

    try:
        metadata = _find_metadata(_load_metadata(metadata_file), identifier)
        if metadata is None:
            return not_found

        result = metadata.copy()
        if 'content_files' in metadata:
            result['content'] = _load_content(metadata['content_files'])
        return json.dumps(result, indent=2)
    except FileNotFoundError as e:
        logger.error(f"Error reading scraped info for '{identifier}': {e}")
        return not_found

if __name__ == "__main__":
    mcp.run(transport="stdio")