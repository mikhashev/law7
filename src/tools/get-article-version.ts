/**
 * Get Article Version Tool
 * Retrieve a specific article from a consolidated code, optionally as of a historical date
 */

import { z } from 'zod';
import { numericString } from './schema-utils.js';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import {
  getCurrentArticleVersion,
  getArticleVersionOnDate,
  getAmendmentChain,
  getAmendmentApplicationCount,
  getCodeStructure,
} from '../db/consolidation_queries.js';

// Input schema for get-article-version tool
export const GetArticleVersionInputSchema = z.object({
  code_id: z.string().describe('Code ID (e.g., "GK_RF", "TK_RF")'),
  article_number: numericString('Article number (e.g., "123", "80")'),
  as_of_date: z.string().optional().describe('Query article as of specific date (YYYY-MM-DD). If not provided, returns current version.'),
  include_amendment_chain: z.boolean().optional().default(false).describe('Include full amendment history'),
});

export type GetArticleVersionInput = z.infer<typeof GetArticleVersionInputSchema>;

/**
 * Format an article for output
 */
function formatArticle(
  article: any,
  codeId: string,
  amendmentChain?: any
): string {
  const parts: string[] = [];

  // Header
  parts.push(`# Article ${article.article_number}`);
  parts.push('');

  // Status badges
  const badges: string[] = [];
  if (article.is_repealed) {
    badges.push('[REPEALED]');
    if (article.repealed_date) {
      badges.push(`repealed on ${formatDate(article.repealed_date)}`);
    }
  } else if (article.is_current) {
    badges.push('[CURRENT]');
  } else {
    badges.push('[HISTORICAL]');
  }

  if (badges.length > 0) {
    parts.push(badges.join(' '));
    parts.push('');
  }

  // Title
  if (article.article_title) {
    parts.push(`## ${article.article_title}`);
    parts.push('');
  }

  // Metadata
  parts.push('## Metadata');
  parts.push(`- **Code ID**: ${codeId}`);
  parts.push(`- **Article Number**: ${article.article_number}`);
  parts.push(`- **Version Date**: ${formatDate(article.version_date)}`);
  parts.push(`- **Status**: ${article.is_current ? 'Current' : 'Historical'}`);

  if (article.is_repealed) {
    parts.push(`- **Repealed**: Yes${article.repealed_date ? ` (${formatDate(article.repealed_date)})` : ''}`);
  }

  if (article.amendment_eo_number) {
    parts.push(`- **Source Amendment**: ${article.amendment_eo_number}`);
    if (article.amendment_date) {
      parts.push(`- **Amendment Date**: ${formatDate(article.amendment_date)}`);
    }
  }

  if (article.text_hash) {
    parts.push(`- **Text Hash**: ${article.text_hash}`);
  }

  parts.push('');

  // Full text
  parts.push('## Full Text');
  parts.push(article.article_text || 'No text available.');
  parts.push('');

  // Amendment chain
  if (amendmentChain) {
    parts.push('## Amendment History');
    parts.push('');
    parts.push(`This article has ${amendmentChain.versions.length} version(s) in the database.`);
    parts.push('');

    for (const version of amendmentChain.versions) {
      const isCurrent = version.is_current ? ' [CURRENT]' : '';
      const date = formatDate(version.version_date);

      parts.push(`### ${date}${isCurrent}`);

      if (version.amendment_eo_number) {
        parts.push(`- **Amendment**: ${version.amendment_eo_number}`);
      }

      if (version.is_repealed) {
        parts.push(`- **Status**: Repealed${version.repealed_date ? ` (${formatDate(version.repealed_date)})` : ''}`);
      }

      // Text preview
      const preview = version.article_text?.substring(0, 150) || '';
      if (preview) {
        parts.push(`- **Preview**: ${preview}${version.article_text?.length > 150 ? '...' : ''}`);
      }

      parts.push('');
    }
  }

  return parts.join('\n');
}

/**
 * Format date for display
 */
function formatDate(date: Date | string | null): string {
  if (!date) return 'N/A';
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('ru-RU');
}

/**
 * Format date as ISO (YYYY-MM-DD) for machine-readable fields.
 *
 * Uses LOCAL calendar fields, not `toISOString()`: node-postgres parses a
 * PostgreSQL `date` into a Date at local midnight, so `toISOString()` would shift
 * the calendar day backwards for every positive UTC offset.
 */
function formatIsoDate(date: Date | string | null): string {
  if (!date) return 'N/A';
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) return date;
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return 'N/A';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/**
 * Compare two dates by calendar day, avoiding the local-midnight vs UTC-midnight
 * skew between a `date` column (local) and a 'YYYY-MM-DD' argument (UTC).
 * Returns true when `a` is on or before `b`.
 */
