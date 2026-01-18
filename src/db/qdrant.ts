/**
 * Qdrant Client for Law7 MCP Server
 * Handles vector storage and similarity search for legal documents
 */

import { QdrantClient } from '@qdrant/js-client-rest';
import { config } from '../config.js';

// Types for Qdrant operations
export interface Point {
  id: string;
  vector: number[];
  payload?: Record<string, any>;
}

export interface SearchResult {
  id: string;
  score: number;
  payload?: Record<string, any>;
}

export interface SearchOptions {
  limit?: number;
  scoreThreshold?: number;
  filter?: Record<string, any>;
}

// Singleton client instance
let client: QdrantClient | null = null;

/**
 * Get or create the Qdrant client
 */
export function getClient(): QdrantClient {
  if (!client) {
    client = new QdrantClient({
      url: config.qdrant.url,
    });
  }
  return client;
}

/**
 * Create the collection if it doesn't exist
 */
export async function ensureCollection(): Promise<void> {
  const client = getClient();

  try {
    await client.getCollection(config.qdrant.collectionName);
    console.log(`Collection ${config.qdrant.collectionName} already exists`);
  } catch {
    // Collection doesn't exist, create it
    await client.createCollection(config.qdrant.collectionName, {
      vectors: {
        size: config.qdrant.vectorSize,
        distance: 'Cosine',
      },
    });
    console.log(`Created collection ${config.qdrant.collectionName}`);
  }
}

/**
 * Search for similar documents by vector
 */
export async function search(
  queryVector: number[],
  options: SearchOptions = {}
): Promise<SearchResult[]> {
  const client = getClient();

  const { limit = 10, scoreThreshold, filter } = options;

  const searchResult = await client.search(config.qdrant.collectionName, {
    vector: queryVector,
    limit,
    score_threshold: scoreThreshold,
    filter: filter ? {
      must: Object.entries(filter).map(([key, value]) => ({
        key,
        match: { value },
      })),
    } : undefined,
  });

  return searchResult.map((result) => ({
    id: result.id as string,
    score: result.score || 0,
    payload: result.payload as Record<string, any> | undefined,
  }));
}

/**
 * Search by text query (requires embedding to be generated externally)
 */
export async function searchByText(
  queryEmbedding: number[],
  options: SearchOptions = {}
): Promise<SearchResult[]> {
  return search(queryEmbedding, options);
}

/**
 * Upsert points to the collection
 */
export async function upsert(points: Point[]): Promise<void> {
  const client = getClient();

  await client.upsert(config.qdrant.collectionName, {
    points: points,
  });
}

/**
 * Delete points by IDs
 */
export async function deletePoints(ids: string[]): Promise<void> {
  const client = getClient();

  await client.delete(config.qdrant.collectionName, {
    points: ids,
  });
}

/**
 * Get collection info
 */
export async function getCollectionInfo(): Promise<any> {
  const client = getClient();

  return await client.getCollection(config.qdrant.collectionName);
}

/**
 * Get point count
 */
export async function getPointCount(): Promise<number> {
  const info = await getCollectionInfo();
  return info.result?.points_count || 0;
}

/**
 * Delete all points from the collection
 */
export async function clearCollection(): Promise<void> {
  // Delete and recreate collection (more efficient than filtering all points)
  await recreateCollection();
}

/**
 * Recreate the collection (delete and create)
 */
export async function recreateCollection(): Promise<void> {
  const client = getClient();

  try {
    await client.deleteCollection(config.qdrant.collectionName);
  } catch {
    // Collection might not exist, ignore error
  }

  await client.createCollection(config.qdrant.collectionName, {
    vectors: {
      size: config.qdrant.vectorSize,
      distance: 'Cosine',
    },
  });
}

/**
 * Health check for Qdrant
 */
export async function healthCheck(): Promise<boolean> {
  try {
    const client = getClient();
    // Try to get collection list
    await client.getCollections();
    return true;
  } catch {
    return false;
  }
}
