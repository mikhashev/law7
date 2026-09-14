"""
Test if we can paginate using the last document ID.

Hypothesis: There might be a parameter that says "start from document ID X"
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
url1 = "https://vsrf.ru/documents/own/?date_start=01.01.2024&before=4"
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

print(f"Page 1: {len(doc_ids_page1)} documents (ID: {doc_ids_page1[0]} - {doc_ids_page1[-1]})")

# Try to use the last ID to get the next page
last_id = doc_ids_page1[-1]  # Oldest document on page 1
print(f"\nTrying to get documents OLDER than ID {last_id}...")

# Test various pagination patterns with the last document ID
test_patterns = [
    f"?date_start=01.01.2024&before=4&start={last_id}",
    f"?date_start=01.01.2024&before=4&from={last_id}",
    f"?date_start=01.01.2024&before=4&after={last_id}",
    f"?date_start=01.01.2024&before=4&offset={last_id}",
    f"?date_start=01.01.2024&before=4&page=2",
    f"?date_start=01.01.2024&before=4&PAGEN_1=2",
]

for pattern in test_patterns:
    url = f"https://vsrf.ru/documents/own/{pattern}"
    print(f"\nTesting: {pattern}")

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
    if doc_ids:
        overlap = set(doc_ids) & set(doc_ids_page1)
        print(f"  Documents: {len(doc_ids)}, Overlap: {len(overlap)}")

        if doc_ids[0] != doc_ids_page1[0]:
            print(f"  *** DIFFERENT FIRST ID: {doc_ids[0]} (was {doc_ids_page1[0]}) ***")
        elif doc_ids[-1] != doc_ids_page1[-1]:
            print(f"  *** DIFFERENT LAST ID: {doc_ids[-1]} (was {doc_ids_page1[-1]}) ***")
        else:
            print(f"  Same documents")
    else:
        print(f"  No documents found")

driver.quit()