function dateOnOrBefore(a: Date | string | null, b: Date | string | null): boolean {
  const left = formatIsoDate(a);
  const right = formatIsoDate(b);
  if (left === 'N/A' || right === 'N/A') return false;
  return left <= right;
}

/**
 * Validate date string
 */
function isValidDateString(dateStr: string): boolean {
  const date = new Date(dateStr);
  return date instanceof Date && !isNaN(date.getTime());
}

/**
 * Build the refusal returned when a historical (`as_of_date`) request cannot be
 * answered truthfully.
 *
 * The shape is deliberately NOT the shape of a normal answer: it leads with
 * `## No historical version available`, carries `history_available: false`, and
 * contains no article text at all - so a calling agent cannot mistake today's
 * wording for the wording in force on the requested date.
 */
function formatNoHistoricalVersion(params: {
  codeId: string;
  articleNumber: string;
  asOfDate: string;
  versionCount: number;
  oldestVersionDate: Date | string | null;
  newestVersionDate: Date | string | null;
  amendmentsApplied: number;
  dateCovered: boolean;
}): string {
  const {
    codeId,
    articleNumber,
    asOfDate,
    versionCount,
    oldestVersionDate,
    newestVersionDate,
    amendmentsApplied,
    dateCovered,
  } = params;

  const parts: string[] = [];

  parts.push('## No historical version available');
  parts.push('');
  parts.push(
    `**REFUSED**: law7 cannot tell you what ${codeId} Article ${articleNumber} said on ${asOfDate}. ` +
      'No article text is returned below - returning the text we hold would misrepresent ' +
      "today's wording as the wording in force on the requested date."
  );
  parts.push('');
  parts.push('- **history_available**: false');
  parts.push(`- **code_id**: ${codeId}`);
  parts.push(`- **article_number**: ${articleNumber}`);
  parts.push(`- **requested_date**: ${asOfDate}`);
  parts.push(`- **versions_held**: ${versionCount}`);
  parts.push(
    `- **oldest_version_date**: ${formatIsoDate(oldestVersionDate)} (${formatDate(oldestVersionDate)})`
  );
  if (versionCount > 1) {
    parts.push(
      `- **newest_version_date**: ${formatIsoDate(newestVersionDate)} (${formatDate(newestVersionDate)})`
    );
  }
  parts.push(`- **amendments_applied**: ${amendmentsApplied}`);
  parts.push('');

  parts.push('### Why');
  parts.push('');
  if (!dateCovered) {
    parts.push(
      `- The requested date ${asOfDate} is EARLIER than the oldest version law7 holds ` +
        `(${formatIsoDate(oldestVersionDate)}). Nothing in the database describes this article at that date.`
    );
  }
  if (versionCount <= 1 && amendmentsApplied === 0) {
    parts.push(
      `- History has NOT been generated for ${codeId}: the database holds ${versionCount} version ` +
        `of this article and ${amendmentsApplied} applied amendments (no rows in ` +
        '`amendment_applications` for this code). There is no version history to query.'
    );
  } else if (amendmentsApplied === 0) {
    parts.push(
      `- ${codeId} has 0 applied amendments recorded in \`amendment_applications\`, so the stored versions are ` +
        'import snapshots, not a reconstructed amendment history.'
    );
  }
  parts.push('');

  parts.push('### What you can do instead');
  parts.push('');
  parts.push(
    '- Call this tool WITHOUT \`as_of_date\` to get the single version law7 actually holds ' +
      `(dated ${formatIsoDate(oldestVersionDate)}).`
  );
  parts.push(
    '- Treat that result as the text as imported, valid only for the date stamped on it - not as a historical version.'
  );
  parts.push('- For a genuine historical wording, consult the official source (pravo.gov.ru) directly.');
  parts.push('');

  return parts.join('\n');
}

/**
 * Execute the get-article-version tool
 */
