# Phase 7C Browser DevTools Analysis Guide

**Purpose:** This guide walks through analyzing the three Phase 7C target portals using browser DevTools to understand their structure before implementing scrapers.

---

## How to Use This Guide

**What you'll need:**
- Chrome/Edge/Firefox browser with DevTools (F12)
- This guide open for reference
- A text editor to record findings

**For each portal:**
1. Open the portal URL
2. Open DevTools (F12)
3. Follow the analysis steps below
4. Record your findings in the "Findings Template" section
5. Take screenshots of key elements (network requests, HTML structure)

---

## Portal 1: Supreme Court (vsrf.gov.ru)

### Target URLs

- **Main documents page:** https://vsrf.gov.ru/documents/own/
- **Practice reviews:** https://vsrf.gov.ru/documents/practice/

### Analysis Steps

#### Step 1: Check for API Calls

1. Open DevTools (F12) → **Network** tab
2. Filter by **XHR/Fetch** (to see API calls)
3. Refresh the page (Ctrl+R)
4. **Look for:**
   - Any JSON responses in the Network tab
   - API endpoints (e.g., `/api/...`, `.json` URLs)
   - Request headers (authentication tokens)
   - Request payload (POST data)

**Record findings:**
- [ ] API endpoints found: _________________
- [ ] Authentication required: Yes/No
- [ ] Rate limiting visible: Yes/No

#### Step 2: Analyze HTML Structure

1. In DevTools → **Elements** tab
2. Inspect the document listing page
3. **Look for:**
   - Container element holding document links
   - CSS classes used for document items
   - Data attributes (e.g., `data-id`, `data-date`)
   - Pagination elements (next/prev buttons, page numbers)

**Example to look for:**
```html
<!-- What does a document link look like? -->
<a href="/documents/own/8386/" class="doc-link">
  Постановление Пленума № 1
  <span class="date">25.11.2024</span>
</a>
```

**Record findings:**
- [ ] Document container selector: _________________
- [ ] Document link pattern: _________________
- [ ] Pagination selector: _________________

#### Step 3: Analyze Individual Document Page

1. Click on a document link (e.g., a plenary resolution)
2. Inspect the document detail page
3. **Look for:**
   - Document title location and structure
   - Document number and date
   - Full text content location
   - PDF download link (if any)
   - Related articles or legal issues

**Record findings:**
- [ ] Title selector: _________________
- [ ] Full text selector: _________________
- [ ] PDF download link pattern: _________________
- [ ] Metadata (date, number) selectors: _________________

#### Step 4: Test Search/Filter Functionality

1. Look for search box or filters
2. Try searching for a keyword (e.g., "труд")
3. Watch Network tab for XHR requests
4. **Look for:**
   - Search API endpoint
   - Filter parameters
   - Response format

**Record findings:**
- [ ] Search URL pattern: _________________
- [ ] Filter parameters: _________________

---

## Portal 2: Ministry of Finance (minfin.gov.ru)

### Target URL

- **Documents section:** https://minfin.gov.ru/ru/document/

### Analysis Steps

#### Step 1: Check for API Calls

1. Open DevTools → **Network** tab
2. Filter by **XHR/Fetch**
3. Scroll down the page (lazy loading may trigger requests)
4. **Look for:**
   - API endpoints returning document lists
   - Filter/sort API calls
   - Pagination requests

**Record findings:**
- [ ] API endpoints found: _________________
- [ ] Response format: JSON/HTML/Other

#### Step 2: Analyze Filter System

1. Locate the filter section (left sidebar or top bar)
2. Try changing filters:
   - Document type: select "Письмо Минфина России"
   - Topic: select "Налоговая политика"
   - Date range: select a range
3. Watch Network tab for each filter change
4. **Look for:**
   - Filter API endpoint
   - Filter parameter names
   - Response structure

**Record findings:**
- [ ] Filter URL pattern: _________________
- [ ] Filter parameter names: _________________
- [ ] Do filters trigger page reload or XHR: _________________

#### Step 3: Analyze Document Listing

1. Inspect a document card/item in the list
2. **Look for:**
   - Document card HTML structure
   - Link to detail page
   - Metadata display (date, number, tags)
   - "Important" markers (if any)

**Example structure:**
```html
<div class="document-card" data-id="12345">
  <div class="type">Письмо</div>
  <div class="date">15.01.2025</div>
  <div class="number">03-04-07/12345</div>
  <div class="title">О применении НК РФ...</div>
  <a href="/ru/document/12345/">Подробнее</a>
</div>
```

**Record findings:**
- [ ] Document card selector: _________________
- [ ] Link pattern to detail page: _________________

#### Step 4: Analyze Letter Detail Page

1. Click on a ministry letter
2. Inspect the letter content
3. **Look for:**
   - Question/answer structure (if present)
   - Full text content
   - Related laws or articles
   - PDF/DOC download link

