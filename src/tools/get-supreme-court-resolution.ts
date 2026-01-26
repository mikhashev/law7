/**
 * Get Supreme Court Resolution Tool
 * Get specific Supreme Court plenary resolution by number or date
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query as dbQuery } from '../db/postgres.js';

// Input schema for get-supreme-court-resolution tool
export const GetSupremeCourtResolutionInputSchema = z.object({
  resolution_number: z.string().optional().describe('Resolution number (e.g., "Пленум ВС РФ от 25.12.2023 № 65")'),
  decision_date: z.string().optional().describe('Decision date (YYYY-MM-DD)'),
  case_number: z.string().optional().describe('Case number'),
});

export type GetSupremeCourtResolutionInput = z.infer<typeof GetSupremeCourtResolutionInputSchema>;

/**
 * Format Supreme Court resolution for output
 */
function formatResolution(resolution: any): string {
  const parts: string[] = [];

  parts.push(`**${resolution.title || 'Постановление Пленума Верховного Суда РФ'}**`);

  if (resolution.case_number) {
    parts.push(`Номер: ${resolution.case_number}`);
  }

  if (resolution.decision_date) {
    const date = new Date(resolution.decision_date).toLocaleDateString('ru-RU');
    parts.push(`Дата: ${date}`);
  }

  if (resolution.summary) {
    parts.push(`\nКраткое содержание:\n${resolution.summary}`);
  }

  if (resolution.legal_issues && resolution.legal_issues.length > 0) {
    parts.push(`\nПравовые вопросы:\n${resolution.legal_issues.map((q: string) => `• ${q}`).join('\n')}`);
  }

  if (resolution.articles_interpreted) {
    const articles = Object.entries(resolution.articles_interpreted)
      .map(([code, articles]) => `${code}: ${(articles as string[]).join(', ')}`)
      .join('; ');
    parts.push(`\nТолкуемые статьи:\n${articles}`);
  }

  if (resolution.binding_nature) {
    const natureMap: Record<string, string> = {
      'mandatory': 'Обязательный',
      'persuasive': 'Рекомендательный',
      'informational': 'Информационный',
    };
    parts.push(`\nХарактер: ${natureMap[resolution.binding_nature] || resolution.binding_nature}`);
  }

  if (resolution.source_url) {
    parts.push(`\nИсточник: ${resolution.source_url}`);
  }

  return parts.join('\n');
}

/**
 * Execute the get-supreme-court-resolution tool
 */
export async function executeGetSupremeCourtResolution(input: GetSupremeCourtResolutionInput): Promise<string> {
  const { resolution_number, case_number, decision_date } = input;

  // Build query conditions
  const conditions: string[] = [
    'country_code = $1',
    'court_type = $2',
    'decision_type = $3'
  ];
  const params: any[] = ['RU', 'supreme', 'plenary_resolution'];
  let paramIndex = 4;

  if (resolution_number) {
    conditions.push(`(case_number ILIKE $${paramIndex++} OR title ILIKE $${paramIndex++})`);
    const pattern = `%${resolution_number}%`;
    params.push(pattern, pattern);
  }

  if (case_number) {
    conditions.push(`case_number = $${paramIndex++}`);
    params.push(case_number);
  }

  if (decision_date) {
    conditions.push(`decision_date = $${paramIndex++}`);
    params.push(decision_date);
  }

  const whereClause = conditions.join(' AND ');

  const sql = `
    SELECT
      id, court_type, decision_type, case_number, decision_date,
      title, summary, legal_issues, articles_interpreted,
      binding_nature, source_url
    FROM court_decisions
    WHERE ${whereClause}
    ORDER BY decision_date DESC
    LIMIT 5
  `;

  try {
    const result = await dbQuery(sql, params);

    if (result.length === 0) {
      return `No Supreme Court plenary resolution found matching the criteria.`;
    }

    if (result.length === 1) {
      return formatResolution(result[0]);
    }

    // Multiple results - list them
    let output = `Found ${result.length} resolution(s):\n\n`;
    for (const doc of result) {
      output += `---\n`;
      output += `**${doc.title || 'Постановление Пленума ВС РФ'}**\n`;
      if (doc.case_number) output += `Номер: ${doc.case_number}\n`;
      if (doc.decision_date) {
        const date = new Date(doc.decision_date).toLocaleDateString('ru-RU');
        output += `Дата: ${date}\n`;
      }
      output += `\n`;
    }

    output += `\nUse specific case_number or decision_date for full details.`;
    return output.trim();
  } catch (error) {
    console.error('Error fetching Supreme Court resolution:', error);
    return `Error fetching Supreme Court resolution: ${(error as Error).message}`;
  }
}

/**
 * Tool definition for MCP server
 */
export const getSupremeCourtResolutionTool: Tool = {
  name: 'get-supreme-court-resolution',
  description: `Get specific Supreme Court plenary resolution (Постановление Пленума ВС РФ).

This tool retrieves detailed information about Supreme Court plenary resolutions,
which provide authoritative interpretations of Russian law.

Args:
  resolution_number: Resolution number (e.g., "Пленум ВС РФ от 25.12.2023 № 65")
  decision_date: Decision date (YYYY-MM-DD)
  case_number: Case number

At least one search parameter is required.

Examples:
  Get resolution by date:
  { "decision_date": "2023-12-25" }

  Get resolution by number:
  { "resolution_number": "65" }

  Get resolution by case number:
  { "case_number": "Пленум ВС РФ 2023-01-01" }`,
  inputSchema: {
    type: 'object',
    properties: {
      resolution_number: {
        type: 'string',
        description: 'Resolution number (e.g., "Пленум ВС РФ от 25.12.2023 № 65")',
      },
      decision_date: {
        type: 'string',
        description: 'Decision date (YYYY-MM-DD)',
      },
      case_number: {
        type: 'string',
        description: 'Case number',
      },
    },
  },
};
