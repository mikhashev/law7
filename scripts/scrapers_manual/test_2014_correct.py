"""Test getting all documents from 2014 with correct parameters."""
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
driver.set_page_load_timeout(120)

# Test with category parameter (as we use in scraper)
test_cases = [
    ('?date_start=01.01.2014&before=1000', '2014 without category'),
    ('?category=resolutions_plenum_supreme_court_russian&date_start=01.01.2014&before=1000', '2014 WITH category'),
    ('?category=resolutions_plenum_supreme_court_russian&date_start=01.01.2015&before=1000', '2015 with category'),
    ('?category=resolutions_plenum_supreme_court_russian&date_start=01.01.2018&before=1000', '2018 with category'),
]

print('='*70)
print('Testing different year ranges with category parameter')
print('='*70)

for params, desc in test_cases:
    url = f'https://vsrf.ru/documents/own/{params}'
    print(f'\n{desc}:')
    print(f'  {url}')

    driver.get(url)
    time.sleep(30)

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

driver.quit()

print('\n' + '='*70)
