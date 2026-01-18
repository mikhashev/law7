/**
 * List Countries Tool
 * List available countries in the database
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { query } from '../db/postgres.js';

// Input schema for list-countries tool
export const ListCountriesInputSchema = z.object({
  include_document_count: z.boolean().optional().default(true).describe('Include document count per country'),
});

export type ListCountriesInput = z.infer<typeof ListCountriesInputSchema>;

/**
 * Country interface
 */
export interface Country {
  id: number;
  code: string;
  name: string;
  native_name: string | null;
  document_count?: number;
}

/**
 * Execute the list-countries tool
 */
export async function executeListCountries(input: ListCountriesInput): Promise<string> {
  const { include_document_count } = input;

  let text = `
    SELECT
      c.id,
      c.code,
      c.name,
      c.native_name
      ${include_document_count ? ', COUNT(d.id) as document_count' : ''}
    FROM countries c
    ${include_document_count ? 'LEFT JOIN documents d ON c.id = d.country_id' : ''}
    GROUP BY c.id, c.code, c.name, c.native_name
    ORDER BY c.name
  `;

  const countries = await query<Country>(text);

  if (countries.length === 0) {
    return 'No countries found in the database.';
  }

  let output = `## Available Countries\n\n`;
  output += `Found ${countries.length} country/countries:\n\n`;

  for (const country of countries) {
    output += `### ${country.name}`;
    if (country.native_name) {
      output += ` (${country.native_name})`;
    }
    output += `\n`;
    output += `- **Code**: ${country.code}\n`;
    output += `- **ID**: ${country.id}\n`;

    if (include_document_count && country.document_count !== undefined) {
      output += `- **Documents**: ${country.document_count}\n`;
    }

    output += `\n`;
  }

  return output;
}

/**
 * Tool definition for MCP server
 */
export const listCountriesTool: Tool = {
  name: 'list-countries',
  description: `List available countries in the legal document database.

This tool returns a list of all countries with legal documents in the database,
along with optional document counts.

Args:
  include_document_count: Include document count per country (default: true)

Example:
  List all countries:
  { "include_document_count": true }`,
  inputSchema: {
    type: 'object',
    properties: {
      include_document_count: {
        type: 'boolean',
        description: 'Include document count per country',
        default: true,
      },
    },
    required: [],
  },
};
