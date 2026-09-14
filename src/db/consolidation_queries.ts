/**
 * Consolidation Queries for Law7 MCP Server
 * Database queries for consolidated codes and article versions
 */

import { query } from './postgres.js';
import type {
  ConsolidatedCode,
  CodeArticleVersion,
  AmendmentApplication,
  CodeStructure,
  AmendmentChain,
} from '../models/ConsolidatedCode.js';

/**
 * Get all consolidated codes
 */
export async function getConsolidatedCodes(): Promise<ConsolidatedCode[]> {
  const text = `
    SELECT * FROM consolidated_codes
    ORDER BY code ASC
  `;
  return query<ConsolidatedCode>(text);
}

/**
 * Get a consolidated code by code ID
 */
export async function getConsolidatedCode(codeId: string): Promise<ConsolidatedCode | null> {
  const text = `
    SELECT * FROM consolidated_codes
    WHERE code = $1
  `;
  const results = await query<ConsolidatedCode>(text, [codeId]);
  return results[0] || null;
}

/**
 * Get code structure (all articles for a code)
 */
export async function getCodeStructure(codeId: string): Promise<CodeStructure | null> {
  // Get the code metadata
  const code = await getConsolidatedCode(codeId);
  if (!code) {
    return null;
  }

  // Get all articles for this code
  const text = `
    SELECT * FROM code_article_versions
    WHERE code_id = $1
    ORDER BY
      CASE
        WHEN article_number ~ '^[0-9]+$' THEN CAST(article_number AS INTEGER)
        ELSE 999999
      END,
      article_number
  `;
  const articles = await query<CodeArticleVersion>(text, [codeId]);

  // Calculate statistics
  const total_articles = articles.length;
  const current_articles = articles.filter(a => a.is_current).length;
  const repealed_articles = articles.filter(a => a.is_repealed).length;

  return {
    code,
    articles,
    total_articles,
    current_articles,
    repealed_articles,
  };
}

/**
 * Get current article version
 */
export async function getCurrentArticleVersion(
  codeId: string,
  articleNumber: string
): Promise<CodeArticleVersion | null> {
  const text = `
    SELECT * FROM code_article_versions
    WHERE code_id = $1
    AND article_number = $2
    AND is_current = true
    ORDER BY version_date DESC
    LIMIT 1
  `;
  const results = await query<CodeArticleVersion>(text, [codeId, articleNumber]);
  return results[0] || null;
}

/**
 * Get article version as of a specific date
 */
export async function getArticleVersionOnDate(
  codeId: string,
  articleNumber: string,
  queryDate: string
): Promise<CodeArticleVersion | null> {
  const text = `
    SELECT * FROM code_article_versions
    WHERE code_id = $1
    AND article_number = $2
    AND version_date <= $3
    ORDER BY version_date DESC
    LIMIT 1
  `;
  const results = await query<CodeArticleVersion>(text, [codeId, articleNumber, queryDate]);
  return results[0] || null;
}

/**
 * Get amendment chain for an article
 */
export async function getAmendmentChain(
  codeId: string,
  articleNumber: string
): Promise<AmendmentChain> {
  const text = `
    SELECT * FROM code_article_versions
    WHERE code_id = $1
    AND article_number = $2
    ORDER BY version_date ASC
  `;
  const versions = await query<CodeArticleVersion>(text, [codeId, articleNumber]);

  // Find current version
  const current_version = versions.find(v => v.is_current) || null;

  return {
    article_number: articleNumber,
    code_id: codeId,
    versions,
    current_version,
  };
}

/**
 * Get all articles for a code
 */
export async function getArticlesForCode(
  codeId: string,
  options: {
    isCurrent?: boolean;
    isRepealed?: boolean;
    limit?: number;
    offset?: number;
  } = {}
): Promise<CodeArticleVersion[]> {
  const { isCurrent, isRepealed, limit, offset } = options;

  let text = `
    SELECT * FROM code_article_versions
    WHERE code_id = $1
  `;

  const params: any[] = [codeId];
  let paramIndex = 2;

  if (isCurrent !== undefined) {
    text += ` AND is_current = $${paramIndex}`;
    params.push(isCurrent);
    paramIndex++;
  }

  if (isRepealed !== undefined) {
    text += ` AND is_repealed = $${paramIndex}`;
    params.push(isRepealed);
    paramIndex++;
  }

  text += `
    ORDER BY
      CASE
        WHEN article_number ~ '^[0-9]+$' THEN CAST(article_number AS INTEGER)
        ELSE 999999
      END,
      article_number
  `;

  if (limit) {
    text += ` LIMIT $${paramIndex}`;
    params.push(limit);
    paramIndex++;
  }

  if (offset) {
    text += ` OFFSET $${paramIndex}`;
    params.push(offset);
  }

  return query<CodeArticleVersion>(text, params);
}

/**
 * Get amendment applications for a code
 */
export async function getAmendmentApplications(
  codeId: string,
  status?: string
): Promise<AmendmentApplication[]> {
  let text = `
    SELECT * FROM amendment_applications
    WHERE code_id = $1
  `;

  const params: any[] = [codeId];

  if (status) {
    text += ` AND status = $2`;
    params.push(status);
  }

  text += ` ORDER BY amendment_date DESC, created_at DESC`;

  return query<AmendmentApplication>(text, params);
}

/**
 * Count amendment applications recorded for a code.
 *
 * This is the honesty check used by `get-article-version` and
 * `trace-amendment-history`: if a code has zero amendment applications, no
 * historical consolidation has ever been generated for it, so the single
 * snapshot stored per article cannot be attributed to any past date.
 */
