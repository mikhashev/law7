/**
 * Query Laws Tool
 * Search for legal documents using semantic and keyword search
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { search } from '../db/qdrant.js';
import { searchDocuments } from '../db/postgres.js';
import { config } from '../config.js';

// Input schema for query-laws tool
export const QueryLawsInputSchema = z.object({
  country_code: z.string().optional().default('RU').describe('Country code (ISO 3166-1 alpha-2, e.g., "RU", "US")'),
  query: z.string().describe('Search query for finding relevant legal documents'),
  max_results: z.number().optional().default(10).describe('Maximum number of results to return'),
  use_hybrid: z.boolean().optional().default(false).describe('Use hybrid search (keyword + semantic)'),
});

export type QueryLawsInput = z.infer<typeof QueryLawsInputSchema>;

/**
 * Format a document for output
 */
function formatDocument(doc: any): string {
  const parts: string[] = [];

  if (doc.complex_name) {
    parts.push(`**${doc.complex_name}**`);
  } else if (doc.title) {
    parts.push(`**${doc.title}**`);
  }

  if (doc.name && doc.name !== doc.complex_name) {
    parts.push(`*${doc.name}*`);
  }

  if (doc.document_date) {
    const date = new Date(doc.document_date).toLocaleDateString('ru-RU');
    parts.push(`Дата: ${date}`);
  }

  if (doc.document_number) {
    parts.push(`Номер: ${doc.document_number}`);
  }

  if (doc.full_text) {
    parts.push(`\nТекст:\n${doc.full_text}`);
  }

  if (doc.pdf_url) {
    parts.push(`\nPDF: ${doc.pdf_url}`);
  }

  if (doc.html_url) {
    parts.push(`HTML: ${doc.html_url}`);
  }

  return parts.join('\n');
}

/**
 * Execute the query-laws tool
 */
export async function executeQueryLaws(input: QueryLawsInput): Promise<string> {
  const { country_code, query, max_results, use_hybrid } = input;

  // For now, use keyword search since we don't have embedding generation in MCP server yet
  // TODO: Add embedding generation for semantic search

  const results = await searchDocuments(query, max_results, undefined, country_code);

  if (results.length === 0) {
    return `No documents found for query: "${query}"`;
  }

  let output = `Found ${results.length} document(s) for query: "${query}"\n\n`;

  for (const doc of results) {
    output += `---\n`;
    output += `ID: ${doc.eo_number}\n`;
    output += formatDocument(doc);
    output += `\n\n`;
  }

  return output;
}

/**
 * Tool definition for MCP server
 */
export const queryLawsTool: Tool = {
  name: 'query-laws',
  description: `Search for INDIVIDUAL legal documents (laws, decrees, resolutions, court decisions, regulations) using full-text search.

⚠️ IMPORTANT - Choose the RIGHT tool:
❌ DO NOT use this for queries about specific code articles (e.g., "Constitution article 1", "Civil Code article 420")
   → For consolidated legal codes with articles, use get-article-version instead
❌ DO NOT use this for code structure or code listings
   → Use get-code-structure instead
✅ USE this for individual legal acts, court decisions, published documents
   → Examples: "federal law about taxes", "presidential decree", "court decision N100"

This tool searches the documents table which contains individual legal publications.

Args:
  country_code: Country code (ISO 3166-1 alpha-2, e.g., "RU", "US") to search within (default: "RU")
  query: Search query text (keywords or phrases)
  max_results: Maximum number of results to return (default: 10)
  use_hybrid: Enable hybrid keyword + semantic search (default: false)

Examples:
  Search for documents about labor:
  { "country_code": "RU", "query": "labor contract", "max_results": 5 }

  ❌ WRONG: "Constitution article 1" → Use get-article-version with code_id instead
  ❌ WRONG: "Civil Code article 420" → Use get-article-version instead`,
  inputSchema: {
    type: 'object',
    properties: {
      country_code: {
        type: 'string',
        description: 'Country code (ISO 3166-1 alpha-2, e.g., "RU", "US")',
        default: 'RU',
      },
      query: {
        type: 'string',
        description: 'Search query for finding relevant legal documents',
      },
      max_results: {
        type: 'number',
        description: 'Maximum number of results to return',
        default: 10,
      },
      use_hybrid: {
        type: 'boolean',
        description: 'Use hybrid search (keyword + semantic)',
        default: false,
      },
    },
    required: ['query'],
  },
};
