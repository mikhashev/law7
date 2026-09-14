"""
Test vsrf.ru date-based pagination using date_start parameter.

This could be the real pagination mechanism - using date ranges!
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)

# Test different date ranges for year 2025
test_cases = [
    # Full year 2025
    ("?year=2025", "Year filter only"),
    # Date ranges
    ("?date_start=01.01.2025&before=2", "Full 2025 with date_start"),
    ("?date_start=01.01.2024&date_end=31.12.2024&before=2", "Full 2024 range"),
    # Multiple ranges for 2025
    ("?date_start=01.01.2025&date_end=30.06.2025&before=2", "First half 2025"),
    ("?date_start=01.07.2025&date_end=31.12.2025&before=2", "Second half 2025"),
]

results = []
for params, description in test_cases:
    url = f"https://vsrf.ru/documents/own/{params}"
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    driver.get(url)
    time.sleep(12)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    doc_ids = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            doc_ids.append(href.strip('/'))

    print(f"Documents: {len(doc_ids)}")
    if doc_ids:
        print(f"ID range: {doc_ids[0]} - {doc_ids[-1]}")

    results.append((description, len(doc_ids), doc_ids))

driver.quit()

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
for desc, count, ids in results:
    print(f"{desc:40} -> {count:3} documents")
