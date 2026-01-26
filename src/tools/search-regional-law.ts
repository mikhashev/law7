/**
 * Search Regional Law Tool
 * Search for regional Russian legislation (laws, decrees, regional codes)
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query as dbQuery } from '../db/postgres.js';

// Input schema for search-regional-law tool
export const SearchRegionalLawInputSchema = z.object({
  region_id: z.string().optional().describe('Region ID (OKATO code, e.g., "77" for Moscow, "78" for SPb)'),
  region_name: z.string().optional().describe('Region name (e.g., "Moscow", "Saint Petersburg")'),
  query: z.string().describe('Search query text'),
  document_type: z.string().optional().describe('Filter by document type (e.g., "law", "decree", "resolution")'),
  max_results: z.number().optional().default(10).describe('Maximum number of results to return'),
});

export type SearchRegionalLawInput = z.infer<typeof SearchRegionalLawInputSchema>;

/**
 * Format regional document for output
 */
function formatRegionalDocument(doc: any): string {
  const parts: string[] = [];

  if (doc.complex_name) {
    parts.push(`**${doc.complex_name}**`);
  } else if (doc.title) {
    parts.push(`**${doc.title}**`);
  }

  if (doc.region_name) {
    parts.push(`Регион: ${doc.region_name}`);
  }

  if (doc.document_type) {
    parts.push(`Тип: ${doc.document_type}`);
  }

  if (doc.document_date) {
    const date = new Date(doc.document_date).toLocaleDateString('ru-RU');
    parts.push(`Дата: ${date}`);
  }

  if (doc.document_number) {
    parts.push(`Номер: ${doc.document_number}`);
  }

  if (doc.status) {
    parts.push(`Статус: ${doc.status}`);
  }

  if (doc.content) {
    // Show first 500 chars of content
    const preview = doc.content.length > 500
      ? doc.content.substring(0, 500) + '...'
      : doc.content;
    parts.push(`\nТекст:\n${preview}`);
  }

  if (doc.source_url) {
    parts.push(`\nИсточник: ${doc.source_url}`);
  }

  return parts.join('\n');
}

/**
 * Execute the search-regional-law tool
 */
export async function executeSearchRegionalLaw(input: SearchRegionalLawInput): Promise<string> {
  const { region_id, region_name, query, document_type, max_results } = input;

  // Build query conditions
  const conditions: string[] = ['country_code = $1'];
  const params: any[] = ['RU'];
  let paramIndex = 2;

  if (region_id) {
    conditions.push(`region_id = $${paramIndex++}`);
    params.push(region_id);
  }

  if (region_name) {
    conditions.push(`region_name ILIKE $${paramIndex++}`);
    params.push(`%${region_name}%`);
  }

  if (document_type) {
    conditions.push(`document_type = $${paramIndex++}`);
    params.push(document_type);
  }

  if (query) {
    conditions.push(`(title ILIKE $${paramIndex++} OR name ILIKE $${paramIndex++} OR content ILIKE $${paramIndex++})`);
    const queryPattern = `%${query}%`;
    params.push(queryPattern, queryPattern, queryPattern);
  }

  const whereClause = conditions.join(' AND ');

  const sql = `
    SELECT
      id, region_id, region_name, jurisdiction_level,
      document_type, document_number, document_date,
      title, name, complex_name, status, source_url,
      LEFT(content, 1000) as content
    FROM regional_documents
    WHERE ${whereClause}
    ORDER BY document_date DESC
    LIMIT $${paramIndex}
  `;

  params.push(max_results);

  try {
    const results = await dbQuery(sql, params);

    if (results.length === 0) {
      return `No regional documents found matching the criteria.`;
    }

    let output = `Found ${results.length} regional document(s)\n\n`;

    for (const doc of results) {
      output += `---\n`;
      output += formatRegionalDocument(doc);
      output += `\n\n`;
    }

    return output.trim();
  } catch (error) {
    console.error('Error searching regional documents:', error);
    return `Error searching regional documents: ${(error as Error).message}`;
  }
}

/**
 * Tool definition for MCP server
 */
export const searchRegionalLawTool: Tool = {
  name: 'search-regional-law',
  description: `Search for regional Russian legislation (laws, decrees, resolutions, regional codes).

This tool searches the regional_documents table which contains legal documents from Russian regions.

Phase 7C covers top 10 regions by population:
- Moscow (77), Moscow Region (50), Saint Petersburg (78)
- Krasnodar (23), Sverdlovsk (66), Rostov (61)
- Tatarstan (16), Bashkortostan (02), Novosibirsk (54), Nizhny Novgorod (52)

Args:
  region_id: Region ID (OKATO code, e.g., "77" for Moscow)
  region_name: Region name (e.g., "Moscow", "Saint Petersburg")
  query: Search query text (searches in title, name, content)
  document_type: Filter by document type (e.g., "law", "decree", "resolution")
  max_results: Maximum number of results to return (default: 10)

Examples:
  Search Moscow regional laws about taxes:
  { "region_id": "77", "query": "tax", "document_type": "law", "max_results": 5 }

  Search Saint Petersburg decrees:
  { "region_name": "Saint Petersburg", "document_type": "decree", "max_results": 10 }

  Search all regional documents about transportation:
  { "query": "transport", "max_results": 20 }`,
  inputSchema: {
    type: 'object',
    properties: {
      region_id: {
        type: 'string',
        description: 'Region ID (OKATO code, e.g., "77" for Moscow, "78" for SPb)',
      },
      region_name: {
        type: 'string',
        description: 'Region name (e.g., "Moscow", "Saint Petersburg")',
      },
      query: {
        type: 'string',
        description: 'Search query text (searches in title, name, content)',
      },
      document_type: {
        type: 'string',
        description: 'Filter by document type (e.g., "law", "decree", "resolution")',
      },
      max_results: {
        type: 'number',
        description: 'Maximum number of results to return',
        default: 10,
      },
    },
  },
};
