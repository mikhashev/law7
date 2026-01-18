# Pravo.gov.ru API Analysis

**Generated:** 2026-01-19
**Base URL:** `http://publication.pravo.gov.ru/api` (Note: HTTP, not HTTPS)

---

## API Endpoints Summary

| Endpoint | Method | Status | Description |
|----------|--------|--------|-------------|
| `/PublicBlocks/` | GET | OK | Get publication blocks (categories of legal documents) |
| `/Categories` | GET | OK | Get categories of signing authorities |
| `/DocumentTypes` | GET | OK | Get document types |
| `/SignatoryAuthorities` | GET | OK | Get signing authorities (organizations) |
| `/Documents` | GET | OK | Search/get documents with pagination |
| `/Document?eoNumber={id}` | GET | OK | Get extended document detail by eoNumber |
| `/BlockStatistics/daily` | GET | OK | Get daily document count statistics by block |
| `/BlockStatistics/weekly` | GET | OK | Get weekly document count statistics by block |
| `/BlockStatistics/monthly` | GET | OK | Get monthly document count statistics by block |

---

## Data Structure Analysis

### 1. Public Blocks (Publication Blocks)

Represents categories of legal documents:

```json
{
  "id": "uuid",
  "shortName": "Президент Российской Федерации",
  "menuName": "Президент Российской Федерации",
  "code": "president",
  "description": "Законы Российской Федерации...",
  "weight": 1000,
  "isBlocked": false,
  "hasChildren": false,
  "isAgenciesOfStateAuthorities": false,
  "name": "Президент Российской Федерации"
}
```

**Available Blocks:**
- `president` - President of Russian Federation
- `assembly` - Federal Assembly
- `government` - Government of Russian Federation
- `federal_authorities` - Federal executive authorities
- `court` - Constitutional Court
- `subjects` - Regional authorities
- `international` - International treaties

### 2. Documents Search Response

```json
{
  "items": [
    {
      "eoNumber": "0001202601170001",
      "id": "uuid",
      "title": "Распоряжение Правительства...",
      "name": "О присвоении классных чинов...",
      "complexName": "Распоряжение Правительства... от 17.01.2026 № 28-р",
      "number": "28-р",
      "documentDate": "2026-01-17T00:00:00",
      "publishDateShort": "2026-01-17T00:00:00",
      "viewDate": "17.01.2026",
      "pagesCount": 22,
      "pdfFileLength": 3692632,
      "hasSvg": false,
      "signatoryAuthorityId": "uuid",
      "documentTypeId": "uuid",
      "jdRegNumber": null,
      "jdRegDate": null
    }
  ],
  "itemsTotalCount": 1593675,
  "itemsPerPage": 10,
  "currentPage": 1,
  "pagesTotalCount": 159368
}
```

**Key Document Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `eoNumber` | string | YES | Unique document identifier |
| `id` | string | YES | UUID |
| `title` | string | YES | Full title with HTML formatting |
| `name` | string | YES | Short name/description |
| `complexName` | string | YES | Full name with date and number |
| `number` | string | YES | Document number |
| `documentDate` | datetime | YES | Date of document adoption |
| `publishDateShort` | datetime | YES | Date of publication |
| `viewDate` | string | YES | Date in DD.MM.YYYY format |
| `pagesCount` | int | YES | Number of pages |
| `pdfFileLength` | int | NO | PDF file size in bytes |
| `signatoryAuthorityId` | uuid | YES | Reference to signing authority |
| `documentTypeId` | uuid | YES | Reference to document type |
| `jdRegNumber` | string | NO | Ministry of Justice registration number |
| `jdRegDate` | datetime | NO | Ministry of Justice registration date |

### 3. Document Types

Example document types (from sample):
- Federal Laws
- Presidential Decrees
- Government Resolutions
- Court Decisions
- Regional Laws

### 4. Signatory Authorities

Organizations that issue/sign documents. Very large dataset (700KB+).

---

## Pagination

