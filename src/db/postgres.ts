/**
 * PostgreSQL Client for Law7 MCP Server
 * Handles database connections and queries for legal documents
 */

import pg, { Pool, PoolClient } from 'pg';
import { config } from '../config.js';

// Query result types
export interface Document {
  id: string;
  eo_number: string;
  title: string | null;
  name: string | null;
  complex_name: string | null;
  document_number: string | null;
  document_date: Date | null;
  publish_date: Date | null;
  pages_count: number | null;
  pdf_file_size: number | null;
  signatory_authority_id: string | null;
  document_type_id: string | null;
  publication_block_id: string | null;
  country_id: number;
  jd_reg_number: string | null;
  jd_reg_date: Date | null;
  created_at: Date;
  updated_at: Date;
}

export interface DocumentContent {
  document_id: string;
  full_text: string | null;
  raw_text: string | null;
  pdf_url: string | null;
  html_url: string | null;
  text_hash: string | null;
  updated_at: Date;
}

export interface SignatoryAuthority {
  id: string;
  name: string | null;
  code: string | null;
  description: string | null;
}

export interface DocumentType {
  id: string;
  name: string | null;
  code: string | null;
  description: string | null;
}

export interface PublicationBlock {
  id: string;
  short_name: string | null;
  code: string | null;
  description: string | null;
}

// Singleton pool instance
let pool: Pool | null = null;

/**
 * Get or create the PostgreSQL connection pool
 */
export function getPool(): Pool {
  if (!pool) {
    pool = new Pool({
      user: config.db.user,
      host: config.db.host,
      port: config.db.port,
      database: config.db.database,
      password: config.db.password,
      max: 20, // Maximum pool size
      idleTimeoutMillis: 30000, // Close idle clients after 30 seconds
      connectionTimeoutMillis: 2000, // Return an error after 2 seconds if connection could not be established
    });

    pool.on('error', (err) => {
      console.error('Unexpected error on idle client', err);
      process.exit(-1);
    });
  }

  return pool;
}

/**
 * Execute a SQL query and return all rows
 */
export async function query<T = any>(text: string, params?: any[]): Promise<T[]> {
  const pool = getPool();
  const start = Date.now();

  try {
    const res = await pool.query<T>(text, params);
    const duration = Date.now() - start;

    if (config.logging.level === 'debug') {
      console.log('Executed query', { text, duration, rows: res.rowCount });
    }

    return res.rows;
  } catch (error) {
    console.error('Query error', { text, error });
    throw error;
  }
}

/**
 * Get a document by eo_number
 */
export async function getDocumentByEoNumber(eoNumber: string): Promise<(Document & DocumentContent) | null> {
  const text = `
    SELECT
      d.*,
      dc.full_text,
      dc.raw_text,
      dc.pdf_url,
      dc.html_url,
      dc.text_hash
    FROM documents d
    LEFT JOIN document_content dc ON d.id = dc.document_id
    WHERE d.eo_number = $1
  `;

  const results = await query<Document & DocumentContent>(text, [eoNumber]);
  return results[0] || null;
}

/**
 * Get multiple documents by eo_numbers
 */
export async function getDocumentsByEoNumbers(eoNumbers: string[]): Promise<(Document & DocumentContent)[]> {
  if (eoNumbers.length === 0) return [];

  const text = `
    SELECT
      d.*,
      dc.full_text,
      dc.raw_text,
      dc.pdf_url,
      dc.html_url,
      dc.text_hash
    FROM documents d
    LEFT JOIN document_content dc ON d.id = dc.document_id
    WHERE d.eo_number = ANY($1)
  `;

  return query<Document & DocumentContent>(text, [eoNumbers]);
}

/**
 * Search documents by text content
 */
export async function searchDocuments(
  searchText: string,
  limit: number = 10,
  countryId?: number
): Promise<(Document & DocumentContent)[]> {
  const text = `
    SELECT
      d.*,
      dc.full_text,
      dc.raw_text,
      dc.pdf_url,
      dc.html_url,
      dc.text_hash,
      ts_rank(dc.text_search, plainto_tsquery('russian', $1)) as rank
    FROM documents d
    LEFT JOIN document_content dc ON d.id = dc.document_id
    WHERE dc.text_search @@ plainto_tsquery('russian', $1)
    ${countryId ? 'AND d.country_id = $2' : ''}
    ORDER BY rank DESC
    LIMIT $${countryId ? 3 : 2}
  `;

  const params = countryId
    ? [searchText, countryId, limit]
    : [searchText, limit];

  return query<Document & DocumentContent>(text, params);
}

/**
 * Get documents by date range
 */
export async function getDocumentsByDateRange(
  startDate: string,
  endDate: string,
  limit: number = 100
): Promise<(Document & DocumentContent)[]> {
  const text = `
    SELECT
      d.*,
      dc.full_text,
      dc.raw_text,
      dc.pdf_url,
      dc.html_url,
      dc.text_hash
    FROM documents d
    LEFT JOIN document_content dc ON d.id = dc.document_id
    WHERE d.document_date >= $1 AND d.document_date <= $2
    ORDER BY d.document_date DESC
    LIMIT $3
  `;

  return query<Document & DocumentContent>(text, [startDate, endDate, limit]);
}

/**
 * Get document count by country
 */
export async function getDocumentCount(countryId?: number): Promise<number> {
  const text = countryId
    ? 'SELECT COUNT(*) as count FROM documents WHERE country_id = $1'
    : 'SELECT COUNT(*) as count FROM documents';

  const result = await query<{ count: bigint }>(text, countryId ? [countryId] : []);
  return Number(result[0].count);
}

/**
 * Get signatory authority by ID
 */
export async function getSignatoryAuthority(id: string): Promise<SignatoryAuthority | null> {
  const text = 'SELECT * FROM signatory_authorities WHERE id = $1';
  const results = await query<SignatoryAuthority>(text, [id]);
  return results[0] || null;
}

/**
 * Get document type by ID
 */
export async function getDocumentType(id: string): Promise<DocumentType | null> {
  const text = 'SELECT * FROM document_types WHERE id = $1';
  const results = await query<DocumentType>(text, [id]);
  return results[0] || null;
}

/**
 * Get all publication blocks
 */
export async function getPublicationBlocks(): Promise<PublicationBlock[]> {
  const text = 'SELECT * FROM publication_blocks ORDER BY weight DESC';
  return query<PublicationBlock>(text);
}

/**
 * Close the connection pool
 */
export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = null;
  }
}

// Health check
export async function healthCheck(): Promise<boolean> {
  try {
    await query('SELECT 1');
    return true;
  } catch {
    return false;
  }
}
