"""Test large before values to get ALL documents."""
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
driver.set_page_load_timeout(120)  # Longer timeout for large queries

# Test with very large before value
test_cases = [
    ('?date_start=01.01.2024&before=10', 'before=10'),
    ('?date_start=01.01.2024&before=100', 'before=100'),
    ('?date_start=01.01.2024&before=500', 'before=500'),
    ('?date_start=01.01.2024&before=1000', 'before=1000'),
    ('?date_start=01.01.2020&before=1000', 'before=1000 (year 2020)'),
]

print('Testing large before= values to get ALL documents')
print('='*70)

for params, label in test_cases:
    url = f'https://vsrf.ru/documents/own/{params}'
    print(f'{label}:')
    print(f'  URL: {url}')

    try:
        driver.get(url)
        time.sleep(20)  # Longer wait for large results

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        doc_ids = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if re.match(r'^\d+/$', href):
                doc_ids.append(href.strip('/'))

        print(f'  Result: {len(doc_ids)} documents')
        if doc_ids:
            print(f'  ID range: {doc_ids[0]} - {doc_ids[-1]}')
            print(f'  Date span: {doc_ids[0]} (newest) to {doc_ids[-1]} (oldest)')
        print()

    except Exception as e:
        print(f'  ERROR: {e}')
        print()

driver.quit()

print('='*70)
print('CONCLUSION: If before=1000 returns all docs, use that for imports!')
