/**
 * Tests for the MCP server request plumbing.
 *
 * These drive the real `createServer()` over an in-memory transport, so they
 * cover what a client actually gets - in particular that tool arguments are run
 * through each tool's zod schema (applying documented defaults) instead of being
 * cast with `args as any`.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';

vi.mock('../db/postgres.js', () => ({
  query: vi.fn().mockResolvedValue([]),
  getDocumentByEoNumber: vi.fn(),
  getDocumentCount: vi.fn().mockResolvedValue(0),
  getCountryIdFromCode: vi.fn().mockResolvedValue(null),
  searchDocuments: vi.fn().mockResolvedValue([]),
}));

vi.mock('../db/qdrant.js', () => ({
  getPointCount: vi.fn().mockResolvedValue(0),
}));

vi.mock('../db/consolidation_queries.js', () => ({
  getCurrentArticleVersion: vi.fn(),
  getArticleVersionOnDate: vi.fn(),
  getAmendmentChain: vi.fn(),
  getAmendmentApplications: vi.fn(),
  getAmendmentApplicationCount: vi.fn().mockResolvedValue(0),
  getCodeStructure: vi.fn(),
  listConsolidatedCodes: vi.fn().mockResolvedValue([]),
}));

import { createServer } from '../server.js';
import { getDocumentByEoNumber } from '../db/postgres.js';

const SAMPLE_DOCUMENT = {
  id: 'doc-1',
  eo_number: '0001202512290061',
  title: 'Test Federal Law',
  complex_name: 'Федеральный закон о тестировании',
  document_number: '123-ФЗ',
  document_date: new Date('2025-12-29'),
  publish_date: new Date('2025-12-29'),
  pages_count: 4,
  full_text: 'THE FULL BODY TEXT OF THE ACT',
  pdf_url: 'http://example.invalid/doc.pdf',
  html_url: null,
  text_hash: 'hash-1',
};

async function connectedClient() {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const server = createServer();
  const client = new Client({ name: 'test-client', version: '0.0.0' }, { capabilities: {} });

  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);

  return client;
}

/** Concatenate the text blocks of a tools/call result. */
function textOf(result: any): string {
  return (result.content ?? [])
    .filter((block: any) => block.type === 'text')
    .map((block: any) => block.text)
    .join('\n');
}

describe('MCP server tool dispatch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDocumentByEoNumber).mockResolvedValue(SAMPLE_DOCUMENT as any);
  });

  it('should list all registered tools', async () => {
    const client = await connectedClient();

    const { tools } = await client.listTools();
    const names = tools.map((tool) => tool.name);

    expect(names).toContain('get-law');
    expect(names).toContain('query-laws');
    expect(names).toContain('get-statistics');
    // use_hybrid was removed from query-laws: the advertised schema must agree.
    const queryLaws = tools.find((tool) => tool.name === 'query-laws');
    expect(Object.keys(queryLaws!.inputSchema.properties ?? {})).not.toContain('use_hybrid');
  });

  it('should apply schema defaults: get-law without include_content returns content', async () => {
    const client = await connectedClient();

    const result = await client.callTool({
      name: 'get-law',
      arguments: { eo_number: '0001202512290061' },
    });

    expect(result.isError).toBeFalsy();
    const text = textOf(result);
    expect(text).toContain('## Content');
    expect(text).toContain('THE FULL BODY TEXT OF THE ACT');
  });

  it('should honour include_content: false', async () => {
    const client = await connectedClient();

    const result = await client.callTool({
      name: 'get-law',
      arguments: { eo_number: '0001202512290061', include_content: false },
    });

    const text = textOf(result);
    expect(text).toContain('0001202512290061');
    expect(text).not.toContain('## Content');
    expect(text).not.toContain('THE FULL BODY TEXT OF THE ACT');
  });

  it('should reject invalid arguments with the zod issues', async () => {
    const client = await connectedClient();

    const result = await client.callTool({
      name: 'get-law',
      arguments: { include_content: 'yes' },
    });

    expect(result.isError).toBe(true);
    const text = textOf(result);
    expect(text).toContain('Invalid arguments for tool "get-law"');
    expect(text).toContain('eo_number');
    expect(text).toContain('include_content');
    // Nothing should have reached the database.
    expect(getDocumentByEoNumber).not.toHaveBeenCalled();
  });

  it('should reject an unknown tool name', async () => {
    const client = await connectedClient();

    const result = await client.callTool({ name: 'no-such-tool', arguments: {} });

    expect(result.isError).toBe(true);
    expect(textOf(result)).toContain('Unknown tool: no-such-tool');
  });
});
