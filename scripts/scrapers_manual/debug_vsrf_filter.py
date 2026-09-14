"""
Debug vsrf.ru scraper to see what links are being processed.
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

url = "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025"

# Setup Chrome
options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

driver.get(url)
time.sleep(15)

html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Find all links
all_links = soup.find_all("a", href=True)
print(f"Total links: {len(all_links)}")

# Look for numeric links (documents)
numeric_count = 0
for link in all_links:
    href = link.get("href", "")
    if re.match(r'^\d+/$', href):
        numeric_count += 1
        text = link.get_text(strip=True)
        print(f"\nLink {numeric_count}: href='{href}'")
        print(f"  Text length: {len(text)}")
        print(f"  Text (first 100 chars): {text[:100]}")

        # Check if it would pass the filter
        if not text or len(text) < 10:
            print("  WOULD BE FILTERED: text too short")
        elif text in ["Документы", "Documents", "", "/"]:
            print("  WOULD BE FILTERED: generic text")
        else:
            print("  WOULD PASS FILTER")

print(f"\nTotal numeric links found: {numeric_count}")

driver.quit()
