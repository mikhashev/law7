/**
 * Document Models for Law7 MCP Server
 * Type definitions for legal documents
 */

import type { Document, DocumentContent } from '../db/postgres.js';

/**
 * Combined document with content
 */
export interface LawDocument extends Document, DocumentContent {}

/**
 * Document search result
 */
export interface DocumentSearchResult {
  id: string;
  eo_number: string;
  title: string | null;
  name: string | null;
  complex_name: string | null;
  document_date: Date | null;
  publish_date: Date | null;
  score?: number;
  full_text: string | null;
  pdf_url: string | null;
  html_url: string | null;
}

/**
 * Document with relations
 */
export interface DocumentWithRelations extends Document {
  signatory_authority?: {
    id: string;
    name: string | null;
    code: string | null;
  } | null;
  document_type?: {
    id: string;
    name: string | null;
    code: string | null;
  } | null;
  publication_block?: {
    id: string;
    short_name: string | null;
    code: string | null;
  } | null;
  content?: DocumentContent | null;
}

/**
 * Document chunk for embeddings
 */
export interface DocumentChunk {
  chunk_id: string;
  document_id: string;
  chunk_text: string;
  chunk_index: number;
  embedding?: number[];
  embedding_size?: number;
}

/**
 * Query parameters for document search
 */
export interface DocumentQuery {
  country_id?: number;
  date_from?: string;
  date_to?: string;
  document_type_id?: string;
  signatory_authority_id?: string;
  publication_block_id?: string;
  search_text?: string;
  limit?: number;
  offset?: number;
}

/**
 * Semantic search result
 */
export interface SemanticSearchResult {
  document_id: string;
  score: number;
  chunk_text?: string;
  chunk_index?: number;
  document?: Partial<Document>;
}

/**
 * Hybrid search result (keyword + semantic)
 */
export interface HybridSearchResult {
  document_id: string;
  combined_score: number;
  keyword_score?: number;
  semantic_score?: number;
  document?: Partial<Document>;
  chunk_text?: string;
}
