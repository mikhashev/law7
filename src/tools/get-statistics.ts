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
  publication_blocks: { code: string; name: string; count: number }[];
  vector_count?: number;
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
  output += `- **Total Documents**: ${totalDocuments.toLocaleString()}\n`;
  output += `- **Documents with Content**: ${documentsWithContent.toLocaleString()}\n`;
  output += `- **Content Coverage**: ${totalDocuments > 0 ? ((documentsWithContent / totalDocuments) * 100).toFixed(1) : 0}%\n`;

  if (include_vector_stats) {
    output += `- **Vector Chunks**: ${vectorCount.toLocaleString()}\n`;
  }

  output += `\n`;

  // Countries
  if (countriesResult.length > 0) {
    output += `### Documents by Country\n\n`;
    for (const country of countriesResult) {
      output += `- **${country.name}** (ID: ${country.id}): ${Number(country.document_count).toLocaleString()} documents\n`;
    }
    output += `\n`;
  }

  // Publication blocks
  if (blocksResult.length > 0) {
    output += `### Documents by Publication Block\n\n`;
    for (const block of blocksResult) {
      output += `- **${block.short_name || block.code}**: ${Number(block.count).toLocaleString()} documents\n`;
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

This tool returns aggregate statistics about the indexed legal documents,
including document counts, coverage, and breakdown by category.

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
