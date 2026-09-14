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
  /** document_content rows whose full_text is longer than BODY_TEXT_MIN_CHARS */
  documents_with_body_text: number;
  /** max(documents.publish_date): how current the crawled corpus is */
  snapshot_date: string | null;
  /** max(documents.updated_at): when a sync last wrote to the corpus */
  last_sync_at: string | null;
  /** rows in code_article_versions */
  article_versions_total: number;
  /** rows in amendment_applications */
  amendments_applied: number;
  /** false while no amendment has ever been applied */
  history_available: boolean;
  publication_blocks: { code: string; name: string; count: number }[];
  vector_count?: number;
}

/**
 * Minimum full_text length that indicates a real act body rather than the
 * annotation-level text the crawler stores for most documents.
 */
const BODY_TEXT_MIN_CHARS = 5000;

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
  const factsResult = await query<{
    snapshot_date: Date | string | null;
    last_sync_at: Date | string | null;
    documents_with_body_text: bigint;
    article_versions_total: bigint;
    amendments_applied: bigint;
  }>(`
    SELECT
      (SELECT MAX(publish_date) FROM documents ${docFilter}) AS snapshot_date,
      (SELECT MAX(updated_at) FROM documents ${docFilter}) AS last_sync_at,
      (SELECT COUNT(*) FROM document_content
         WHERE length(full_text) > ${BODY_TEXT_MIN_CHARS} ${contentFilter}) AS documents_with_body_text,
      (SELECT COUNT(*) FROM code_article_versions) AS article_versions_total,
      (SELECT COUNT(*) FROM amendment_applications) AS amendments_applied
  `);
  const facts = factsResult[0] ?? ({} as Record<string, never>);
  const documentsWithBodyText = Number(facts.documents_with_body_text ?? 0);
  const articleVersionsTotal = Number(facts.article_versions_total ?? 0);
  const amendmentsApplied = Number(facts.amendments_applied ?? 0);
  const historyAvailable = amendmentsApplied > 0;

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
  output += `- **Documents with Body Text** (full_text > ${formatCount(BODY_TEXT_MIN_CHARS)} chars): ${formatCount(documentsWithBodyText)}\n`;
  output += `- **Content Coverage**: ${totalDocuments > 0 ? ((documentsWithContent / totalDocuments) * 100).toFixed(1) : 0}%\n`;

  if (include_vector_stats) {
    output += `- **Vector Chunks**: ${formatCount(vectorCount)}\n`;
  }

  output += `\n`;

  // Freshness
  output += `### Freshness\n\n`;
  output += `- **Snapshot Date** (max documents.publish_date): ${formatDateOnly(facts.snapshot_date)}\n`;
  output += `- **Last Sync At** (max documents.updated_at): ${formatTimestamp(facts.last_sync_at)}\n`;
  output += `\n`;

  // Consolidated codes / history
  output += `### Consolidated Codes\n\n`;
  output += `- **Article Versions Total**: ${formatCount(articleVersionsTotal)}\n`;
  output += `- **Amendments Applied**: ${formatCount(amendmentsApplied)}\n`;
  output += `- **history_available**: ${historyAvailable}\n`;
  output += `\n`;

  if (!historyAvailable) {
    output += `> No amendment has ever been applied (\`amendment_applications\` is empty), so every\n`;
    output += `> article holds a single import snapshot. Historical (\`as_of_date\`) queries cannot be\n`;
    output += `> answered and \`get-article-version\` refuses them rather than returning current text.\n`;
    output += `\n`;
  }

  if (documentsWithBodyText < documentsWithContent) {
    output += `> "Documents with Content" counts \`document_content\` rows of any length; most hold\n`;
    output += `> annotation-level text (title, number, date), not the act body. "Documents with Body\n`;
    output += `> Text" is the count that actually carries a full act text.\n`;
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
- total_documents, documents_with_content, documents_with_body_text
  (documents_with_content counts document_content rows of ANY length - most are
   annotation-level text, not act bodies; documents_with_body_text counts the rows
   longer than 5000 characters)
- snapshot_date (max documents.publish_date) and last_sync_at (max documents.updated_at),
  so a caller can tell how stale the corpus is
- article_versions_total, amendments_applied and history_available, so a caller can tell
  whether historical (as_of_date) queries can be answered at all
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
