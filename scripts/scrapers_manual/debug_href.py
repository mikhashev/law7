"""Debug href values from vsrf.ru to understand filtering."""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

url = "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025"

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)

driver.get(url)
time.sleep(10)  # Wait for AJAX

html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

all_links = soup.find_all("a", href=True)
print(f"Total links: {len(all_links)}\n")

# Show first 50 href values
print("First 50 href values:")
for i, link in enumerate(all_links[:50], 1):
    href = link.get("href", "")
    print(f"  {i}. href='{href}'")

# Check for numeric pattern
print("\n\nChecking for numeric pattern r'^\d+/$':")
numeric_count = 0
for link in all_links:
    href = link.get("href", "")
    if re.match(r'^\d+/$', href):
        numeric_count += 1
        text = link.get_text(strip=True)
        print(f"  Match: href='{href}' -> text length={len(text)}")

print(f"\nTotal numeric links found: {numeric_count}")

# Check what patterns match
print("\n\nPattern tests:")
test_hrefs = ["35296/", "35295/", "/35294/", "/documents/own/35293/", "#", "/"]
pattern = r'^\d+/$'
for test_href in test_hrefs:
    matches = bool(re.match(pattern, test_href))
    print(f"  '{test_href}' matches pattern: {matches}")

driver.quit()
