"""
Law7 API Explorer
Fetches and inspects pravo.gov.ru API responses to understand data structure.
Based on ygbis exploration patterns.
"""
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import (
    PRAVO_API_BASE_URL,
    PRAVO_API_TIMEOUT,
)
from utils.retry import fetch_with_retry

# =============================================================================
# Configuration
# =============================================================================
SAMPLES_DIR = Path(__file__).parent.parent / "samples"
DOCS_DIR = Path(__file__).parent.parent / "docs"

# Create directories if they don't exist
SAMPLES_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# API Endpoints to Explore
# =============================================================================
API_ENDPOINTS = {
    "public_blocks": "/PublicBlocks/",
    "categories": "/Categories",
    "document_types": "/DocumentTypes",
    "signatory_authorities": "/SignatoryAuthorities",
}

# =============================================================================
# Helper Functions
# =============================================================================
def fetch_url_with_retry(url: str, max_retries: int = 3) -> requests.Response | None:
    """
    Fetch URL with exponential backoff retry (wrapper for utils.retry.fetch_with_retry).

    Args:
        url: The URL to fetch
        max_retries: Maximum number of retry attempts

    Returns:
        Response object or None if all retries fail
    """
    return fetch_with_retry(
        lambda: requests.get(url, timeout=PRAVO_API_TIMEOUT),
        max_retries=max_retries,
        operation_name=f"fetch {url}",
    )


def save_json_sample(data: Any, filename: str) -> None:
    """Save JSON data to samples directory."""
    filepath = SAMPLES_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"  Saved sample to {filepath}")


def explore_structure(data: Any, path: str = "", max_depth: int = 5, current_depth: int = 0) -> Dict[str, Any]:
    """
    Recursively explore the structure of JSON data.

    Args:
        data: The data to explore
        path: Current path in the structure
        max_depth: Maximum depth to explore
        current_depth: Current depth level

    Returns:
        Dictionary describing the structure
    """
    if current_depth >= max_depth:
        return {"type": type(data).__name__, "value": str(data)[:100]}

    if isinstance(data, dict):
        structure = {}
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            structure[key] = explore_structure(value, new_path, max_depth, current_depth + 1)
        return {"type": "dict", "keys": structure}
    elif isinstance(data, list):
        if len(data) > 0:
            # Explore first item, count rest
            first_item_structure = explore_structure(data[0], f"{path}[0]", max_depth, current_depth + 1)
            return {
                "type": "list",
                "length": len(data),
                "first_item": first_item_structure,
            }
        else:
            return {"type": "list", "length": 0}
    else:
        return {"type": type(data).__name__, "value": str(data)[:100]}


# =============================================================================
# Main Exploration Functions
# =============================================================================
def explore_endpoint(endpoint_name: str, endpoint_path: str) -> Dict[str, Any] | None:
    """
    Explore a single API endpoint.

    Args:
        endpoint_name: Name of the endpoint
        endpoint_path: Path part of the URL

    Returns:
        JSON response data or None if failed
    """
    url = f"{PRAVO_API_BASE_URL.rstrip('/')}/{endpoint_path.lstrip('/')}"
    logger.info(f"\n{'='*60}")
    logger.info(f"Exploring: {endpoint_name}")
    logger.info(f"URL: {url}")
    logger.info(f"{'='*60}")

    response = fetch_url_with_retry(url)
    if not response:
        return None

    try:
        data = response.json()

        # Save raw sample
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{endpoint_name}_{timestamp}.json"
        save_json_sample(data, filename)

        # Explore structure
        structure = explore_structure(data, endpoint_name)

        # Log structure
        logger.info(f"\nStructure:")
        logger.info(json.dumps(structure, indent=2, ensure_ascii=False))

        # Log basic info
        if isinstance(data, dict):
            logger.info(f"\nTop-level keys: {list(data.keys())}")
        elif isinstance(data, list):
            logger.info(f"\nResponse is a list with {len(data)} items")
            if len(data) > 0 and isinstance(data[0], dict):
                logger.info(f"First item keys: {list(data[0].keys())}")

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.info(f"Response text (first 500 chars): {response.text[:500]}")
        return None


