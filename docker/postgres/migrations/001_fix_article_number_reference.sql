-- Migration: Fix article_number_reference table for missing articles support
-- This migration:
-- 1. Drops the old unique constraint
-- 2. Makes article_number_source nullable (to track missing articles)
-- 3. Creates separate partial unique indexes for matched and missing articles

-- Start transaction
BEGIN;

-- Drop the old unique CONSTRAINT (not just index)
ALTER TABLE article_number_reference
DROP CONSTRAINT IF EXISTS article_number_reference_code_id_article_number_source_arti_key;

-- Make article_number_source nullable (to track missing consultant articles)
ALTER TABLE article_number_reference
ALTER COLUMN article_number_source DROP NOT NULL;

-- Create partial unique index for matched articles (article_number_source IS NOT NULL)
CREATE UNIQUE INDEX idx_article_number_reference_matched_unique
ON article_number_reference(code_id, article_number_source, article_number_consultant)
WHERE article_number_source IS NOT NULL;

-- Create partial unique index for missing articles (article_number_source IS NULL)
CREATE UNIQUE INDEX idx_article_number_reference_missing_unique
ON article_number_reference(code_id, article_number_consultant)
WHERE article_number_source IS NULL;

COMMIT;

-- Verification query
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'article_number_reference'
ORDER BY indexname;
