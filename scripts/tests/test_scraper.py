#!/usr/bin/env python3
"""
Test Ministry of Finance scraper implementation.

Usage:
    cd scripts && poetry run python tests/test_scraper.py
"""

import asyncio
import sys
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))


async def test_minfin_scraper():
    """Test the MinistryScraper class."""
    print("\n" + "="*70)
    print("MINFIN SCRAPER CLASS TEST")
    print("="*70)

    # Import dependencies
    try:
        import aiohttp
        from bs4 import BeautifulSoup
        print("[OK] Required packages imported")
    except ImportError as e:
        print(f"[FAIL] {e}")
        return

    # Import MinistryScraper
    try:
        # Import using absolute import from scripts directory
        sys.path.insert(0, str(scripts_dir / "country_modules" / "russia" / "scrapers"))

        # We need to import the base module first
        sys.path.insert(0, str(scripts_dir / "country_modules"))
        sys.path.insert(0, str(scripts_dir / "country_modules" / "russia"))
        sys.path.insert(0, str(scripts_dir))

        # Now import the scraper
        from country_modules.russia.scrapers.ministry_scraper import MinistryScraper
        print("[OK] MinistryScraper imported")
    except ImportError as e:
        print(f"[FAIL] Could not import MinistryScraper: {e}")
        print("\nTrying direct execution test instead...")

        # Direct execution test
        await test_minfin_direct()
        return

    # Create scraper instance
    scraper = MinistryScraper("minfin")

    try:
        # Test 1: Fetch manifest
        print("\n--- Test 1: Fetch Manifest ---")
        manifest = await scraper.fetch_manifest()

        print(f"[OK] Manifest fetched")
        print(f"  Agency: {manifest['agency_name_short']}")
        print(f"  Letters found: {len(manifest.get('letters', []))}")
        print(f"  Total found: {manifest.get('metadata', {}).get('total_found', 'N/A')}")

        if manifest.get('letters'):
            print(f"\n  First 3 letters:")
            for i, letter in enumerate(manifest['letters'][:3], 1):
                print(f"    {i}. {letter.get('title', 'N/A')[:60]}")
                print(f"       Date: {letter.get('document_date', 'N/A')}")
                print(f"       Number: {letter.get('document_number', 'N/A')}")
                print(f"       URL: {letter.get('url', 'N/A')[:60]}...")

        # Test 2: Fetch a single document
        if manifest.get('letters') and len(manifest['letters']) > 0:
            print("\n--- Test 2: Fetch Document ---")
            first_letter = manifest['letters'][0]
            doc_url = first_letter['url']

            print(f"Fetching: {doc_url}")
            doc = await scraper.fetch_document(doc_url)

            print(f"[OK] Document fetched")
            print(f"  Content length: {len(doc.content)} bytes")
            print(f"  Content type: {doc.content_type}")
            print(f"  Title: {doc.metadata.get('title', 'N/A')[:80]}")
            print(f"  Date: {doc.metadata.get('document_date', 'N/A')}")
            print(f"  Number: {doc.metadata.get('document_number', 'N/A')}")

            # Show content preview
            content_preview = doc.content.decode("utf-8", errors="ignore")[:300]
            print(f"\n  Content preview:")
            print(f"    {content_preview}...")

        print("\n" + "="*70)
        print("ALL TESTS PASSED")
        print("="*70)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await scraper.close()
        print("\nTest complete\n")


async def test_minfin_direct():
    """Test Minfin portal access directly without the scraper class."""
    import aiohttp
    from bs4 import BeautifulSoup
    import re

    print("\n--- Direct Minfin Portal Test ---")

    url = "https://minfin.gov.ru/ru/document/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                html = await response.text()
                print(f"[OK] Fetched {len(html)} bytes")

                soup = BeautifulSoup(html, "html.parser")

                # Find document cards
                doc_cards = soup.find_all("div", class_="document_card")
                print(f"[OK] Found {len(doc_cards)} document cards")

                if doc_cards:
                    print("\n  First 3 cards:")
                    for i, card in enumerate(doc_cards[:3], 1):
                        # Find the link
                        link = card.find("a", class_="inner_link")
                        if not link:
                            link = card.find("a", href=True)

                        if link:
                            href = link.get("href")
                            text = link.get_text(strip=True)[:80]

                            # Look for date
                            date_elem = card.find("div", class_="date_list")
                            date_text = date_elem.get_text(strip=True) if date_elem else "N/A"

                            print(f"    {i}. {text}")
                            print(f"       Date: {date_text}")
                            if href:
                                full_url = f"https://minfin.gov.ru{href}" if href.startswith("/") else href
                                print(f"       URL: {full_url[:80]}")

                    # Try to fetch first document
                    first_card = doc_cards[0]
                    first_link = first_card.find("a", class_="inner_link")
                    if not first_link:
                        first_link = first_card.find("a", href=True)

                    if first_link and first_link.get("href"):
                        href = first_link.get("href")
                        doc_url = f"https://minfin.gov.ru{href}" if href.startswith("/") else href

                        print(f"\n--- Fetching Document ---")
                        print(f"URL: {doc_url}")

                        async with session.get(doc_url, timeout=aiohttp.ClientTimeout(total=30)) as doc_response:
                            doc_response.raise_for_status()
                            doc_html = await doc_response.text()
                            print(f"[OK] Fetched {len(doc_html)} bytes")

                            doc_soup = BeautifulSoup(doc_html, "html.parser")

                            # Find title
                            title = doc_soup.find("h1")
                            if title:
                                print(f"  Title: {title.get_text(strip=True)[:100]}")

                            # Find content
                            content_div = doc_soup.find("div", class_=re.compile(r"content|text|document"))
                            if content_div:
                                paragraphs = content_div.find_all("p")
                                print(f"  Found {len(paragraphs)} paragraphs")

                                if paragraphs:
                                    first_p = paragraphs[0].get_text(strip=True)
                                    print(f"  First paragraph: {first_p[:150]}...")

                print("\n" + "="*70)
                print("DIRECT TEST PASSED")
                print("="*70)

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\nDirect test complete\n")


if __name__ == "__main__":
    asyncio.run(test_minfin_scraper())
