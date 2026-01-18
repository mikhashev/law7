/**
 * Get Law Tool
 * Retrieve a specific legal document by ID
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { getDocumentByEoNumber } from '../db/postgres.js';

// Input schema for get-law tool
export const GetLawInputSchema = z.object({
  eo_number: z.string().describe('Document eoNumber (e.g., "0001202601170001")'),
  include_content: z.boolean().optional().default(true).describe('Include full document text'),
});

export type GetLawInput = z.infer<typeof GetLawInputSchema>;

/**
 * Format a document for output
 */
function formatDocument(doc: any, includeContent: boolean): string {
  const parts: string[] = [];

  // Header
  parts.push(`# ${doc.complex_name || doc.title || 'Untitled Document'}`);
  parts.push('');

  // Metadata
  parts.push('## Metadata');
  parts.push(`- **ID**: ${doc.eo_number}`);
  parts.push(`- **Database ID**: ${doc.id}`);

  if (doc.document_number) {
    parts.push(`- **Number**: ${doc.document_number}`);
  }

  if (doc.document_date) {
    const date = new Date(doc.document_date).toLocaleDateString('ru-RU');
    parts.push(`- **Document Date**: ${date}`);
  }

  if (doc.publish_date) {
    const date = new Date(doc.publish_date).toLocaleDateString('ru-RU');
    parts.push(`- **Publish Date**: ${date}`);
  }

  if (doc.pages_count) {
    parts.push(`- **Pages**: ${doc.pages_count}`);
  }

  if (doc.signatory_authority_id) {
    parts.push(`- **Signatory Authority ID**: ${doc.signatory_authority_id}`);
  }

  if (doc.document_type_id) {
    parts.push(`- **Document Type ID**: ${doc.document_type_id}`);
  }

  parts.push('');

  // Content
  if (includeContent && doc.full_text) {
    parts.push('## Content');
    parts.push(doc.full_text);
    parts.push('');
  }

  // Links
  parts.push('## Links');

  if (doc.pdf_url) {
    parts.push(`- [PDF](${doc.pdf_url})`);
  }

  if (doc.html_url) {
    parts.push(`- [HTML View](${doc.html_url})`);
  }

  // Search info
  if (doc.text_hash) {
    parts.push('');
    parts.push(`**Text Hash**: ${doc.text_hash}`);
  }

  return parts.join('\n');
}

/**
 * Execute the get-law tool
 */
export async function executeGetLaw(input: GetLawInput): Promise<string> {
  const { eo_number, include_content } = input;

  const doc = await getDocumentByEoNumber(eo_number);

  if (!doc) {
    return `Document not found: ${eo_number}`;
  }

  return formatDocument(doc, include_content);
}

/**
 * Tool definition for MCP server
 */
export const getLawTool: Tool = {
  name: 'get-law',
  description: `Retrieve a specific legal document by its eoNumber.

This tool fetches a single legal document and returns its metadata and full text content.

Args:
  eo_number: Document eoNumber (e.g., "0001202601170001")
  include_content: Include full document text in response (default: true)

Example:
  Get a specific document:
  { "eo_number": "0001202601170001", "include_content": true }`,
  inputSchema: {
    type: 'object',
    properties: {
      eo_number: {
        type: 'string',
        description: 'Document eoNumber (e.g., "0001202601170001")',
      },
      include_content: {
        type: 'boolean',
        description: 'Include full document text in response',
        default: true,
      },
    },
    required: ['eo_number'],
  },
};
