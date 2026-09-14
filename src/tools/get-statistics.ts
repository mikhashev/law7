/**
 * Get Statistics Tool
 * Get statistics about the legal document database
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query, getDocumentCount, getCountryIdFromCode } from '../db/postgres.js';
import { getPointCount } from '../db/qdrant.js';

// Input schema for get-statistics tool
export const GetStatisticsInputSchema = z.object({
  country_code: z.string().optional().describe('Filter statistics by country code (ISO 3166-1 alpha-2, e.g., "RU", "US")'),
  include_vector_stats: z.boolean().optional().default(true).describe('Include vector database statistics'),
});

export type GetStatisticsInput = z.infer<typeof GetStatisticsInputSchema>;

/**
 * Statistics interface
 */
export interface Statistics {
  countries: { id: number; name: string; document_count: number }[];
  total_documents: number;
  documents_with_content: number;
  /** length(full_text) percentiles over document_content rows in scope */
  content_length_p50: number | null;
  content_length_p90: number | null;
  content_length_max: number | null;
  /** document_content rows whose full_text is longer than LONG_TEXT_CHARS */
  documents_over_long_text: number;
  /** max(documents.publish_date): how current the crawled corpus is */
  snapshot_date: string | null;
  /**
   * max(documents.updated_at): the newest row write in `documents`. NOT the time a
   * sync ran - law7 keeps no sync log, and a restore rewrites this timestamp.
   */
  corpus_last_write_at: string | null;
  /** rows in code_article_versions for codes in scope */
  article_versions_total: number;
  /** rows in amendment_applications for codes in scope */
  amendments_applied: number;
  /** codes in scope holding at least one applied amendment */
  codes_with_applied_amendments: number;
  /** consolidated codes in scope (the M of "N of M") */
  codes_in_scope: number;
  /** derived: codes_with_applied_amendments > 0 */
  history_available: boolean;
  publication_blocks: { code: string; name: string; count: number }[];
  vector_count?: number;
}

/**
 * One arbitrary cut through the full_text length distribution, reported alongside
 * the distribution itself so nobody reads it as a body/annotation boundary: the
 * live median is 447 characters and the maximum 5,565, so this line separates
 * "the single longest rows" from the rest, not "act bodies" from "annotations".
 */
const LONG_TEXT_CHARS = 5000;

/** Format every number in this tool the same way: 1136605 -> "1,136,605". */
function formatCount(value: number | bigint | string | null | undefined): string {
  return Number(value ?? 0).toLocaleString('en-US');
}

function pad(n: number, width = 2): string {
  return String(n).padStart(width, '0');
}

/**
 * Render a date as YYYY-MM-DD, or "never" when the database has no value.
 *
 * Uses LOCAL calendar fields, not `toISOString()`: node-postgres parses a
 * PostgreSQL `date` into a Date at local midnight, so `toISOString()` shifts the
 * calendar day backwards for every positive UTC offset (2026-02-06 was being
 * reported as 2026-02-05).
 */
