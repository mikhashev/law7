-- Migration 001: Add Phase 7 multi-country support columns
-- This migration adds the required columns for Phase 7A country modules architecture

-- ============================================================
-- Add missing columns to 'countries' table
-- ============================================================

-- Legal system type (civil_law, common_law, mixed)
ALTER TABLE countries
ADD COLUMN IF NOT EXISTS legal_system_type VARCHAR(50);

-- Federal structure indicator (for federal vs unitary states)
ALTER TABLE countries
ADD COLUMN IF NOT EXISTS federal_structure BOOLEAN DEFAULT true;

-- Official languages array
ALTER TABLE countries
ADD COLUMN IF NOT EXISTS official_languages VARCHAR(100)[];

-- Data sources JSONB (stores API endpoints, official portals, etc.)
ALTER TABLE countries
ADD COLUMN IF NOT EXISTS data_sources JSONB DEFAULT '{}'::jsonb;

-- Scraper configuration JSONB (country-specific scraper settings)
ALTER TABLE countries
ADD COLUMN IF NOT EXISTS scraper_config JSONB DEFAULT '{}'::jsonb;

-- Parser configuration JSONB (country-specific parser settings)
ALTER TABLE countries
ADD COLUMN IF NOT EXISTS parser_config JSONB DEFAULT '{}'::jsonb;

-- ============================================================
-- Add missing columns to 'documents' table
-- ============================================================

-- Jurisdiction level (federal, regional, municipal, state, etc.)
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS jurisdiction_level VARCHAR(20);

-- Jurisdiction ID (for federal systems: region code, state code, etc.)
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(100);

-- ============================================================
-- Create indexes for Phase 7 queries
-- ============================================================

-- Index for jurisdiction-based queries
CREATE INDEX IF NOT EXISTS idx_documents_jurisdiction
ON documents(jurisdiction_level, jurisdiction_id);

-- Index for country + jurisdiction queries (regional documents)
CREATE INDEX IF NOT EXISTS idx_documents_country_jurisdiction
ON documents(country_id, jurisdiction_level);

-- ============================================================
-- Update existing Russia entry with default values
-- ============================================================

-- Update Russia record with Phase 7 configuration
UPDATE countries
SET
    legal_system_type = 'civil_law',
    federal_structure = true,
    official_languages = ARRAY['ru'],
    data_sources = '{
        "federal": "http://pravo.gov.ru",
        "supreme_court": "https://vsrf.ru",
        "constitutional_court": "http://www.ksrf.ru",
        "minfin": "https://minfin.gov.ru",
        "rostrud": "https://rostrud.gov.ru"
    }'::jsonb,
    scraper_config = '{
        "api_base_url": "http://publication.pravo.gov.ru/api",
        "timeout": 30,
        "max_retries": 3
    }'::jsonb,
    parser_config = '{
        "ocr_enabled": true,
        "ocr_language": "rus+eng",
        "encoding": "windows-1251"
    }'::jsonb
WHERE code = 'RU';

-- ============================================================
-- Set default jurisdiction_level for existing federal documents
-- ============================================================

-- Mark existing documents as federal (they're all from pravo.gov.ru)
UPDATE documents
SET jurisdiction_level = 'federal'
WHERE jurisdiction_level IS NULL;

-- ============================================================
-- Verification queries (for manual testing)
-- ============================================================

-- Check countries table after migration:
-- SELECT * FROM countries WHERE code = 'RU';

-- Check documents table after migration:
-- SELECT COUNT(*) as total_docs,
--        COUNT(*) FILTER (WHERE jurisdiction_level = 'federal') as federal_docs,
--        COUNT(*) FILTER (WHERE jurisdiction_level IS NOT NULL) as with_jurisdiction
-- FROM documents;

-- Check new indexes:
-- \d countries
-- \d documents
