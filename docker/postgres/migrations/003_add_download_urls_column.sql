-- Migration: Add download_urls column to official_interpretations table
-- Date: 2026-02-04
-- Description: Store PDF/DOCX download links for documents that need content parsing

-- ============================================================================
-- ADD DOWNLOAD_URLS COLUMN
-- ============================================================================

-- Add JSONB column for download URLs (PDF, DOCX, etc.)
ALTER TABLE official_interpretations
ADD COLUMN IF NOT EXISTS download_urls JSONB DEFAULT '[]'::jsonb;

-- Add comment for documentation
COMMENT ON COLUMN official_interpretations.download_urls IS
'Download URLs for document files (PDF, DOCX, etc.) in format: {"pdf": ["url1", ...], "docx": ["url1", ...]}';
