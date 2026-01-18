# Pravo.gov.ru API Testing Instructions

## VPN Troubleshooting

If you have an active VPN, it may be causing connection timeouts with the Russian government API. Try these steps:

### Option 1: Temporarily Disable VPN
1. Disconnect your VPN
2. Run the API explorer
3. Reconnect VPN after testing

### Option 2: Configure VPN to Exclude pravo.gov.ru
If your VPN supports split tunneling, add `publication.pravo.gov.ru` to the exclude list.

### Option 3: Use Russian VPN Server
Some Russian government APIs block international traffic. Try connecting to a VPN server in Russia.

---

## Manual API Testing

### 1. Test API Endpoints in Browser

Open these URLs in your browser:

- **Public Blocks**: http://publication.pravo.gov.ru/api/PublicBlocks/
- **Categories**: http://publication.pravo.gov.ru/api/Categories
- **Document Types**: http://publication.pravo.gov.ru/api/DocumentTypes
- **Signatory Authorities**: http://publication.pravo.gov.ru/api/SignatoryAuthorities

### 2. Test Document Search

```
http://publication.pravo.gov.ru/api/Documents?pageSize=10
```

With search term:
```
http://publication.pravo.gov.ru/api/Documents?pageSize=10&search=труд
```

By date range:
```
http://publication.pravo.gov.ru/api/Documents?pageSize=10&startDate=2024-01-01&endDate=2024-01-31
```

### 3. Test Document Detail

Replace `0001202401170001` with any eoNumber you find:
```
http://publication.pravo.gov.ru/api/Document/0001202401170001
```

### 4. Using curl

```bash
# Test basic endpoint
curl -v "http://publication.pravo.gov.ru/api/PublicBlocks/"

# Test document search
curl -v "http://publication.pravo.gov.ru/api/Documents?pageSize=10"

# Test document detail
curl -v "http://publication.pravo.gov.ru/api/Document/0001202401170001"
```

### 5. Using PowerShell

```powershell
# Test basic endpoint
Invoke-WebRequest -Uri "http://publication.pravo.gov.ru/api/PublicBlocks/" | Select-Object -ExpandProperty Content

# Test document search
Invoke-WebRequest -Uri "http://publication.pravo.gov.ru/api/Documents?pageSize=10" | Select-Object -ExpandProperty Content
```

---

## After Manual Testing

If you successfully access the API:

1. **Save sample responses** to `scripts/samples/` directory:
   - Copy JSON response from browser
   - Save as `public_blocks_sample.json`
   - Save as `documents_sample.json`
   - etc.

2. **Note your observations**:
   - What fields are present?
   - What data types are used?
   - How does pagination work?
   - Are there rate limits?

3. **Share findings** so we can:
   - Update the database schema
   - Build the parser accordingly
   - Continue with implementation

---

## Python Script Testing (After VPN Fix)

Once VPN is configured, run:

```bash
# From law7 directory
poetry run python scripts/explorer/api_explorer.py
```

Expected output:
- Creates sample JSON files in `scripts/samples/`
- Creates analysis document in `scripts/docs/pravo_api_analysis.md`
- Logs API structure to console
