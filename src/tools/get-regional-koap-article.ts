/**
 * Get Regional KoAP Article Tool
 * Get specific article from regional Administrative Code (KoAP)
 */

import { z } from 'zod';
import { numericString } from './schema-utils.js';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query as dbQuery } from '../db/postgres.js';

// Input schema for get-regional-koap-article tool
export const GetRegionalKoapArticleInputSchema = z.object({
  region_id: numericString('Region ID (OKATO code, e.g., "77" for Moscow)'),
  code_id: z.string().optional().describe('Code ID (e.g., "KOAP_MOSCOW") - inferred from region if not provided'),
  article_number: numericString('Article number (e.g., "1.1", "5.35")'),
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

  parts.push(`**${article.code_name || article.code_id}**`);
  parts.push(`Регион: ${article.region_name || article.region_id}`);

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

  // NOTE: `regional_code_articles` has NO `region_name` column - the region and code
  // names live in `regional_codes`, which keys its country as `country_id` ('RUS'),
  // not `country_code`. The previous query selected non-existent columns and spliced
  // `ORDER BY ... LIMIT 1` into its AND-joined WHERE list, so it could only ever throw.
  const params: any[] = ['RU', region_id, koapCodeId, article_number];
  let versionClause = 'AND a.is_current = true';
  if (version_date) {
    params.push(version_date);
    versionClause = `AND a.version_date <= $${params.length}`;
  }

  const sql = `
    SELECT
      a.id, a.region_id, a.code_id,
      a.article_number, a.chapter_number, a.part_number,
      a.article_title, a.article_content,
      a.status, a.effective_from, a.effective_until,
      a.version_date, a.is_current, a.source_url,
      rc.region_name,
      rc.code_name
    FROM regional_code_articles a
    LEFT JOIN regional_codes rc
      ON rc.region_id = a.region_id
     AND rc.code_id = a.code_id
    WHERE a.country_code = $1
      AND a.region_id = $2
      AND a.code_id = $3
      AND a.article_number = $4
      ${versionClause}
    ORDER BY a.version_date DESC
    LIMIT 1
  `;

  try {
    const result = await dbQuery(sql, params);

    if (result.length === 0) {
      // Distinguish "this article is missing" from "no regional law has ever been
      // imported" - the second is the current state and must not read as a fact
      // about the article.
      const totals = await dbQuery<{ articles: string; codes: string }>(`
        SELECT
          (SELECT COUNT(*) FROM regional_code_articles) AS articles,
          (SELECT COUNT(*) FROM regional_codes) AS codes
      `);
      const articleRows = Number(totals[0]?.articles ?? 0);
      const codeRows = Number(totals[0]?.codes ?? 0);

      if (articleRows === 0) {
        return [
          '## No regional data',
          '',
          '**data_available**: false',
          '',
          `law7 holds NO regional legal acts at all: \`regional_code_articles\` has ${articleRows} rows ` +
            `and \`regional_codes\` has ${codeRows} rows. The regional KoAP corpus has never been ` +
            'imported.',
          '',
          `This is NOT a statement about region ${region_id} article ${article_number} - law7 simply ` +
            'has nothing to say about regional administrative law yet. Consult the official regional ' +
            'publication instead.',
          '',
        ].join('\n');
      }

      return version_date
        ? `Article ${article_number} not found in ${koapCodeId} for region ${region_id} as of ${version_date}.`
        : `Article ${article_number} not found in ${koapCodeId} for region ${region_id}.`;
    }

    return formatKoapArticle(result[0]);
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

⚠️ NO REGIONAL DATA IS LOADED YET. \`regional_code_articles\` and \`regional_codes\` are both
empty, so this tool returns a \`## No regional data\` result (\`data_available: false\`) for
every query. That result means law7 has nothing imported - never report it as "no such
article exists".

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
