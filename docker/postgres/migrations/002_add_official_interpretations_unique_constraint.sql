-- Migration: Add unique constraint to official_interpretations table
-- Date: 2026-02-04
-- Description: Add unique constraint on (country_id, agency_id, document_number, document_date)
--              to support ON CONFLICT upsert operations in batch imports

-- ============================================================================
-- UNIQUE CONSTRAINT FOR OFFICIAL INTERPRETATIONS
-- ============================================================================

-- Add unique constraint for upsert operations
-- This combination should uniquely identify a document:
-- - country_id: Russia vs other countries
-- - agency_id: FNS, Minfin, Rostrud, etc.
-- - document_number: The official document number
-- - document_date: The date of the document

-- First, check for and remove any existing duplicates
DELETE FROM official_interpretations a
WHERE EXISTS (
    SELECT 1
    FROM official_interpretations b
    WHERE a.country_id = b.country_id
      AND a.agency_id = b.agency_id
      AND COALESCE(a.document_number, '') = COALESCE(b.document_number, '')
      AND a.document_date = b.document_date
      AND a.id < b.id
);

-- Now add the unique constraint
ALTER TABLE official_interpretations
ADD CONSTRAINT official_interpretations_unique_doc
UNIQUE (country_id, agency_id, document_number, document_date);

-- Create index for the unique constraint (PostgreSQL creates this automatically)
-- but we're being explicit about it for documentation purposes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_official_interpretations_unique_doc
ON official_interpretations (country_id, agency_id, document_number, document_date);
