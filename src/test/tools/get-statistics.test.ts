/**
 * Tests for get-statistics MCP tool
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { executeGetStatistics, GetStatisticsInputSchema } from '../../tools/get-statistics.js';

// Mock dependencies
vi.mock('../../db/postgres.js', () => ({
  query: vi.fn(),
  getDocumentCount: vi.fn(),
}));

vi.mock('../../db/qdrant.js', () => ({
  getPointCount: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    db: { host: 'localhost', port: 5433 },
    qdrant: { url: 'http://localhost:6333' },
  },
}));

import { query, getDocumentCount } from '../../db/postgres.js';
import { getPointCount } from '../../db/qdrant.js';

describe('get-statistics tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Input schema validation', () => {
    it('should validate correct input with all fields', () => {
      const input = {
        country_id: 1,
        include_vector_stats: true,
      };
      const result = GetStatisticsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate input with only country_id', () => {
      const input = {
        country_id: 42,
      };
      const result = GetStatisticsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.include_vector_stats).toBe(true); // default
      }
    });

    it('should validate empty input (uses defaults)', () => {
      const input = {};
      const result = GetStatisticsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.include_vector_stats).toBe(true); // default
      }
    });

    it('should reject invalid country_id type', () => {
      const input = {
        country_id: 'not-a-number',
      };
      const result = GetStatisticsInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject invalid include_vector_stats type', () => {
      const input = {
        include_vector_stats: 'yes',
      };
      const result = GetStatisticsInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('executeGetStatistics function', () => {
    const setupMocks = () => {
      vi.mocked(getDocumentCount).mockResolvedValue(157730);
      vi.mocked(query).mockImplementation((text: string) => {
        if (text.includes('document_content')) {
          return Promise.resolve([{ count: 145500n }]);
        }
        if (text.includes('publication_blocks')) {
          return Promise.resolve([
            { code: 'PP', short_name: 'Pravitelstvo', count: 50000n },
            { code: 'SP', short_name: 'Sovet Federacii', count: 30000n },
          ]);
        }
        if (text.includes('countries c')) {
          return Promise.resolve([
            { id: 1, name: 'Russia', document_count: 157730n },
          ]);
        }
        return Promise.resolve([]);
      });
      vi.mocked(getPointCount).mockResolvedValue(450000);
    };

    it('should return formatted statistics with all data', async () => {
      setupMocks();

      const input = {
        country_id: undefined,
        include_vector_stats: true,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('Legal Document Database Statistics');
      expect(result).toContain('**Total Documents**');
      // Locale format uses thin space separator on this system
      expect(result).toContain('157\u00A0730');
      expect(result).toContain('**Documents with Content**');
      expect(result).toContain('145\u00A0500');
      expect(result).toContain('92.2'); // coverage percentage
      expect(result).toContain('**Vector Chunks**');
      expect(result).toContain('450\u00A0000');
    });

    it('should filter statistics by country_id when provided', async () => {
      vi.mocked(getDocumentCount).mockResolvedValue(50000);
      vi.mocked(query).mockImplementation((text: string) => {
        if (text.includes('document_content')) {
          return Promise.resolve([{ count: 45000n }]);
        }
        return Promise.resolve([]);
      });

      const input = {
        country_id: 1,
        include_vector_stats: false,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('**Country ID**: 1');
      expect(result).toContain('50\u00A0000');
      expect(getDocumentCount).toHaveBeenCalledWith(1);
    });

    it('should exclude vector stats when include_vector_stats is false', async () => {
      setupMocks();

      const input = {
        include_vector_stats: false,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('**Total Documents**');
      expect(result).not.toContain('**Vector Chunks**');
      expect(getPointCount).not.toHaveBeenCalled();
    });

    it('should handle Qdrant errors gracefully', async () => {
      vi.mocked(getDocumentCount).mockResolvedValue(157730);
      vi.mocked(query).mockResolvedValue([{ count: 145500n }]);
      vi.mocked(getPointCount).mockRejectedValue(new Error('Qdrant connection failed'));

      const input = {
        include_vector_stats: true,
      };

      const result = await executeGetStatistics(input);

      // Should still return other stats
      expect(result).toContain('**Total Documents**');
      expect(result).toContain('157\u00A0730');
      // Vector count should be 0 when Qdrant fails
      expect(result).toContain('**Vector Chunks**');
      expect(result).toContain('0');
    });

    it('should show documents by country', async () => {
      setupMocks();

      const input = {
        include_vector_stats: true,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('Documents by Country');
      expect(result).toContain('Russia');
      expect(result).toContain('157\u00A0730');
    });

    it('should show documents by publication block', async () => {
      setupMocks();

      const input = {
        include_vector_stats: true,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('Documents by Publication Block');
      expect(result).toContain('Pravitelstvo');
      expect(result).toContain('50\u00A0000');
      expect(result).toContain('Sovet Federacii');
      expect(result).toContain('30\u00A0000');
    });

    it('should handle zero documents gracefully', async () => {
      vi.mocked(getDocumentCount).mockResolvedValue(0);
      vi.mocked(query).mockResolvedValue([{ count: 0n }]);
      vi.mocked(getPointCount).mockResolvedValue(0); // Add missing mock

      const input = {
        include_vector_stats: true,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('**Total Documents**: 0');
      expect(result).toContain('**Content Coverage**: 0%');
    });

    it('should calculate coverage percentage correctly', async () => {
      vi.mocked(getDocumentCount).mockResolvedValue(200000);
      vi.mocked(query).mockResolvedValue([{ count: 150000n }]);
      vi.mocked(getPointCount).mockResolvedValue(0); // Add missing mock

      const input = {
        include_vector_stats: true,
      };

      const result = await executeGetStatistics(input);

      expect(result).toContain('75.0'); // 150000/200000 = 75%
    });
  });

  describe('Error handling', () => {
    it('should handle database errors gracefully', async () => {
      vi.mocked(getDocumentCount).mockRejectedValue(new Error('Database connection failed'));

      const input = {
        include_vector_stats: true,
      };

      await expect(executeGetStatistics(input)).rejects.toThrow('Database connection failed');
    });
  });
});
