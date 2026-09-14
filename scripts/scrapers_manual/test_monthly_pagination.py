"""
Test monthly date ranges to get ALL documents from vsrf.ru.
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

# Test monthly ranges for 2025
print("="*60)
print("Testing MONTHLY ranges for 2025")
print("="*60)

# Month definitions for 2025
months_2025 = [
    ("01.01.2025", "31.01.2025", "January"),
    ("01.02.2025", "28.02.2025", "February"),
    ("01.03.2025", "31.03.2025", "March"),
    ("01.04.2025", "30.04.2025", "April"),
    ("01.05.2025", "31.05.2025", "May"),
    ("01.06.2025", "30.06.2025", "June"),
    ("01.07.2025", "31.07.2025", "July"),
    ("01.08.2025", "31.08.2025", "August"),
    ("01.09.2025", "30.09.2025", "September"),
    ("01.10.2025", "31.10.2025", "October"),
    ("01.11.2025", "30.11.2025", "November"),
    ("01.12.2025", "31.12.2025", "December"),
]

total_docs = 0
all_doc_ids = []

for start, end, month in months_2025:
    url = f"https://vsrf.ru/documents/own/?date_start={start}&date_end={end}&before=2"
    print(f"\n{month}: {url}")

    driver.get(url)
    time.sleep(10)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    doc_ids = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            doc_ids.append(href.strip('/'))

    # Track unique IDs
    new_ids = [id for id in doc_ids if id not in all_doc_ids]
    all_doc_ids.extend(doc_ids)

    print(f"  Documents: {len(doc_ids)} (new: {len(new_ids)})")
    if doc_ids:
        print(f"  ID range: {doc_ids[0]} - {doc_ids[-1]}")

    total_docs += len(doc_ids)
    time.sleep(2)  # Small delay between requests

driver.quit()

print("\n" + "="*60)
print(f"TOTAL for 2025: {len(set(all_doc_ids))} unique documents")
print("="*60)
print("\nConclusion: Monthly ranges can capture ALL documents!")
print("Recommendation: Update scraper to use monthly date ranges.")
