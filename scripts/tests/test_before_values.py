"""Test different &before= values to find pagination pattern."""
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

# Test different before values
before_values = [None, 1, 2, 3, 5, 10, 50]

results = []
for before in before_values:
    if before is None:
        url = "https://vsrf.ru/documents/own/?year=2025"
        label = "default"
    else:
        url = f"https://vsrf.ru/documents/own/?year=2025&before={before}"
        label = f"before={before}"

    driver.get(url)
    time.sleep(10)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    numeric_links = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            numeric_links.append(href.strip('/'))

    results.append((label, len(numeric_links), numeric_links))
    print(f"{label:15} -> {len(numeric_links):3} documents (ID range: {numeric_links[0] if numeric_links else 'N/A'} - {numeric_links[-1] if numeric_links else 'N/A'})")

driver.quit()

print("\n=== Summary ===")
print("&before= affects how many documents are loaded per page")
print("Higher values may load more documents or enable infinite scroll")
