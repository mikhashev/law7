/**
 * Fetch and Ingest Tool
 * Fetches documents from external sources (kremlin.ru) and ingests into law7 database
 *
 * Called when query-laws returns no results to fetch missing documents on-demand.
 */

import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';

// Get directory of current module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Input schema for fetch-and-ingest tool
export const FetchAndIngestInputSchema = z.object({
  query: z.string().describe('Search query in Russian (e.g., "Центральный банк", "Федеральный закон о налогах")'),
  doc_type: z.enum(['', '1', '3', '4', '5', '6', '7', '8']).optional().default('').describe(
    'Document type filter: "" = All, "1" = Code, "3" = Decree, "4" = Order, "5" = Federal Law, "6" = Constitutional Federal Law, "7" = Message, "8" = Constitutional Amendment'
  ),
  max_results: z.number().optional().default(10).describe('Maximum number of results to fetch and ingest'),
  persist: z.boolean().optional().default(true).describe('Whether to save documents to database (set false for preview only)'),
  fetch_content: z.boolean().optional().default(true).describe('Whether to fetch full text content (set false for faster metadata-only search)'),
  search_mode: z.enum(['text', 'title']).optional().default('text').describe(
    'Search mode: "text" for full-text search in document content, "title" for title/number only'
  ),
});

export type FetchAndIngestInput = z.infer<typeof FetchAndIngestInputSchema>;

/**
 * Execute the Python search_and_ingest script
 */
export async function executeFetchAndIngest(input: FetchAndIngestInput): Promise<string> {
  const { query, doc_type, max_results, persist, fetch_content, search_mode } = input;

  // Path to Python script (relative to dist/tools/)
  const scriptPath = path.resolve(__dirname, '../../scripts/search_and_ingest.py');

  // Build command arguments
  const args = [
    scriptPath,
    '--query', query,
    '--max', String(max_results),
    '--mode', search_mode || 'text',
    '--json',
  ];

  if (doc_type) {
    args.push('--type', doc_type);
  }

  if (!persist) {
    args.push('--no-persist');
  }

  if (!fetch_content) {
    args.push('--no-content');
  }

  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';

    // Spawn Python process
    const pythonProcess = spawn('python', args, {
      cwd: path.resolve(__dirname, '../..'),
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
      },
    });

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('error', (error) => {
      reject(new Error(`Failed to spawn Python process: ${error.message}`));
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Python script failed with code ${code}: ${stderr}`));
        return;
      }

      try {
        // Parse JSON output
        const result = JSON.parse(stdout);
        resolve(formatResult(result));
      } catch (error) {
        // If JSON parsing fails, return raw output
        resolve(`Raw output:\n${stdout}\n\nStderr:\n${stderr}`);
      }
    });

    // Set timeout (5 minutes for large fetches)
    setTimeout(() => {
      pythonProcess.kill();
      reject(new Error('Fetch and ingest timed out after 5 minutes'));
    }, 5 * 60 * 1000);
  });
}

/**
 * Format the result for MCP output
 */
function formatResult(result: any): string {
  const lines: string[] = [];

  lines.push(`## Fetch and Ingest Results`);
  lines.push(``);
  lines.push(`**Query:** ${result.query}`);
  lines.push(`**Document Type:** ${result.doc_type || 'All'}`);
  lines.push(`**Search Mode:** ${result.search_mode || 'text'}`);
  lines.push(`**Timestamp:** ${result.timestamp}`);
  lines.push(``);
  lines.push(`**Summary:**`);
  lines.push(`- Total found: ${result.total_found}`);
  lines.push(`- Processed: ${result.processed}`);
  lines.push(`- Ingested: ${result.ingested}`);
  lines.push(`- Skipped: ${result.skipped}`);
  lines.push(`- Errors: ${result.errors}`);
  lines.push(``);

  if (result.documents && result.documents.length > 0) {
    lines.push(`**Documents:**`);
    lines.push(``);

    for (const doc of result.documents) {
      const status = doc.ingested ? '[INGESTED]' : doc.skipped ? '[SKIPPED]' : '[ERROR]';
      lines.push(`### ${status} ${doc.eo_number}`);
      lines.push(`**Title:** ${doc.title}`);
      lines.push(`**URL:** ${doc.url}`);

      if (doc.document_id) {
        lines.push(`**Document ID:** ${doc.document_id}`);
      }

      if (doc.reason) {
        lines.push(`**Reason:** ${doc.reason}`);
      }

      if (doc.error) {
        lines.push(`**Error:** ${doc.error}`);
      }

      lines.push(``);
    }
  }

  if (result.ingested > 0) {
    lines.push(`---`);
    lines.push(`Documents are now available in the database. Use \`query-laws\` to search them.`);
  }

  return lines.join('\n');
}

/**
 * Tool definition for MCP server
 */
export const fetchAndIngestTool: Tool = {
  name: 'fetch-and-ingest',
  description: `Fetch legal documents from external sources (kremlin.ru) and ingest into law7 database.

Use this tool when:
- query-laws returns no results for a user's question
- The user asks about a legal topic that might not be in the database yet

This tool searches kremlin.ru (official Russian legal document portal) for documents matching the query,
fetches their full text, and stores them in the law7 database for future queries.

Document Types (doc_type parameter):
- "" = All types
- "1" = Code (Кодекс)
- "3" = Decree (Указ)
- "4" = Order (Распоряжение)
- "5" = Federal Law (Федеральный закон) - MOST COMMON
- "6" = Constitutional Federal Law (Федеральный конституционный закон)
- "7" = Message (Послание)
- "8" = Constitutional Amendment (Закон о поправке к Конституции)

Examples:
  Fetch federal laws about banking:
  { "query": "Центральный банк", "doc_type": "5", "max_results": 5 }

  Preview without saving:
  { "query": "налоги", "doc_type": "5", "persist": false }`,
  inputSchema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Search query in Russian',
      },
      doc_type: {
        type: 'string',
        enum: ['', '1', '3', '4', '5', '6', '7', '8'],
        default: '',
        description: 'Document type filter',
      },
      max_results: {
        type: 'number',
        description: 'Maximum number of results to fetch',
        default: 10,
      },
      persist: {
        type: 'boolean',
        description: 'Whether to save to database',
        default: true,
      },
      fetch_content: {
        type: 'boolean',
        description: 'Whether to fetch full text content',
        default: true,
      },
      search_mode: {
        type: 'string',
        enum: ['text', 'title'],
        default: 'text',
        description: 'Search mode: "text" for full-text search, "title" for title/number only',
      },
    },
    required: ['query'],
  },
};
