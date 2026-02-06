"""
Test real pagination by using document IDs as navigation.

Hypothesis: vsrf.ru might use document IDs for pagination like:
- Page 1: Start from most recent (35296)
- Page 2: Start from last document of page 1
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

# Get first page with max documents
url1 = "https://vsrf.ru/documents/own/?year=2025&before=2"
print(f"Page 1: {url1}")
driver.get(url1)
time.sleep(12)

html1 = driver.page_source
soup1 = BeautifulSoup(html1, 'html.parser')

doc_ids_page1 = []
for link in soup1.find_all("a", href=True):
    href = link.get("href", "")
    if re.match(r'^\d+/$', href):
        doc_ids_page1.append(href.strip('/'))

print(f"Page 1: {len(doc_ids_page1)} documents")
print(f"  First ID: {doc_ids_page1[0]}, Last ID: {doc_ids_page1[-1]}")

# Try to use the last ID as a pagination parameter
last_id = doc_ids_page1[-1]
print(f"\n--- Trying pagination with last ID ({last_id}) ---")

# Test different pagination patterns with the last document ID
test_patterns = [
    f"?year=2025&before={last_id}",
    f"?year=2025&after={last_id}",
    f"?year=2025&from={last_id}",
    f"?year=2025&PAGEN_1={last_id}",
]

for pattern in test_patterns:
    url = f"https://vsrf.ru/documents/own/{pattern}"
    print(f"\nTesting: {url}")

    driver.get(url)
    time.sleep(10)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    doc_ids = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            doc_ids.append(href.strip('/'))

    # Check if this page has different documents
    overlap = set(doc_ids) & set(doc_ids_page1)
    print(f"  Documents: {len(doc_ids)}, Overlap: {len(overlap)}")

    if doc_ids and doc_ids[0] != doc_ids_page1[0]:
        print(f"  *** DIFFERENT FIRST ID: {doc_ids[0]} (page 1 was {doc_ids_page1[0]}) ***")
    elif len(doc_ids) != len(doc_ids_page1):
        print(f"  *** DIFFERENT COUNT: {len(doc_ids)} vs {len(doc_ids_page1)} ***")

driver.quit()
