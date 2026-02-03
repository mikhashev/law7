import asyncio
from scripts.country_modules.russia.scrapers.ministry_scraper import MinistryScraper
from bs4 import BeautifulSoup
import re

async def test():
    scraper = MinistryScraper('fns')

    # Build URL WITHOUT date filter (fdp=&tdp=)
    search_url = (
        f"{scraper.agency_config['base_url']}/rn77/about_fts/about_nalog/1.html"
        f"?n=&fd=&td=&fdp=&tdp=&ds=0&st=0&dn=0"
    )

    print(f"Fetching: {search_url}")

    html = await scraper._fetch_html(search_url)
    soup = BeautifulSoup(html, 'html.parser')

    with open('test_fns_full_pages.txt', 'w', encoding='utf-8') as f:
        # Check for "всего:" text indicating total documents
        total_text = soup.get_text()
        total_match = re.search(r'всего:\s*(\d+)', total_text)
        if total_match:
            f.write(f"Total documents found (всего): {total_match.group(1)}\n")
        else:
            f.write("No 'всего:' text found in page\n")

        # Look for pagination links
        pagination_links = soup.find_all("a", href=re.compile(r"/about_nalog/\d+\.html"))

        f.write(f"\nPagination links found: {len(pagination_links)}\n")

        # Extract unique page numbers
        page_numbers = set()
        for link in pagination_links:
            href = link.get("href", "")
            match = re.search(r"/about_nalog/(\d+)\.html", href)
            if match:
                page_numbers.add(int(match.group(1)))

        # Also check for active page
        active_page = soup.find("a", class_="active")
        if active_page:
            active_text = active_page.get_text(strip=True)
            if active_text.isdigit():
                page_numbers.add(int(active_text))
                f.write(f"Active page found: {active_text}\n")

        sorted_pages = sorted(page_numbers)
        f.write(f"\nUnique page numbers: {sorted_pages}\n")
        f.write(f"Total pages detected: {len(sorted_pages)}\n")
        f.write(f"Highest page number: {max(sorted_pages) if sorted_pages else 0}\n")

        # Write sample pagination links
        f.write(f"\nLast 10 pagination links:\n")
        for i, link in enumerate(pagination_links[-10:]):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            f.write(f"  [{i+1}] href={href}, text={text[:30]}\n")

        # Check document links on page 1
        doc_links = soup.find_all("a", href=re.compile(r"/rn77/about_fts/about_nalog/\d+/"))
        f.write(f"\n\nDocument links on page 1: {len(doc_links)}\n")

    await scraper.close()
    print("Test complete. Check test_fns_full_pages.txt")

if __name__ == '__main__':
    asyncio.run(test())
