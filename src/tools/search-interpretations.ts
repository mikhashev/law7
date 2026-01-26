/**
 * Search Interpretations Tool
 * Search for official ministry interpretations (letters, guidance)
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query as dbQuery } from '../db/postgres.js';

// Input schema for search-interpretations tool
export const SearchInterpretationsInputSchema = z.object({
  agency: z.enum(['Минфин', 'ФНС', 'Роструд', 'all']).optional().default('all').describe('Government agency'),
  document_type: z.string().optional().describe('Document type (e.g., "letter", "guidance", "instruction")'),
  legal_topic: z.string().optional().describe('Legal topic (e.g., "tax", "labor")'),
  query: z.string().optional().describe('Search query text'),
  start_date: z.string().optional().describe('Filter from this date (YYYY-MM-DD)'),
  end_date: z.string().optional().describe('Filter until this date (YYYY-MM-DD)'),
  max_results: z.number().optional().default(10).describe('Maximum number of results to return'),
});

export type SearchInterpretationsInput = z.infer<typeof SearchInterpretationsInputSchema>;

/**
 * Format ministry interpretation for output
 */
function formatInterpretation(doc: any): string {
  const parts: string[] = [];

  if (doc.title) {
    parts.push(`**${doc.title}**`);
  }

  parts.push(`Ведомство: ${doc.agency_name_short}`);

  if (doc.document_type) {
    const typeMap: Record<string, string> = {
      'letter': 'Письмо',
      'guidance': 'Разъяснение',
      'instruction': 'Инструкция',
      'explanation': 'Пояснение',
    };
    parts.push(`Тип: ${typeMap[doc.document_type] || doc.document_type}`);
  }

  if (doc.document_number) {
    parts.push(`Номер: ${doc.document_number}`);
  }

  if (doc.document_date) {
    const date = new Date(doc.document_date).toLocaleDateString('ru-RU');
    parts.push(`Дата: ${date}`);
  }

  if (doc.legal_topic) {
    parts.push(`Тема: ${doc.legal_topic}`);
  }

  if (doc.binding_nature) {
    const natureMap: Record<string, string> = {
      'official': 'Официальное',
      'informational': 'Информационное',
      'recommendation': 'Рекомендательное',
    };
    parts.push(`Характер: ${natureMap[doc.binding_nature] || doc.binding_nature}`);
  }

  if (doc.question) {
    parts.push(`\nВопрос:\n${doc.question}`);
  }

  if (doc.answer) {
    parts.push(`\nОтвет:\n${doc.answer}`);
  }

  if (doc.related_laws) {
    const laws = Object.entries(doc.related_laws)
      .map(([law, refs]) => `${law}: ${(refs as string[]).join(', ')}`)
      .join('; ');
    parts.push(`\nСвязанные нормы:\n${laws}`);
  }

  if (doc.source_url) {
    parts.push(`\nИсточник: ${doc.source_url}`);
  }

  return parts.join('\n');
}

/**
 * Execute the search-interpretations tool
 */
export async function executeSearchInterpretations(input: SearchInterpretationsInput): Promise<string> {
  const { agency, document_type, legal_topic, query, start_date, end_date, max_results } = input;

  // Build query conditions
  const conditions: string[] = ['oi.country_code = $1'];
  const params: any[] = ['RU'];
  let paramIndex = 2;

  if (agency && agency !== 'all') {
    conditions.push(`ga.agency_name_short = $${paramIndex++}`);
    params.push(agency);
  }

  if (document_type) {
    conditions.push(`oi.document_type = $${paramIndex++}`);
    params.push(document_type);
  }

  if (legal_topic) {
    conditions.push(`oi.legal_topic ILIKE $${paramIndex++}`);
    params.push(`%${legal_topic}%`);
  }

  if (query) {
    conditions.push(`(oi.title ILIKE $${paramIndex++} OR oi.question ILIKE $${paramIndex++} OR oi.answer ILIKE $${paramIndex++})`);
    const queryPattern = `%${query}%`;
    params.push(queryPattern, queryPattern, queryPattern);
  }

  if (start_date) {
    conditions.push(`oi.document_date >= $${paramIndex++}`);
    params.push(start_date);
  }

  if (end_date) {
    conditions.push(`oi.document_date <= $${paramIndex++}`);
    params.push(end_date);
  }

  const whereClause = conditions.join(' AND ');

  const sql = `
    SELECT
      oi.id, oi.document_type, oi.document_number, oi.document_date,
      oi.title, oi.question, oi.answer, oi.legal_topic,
      oi.related_laws, oi.binding_nature, oi.validity_status, oi.source_url,
      ga.agency_name_short
    FROM official_interpretations oi
    JOIN government_agencies ga ON oi.agency_id = ga.id
    WHERE ${whereClause}
    ORDER BY oi.document_date DESC
    LIMIT $${paramIndex}
  `;

  params.push(max_results);

  try {
    const result = await dbQuery(sql, params);

    if (result.length === 0) {
      return `No ministry interpretations found matching the criteria.`;
    }

    let output = `Found ${result.length} interpretation(s)\n\n`;

    for (const doc of result) {
      output += `---\n`;
      output += formatInterpretation(doc);
      output += `\n\n`;
    }

    return output.trim();
  } catch (error) {
    console.error('Error searching interpretations:', error);
    return `Error searching interpretations: ${(error as Error).message}`;
  }
}

/**
 * Tool definition for MCP server
 */
export const searchInterpretationsTool: Tool = {
  name: 'search-interpretations',
  description: `Search for official ministry interpretations (letters, guidance).

This tool searches the official_interpretations table which contains official
letters and guidance from Russian government agencies.

Phase 7C covers interpretations from:
- Минфин (Ministry of Finance) - tax law interpretations
- ФНС (Federal Tax Service) - tax procedure clarifications
- Роструд (Rostrud) - labor law interpretations

Scope: Last 5 years of interpretations

Args:
  agency: Filter by agency ("Минфин", "ФНС", "Роструд", or "all")
  document_type: Filter by document type ("letter", "guidance", "instruction")
  legal_topic: Filter by legal topic (e.g., "tax", "labor")
  query: Search query text (searches in title, question, answer)
  start_date: Filter from this date (YYYY-MM-DD)
  end_date: Filter until this date (YYYY-MM-DD)
  max_results: Maximum number of results to return (default: 10)

Examples:
  Search Minfin tax interpretations:
  { "agency": "Минфин", "legal_topic": "tax", "max_results": 5 }

  Search Rostrud labor guidance:
  { "agency": "Роструд", "query": "employment contract", "max_results": 10 }

  Search all agencies for VAT-related letters:
  { "query": "VAT НДС", "document_type": "letter", "max_results": 20 }`,
  inputSchema: {
    type: 'object',
    properties: {
      agency: {
        type: 'string',
        enum: ['Минфин', 'ФНС', 'Роструд', 'all'],
        description: 'Government agency',
        default: 'all',
      },
      document_type: {
        type: 'string',
        description: 'Document type (e.g., "letter", "guidance", "instruction")',
      },
      legal_topic: {
        type: 'string',
        description: 'Legal topic (e.g., "tax", "labor")',
      },
      query: {
        type: 'string',
        description: 'Search query text (searches in title, question, answer)',
      },
      start_date: {
        type: 'string',
        description: 'Filter from this date (YYYY-MM-DD)',
      },
      end_date: {
        type: 'string',
        description: 'Filter until this date (YYYY-MM-DD)',
      },
      max_results: {
        type: 'number',
        description: 'Maximum number of results to return',
        default: 10,
      },
    },
  },
};
