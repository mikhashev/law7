/**
 * Search Court Decisions Tool
 * Search for Supreme Court and Constitutional Court decisions
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query as dbQuery } from '../db/postgres.js';

// Input schema for search-court-decisions tool
export const SearchCourtDecisionsInputSchema = z.object({
  court_type: z.enum(['supreme', 'constitutional']).optional().describe('Court type: "supreme" or "constitutional"'),
  decision_type: z.string().optional().describe('Decision type (e.g., "plenary_resolution", "ruling", "determination")'),
  case_number: z.string().optional().describe('Specific case number'),
  query: z.string().optional().describe('Search query text (searches in title, summary, legal_issues)'),
  start_date: z.string().optional().describe('Filter decisions from this date (YYYY-MM-DD)'),
  end_date: z.string().optional().describe('Filter decisions until this date (YYYY-MM-DD)'),
  max_results: z.number().optional().default(10).describe('Maximum number of results to return'),
});

export type SearchCourtDecisionsInput = z.infer<typeof SearchCourtDecisionsInputSchema>;

/**
 * Format court decision for output
 */
function formatCourtDecision(doc: any): string {
  const parts: string[] = [];

  parts.push(`**${doc.title || 'Без названия'}**`);

  if (doc.court_type === 'supreme') {
    parts.push(`Суд: Верховный Суд РФ`);
  } else if (doc.court_type === 'constitutional') {
    parts.push(`Суд: Конституционный Суд РФ`);
  }

  if (doc.decision_type) {
    const typeMap: Record<string, string> = {
      'plenary_resolution': 'Постановление Пленума',
      'ruling': 'Постановление',
      'determination': 'Определение',
      'review': 'Обзор',
    };
    parts.push(`Тип: ${typeMap[doc.decision_type] || doc.decision_type}`);
  }

  if (doc.case_number) {
    parts.push(`Номер дела: ${doc.case_number}`);
  }

  if (doc.decision_date) {
    const date = new Date(doc.decision_date).toLocaleDateString('ru-RU');
    parts.push(`Дата: ${date}`);
  }

  if (doc.binding_nature) {
    const natureMap: Record<string, string> = {
      'mandatory': 'Обязательный',
      'persuasive': 'Рекомендательный',
      'informational': 'Информационный',
    };
    parts.push(`Характер: ${natureMap[doc.binding_nature] || doc.binding_nature}`);
  }

  if (doc.legal_issues && doc.legal_issues.length > 0) {
    parts.push(`\nПравовые вопросы:\n${doc.legal_issues.map((q: string) => `• ${q}`).join('\n')}`);
  }

  if (doc.summary) {
    parts.push(`\nКраткое содержание:\n${doc.summary}`);
  }

  if (doc.source_url) {
    parts.push(`\nИсточник: ${doc.source_url}`);
  }

  return parts.join('\n');
}

/**
 * Execute the search-court-decisions tool
 */
export async function executeSearchCourtDecisions(input: SearchCourtDecisionsInput): Promise<string> {
  const { court_type, decision_type, case_number, query, start_date, end_date, max_results } = input;

  // Build query conditions
  const conditions: string[] = ['country_code = $1'];
  const params: any[] = ['RU'];
  let paramIndex = 2;

  if (court_type) {
    conditions.push(`court_type = $${paramIndex++}`);
    params.push(court_type);
  }

  if (decision_type) {
    conditions.push(`decision_type = $${paramIndex++}`);
    params.push(decision_type);
  }

  if (case_number) {
    conditions.push(`case_number = $${paramIndex++}`);
    params.push(case_number);
  }

  if (query) {
    conditions.push(`(title ILIKE $${paramIndex++} OR summary ILIKE $${paramIndex++} OR legal_issues::text ILIKE $${paramIndex++})`);
    const queryPattern = `%${query}%`;
    params.push(queryPattern, queryPattern, queryPattern);
  }

  if (start_date) {
    conditions.push(`decision_date >= $${paramIndex++}`);
    params.push(start_date);
  }

  if (end_date) {
    conditions.push(`decision_date <= $${paramIndex++}`);
    params.push(end_date);
  }

  const whereClause = conditions.join(' AND ');

  const sql = `
    SELECT
      id, court_type, court_level, decision_type,
      case_number, decision_date, title, summary,
      legal_issues, binding_nature, source_url
    FROM court_decisions
    WHERE ${whereClause}
    ORDER BY decision_date DESC
    LIMIT $${paramIndex}
  `;

  params.push(max_results);

  try {
    const result = await dbQuery(sql, params);

    if (result.length === 0) {
      return `No court decisions found matching the criteria.`;
    }

    let output = `Found ${result.length} court decision(s)\n\n`;

    for (const doc of result) {
      output += `---\n`;
      output += formatCourtDecision(doc);
      output += `\n\n`;
    }

    return output.trim();
  } catch (error) {
    console.error('Error searching court decisions:', error);
    return `Error searching court decisions: ${(error as Error).message}`;
  }
}

/**
 * Tool definition for MCP server
 */
export const searchCourtDecisionsTool: Tool = {
  name: 'search-court-decisions',
  description: `Search for Supreme Court and Constitutional Court decisions.

This tool searches the court_decisions table which contains decisions from:
- Supreme Court of Russian Federation (Верховный Суд РФ)
- Constitutional Court of Russian Federation (Конституционный Суд РФ)

Phase 7C covers:
- Supreme Court: Plenary resolutions, practice reviews
- Constitutional Court: Rulings, determinations with legal positions

Args:
  court_type: Filter by court type ("supreme" or "constitutional")
  decision_type: Filter by decision type (e.g., "plenary_resolution", "ruling", "determination")
  case_number: Specific case number to retrieve
  query: Search query text (searches in title, summary, legal_issues)
  start_date: Filter decisions from this date (YYYY-MM-DD)
  end_date: Filter decisions until this date (YYYY-MM-DD)
  max_results: Maximum number of results to return (default: 10)

Examples:
  Search Supreme Court plenary resolutions:
  { "court_type": "supreme", "decision_type": "plenary_resolution", "max_results": 5 }

  Search Constitutional Court rulings about taxes:
  { "court_type": "constitutional", "query": "tax", "max_results": 10 }

  Get specific case:
  { "case_number": "Пленум ВС РФ 2023-01-01" }`,
  inputSchema: {
    type: 'object',
    properties: {
      court_type: {
        type: 'string',
        enum: ['supreme', 'constitutional'],
        description: 'Court type: "supreme" or "constitutional"',
      },
      decision_type: {
        type: 'string',
        description: 'Decision type (e.g., "plenary_resolution", "ruling", "determination")',
      },
      case_number: {
        type: 'string',
        description: 'Specific case number',
      },
      query: {
        type: 'string',
        description: 'Search query text (searches in title, summary, legal_issues)',
      },
      start_date: {
        type: 'string',
        description: 'Filter decisions from this date (YYYY-MM-DD)',
      },
      end_date: {
        type: 'string',
        description: 'Filter decisions until this date (YYYY-MM-DD)',
      },
      max_results: {
        type: 'number',
        description: 'Maximum number of results to return',
        default: 10,
      },
    },
  },
};
