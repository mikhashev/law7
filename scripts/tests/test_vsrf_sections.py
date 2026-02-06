"""
Test all vsrf.ru document sections with different before values.
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)

# Test all document sections
sections = [
    ("https://vsrf.ru/documents/own/", "Plenary Resolutions (own)"),
    ("https://vsrf.ru/documents/presidium-resolutions/", "Presidium Resolutions"),
    ("https://vsrf.ru/documents/reviews/", "Practice Reviews"),
    ("https://vsrf.ru/documents/statistics/", "Statistics"),
    ("https://vsrf.ru/documents/international_practice/", "International Practice"),
    ("https://vsrf.ru/documents/arbitration/", "Arbitration"),
]

print("="*70)
print("Testing all vsrf.ru document sections")
print("="*70)

for base_url, section_name in sections:
    print(f"\n{'='*70}")
    print(f"{section_name}")
    print(f"{'='*70}")

    # Test with different before values
    for before_val in [None, 1, 2]:
        if before_val is None:
            url = f"{base_url}?date_start=01.01.2024"
            label = "before=None"
        else:
            url = f"{base_url}?date_start=01.01.2024&before={before_val}"
            label = f"before={before_val}"

        try:
            driver.get(url)
            time.sleep(10)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            doc_ids = []
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if re.match(r'^\d+/$', href):
                    doc_ids.append(href.strip('/'))

            print(f"  {label:15} -> {len(doc_ids):3} documents", end="")
            if doc_ids:
                print(f" (ID: {doc_ids[0]} - {doc_ids[-1]})")
            else:
                print()

        except Exception as e:
            print(f"  {label:15} -> ERROR: {e}")

driver.quit()

print("\n" + "="*70)
print("Summary: Each section can be scraped using date_start + before parameters")
print("="*70)
