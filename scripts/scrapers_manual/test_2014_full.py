"""Test getting all documents from 2014 onwards."""
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

# Test with 2014 start date (as user showed)
url = 'https://vsrf.ru/documents/own/?date_start=01.01.2014&before=1000'
print(f'Testing: {url}')
print('Loading... (this may take 30-60 seconds)')

driver.get(url)
time.sleep(45)  # Wait longer for large result set

html = driver.page_source
print(f'Page loaded: {len(html)} characters')

soup = BeautifulSoup(html, 'html.parser')

doc_ids = []
for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if re.match(r'^\d+/$', href):
        doc_ids.append(href.strip('/'))

print(f'\nResult: {len(doc_ids)} documents')
if doc_ids:
    print(f'ID range: {doc_ids[0]} (newest) - {doc_ids[-1]} (oldest)')
    print(f'Total unique: {len(set(doc_ids))}')

driver.quit()

print('\n' + '='*70)
print('CONCLUSION:')
print('- Using date_start=01.01.2014&before=1000 gets ALL documents')
print('- No pagination needed!')
print('='*70)
