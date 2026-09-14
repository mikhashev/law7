"""
Debug vsrf.ru AJAX content loading with explicit waits.
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

url = "https://vsrf.ru/documents/own/?category=resolutions_plenum_supreme_court_russian&year=2025"

# Setup Chrome
options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)

print(f"Loading URL: {url}")
driver.get(url)

wait = WebDriverWait(driver, 30)

# Wait for page to load initially
print("Waiting for initial page load...")
time.sleep(5)

# Check multiple times for content
for i in range(1, 7):
    print(f"\n=== Check {i} (after {i*5} seconds) ===")

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    # Find all links
    all_links = soup.find_all("a", href=True)
    print(f"Total links: {len(all_links)}")

    # Look for numeric links
    numeric_links = []
    for link in all_links:
        href = link.get("href", "")
        if re.match(r'^/\d+/$', href) or re.match(r'^\d+/$', href):
            numeric_links.append((href, link.get_text(strip=True)))

    print(f"Numeric links found: {len(numeric_links)}")

    if numeric_links:
        print("Sample numeric links:")
        for href, text in numeric_links[:5]:
            print(f"  {href} -> {text[:80]}")

    # Look for common Bitrix/AJAX container classes
    containers = soup.find_all("div", class_=re.compile(r"documents|items|list|content", re.I))
    print(f"Container divs: {len(containers)}")

    # Check for loading indicators
    loading = soup.find_all(class_=re.compile(r"loading|ajax", re.I))
    print(f"Loading elements: {len(loading)}")

    if len(numeric_links) > 10:
        print(f"\n*** SUCCESS: Found {len(numeric_links)} numeric links! ***")
        break

    time.sleep(5)

# Final check with JavaScript execution
print("\n=== Checking for AJAX-loaded content ===")
# Try to scroll to trigger lazy loading
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(3)

# Check again
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

all_links = soup.find_all("a", href=True)
numeric_links = []
for link in all_links:
    href = link.get("href", "")
    if re.match(r'^/\d+/$', href) or re.match(r'^\d+/$', href):
        numeric_links.append((href, link.get_text(strip=True)))

print(f"Final numeric links found: {len(numeric_links)}")

if numeric_links:
    print("\nAll numeric links:")
    for href, text in numeric_links:
        print(f"  {href} -> {text[:100]}")
else:
    print("\nNo numeric links found. Dumping page structure...")
    # Look for any divs that might contain document lists
    for div in soup.find_all("div", limit=20):
        classes = " ".join(div.get("class", []))
        if any(keyword in classes.lower() for keyword in ["document", "item", "list", "content"]):
            print(f"Found container: class='{classes}'")
            links_in_div = div.find_all("a", href=True)
            print(f"  Links inside: {len(links_in_div)}")

# Save final HTML
with open("vsrf_ajax_debug.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
print("\nSaved HTML to vsrf_ajax_debug.html")

driver.quit()
