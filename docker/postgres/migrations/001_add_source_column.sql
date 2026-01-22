-- Migration 001: Add source column to track data origin
-- This tracks which parser/source (kremlin.ru, government.ru, pravo.gov.ru) was used
-- for each consolidated code and article version

-- Add source column to consolidated_codes
ALTER TABLE consolidated_codes
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

-- Add source column to code_article_versions
ALTER TABLE code_article_versions
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

-- Add comment for documentation
COMMENT ON COLUMN consolidated_codes.source IS 'Data source: kremlin.ru, government.ru, pravo.gov.ru, etc.';
COMMENT ON COLUMN code_article_versions.source IS 'Data source: kremlin.ru, government.ru, pravo.gov.ru, etc.';

-- Create index for source queries
CREATE INDEX IF NOT EXISTS idx_consolidated_codes_source ON consolidated_codes(source);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_source ON code_article_versions(source);
