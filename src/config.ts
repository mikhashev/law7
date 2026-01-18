/**
 * Laws-Context7 MCP Server Configuration
 * TypeScript configuration for MCP server
 */

import { config as loadEnv } from 'dotenv';
import { resolve } from 'path';

// Load environment variables from .env file
const envPath = resolve(process.cwd(), '.env');
loadEnv({ path: envPath });

// Database configuration
export const db = {
  user: process.env.DB_USER || 'laws_context7',
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5433'),
  database: process.env.DB_NAME || 'laws_context7',
  password: process.env.DB_PASSWORD || '',
  get connectionString(): string {
    return `postgresql://${this.user}:${this.password}@${this.host}:${this.port}/${this.database}`;
  }
};

// Qdrant configuration
export const qdrant = {
  url: process.env.QDRANT_URL || 'http://localhost:6333',
  collectionName: process.env.QDRANT_COLLECTION || 'law_chunks',
  vectorSize: parseInt(process.env.QDRANT_VECTOR_SIZE || '1024'),
};

// Redis configuration
export const redis = {
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT || '6380'),
  password: process.env.REDIS_PASSWORD || '',
  ttl: parseInt(process.env.REDIS_TTL || '3600'), // 1 hour default
};

// MCP Server configuration
export const server = {
  name: process.env.MCP_SERVER_NAME || 'laws-context7',
  version: process.env.MCP_SERVER_VERSION || '0.1.0',
};

// Search configuration
export const search = {
  defaultMaxResults: parseInt(process.env.DEFAULT_MAX_RESULTS || '10'),
  defaultMaxTokens: parseInt(process.env.DEFAULT_MAX_TOKENS || '10000'),
  hybridSearchEnabled: process.env.HYBRID_SEARCH_ENABLED === 'true',
  semanticWeight: parseFloat(process.env.SEMANTIC_WEIGHT || '0.7'),
  keywordWeight: parseFloat(process.env.KEYWORD_WEIGHT || '0.3'),
};

// Logging configuration
export const logging = {
  level: process.env.LOG_LEVEL || 'info',
  format: process.env.LOG_FORMAT || 'json', // 'json' or 'text'
};

// Export all configuration
export const config = {
  db,
  qdrant,
  redis,
  server,
  search,
  logging,
} as const;

// Type exports
export type Config = typeof config;