function formatDateOnly(value: Date | string | null | undefined): string {
  if (!value) return 'never';
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return 'never';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Render a character length, or "n/a" when the scope holds no rows. */
function formatLength(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return 'n/a';
  return `${formatCount(Math.round(Number(value)))} chars`;
}

/**
 * Render a timestamp as YYYY-MM-DD HH:MM:SS, or "never".
 *
 * `documents.updated_at` is `timestamp without time zone`, which node-postgres
 * hands back as a local-time Date; it is printed back in the same wall-clock
 * fields it was stored in, with no timezone claim attached.
 */
function formatTimestamp(value: Date | string | null | undefined): string {
  if (!value) return 'never';
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return 'never';
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

/**
 * Execute the get-statistics tool
 */
export async function executeGetStatistics(input: GetStatisticsInput): Promise<string> {
  const { country_code, include_vector_stats } = input;

  // Convert country code to ID if provided
  let countryId: number | undefined;
  if (country_code) {
    countryId = await getCountryIdFromCode(country_code) || undefined;
  }

  // Get document count
  const totalDocuments = await getDocumentCount(undefined, country_code);

  // Get documents with content
  const contentResult = await query<{ count: bigint }>(`
    SELECT COUNT(*) as count
    FROM document_content
    WHERE full_text IS NOT NULL
    ${countryId ? `AND document_id IN (SELECT id FROM documents WHERE country_id = ${countryId})` : ''}
  `);
  const documentsWithContent = Number(contentResult[0].count);

  // Corpus freshness + consolidation facts, fetched together so the reported
  // numbers all come from the same moment.
  const docFilter = countryId ? `WHERE country_id = ${countryId}` : '';
  const contentFilter = countryId
    ? `AND document_id IN (SELECT id FROM documents WHERE country_id = ${countryId})`
    : '';
  //
  // Scope note: `consolidated_codes`, `code_article_versions` and
  // `amendment_applications` carry NO country column (verified against the live
  // schema), so the consolidation counters are scoped to the set of registered
  // consolidated codes - joined through `consolidated_codes` rather than counted
  // over the whole table - and the country filter cannot narrow them further. That
  // limit is stated in the output instead of being papered over.
  const factsResult = await query<{
    snapshot_date: Date | string | null;
    corpus_last_write_at: Date | string | null;
    content_length_p50: number | string | null;
    content_length_p90: number | string | null;
    content_length_max: number | string | null;
    documents_over_long_text: bigint;
    article_versions_total: bigint;
    amendments_applied: bigint;
    codes_with_applied_amendments: bigint;
    codes_in_scope: bigint;
  }>(`
    SELECT
      (SELECT MAX(publish_date) FROM documents ${docFilter}) AS snapshot_date,
      (SELECT MAX(updated_at) FROM documents ${docFilter}) AS corpus_last_write_at,
      (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY length(full_text))
         FROM document_content WHERE full_text IS NOT NULL ${contentFilter}) AS content_length_p50,
      (SELECT percentile_cont(0.9) WITHIN GROUP (ORDER BY length(full_text))
         FROM document_content WHERE full_text IS NOT NULL ${contentFilter}) AS content_length_p90,
      (SELECT MAX(length(full_text))
         FROM document_content WHERE full_text IS NOT NULL ${contentFilter}) AS content_length_max,
      (SELECT COUNT(*) FROM document_content
         WHERE length(full_text) > ${LONG_TEXT_CHARS} ${contentFilter}) AS documents_over_long_text,
      (SELECT COUNT(*) FROM code_article_versions cav
         JOIN consolidated_codes cc ON cc.code = cav.code_id) AS article_versions_total,
      (SELECT COUNT(*) FROM amendment_applications aa
         JOIN consolidated_codes cc ON cc.code = aa.code_id) AS amendments_applied,
      (SELECT COUNT(DISTINCT aa.code_id) FROM amendment_applications aa
         JOIN consolidated_codes cc ON cc.code = aa.code_id
         WHERE aa.status = 'applied') AS codes_with_applied_amendments,
      (SELECT COUNT(*) FROM consolidated_codes) AS codes_in_scope
  `);
  const facts = factsResult[0] ?? ({} as Record<string, never>);
  const documentsOverLongText = Number(facts.documents_over_long_text ?? 0);
  const articleVersionsTotal = Number(facts.article_versions_total ?? 0);
  const amendmentsApplied = Number(facts.amendments_applied ?? 0);
  const codesWithAppliedAmendments = Number(facts.codes_with_applied_amendments ?? 0);
  const codesInScope = Number(facts.codes_in_scope ?? 0);
  const historyAvailable = codesWithAppliedAmendments > 0;

  // Get publication blocks
  const blocksResult = await query<{ code: string; short_name: string; count: bigint }>(`
    SELECT
      pb.code,
      pb.short_name,
      COUNT(d.id) as count
    FROM publication_blocks pb
    LEFT JOIN documents d ON pb.id = d.publication_block_id
    ${countryId ? `WHERE d.country_id = ${countryId}` : 'WHERE 1=1'}
    GROUP BY pb.id, pb.code, pb.short_name
    HAVING COUNT(d.id) > 0
    ORDER BY count DESC
  `);

  // Get countries
  const countriesResult = await query<{ id: number; name: string; document_count: bigint }>(`
    SELECT
      c.id,
      c.name,
      COUNT(d.id) as document_count
    FROM countries c
    LEFT JOIN documents d ON c.id = d.country_id
    GROUP BY c.id, c.name
    HAVING COUNT(d.id) > 0
    ORDER BY document_count DESC
  `);

  // Get vector count
  let vectorCount = 0;
  if (include_vector_stats) {
    try {
      vectorCount = await getPointCount();
    } catch (error) {
      console.error('Failed to get vector count:', error);
    }
  }

  // Format output
  let output = `## Legal Document Database Statistics\n\n`;

  if (country_code) {
    output += `**Country Code**: ${country_code.toUpperCase()}\n\n`;
  }

  // Overview
  output += `### Overview\n\n`;
  output += `- **Total Documents**: ${formatCount(totalDocuments)}\n`;
  output += `- **Documents with Content**: ${formatCount(documentsWithContent)}\n`;
  output += `- **Content Coverage**: ${totalDocuments > 0 ? ((documentsWithContent / totalDocuments) * 100).toFixed(1) : 0}%\n`;

  if (include_vector_stats) {
    output += `- **Vector Chunks**: ${formatCount(vectorCount)}\n`;
  }

  output += `\n`;

  // Content length distribution
  output += `### Document Content Length\n\n`;
  output += `- **document_content length p50**: ${formatLength(facts.content_length_p50)}\n`;
  output += `- **document_content length p90**: ${formatLength(facts.content_length_p90)}\n`;
  output += `- **document_content length max**: ${formatLength(facts.content_length_max)}\n`;
  output += `- **Rows longer than ${formatCount(LONG_TEXT_CHARS)} chars**: ${formatCount(documentsOverLongText)}\n`;
  output += `\n`;
  output += `> "Documents with Content" counts \`document_content\` rows of ANY length. The\n`;
  output += `> percentiles above say what those rows actually hold: at p50 they carry\n`;
  output += `> annotation-level text (title, number, date), not an act body. The ${formatCount(LONG_TEXT_CHARS)}-character\n`;
  output += `> line is one arbitrary cut through that distribution, not a body/annotation boundary -\n`;
  output += `> read it against the maximum above before treating it as a count of full act texts.\n`;
  output += `\n`;

  // Freshness
  output += `### Freshness\n\n`;
  output += `- **Snapshot Date** (max documents.publish_date): ${formatDateOnly(facts.snapshot_date)}\n`;
  output += `- **corpus_last_write_at** (max documents.updated_at): ${formatTimestamp(facts.corpus_last_write_at)}\n`;
  output += `- **sync_log**: none (no record of sync runs exists yet)\n`;
  output += `\n`;
  output += `> \`corpus_last_write_at\` is the newest row write in \`documents\`, NOT the time a sync\n`;
  output += `> ran: a restore from backup rewrites it, and a sync that found nothing to change\n`;
  output += `> leaves it untouched. law7 keeps no sync log, so "a sync ran and found nothing" and\n`;
  output += `> "a sync never ran" cannot be told apart from this field.\n`;
  output += `\n`;

  // Consolidated codes / history
  output += `### Consolidated Codes\n\n`;
  output += `- **Codes in Scope** (rows in consolidated_codes): ${formatCount(codesInScope)}\n`;
  output += `- **Article Versions Total** (code_article_versions for codes in scope): ${formatCount(articleVersionsTotal)}\n`;
  output += `- **Amendments Applied** (amendment_applications for codes in scope): ${formatCount(amendmentsApplied)}\n`;
  output += `- **codes_with_applied_amendments**: ${formatCount(codesWithAppliedAmendments)} of ${formatCount(codesInScope)}\n`;
  output += `- **history_available** (derived): ${historyAvailable} - ${formatCount(codesWithAppliedAmendments)} of ${formatCount(codesInScope)} codes have any applied amendment\n`;
  output += `\n`;

  if (country_code) {
    output += `> Scope note: \`consolidated_codes\`, \`code_article_versions\` and\n`;
    output += `> \`amendment_applications\` carry no country column, so the counters in this section\n`;
    output += `> cover every registered code and are NOT narrowed by \`country_code\`.\n`;
    output += `\n`;
  }

  if (!historyAvailable) {
    output += `> No amendment has ever been applied for any code in scope, so every article holds a\n`;
    output += `> single import snapshot. Historical (\`as_of_date\`) queries cannot be answered and\n`;
    output += `> \`get-article-version\` refuses them rather than returning current text.\n`;
    output += `\n`;
  }

  // Countries
  if (countriesResult.length > 0) {
    output += `### Documents by Country\n\n`;
    for (const country of countriesResult) {
      output += `- **${country.name}** (ID: ${country.id}): ${formatCount(country.document_count)} documents\n`;
    }
    output += `\n`;
  }

  // Publication blocks
  if (blocksResult.length > 0) {
    output += `### Documents by Publication Block\n\n`;
    for (const block of blocksResult) {
      output += `- **${block.short_name || block.code}**: ${formatCount(block.count)} documents\n`;
    }
    output += `\n`;
  }

  return output;
}

/**
 * Tool definition for MCP server
 */
export const getStatisticsTool: Tool = {
  name: 'get-statistics',
  description: `Get statistics about the legal document database.

This tool returns aggregate statistics about the indexed legal documents:
- total_documents, documents_with_content (document_content rows of ANY length), plus the
  length distribution of those rows (p50 / p90 / max) and the count longer than 5000
  characters - the distribution shows that most rows are annotation-level text, not act
  bodies, and that the 5000-character line is one arbitrary cut, not a body/annotation
  boundary
- snapshot_date (max documents.publish_date) and corpus_last_write_at
  (max documents.updated_at, the newest row write - NOT a sync timestamp; law7 keeps no
  sync log, reported as sync_log: none), so a caller can tell how stale the corpus is
- codes_in_scope, article_versions_total and amendments_applied (all scoped to registered
  consolidated codes), codes_with_applied_amendments ("N of M") and the derived
  history_available, so a caller can tell whether historical (as_of_date) queries can be
  answered at all. The consolidation tables carry no country column, so country_code does
  not narrow those counters.
- vector chunk count, coverage, and breakdown by country / publication block

All counts are formatted with thousands separators (en-US), e.g. 1,136,605.

Currently supports data from Russia (Phase 1). Multi-country statistics planned for Phase 2.

Args:
  country_code: Optional country code to filter statistics (ISO 3166-1 alpha-2, e.g., "RU", "US")
  include_vector_stats: Include vector database statistics (default: true)

Examples:
  Get overall statistics:
  { "include_vector_stats": true }

  Get statistics for specific country:
  { "country_code": "RU", "include_vector_stats": true }`,
  inputSchema: {
    type: 'object',
    properties: {
      country_code: {
        type: 'string',
        description: 'Filter statistics by country code (ISO 3166-1 alpha-2, e.g., "RU", "US")',
      },
      include_vector_stats: {
        type: 'boolean',
        description: 'Include vector database statistics',
        default: true,
      },
    },
    required: [],
  },
};