**IMPORTANT:** The `/Documents` endpoint uses `index` (NOT `page`) for pagination.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pageSize` | int | ? | Number of items per page (valid: 10, 30, 100, 200, 300, etc.) |
| `index` | int | 1 | Page number (1-indexed) |

**Response:**
```json
{
  "itemsTotalCount": 1593675,
  "itemsPerPage": 10,
  "currentPage": 1,
  "pagesTotalCount": 159368
}
```

---

## Search Parameters

Based on API documentation and testing:

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Full-text search query |
| `startDate` | date | Filter by start date (YYYY-MM-DD) |
| `endDate` | date | Filter by end date |
| `docType` | string | Filter by document type |
| `block` | string | Filter by publication block (president, government, etc.) |
| `index` | int | Page number (1-indexed) - **NOT `page`** |
| `pageSize` | int | Items per page (valid: 10, 30, 100, 200, 300, etc.) |
| `category` | string | Filter by category (with block parameter) |
| `signatoryAuthority` | string | Filter by signatory authority ID |
| `documentType` | string | Filter by document type ID |

**Note:** All parameters are optional.

---

## Document Text Access

**Document Detail Endpoint:** `/api/Document?eoNumber={eoNumber}`

This endpoint returns extended document information including:
- Document type details
- Signatory authority details
- All document fields

**Note:** The endpoint uses a query parameter (`?eoNumber=`), NOT a path parameter.

**Alternative:** Document text access methods:
1. PDF download: Use the document's eoNumber to construct PDF URL
2. HTML view: Document page on the website
3. Need further investigation for actual PDF/HTML download URLs

---

## Rate Limiting

- **Observation:** No rate limiting detected during testing
- **Multiple requests:** Successfully made multiple requests in quick succession
- **Timeout:** Default 30s timeout is sufficient

---

## Database Schema Recommendations

Based on the API structure, the following tables are recommended:

```sql
-- Countries (for multi-country support)
CREATE TABLE countries (
  id SERIAL PRIMARY KEY,
  code VARCHAR(2) UNIQUE NOT NULL,  -- 'ru'
  name VARCHAR(100) NOT NULL,
  native_name VARCHAR(100)  -- 'Россия'
);

-- Publication Blocks (categories)
CREATE TABLE publication_blocks (
  id UUID PRIMARY KEY,
  short_name VARCHAR(200),
  code VARCHAR(50) UNIQUE,  -- 'president', 'government'
  description TEXT,
  weight INT,
  is_blocked BOOLEAN DEFAULT FALSE
);

-- Signatory Authorities
CREATE TABLE signatory_authorities (
  id UUID PRIMARY KEY,
  name VARCHAR(500),
  code VARCHAR(100)
);

-- Document Types
CREATE TABLE document_types (
  id UUID PRIMARY KEY,
  name VARCHAR(200),
  code VARCHAR(50)
);

-- Documents (main table)
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  eo_number VARCHAR(50) UNIQUE NOT NULL,  -- Natural key
  title TEXT,
  name VARCHAR(1000),
  complex_name TEXT,
  document_number VARCHAR(100),
  document_date DATE,
  publish_date DATE,
  view_date VARCHAR(20),
  pages_count INT,
  pdf_file_size BIGINT,

  -- Foreign keys
  signatory_authority_id UUID REFERENCES signatory_authorities(id),
  document_type_id UUID REFERENCES document_types(id),
  publication_block_id UUID REFERENCES publication_blocks(id),
  country_id INTEGER REFERENCES countries(id),

  -- Ministry of Justice registration
  jd_reg_number VARCHAR(100),
  jd_reg_date DATE,

  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Document Content (separate table for full text)
CREATE TABLE document_content (
  document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  full_text TEXT,
  raw_text TEXT,
  pdf_url TEXT,
  html_url TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_documents_eo_number ON documents(eo_number);
CREATE INDEX idx_documents_document_date ON documents(document_date DESC);
CREATE INDEX idx_documents_signatory_authority ON documents(signatory_authority_id);
CREATE INDEX idx_documents_document_type ON documents(document_type_id);
CREATE INDEX idx_documents_publication_block ON documents(publication_block_id);
```

---

## Next Steps

1. **Investigate document text access:**
   - Use browser DevTools to find PDF/HTML download endpoints
   - Test PDF download URL format
   - Implement PDF parser

2. **Implement crawler:**
   - Create `pravo_api_client.py` with exponential backoff
   - Implement pagination handling
   - Add rate limiting

3. **Implement parser:**
   - PDF text extraction (pdfplumber)
   - HTML parsing fallback
   - Text cleaning for Russian language

4. **Create database schema:**
   - Update `docker/postgres/init.sql` based on findings
   - Add proper indexes

5. **Build sync pipeline:**
   - Initial sync (fetch all documents by date range)
   - Daily sync (fetch recent documents)
   - Upsert logic based on `eo_number`

---

## Sample Files

The following sample files have been saved to `scripts/samples/`:

| File | Size | Description |
|------|------|-------------|
| `public_blocks_sample.json` | 8 KB | Publication blocks (categories) |
| `categories_sample.json` | 106 B | Categories endpoint |
| `document_types_sample.json` | 5 KB | Document types |
| `signatory_authorities_sample.json` | 728 KB | Signing authorities |
| `documents_search_sample.json` | 19 KB | Document search results |

---

## Notes

1. **HTTP vs HTTPS:** API uses HTTP, not HTTPS
2. **No authentication:** Public API, no API key required
3. **UTF-8 encoding:** All text is in Russian (Cyrillic)
4. **Large dataset:** Over 1.5 million documents
5. **Daily updates:** New documents published daily
