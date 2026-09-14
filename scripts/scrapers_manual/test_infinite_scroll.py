"""
Test if vsrf.ru uses infinite scroll by scrolling down the page.
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

url = "https://vsrf.ru/documents/own/?year=2025&before=2"
print(f"Loading: {url}")
driver.get(url)
time.sleep(15)

# Count documents before scrolling
html_before = driver.page_source
soup_before = BeautifulSoup(html_before, 'html.parser')
doc_ids_before = set()
for link in soup_before.find_all("a", href=True):
    href = link.get("href", "")
    if re.match(r'^\d+/$', href):
        doc_ids_before.add(href.strip('/'))

print(f"Before scroll: {len(doc_ids_before)} documents (ID range: {min(doc_ids_before)} - {max(doc_ids_before)})")

# Scroll down to trigger infinite scroll
print("\nScrolling down...")
for i in range(5):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    # Check if new documents appeared
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    doc_ids_current = set()
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            doc_ids_current.add(href.strip('/'))

    new_docs = doc_ids_current - doc_ids_before
    print(f"  After scroll {i+1}: {len(doc_ids_current)} documents ({len(new_docs)} new)")

    if new_docs:
        print(f"    New document IDs: {sorted(new_docs)[:5]}...")
        doc_ids_before = doc_ids_current
    else:
        print(f"    No new documents loaded")

print(f"\nFinal: {len(doc_ids_current)} documents")
print(f"ID range: {min(doc_ids_current)} - {max(doc_ids_current)}")

driver.quit()