def explore_documents_search() -> Dict[str, Any] | None:
    """
    Explore the Documents search endpoint with sample queries.

    Returns:
        JSON response data or None if failed
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Exploring: Documents Search")
    logger.info(f"{'='*60}")

    # Sample queries to test
    queries = [
        {"pageSize": 10},
        {"pageSize": 10, "search": "труд"},
        {"pageSize": 10, "docType": "law", "startDate": "2024-01-01", "endDate": "2024-01-31"},
    ]

    for i, params in enumerate(queries, 1):
        logger.info(f"\nQuery {i}: {params}")
        url = f"{PRAVO_API_BASE_URL.rstrip('/')}/Documents"
        response = fetch_url_with_retry(url)

        if response:
            try:
                # For GET requests, encode params in URL
                full_url = f"{url}?{requests.compat.urlencode(params)}"
                response = requests.get(full_url, timeout=PRAVO_API_TIMEOUT)

                if response.status_code == 200:
                    data = response.json()

                    # Save sample
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"documents_query_{i}_{timestamp}.json"
                    save_json_sample(data, filename)

                    logger.info(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")

                    if isinstance(data, dict) and "data" in data:
                        logger.info(f"  Data type: {type(data['data']).__name__}")
                        if isinstance(data["data"], list):
                            logger.info(f"  Data length: {len(data['data'])}")
                else:
                    logger.warning(f"  Status: {response.status_code}")

            except Exception as e:
                logger.error(f"  Error: {e}")


def explore_document_detail(eo_number: str = "0001202401170001") -> Dict[str, Any] | None:
    """
    Explore the Document detail endpoint.

    Args:
        eo_number: Example eoNumber to fetch

    Returns:
        JSON response data or None if failed
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Exploring: Document Detail")
    logger.info(f"{'='*60}")

    url = f"{PRAVO_API_BASE_URL.rstrip('/')}/Document/{eo_number}"
    logger.info(f"URL: {url}")

    response = fetch_url_with_retry(url)
    if not response:
        return None

    try:
        data = response.json()

        # Save sample
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"document_detail_{eo_number}_{timestamp}.json"
        save_json_sample(data, filename)

        logger.info(f"\nResponse keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return None


# =============================================================================
# Main
# =============================================================================
def main():
    """Main exploration function."""
    logger.info("="*60)
    logger.info("Law7 API Explorer")
    logger.info("="*60)
    logger.info(f"Base URL: {PRAVO_API_BASE_URL}")
    logger.info(f"Timeout: {PRAVO_API_TIMEOUT}s")
    logger.info(f"Samples directory: {SAMPLES_DIR}")
    logger.info(f"Docs directory: {DOCS_DIR}")

    # 1. Explore basic endpoints
    results = {}
    for endpoint_name, endpoint_path in API_ENDPOINTS.items():
        data = explore_endpoint(endpoint_name, endpoint_path)
        results[endpoint_name] = data
        time.sleep(1)  # Brief pause between requests

    # 2. Explore documents search
    explore_documents_search()
    time.sleep(1)

    # 3. Explore document detail
    explore_document_detail()

    # 4. Generate analysis document
    generate_analysis_document(results)


def generate_analysis_document(results: Dict[str, Any]) -> None:
    """Generate a markdown document with API analysis findings."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"""# Pravo.gov.ru API Analysis

**Generated:** {timestamp}
**Base URL:** {PRAVO_API_BASE_URL}

---

## API Endpoints

| Endpoint | Path | Status |
|----------|------|--------|
"""

    for endpoint_name, endpoint_path in API_ENDPOINTS.items():
        status = "OK" if results.get(endpoint_name) else "FAILED"
        content += f"| {endpoint_name} | `{endpoint_path}` | {status} |\n"

    content += """
---

## Findings

### Required vs Optional Fields

[To be filled after manual inspection of samples]

### Data Types and Formats

[To be filled after manual inspection of samples]

### Pagination Behavior

[To be filled after manual inspection of samples]

### Rate Limiting Observations

[To be filled after manual inspection of samples]

---

## Next Steps

1. Manually inspect JSON samples in `scripts/samples/`
2. Identify common fields across document types
3. Design database schema based on actual data structure
4. Implement parser for each document type

---

## Sample Files

The following sample files have been saved to `scripts/samples/`:
"""

    # List sample files
    for filepath in sorted(SAMPLES_DIR.glob("*.json")):
        size = filepath.stat().st_size
        content += f"- `{filepath.name}` ({size:,} bytes)\n"

    # Save analysis document
    analysis_path = DOCS_DIR / "pravo_api_analysis.md"
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"\n{'='*60}")
    logger.info(f"Analysis document saved to: {analysis_path}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