export async function getAmendmentApplicationCount(codeId: string): Promise<number> {
  const text = `
    SELECT COUNT(*) as count
    FROM amendment_applications
    WHERE code_id = $1
  `;
  const results = await query<{ count: string | number | bigint }>(text, [codeId]);
  return Number(results[0]?.count ?? 0);
}

/**
 * Count the article rows law7 holds for a code.
 *
 * Used to tell "this article number is absent from a code we did import" apart
 * from "we never imported this code at all" - the two are indistinguishable in an
 * empty result set, and reporting the first when the second is true states
 * something false about the article.
 */
export async function getCodeArticleCount(codeId: string): Promise<number> {
  const text = `
    SELECT COUNT(*) as count
    FROM code_article_versions
    WHERE code_id = $1
  `;
  const results = await query<{ count: string | number | bigint }>(text, [codeId]);
  return Number(results[0]?.count ?? 0);
}

/**
 * Newest `documents.publish_date` in the corpus: the date the crawled corpus is
 * frozen at. Nothing published after it is known to law7, so a query about a date
 * later than this cannot be answered from the database at all - not even with a
 * complete amendment history.
 *
 * Cached for the lifetime of the process: the corpus does not change while the
 * MCP server runs, and every refusal path would otherwise pay for the scan.
 */
let corpusSnapshotDateCache: { value: string | null } | null = null;

export async function getCorpusSnapshotDate(): Promise<string | null> {
  if (corpusSnapshotDateCache) {
    return corpusSnapshotDateCache.value;
  }

  const text = `SELECT MAX(publish_date) AS snapshot_date FROM documents`;
  const results = await query<{ snapshot_date: Date | string | null }>(text);
  const raw = results[0]?.snapshot_date ?? null;

  let value: string | null = null;
  if (raw) {
    if (typeof raw === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      value = raw;
    } else {
      // node-postgres parses a PostgreSQL `date` into a Date at LOCAL midnight;
      // toISOString() would shift the calendar day back for positive UTC offsets.
      const d = raw instanceof Date ? raw : new Date(raw);
      if (!isNaN(d.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0');
        value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      }
    }
  }

  corpusSnapshotDateCache = { value };
  return value;
}

/** Test seam: drop the memoised corpus snapshot date. */
export function resetCorpusSnapshotDateCache(): void {
  corpusSnapshotDateCache = null;
}

/**
 * Get amendment application by eo_number
 */
export async function getAmendmentApplication(
  eoNumber: string
): Promise<AmendmentApplication | null> {
  const text = `
    SELECT * FROM amendment_applications
    WHERE amendment_eo_number = $1
  `;
  const results = await query<AmendmentApplication>(text, [eoNumber]);
  return results[0] || null;
}

/**
 * Search articles by text content
 */
export async function searchArticles(
  codeId: string,
  searchText: string,
  limit: number = 10
): Promise<CodeArticleVersion[]> {
  const text = `
    SELECT
      cav.*,
      ts_rank(
        to_tsvector('russian', cav.article_text || ' ' || COALESCE(cav.article_title, '')),
        plainto_tsquery('russian', $2)
      ) as rank
    FROM code_article_versions cav
    WHERE cav.code_id = $1
    AND to_tsvector('russian', cav.article_text || ' ' || COALESCE(cav.article_title, ''))
      @@ plainto_tsquery('russian', $2)
    ORDER BY rank DESC
    LIMIT $3
  `;

  return query<CodeArticleVersion>(text, [codeId, searchText, limit]);
}

/**
 * Get article by ID
 */
export async function getArticleById(id: string): Promise<CodeArticleVersion | null> {
  const text = `
    SELECT * FROM code_article_versions
    WHERE id = $1
  `;
  const results = await query<CodeArticleVersion>(text, [id]);
  return results[0] || null;
}

/**
 * Get article statistics for a code
 */
export async function getCodeStatistics(codeId: string): Promise<{
  total_articles: number;
  current_articles: number;
  repealed_articles: number;
  total_versions: number;
  last_amendment: Date | null;
}> {
  const text = `
    SELECT
      COUNT(*) as total_articles,
      COUNT(*) FILTER (WHERE is_current = true) as current_articles,
      COUNT(*) FILTER (WHERE is_repealed = true) as repealed_articles,
      MAX(version_date) as last_amendment
    FROM code_article_versions
    WHERE code_id = $1
  `;

  const results = await query<{
    total_articles: bigint;
    current_articles: bigint;
    repealed_articles: bigint;
    last_amendment: Date | null;
  }>(text, [codeId]);

  const row = results[0];

  // Get total versions count
  const versionsText = `
    SELECT COUNT(*) as total_versions
    FROM code_article_versions
    WHERE code_id = $1
  `;
  const versionResults = await query<{ total_versions: bigint }>(versionsText, [codeId]);

  return {
    total_articles: Number(row.total_articles),
    current_articles: Number(row.current_articles),
    repealed_articles: Number(row.repealed_articles),
    total_versions: Number(versionResults[0].total_versions),
    last_amendment: row.last_amendment,
  };
}

/**
 * List available codes with basic info
 */
export async function listConsolidatedCodes(): Promise<Array<{
  code: string;
  name: string;
  short_name: string | null;
  is_consolidated: boolean;
  total_amendments: number;
}>> {
  const text = `
    SELECT
      code,
      name,
      short_name,
      is_consolidated,
      total_amendments
    FROM consolidated_codes
    ORDER BY code ASC
  `;

  return query(text);
}