export async function executeGetArticleVersion(input: GetArticleVersionInput): Promise<string> {
  const { code_id, article_number, as_of_date, include_amendment_chain } = input;

  // Get code info for context
  const codeStructure = await getCodeStructure(code_id);

  let article;
  let amendmentChain;

  if (as_of_date) {
    // Validate date format
    if (!isValidDateString(as_of_date)) {
      return `Error: Invalid date format "${as_of_date}". Use YYYY-MM-DD format.`;
    }

    // A historical request may only be answered when we actually hold history.
    // `code_article_versions` currently stores ONE import snapshot per article and
    // `amendment_applications` is empty, so silently returning the current text for a
    // 2015 query would be a plausible-but-wrong answer. Refuse explicitly instead.
    const chain = await getAmendmentChain(code_id, article_number);
    const versions = chain?.versions ?? [];

    if (versions.length === 0) {
      return `Article not found: ${code_id} Article ${article_number} as of ${as_of_date}`;
    }

    // getAmendmentChain returns versions ordered by version_date ASC
    const oldestVersion = versions[0];
    const newestVersion = versions[versions.length - 1];
    const amendmentsApplied = await getAmendmentApplicationCount(code_id);

    const dateCovered = dateOnOrBefore(oldestVersion.version_date, as_of_date);
    const hasRealHistory = versions.length > 1 || amendmentsApplied > 0;

    if (!dateCovered || !hasRealHistory) {
      return formatNoHistoricalVersion({
        codeId: code_id,
        articleNumber: article_number,
        asOfDate: as_of_date,
        versionCount: versions.length,
        oldestVersionDate: oldestVersion.version_date,
        newestVersionDate: newestVersion.version_date,
        amendmentsApplied,
        dateCovered,
      });
    }

    // Get historical version
    article = await getArticleVersionOnDate(code_id, article_number, as_of_date);

    if (!article) {
      return `Article not found: ${code_id} Article ${article_number} as of ${as_of_date}`;
    }
  } else {
    // Get current version
    article = await getCurrentArticleVersion(code_id, article_number);

    if (!article) {
      // Try to find any version
      const chain = await getAmendmentChain(code_id, article_number);
      if (chain.versions.length > 0) {
        return `Article ${article_number} exists but has no current version. ` +
               `It may be repealed. Use --as-of-date to query historical versions.\n\n` +
               `Available versions: ${chain.versions.length}\n` +
               `Date range: ${formatDate(chain.versions[0].version_date)} - ` +
               `${formatDate(chain.versions[chain.versions.length - 1].version_date)}`;
      }
      return `Article not found: ${code_id} Article ${article_number}`;
    }
  }

  // Get amendment chain if requested
  if (include_amendment_chain) {
    amendmentChain = await getAmendmentChain(code_id, article_number);
  }

  // Add code name to output
  let output = '';

  if (codeStructure?.code) {
    output += `# ${codeStructure.code.name} (${codeStructure.code.short_name || codeStructure.code.code})\n\n`;
  }

  output += formatArticle(article, code_id, amendmentChain);

  return output;
}

/**
 * Tool definition for MCP server
 */
export const getArticleVersionTool: Tool = {
  name: 'get-article-version',
  description: `Retrieve a specific article from a CONSOLIDATED legal code (Constitution, Civil Code, Labor Code, etc.).

⚠️ IMPORTANT - Use this tool when query mentions:
✅ Specific code articles (e.g., "Constitution article 1", "Civil Code article 420")
✅ Code names like "Constitution", "Civil Code", "Labor Code", "Criminal Code", etc.
✅ Article numbers with code references

❌ DO NOT use for general document searches (federal laws, decrees, resolutions)
   → Use query-laws instead for individual legal acts

This tool returns the full text of an article from consolidated codes, including:
- Article title and full text
- Current/historical status
- Amendment information (optional)

⚠️ HISTORICAL QUERIES ARE NOT SUPPORTED FOR MOST CODES.
law7 currently stores ONE imported snapshot per article and has applied ZERO amendments
(\`amendment_applications\` is empty). When \`as_of_date\` is supplied and no real history
exists for the code - or the date precedes the oldest snapshot we hold - this tool
REFUSES with a \`## No historical version available\` block (\`history_available: false\`)
and returns NO article text. It will never label the current text as the text in force
on a past date. Omit \`as_of_date\` to get the snapshot law7 actually holds.

First, use get-code-structure to list available codes, then query specific articles.

Args:
  code_id: Code identifier (required - see get-code-structure for available codes)
  article_number: Article number (required - e.g., "1", "80", "420")
  as_of_date: Query article as of specific date (YYYY-MM-DD). Optional.
  include_amendment_chain: Include full amendment history (default: false)

Examples:
  Get Constitution article 1:
  { "code_id": "KONST_RF", "article_number": "1" }

  Get Labor Code article 80:
  { "code_id": "TK_RF", "article_number": "80" }

  Get article as of historical date:
  { "code_id": "GK_RF", "article_number": "420", "as_of_date": "2020-01-01" }`,
  inputSchema: {
    type: 'object',
    properties: {
      code_id: {
        type: 'string',
        description: 'Code ID (e.g., "GK_RF", "TK_RF")',
      },
      article_number: {
        type: 'string',
        description: 'Article number (e.g., "123", "80")',
      },
      as_of_date: {
        type: 'string',
        description: 'Query article as of specific date (YYYY-MM-DD). If not provided, returns current version.',
      },
      include_amendment_chain: {
        type: 'boolean',
        description: 'Include full amendment history',
        default: false,
      },
    },
    required: ['code_id', 'article_number'],
  },
};
