/**
 * Consolidated Code Models for Law7 MCP Server
 * Type definitions for consolidated Russian legal codes
 */

/**
 * Consolidated code metadata
 * Represents a legal code like Civil Code, Criminal Code, etc.
 */
export interface ConsolidatedCode {
  id: string;
  code: string; // 'GK_RF', 'TK_RF', 'UK_RF', etc.
  name: string; // Full name in Russian
  short_name: string | null; // Short name (ГК РФ, ТК РФ)
  description: string | null;

  // Original publication info
  original_eo_number: string | null; // Original law number
  original_date: Date | null; // Original publication date
  official_url: string | null; // Link to official publication

  // Consolidation status
  last_amended_date: Date | null; // Date of most recent amendment
  total_amendments: number; // Total amendments applied
  is_consolidated: boolean; // Whether consolidation is complete
  last_consolidated_at: Date | null; // When last consolidation ran

  created_at: Date;
  updated_at: Date;
}

/**
 * Code article version (historical snapshot)
 * Represents a specific version of an article at a point in time
 */
export interface CodeArticleVersion {
  id: string;
  code_id: string; // 'GK_RF', 'TK_RF', etc.
  article_number: string; // '123', '124', etc.
  version_date: Date; // Effective date of this version
  article_text: string; // Full article text
  article_title: string | null; // Article title/heading

  // Amendment that created this version
  amendment_eo_number: string | null; // Source amendment document
  amendment_date: Date | null; // Date of amendment

  // Status tracking
  is_current: boolean; // Whether this is the current version
  is_repealed: boolean; // Whether article is repealed
  repealed_date: Date | null; // When article was repealed

  // Change detection
  text_hash: string | null; // Hash of article text for comparison

  created_at: Date;
}

/**
 * Amendment application record
 * Audit log for consolidation process
 */
export interface AmendmentApplication {
  id: string;
  amendment_eo_number: string; // The amendment document
  code_id: string; // Code being amended

  // What was changed
  articles_affected: string[] | null; // ['123', '456']
  articles_added: string[] | null; // Articles that were added
  articles_modified: string[] | null; // Articles that were modified
  articles_repealed: string[] | null; // Articles that were repealed

  // Change metadata
  amendment_type: string | null; // 'addition', 'modification', 'repeal', 'mixed'
  amendment_date: Date | null; // When amendment takes effect

  // Processing status
  status: string; // 'pending', 'applied', 'failed', 'conflict'
  error_message: string | null; // Error details if failed
  applied_at: Date | null; // When application was processed

  created_at: Date;
}

/**
 * Code article with related info
 */
export interface ArticleWithVersion extends CodeArticleVersion {
  code?: ConsolidatedCode | null;
}

/**
 * Amendment chain for an article
 * Shows the history of changes to an article
 */
export interface AmendmentChain {
  article_number: string;
  code_id: string;
  versions: CodeArticleVersion[];
  current_version: CodeArticleVersion | null;
}

/**
 * Code structure hierarchy
 * Represents the hierarchical structure of a legal code
 */
export interface CodeStructure {
  code: ConsolidatedCode;
  articles: CodeArticleVersion[];
  total_articles: number;
  current_articles: number;
  repealed_articles: number;
}

/**
 * Query parameters for code articles
 */
export interface ArticleQuery {
  code_id: string;
  article_number?: string;
  is_current?: boolean;
  is_repealed?: boolean;
  version_date?: string; // Query article as of specific date
  limit?: number;
  offset?: number;
}

/**
 * Consolidation result
 */
export interface ConsolidationResult {
  code_id: string;
  status: string;
  amendments_processed: number;
  articles_updated: number;
  snapshots_saved: number;
}

/**
 * Amendment application result
 */
export interface AmendmentApplicationResult {
  amendment_eo_number: string;
  code_id: string;
  status: 'pending' | 'applied' | 'failed' | 'conflict';
  articles_affected: number;
  error_message?: string;
}
