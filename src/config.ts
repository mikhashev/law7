/**
 * Law7 MCP Server Configuration
 * TypeScript configuration for MCP server
 */

import { config as loadEnv } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// Get the directory where this script is located (works both in dev and compiled)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load environment variables from .env file (look in project root, not process.cwd())
const envPath = resolve(__dirname, '..', '.env');
loadEnv({ path: envPath });

// Database configuration
export const db = {
  user: process.env.DB_USER || 'law7',
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5433'),
  database: process.env.DB_NAME || 'law7',
  password: process.env.DB_PASSWORD || '',
  get connectionString(): string {
    if (!this.password) {
      console.error('[CONFIG] WARNING: DB_PASSWORD is not set! Database authentication will fail.');
      console.error('[CONFIG] Current working directory:', process.cwd());
      console.error('[CONFIG] DB config:', { user: this.user, host: this.host, port: this.port, database: this.database, password: '***' });
    }
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
  name: process.env.MCP_SERVER_NAME || 'law7',
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

// ---------------------------------------------------------------------------
// Secret redaction
// ---------------------------------------------------------------------------

/** Keys whose values must never be logged (password / secret / *token / *key). */
const SENSITIVE_KEY_PATTERN = /password|secret|token$|key$/i;

/** Matches the userinfo part of a URL, e.g. `postgresql://user:pass@host`. */
const URL_USERINFO_PATTERN = /([a-zA-Z][a-zA-Z0-9+.-]*:\/\/)[^/\s@]*@/g;

/** Placeholder written in place of any redacted value. */
const REDACTED = '***';

/**
 * Recursively deep-copy a value, replacing sensitive values with `***`.
 *
 * - Any property whose name matches /password|secret|token|key$/i is replaced.
 * - Any URL userinfo (`scheme://user:pass@host`) inside a string is replaced.
 *
 * Getters (such as `db.connectionString`) are evaluated during the copy, so the
 * resulting object is a plain, safe-to-log snapshot.
 */
export function redactSecrets(value: unknown, seen: WeakSet<object> = new WeakSet()): unknown {
  if (typeof value === 'string') {
    return value.replace(URL_USERINFO_PATTERN, `$1${REDACTED}@`);
  }

  if (value === null || typeof value !== 'object') {
    return value;
  }

  if (seen.has(value as object)) {
    return '[Circular]';
  }
  seen.add(value as object);

  if (Array.isArray(value)) {
    return value.map((item) => redactSecrets(item, seen));
  }

  const result: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    result[key] = SENSITIVE_KEY_PATTERN.test(key) ? REDACTED : redactSecrets(item, seen);
  }
  return result;
}

/**
 * Return a redacted deep copy of the configuration, safe for logging.
 * For a stdio MCP server stderr is the client's log channel, so the raw config
 * (which carries DB/Redis passwords) must never be written there.
 */
export function redactConfig(cfg: unknown = config): Record<string, unknown> {
  return redactSecrets(cfg) as Record<string, unknown>;
}
