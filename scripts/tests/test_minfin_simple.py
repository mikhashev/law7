#!/usr/bin/env python3
"""
Simple test for Minfin portal access.

This script tests if we can access the Minfin portal and parse the HTML structure.

Usage:
    cd scripts && poetry run python tests/test_minfin_simple.py
"""

import asyncio
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Test Minfin portal access."""
    print("\n" + "="*70)
    print("MINFIN PORTAL ACCESS TEST")
    print("="*70)

    # Test imports first
    print("\nChecking required packages...")
    try:
        import aiohttp
        print("[OK] aiohttp imported")
    except ImportError as e:
        print(f"[FAIL] aiohttp not available: {e}")
        print("  Run: poetry run pip install aiohttp")
        return

    try:
        from bs4 import BeautifulSoup
        print("[OK] beautifulsoup4 imported")
    except ImportError as e:
        print(f"[FAIL] beautifulsoup4 not available: {e}")
        return

    # Test 1: Fetch Minfin main page
    print("\nTest 1: Fetching Minfin document page...")
    url = "https://minfin.gov.ru/ru/document/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                html = await response.text()
                print(f"[OK] Fetched {len(html)} bytes")

                # Parse HTML
                soup = BeautifulSoup(html, "html.parser")

                # Find main containers
                main_container = soup.find("div", class_="main_page_container")
                if main_container:
                    print("[OK] Found main_page_container")

                    # Debug: Show all child divs in main_container
                    print("\n  Debug: Child divs in main_container:")
                    child_divs = main_container.find_all("div", class_=True, recursive=False)
                    for i, div in enumerate(child_divs[:10], 1):
                        classes = " ".join(div.get("class", []))
                        print(f"    {i}. class='{classes}'")

                    docs_page = main_container.find("div", class_="docs_page")
                    if docs_page:
                        print("[OK] Found docs_page")

                        # Count links
                        links = docs_page.find_all("a", href=True)
                        print(f"[OK] Found {len(links)} links in docs_page")

                        # Show first few links
                        print("\n  First 5 document links:")
                        for i, link in enumerate(links[:5], 1):
                            href = link.get("href")
                            text = link.get_text(strip=True)[:80]
                            print(f"    {i}. {text}")
                            if href:
                                print(f"       href={href[:80]}")
                    else:
                        print("[FAIL] docs_page not found in main_container")
                        # Try to find any div with document-related class
                        print("\n  Looking for document-related divs in main_container:")
                        for div in main_container.find_all("div", class_=True):
                            classes = " ".join(div.get("class", []))
                            if any(keyword in classes.lower() for keyword in ["doc", "item", "card", "list"]):
                                print(f"    Found: class='{classes}'")
                                # Count links
                                links = div.find_all("a", href=True)
                                if links:
                                    print(f"      Contains {len(links)} links")
                else:
                    print("[FAIL] main_page_container not found")
                    print("  Available div classes with 'page':")
                    for div in soup.find_all("div", class_=True):
                        classes = " ".join(div.get("class", []))
                        if "page" in classes or "doc" in classes:
                            print(f"    {classes}")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    import re  # Import re for regex
    asyncio.run(main())
