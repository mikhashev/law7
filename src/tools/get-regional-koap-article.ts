/**
 * Get Regional KoAP Article Tool
 * Get specific article from regional Administrative Code (KoAP)
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query as dbQuery } from '../db/postgres.js';

// Input schema for get-regional-koap-article tool
export const GetRegionalKoapArticleInputSchema = z.object({
  region_id: z.string().describe('Region ID (OKATO code, e.g., "77" for Moscow)'),
  code_id: z.string().optional().describe('Code ID (e.g., "KOAP_MOSCOW") - inferred from region if not provided'),
  article_number: z.string().describe('Article number (e.g., "1.1", "5.35")'),
  version_date: z.string().optional().describe('Version date (YYYY-MM-DD) - defaults to current version'),
});

export type GetRegionalKoapArticleInput = z.infer<typeof GetRegionalKoapArticleInputSchema>;

// Map region IDs to KoAP code IDs
const REGION_TO_KOAP: Record<string, string> = {
  '77': 'KOAP_MOSCOW',
  '50': 'KOAP_MOSKOV_OBL',
  '78': 'KOAP_SPB',
  '23': 'KOAP_KRASNODAR',
  '66': 'KOAP_SVERDLOVSK',
  '61': 'KOAP_ROSTOV',
  '16': 'KOAP_TATARSTAN',
  '02': 'KOAP_BASHKORTOSTAN',
  '54': 'KOAP_NOVOSIBIRSK',
  '52': 'KOAP_NIZHNY_NOVGOROD',
};

/**
 * Format regional KoAP article for output
 */
function formatKoapArticle(article: any): string {
  const parts: string[] = [];

  parts.push(`**${article.code_name}**`);
  parts.push(`Регион: ${article.region_name}`);

  if (article.chapter_number) {
    parts.push(`Глава: ${article.chapter_number}`);
  }

  parts.push(`Статья ${article.article_number}`);
  if (article.article_title) {
    parts.push(`*${article.article_title}*`);
  }

  if (article.version_date) {
    const date = new Date(article.version_date).toLocaleDateString('ru-RU');
    parts.push(`Версия от: ${date}`);
  }

  if (!article.is_current) {
    parts.push(`⚠️ Историческая версия (не действующая)`);
  }

  if (article.status && article.status !== 'active') {
    parts.push(`Статус: ${article.status}`);
  }

  if (article.effective_from) {
    const fromDate = new Date(article.effective_from).toLocaleDateString('ru-RU');
    parts.push(`Действует с: ${fromDate}`);
  }

  if (article.effective_until) {
    const untilDate = new Date(article.effective_until).toLocaleDateString('ru-RU');
    parts.push(`Действовало до: ${untilDate}`);
  }

  parts.push(`\nТекст статьи:\n${article.article_content}`);

  if (article.source_url) {
    parts.push(`\nИсточник: ${article.source_url}`);
  }

  return parts.join('\n');
}

/**
 * Execute the get-regional-koap-article tool
 */
export async function executeGetRegionalKoapArticle(input: GetRegionalKoapArticleInput): Promise<string> {
  const { region_id, code_id, article_number, version_date } = input;

  // Determine code_id if not provided
  const koapCodeId = code_id || REGION_TO_KOAP[region_id];
  if (!koapCodeId) {
    return `Error: Could not determine KoAP code ID for region ${region_id}. Please provide code_id explicitly.`;
  }

  // Build query
  const conditions: string[] = [
    'country_code = $1',
    'region_id = $2',
    'code_id = $3',
    'article_number = $4'
  ];
  const params: any[] = ['RU', region_id, koapCodeId, article_number];
  let paramIndex = 5;

  // If version_date is specified, get specific version
  // Otherwise, get current version
  if (version_date) {
    conditions.push(`version_date <= $${paramIndex++}`);
    params.push(version_date);
    conditions.push(`ORDER BY version_date DESC LIMIT 1`);
  } else {
    conditions.push(`is_current = true`);
  }

  const whereClause = conditions.join(' AND ');

  const sql = `
    SELECT
      id, region_id, region_name, code_id,
      article_number, chapter_number, part_number,
      article_title, article_content,
      status, effective_from, effective_until,
      version_date, is_current, source_url
    FROM regional_code_articles
    WHERE ${whereClause}
  `;

  try {
    const result = await dbQuery(sql, params);

    if (result.length === 0) {
      return `Article ${article_number} not found in ${koapCodeId} for region ${region_id}.`;
    }

    const article = result[0];

    // Get code name from regional_codes table
    const codeResult = await dbQuery(
      'SELECT code_name FROM regional_codes WHERE country_code = $1 AND region_id = $2 AND code_id = $3',
      ['RU', region_id, koapCodeId]
    );

    if (codeResult.length > 0) {
      article.code_name = codeResult[0].code_name;
    }

    return formatKoapArticle(article);
  } catch (error) {
    console.error('Error fetching regional KoAP article:', error);
    return `Error fetching regional KoAP article: ${(error as Error).message}`;
  }
}

/**
 * Tool definition for MCP server
 */
export const getRegionalKoapArticleTool: Tool = {
  name: 'get-regional-koap-article',
  description: `Get specific article from regional Russian Administrative Code (KoAP).

This tool retrieves articles from regional administrative codes (Кодекс об административных правонарушениях) for Russian regions.

Phase 7C covers top 10 regions by population:
- Moscow (77), Moscow Region (50), Saint Petersburg (78)
- Krasnodar (23), Sverdlovsk (66), Rostov (61)
- Tatarstan (16), Bashkortostan (02), Novosibirsk (54), Nizhny Novgorod (52)

Args:
  region_id: Region ID (OKATO code, e.g., "77" for Moscow) - REQUIRED
  code_id: Code ID (e.g., "KOAP_MOSCOW") - optional, inferred from region
  article_number: Article number (e.g., "1.1", "5.35") - REQUIRED
  version_date: Version date (YYYY-MM-DD) - optional, defaults to current version

Examples:
  Get current version of article 5.35 from Moscow KoAP:
  { "region_id": "77", "article_number": "5.35" }

  Get historical version of article from Saint Petersburg KoAP:
  { "region_id": "78", "article_number": "1.1", "version_date": "2020-01-01" }

  Get specific article with explicit code_id:
  { "region_id": "16", "code_id": "KOAP_TATARSTAN", "article_number": "2.1" }`,
  inputSchema: {
    type: 'object',
    properties: {
      region_id: {
        type: 'string',
        description: 'Region ID (OKATO code, e.g., "77" for Moscow)',
      },
      code_id: {
        type: 'string',
        description: 'Code ID (e.g., "KOAP_MOSCOW") - inferred from region if not provided',
      },
      article_number: {
        type: 'string',
        description: 'Article number (e.g., "1.1", "5.35")',
      },
      version_date: {
        type: 'string',
        description: 'Version date (YYYY-MM-DD) - defaults to current version',
      },
    },
    required: ['region_id', 'article_number'],
  },
};
