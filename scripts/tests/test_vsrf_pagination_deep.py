"""
Test vsrf.ru pagination pattern with &before= parameter.
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

base_url = "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025"

# Test multiple pages to understand the pattern
for page in range(1, 6):
    if page == 1:
        url = base_url
    else:
        url = f"{base_url}&before={page}"

    print(f"\n{'='*60}")
    print(f"Page {page}: {url}")
    print(f"{'='*60}")

    driver.get(url)
    time.sleep(10)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    # Find numeric links
    all_links = soup.find_all("a", href=True)
    numeric_links = []
    for link in all_links:
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            numeric_links.append(href.strip('/'))

    print(f"Numeric links: {len(numeric_links)}")
    if numeric_links:
        print(f"First ID: {numeric_links[0]}")
        print(f"Last ID: {numeric_links[-1]}")
        print(f"Unique IDs: {len(set(numeric_links))}")

    # Check for duplicates across pages
    if page > 1:
        overlap = set(numeric_links) & set(prev_links)
        if overlap:
            print(f"WARNING: OVERLAP with previous page: {len(overlap)} documents")
        else:
            print(f"OK: No overlap - new documents!")

    prev_links = numeric_links.copy()

driver.quit()
