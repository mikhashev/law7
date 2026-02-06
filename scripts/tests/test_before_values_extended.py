"""Test higher before= values (3, 4, 5, 10, etc.) to find maximum."""
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

# Test a wide range of before values
before_values = [None, 1, 2, 3, 4, 5, 10, 20, 50, 100]

# Test on the section that showed the most variation
test_url = "https://vsrf.ru/documents/own/?date_start=01.01.2024"

print("="*70)
print(f"Testing before= values on Plenary Resolutions (2024)")
print("="*70)

results = []
for before in before_values:
    if before is None:
        url = test_url
        label = "default"
    else:
        url = f"{test_url}&before={before}"
        label = f"before={before}"

    driver.get(url)
    time.sleep(10)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    doc_ids = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            doc_ids.append(href.strip('/'))

    results.append((label, len(doc_ids), doc_ids))
    print(f"{label:15} -> {len(doc_ids):3} documents (ID: {doc_ids[0] if doc_ids else 'N/A'} - {doc_ids[-1] if doc_ids else 'N/A'})")

driver.quit()

# Find the maximum
max_before = max(results, key=lambda x: x[1])
print("\n" + "="*70)
print(f"MAXIMUM: {max_before[0]} gives {max_before[1]} documents")
print("="*70)

# Check if all queries returned the same first document ID
first_ids = set(r[2][0] for r in results if r[2])
print(f"\nUnique first document IDs: {first_ids}")
print(f"All start from same document: {len(first_ids) == 1}")
