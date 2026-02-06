"""
Test vsrf.ru pagination with &before= parameter.
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

# Test different pagination patterns
urls = [
    "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025",
    "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025&before=2",
    "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025&PAGEN_1=2",
]

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)

for i, url in enumerate(urls, 1):
    print(f"\n{'='*60}")
    print(f"Test {i}: {url}")
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
            numeric_links.append(href)

    print(f"Total links: {len(all_links)}")
    print(f"Numeric links found: {len(numeric_links)}")

    if numeric_links:
        print(f"Sample IDs: {numeric_links[:5]}")

driver.quit()

print("\n" + "="*60)
print("CONCLUSION:")
print("- If &before=2 shows different results, we should add pagination")
print("- If all pages show same results, vsrf.ru uses infinite scroll instead")
