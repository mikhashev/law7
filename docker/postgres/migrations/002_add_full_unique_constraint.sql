-- Migration: Add full unique constraint for article_number_reference
-- This adds a full unique constraint that works with ON CONFLICT
-- The partial unique indexes are kept for additional data integrity

-- Start transaction
BEGIN;

-- Create a full unique constraint on all three columns
-- This can be used with ON CONFLICT DO NOTHING
CREATE UNIQUE INDEX article_number_reference_full_unique
ON article_number_reference(code_id, article_number_source, article_number_consultant);

-- Keep the partial indexes for additional data integrity checks
-- (they should already exist from migration 001)

COMMIT;

-- Verification query
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'article_number_reference'
ORDER BY indexname;