**Record findings:**
- [ ] Question/answer structure: Yes/No
- [ ] Content selector: _________________
- [ ] Download link pattern: _________________

#### Step 5: Test Document Number Search

1. Look for search by document number
2. Enter a known number format (e.g., "03-04-07/12345")
3. Watch Network tab
4. **Look for:**
   - Search API endpoint
   - Request/response format

---

## Portal 3: Moscow City Duma (duma.mos.ru)

### Target URL

- **Documentation section:** https://duma.mos.ru/ru/documentation/

### Analysis Steps

#### Step 1: Check for API Calls

1. Open DevTools → **Network** tab
2. Filter by **XHR/Fetch**
3. Refresh the page
4. **Look for:**
   - API endpoints for document listings
   - Regional API patterns
   - Authentication (if any)

**Record findings:**
- [ ] API endpoints found: _________________
- [ ] Authentication required: Yes/No

#### Step 2: Analyze Document Categories

1. Look for document categories/filters
2. **Look for:**
   - KoAP section (if present)
   - Regional laws section
   - Category navigation

**Record findings:**
- [ ] KoAP section URL: _________________
- [ ] Category structure: _________________

#### Step 3: Analyze KoAP Structure

1. Navigate to KoAP documents
2. **Look for:**
   - Table of contents (chapters, articles)
   - Individual article links
   - Amendment tracking
   - Consolidation status

**Record findings:**
- [ ] KoAP table of contents selector: _________________
- [ ] Article link pattern: _________________
- [ ] Article content selector: _________________

#### Step 4: Test Search Functionality

1. Use site search (if present)
2. Search for "Кодекс об административных правонарушениях"
3. **Look for:**
   - Search API endpoint
   - Response format

**Record findings:**
- [ ] Search URL pattern: _________________

---

## Findings Template

For each portal, record your findings below:

### Portal: Supreme Court (vsrf.gov.ru)

**API Available:**
- [ ] Yes - JSON API found
- [ ] No - HTML scraping required

**Document Listing:**
- URL pattern for listing: _________________
- Pagination method: _________________
- Document selector: _________________

**Document Detail:**
- URL pattern for individual documents: _________________
- Title selector: _________________
- Content selector: _________________
- PDF download: Yes/No, pattern: _________________

**Search/Filters:**
- Search endpoint: _________________
- Filter parameters: _________________

**Notes:**
_______________
_______________

---

### Portal: Ministry of Finance (minfin.gov.ru)

**API Available:**
- [ ] Yes - JSON API found
- [ ] No - HTML scraping required

**Document Listing:**
- URL pattern for listing: _________________
- Pagination method: _________________
- Document card selector: _________________

**Document Detail:**
- URL pattern: _________________
- Question/answer structure: Yes/No
- Content selector: _________________
- Download link pattern: _________________

**Filters:**
- Filter endpoint: _________________
- Filter parameters: _________________

**Notes:**
_______________
_______________

---

### Portal: Moscow Duma (duma.mos.ru)

**API Available:**
- [ ] Yes - JSON API found
- [ ] No - HTML scraping required

**KoAP Section:**
- KoAP URL: _________________
- Chapter listing selector: _________________
- Article link pattern: _________________

**Article Detail:**
- Article URL pattern: _________________
- Content selector: _________________
- Amendment tracking: Yes/No

**Notes:**
_______________
_______________

---

## Implementation Guidance

Based on your findings, we can determine:

### If API Available:
```python
# Use requests/aiohttp to call API
async def fetch_updates(self, since: date) -> List[RawDocument]:
    params = {"since": since.isoformat()}
    response = await self.session.get(f"{self.base_url}/api/documents", params=params)
    data = response.json()
    return [self._parse_doc(doc) for doc in data["items"]]
```

### If HTML Scraping Required:
```python
# Use BeautifulSoup to parse HTML
from bs4 import BeautifulSoup

async def fetch_updates(self, since: date) -> List[RawDocument]:
    response = await self.session.get(f"{self.base_url}/documents")
    soup = BeautifulSoup(response.text, "html.parser")
    docs = soup.select(".document-card")  # CSS selector from your analysis
    return [self._parse_html_doc(doc) for doc in docs]
```

---

## Next Steps After Analysis

1. **Share findings:** Provide the filled template above
2. **Choose scraper type:** API-based vs HTML-based
3. **Implement proof of concept:** Start with one portal
4. **Validate pattern:** Test with actual data
5. **Expand to other portals:** Apply validated pattern

---

## Screenshots to Take

For each portal, capture:

1. **Network tab:** Show XHR/Fetch requests (if any)
2. **Elements tab:** Show document listing HTML structure
3. **Document detail:** Show individual document page structure
4. **Filters:** Show filter UI and any triggered requests

**Save screenshots as:**
- `screenshots/{portal}_network.png`
- `screenshots/{portal}_html_structure.png`
- `screenshots/{portal}_document_detail.png`
