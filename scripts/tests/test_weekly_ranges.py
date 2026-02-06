"""
Test using weekly date ranges to get ALL documents.

If the API has a 97-document limit, we can work around it by
using smaller date ranges (weekly instead of monthly).
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)

# Test Q1 2024 with weekly ranges
print("="*70)
print("Testing WEEKLY ranges for Q1 2024 (Jan-Mar)")
print("="*70)

# Start from Jan 1, 2024
start_date = datetime(2024, 1, 1)
all_doc_ids = []
total_queries = 0

# Test 12 weeks (3 months)
for week in range(12):
    week_start = start_date + timedelta(weeks=week)
    week_end = week_start + timedelta(days=6)

    # Format dates as DD.MM.YYYY
    date_start = week_start.strftime("%d.%m.%Y")
    date_end = week_end.strftime("%d.%m.%Y")

    url = f"https://vsrf.ru/documents/own/?date_start={date_start}&date_end={date_end}&before=4"
    print(f"\nWeek {week+1} ({date_start} - {date_end})")

    driver.get(url)
    time.sleep(8)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    doc_ids = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.match(r'^\d+/$', href):
            doc_ids.append(href.strip('/'))

    # Track unique IDs
    new_ids = [id for id in doc_ids if id not in all_doc_ids]
    all_doc_ids.extend(doc_ids)
    total_queries += 1

    print(f"  Documents: {len(doc_ids)} (new: {len(new_ids)}, total unique: {len(set(all_doc_ids))})")
    if doc_ids:
        print(f"  ID range: {doc_ids[0]} - {doc_ids[-1]}")

    # Stop if no new documents
    if len(doc_ids) == 0:
        print(f"  No documents found, stopping")
        break

driver.quit()

print("\n" + "="*70)
print(f"SUMMARY for Q1 2024:")
print(f"  Total queries: {total_queries}")
print(f"  Total unique documents: {len(set(all_doc_ids))}")
print(f"  Documents per query (avg): {len(set(all_doc_ids))/total_queries:.1f}")
print("="*70)
print("\nConclusion: Weekly ranges may help overcome the 97-document limit!")
