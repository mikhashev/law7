/**
 * Get Article Version Tool
 * Retrieve a specific article from a consolidated code, optionally as of a historical date
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import {
  getCurrentArticleVersion,
  getArticleVersionOnDate,
  getAmendmentChain,
  getCodeStructure,
} from '../db/consolidation_queries.js';

// Input schema for get-article-version tool
export const GetArticleVersionInputSchema = z.object({
  code_id: z.string().describe('Code ID (e.g., "GK_RF", "TK_RF")'),
  article_number: z.string().describe('Article number (e.g., "123", "80")'),
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
 * Validate date string
 */
function isValidDateString(dateStr: string): boolean {
  const date = new Date(dateStr);
  return date instanceof Date && !isNaN(date.getTime());
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
  description: `Retrieve a specific article from a consolidated Russian legal code.

This tool returns the full text of an article, including:
- Article title and full text
- Current/historical status
- Amendment information
- Optional amendment history

Args:
  code_id: Code ID (e.g., "GK_RF", "TK_RF")
  article_number: Article number (e.g., "123", "80")
  as_of_date: Query article as of specific date (YYYY-MM-DD). Optional.
  include_amendment_chain: Include full amendment history (default: false)

Available codes:
  - GK_RF: Civil Code (Гражданский кодекс)
  - UK_RF: Criminal Code (Уголовный кодекс)
  - TK_RF: Labor Code (Трудовой кодекс)
  - NK_RF: Tax Code (Налоговый кодекс)
  - KoAP_RF: Administrative Code (КоАП РФ)
  - SK_RF: Family Code (Семейный кодекс)
  - ZhK_RF: Housing Code (Жилищный кодекс)
  - ZK_RF: Land Code (Земельный кодекс)

Examples:
  Get current article 80 of Labor Code:
  { "code_id": "TK_RF", "article_number": "80" }

  Get article as of historical date:
  { "code_id": "TK_RF", "article_number": "80", "as_of_date": "2020-01-01" }

  Get article with full history:
  { "code_id": "TK_RF", "article_number": "80", "include_amendment_chain": true }`,
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
