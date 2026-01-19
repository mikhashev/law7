/**
 * Get Code Structure Tool
 * Retrieve the hierarchical structure of a consolidated legal code
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import {
  getConsolidatedCode,
  getCodeStructure,
  listConsolidatedCodes,
} from '../db/consolidation_queries.js';

// Input schema for get-code-structure tool
export const GetCodeStructureInputSchema = z.object({
  code_id: z.string().optional().describe('Code ID (e.g., "GK_RF", "TK_RF"). If not provided, lists all available codes.'),
  include_articles: z.boolean().optional().default(true).describe('Include full list of articles'),
  article_limit: z.number().optional().default(100).describe('Maximum number of articles to return'),
});

export type GetCodeStructureInput = z.infer<typeof GetCodeStructureInputSchema>;

/**
 * Format a code for output
 */
function formatCodeStructure(structure: any, includeArticles: boolean, articleLimit: number = 100): string {
  const parts: string[] = [];

  const { code, articles, total_articles, current_articles, repealed_articles } = structure;

  // Header
  parts.push(`# ${code.name} (${code.short_name || code.code})`);
  parts.push('');

  // Metadata
  parts.push('## Code Information');
  parts.push(`- **Code ID**: ${code.code}`);
  parts.push(`- **Full Name**: ${code.name}`);

  if (code.short_name) {
    parts.push(`- **Short Name**: ${code.short_name}`);
  }

  if (code.description) {
    parts.push(`- **Description**: ${code.description}`);
  }

  if (code.original_eo_number) {
    parts.push(`- **Original Law**: ${code.original_eo_number} from ${formatDate(code.original_date)}`);
  }

  if (code.official_url) {
    parts.push(`- **Official URL**: ${code.official_url}`);
  }

  parts.push(`- **Total Amendments**: ${code.total_amendments}`);
  parts.push(`- **Consolidation Status**: ${code.is_consolidated ? 'Complete' : 'In Progress'}`);

  if (code.last_amended_date) {
    parts.push(`- **Last Amended**: ${formatDate(code.last_amended_date)}`);
  }

  parts.push('');

  // Statistics
  parts.push('## Statistics');
  parts.push(`- **Total Articles**: ${total_articles}`);
  parts.push(`- **Current Articles**: ${current_articles}`);
  parts.push(`- **Repealed Articles**: ${repealed_articles}`);
  parts.push(`- **Historical Versions**: ${articles.length}`);
  parts.push('');

  // Articles
  if (includeArticles && articles.length > 0) {
    parts.push('## Articles');

    for (const article of articles.slice(0, articleLimit)) {
      const status = article.is_repealed
        ? '[REPEALED]'
        : article.is_current
          ? '[CURRENT]'
          : '[HISTORICAL]';

      parts.push(`### Article ${article.article_number} ${status}`);

      if (article.article_title) {
        parts.push(`**Title**: ${article.article_title}`);
      }

      parts.push(`**Version Date**: ${formatDate(article.version_date)}`);

      if (article.amendment_eo_number) {
        parts.push(`**Source Amendment**: ${article.amendment_eo_number}`);
      }

      // Show preview of article text
      const preview = article.article_text.substring(0, 200);
      if (article.article_text.length > 200) {
        parts.push(`**Preview**: ${preview}...`);
      } else if (preview) {
        parts.push(`**Text**: ${preview}`);
      }

      parts.push('');
    }

    if (articles.length > articleLimit) {
      parts.push(`*... and ${articles.length - articleLimit} more articles*`);
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
 * List all available codes
 */
function formatCodeList(codes: Array<{
  code: string;
  name: string;
  short_name: string | null;
  is_consolidated: boolean;
  total_amendments: number;
}>): string {
  const parts: string[] = [];

  parts.push('# Available Consolidated Codes');
  parts.push('');
  parts.push('| Code | Name | Short Name | Status | Amendments |');
  parts.push('|------|------|------------|--------|------------|');

  for (const code of codes) {
    parts.push(
      `| ${code.code} | ${code.name} | ${code.short_name || 'N/A'} | ` +
      `${code.is_consolidated ? 'Complete' : 'In Progress'} | ${code.total_amendments} |`
    );
  }

  parts.push('');
  parts.push('Use the code_id with --code-id parameter to get full structure.');

  return parts.join('\n');
}

/**
 * Execute the get-code-structure tool
 */
export async function executeGetCodeStructure(input: GetCodeStructureInput): Promise<string> {
  const { code_id, include_articles, article_limit } = input;

  // If no code_id provided, list all available codes
  if (!code_id) {
    const codes = await listConsolidatedCodes();
    return formatCodeList(codes);
  }

  // Get the code structure
  const structure = await getCodeStructure(code_id);

  if (!structure) {
    // Code not found, list available codes
    const codes = await listConsolidatedCodes();
    return `Code not found: ${code_id}\n\n${formatCodeList(codes)}`;
  }

  return formatCodeStructure(structure, include_articles, article_limit);
}

/**
 * Tool definition for MCP server
 */
export const getCodeStructureTool: Tool = {
  name: 'get-code-structure',
  description: `Retrieve the hierarchical structure of a consolidated Russian legal code.

This tool returns information about legal codes (Civil Code, Labor Code, etc.) including:
- Code metadata (name, description, original publication)
- Consolidation status and statistics
- Full list of articles with their current status
- Historical version information

Args:
  code_id: Code ID (e.g., "GK_RF", "TK_RF"). If not provided, lists all available codes.
  include_articles: Include full list of articles (default: true)
  article_limit: Maximum number of articles to return (default: 100)

Available codes:
  - KONST_RF: Constitution (Конституция Российской Федерации)
  - GK_RF: Civil Code Part 1 (Гражданский кодекс)
  - GK_RF_2: Civil Code Part 2 (Гражданский кодекс ч.2)
  - GK_RF_3: Civil Code Part 3 (Гражданский кодекс ч.3)
  - GK_RF_4: Civil Code Part 4 (Гражданский кодекс ч.4)
  - UK_RF: Criminal Code (Уголовный кодекс)
  - TK_RF: Labor Code (Трудовой кодекс)
  - NK_RF: Tax Code Part 1 (Налоговый кодекс)
  - NK_RF_2: Tax Code Part 2 (Налоговый кодекс ч.2)
  - KoAP_RF: Administrative Code (КоАП РФ)
  - SK_RF: Family Code (Семейный кодекс)
  - ZhK_RF: Housing Code (Жилищный кодекс)
  - ZK_RF: Land Code (Земельный кодекс)
  - APK_RF: Arbitration Procedure Code (Арбитражный процессуальный кодекс)
  - GPK_RF: Civil Procedure Code (Гражданский процессуальный кодекс)
  - UPK_RF: Criminal Procedure Code (Уголовно-процессуальный кодекс)

Example:
  Get structure of Labor Code:
  { "code_id": "TK_RF", "include_articles": true, "article_limit": 50 }

  List all available codes:
  {}`,
  inputSchema: {
    type: 'object',
    properties: {
      code_id: {
        type: 'string',
        description: 'Code ID (e.g., "GK_RF", "TK_RF"). If not provided, lists all available codes.',
      },
      include_articles: {
        type: 'boolean',
        description: 'Include full list of articles',
        default: true,
      },
      article_limit: {
        type: 'number',
        description: 'Maximum number of articles to return',
        default: 100,
      },
    },
  },
};
