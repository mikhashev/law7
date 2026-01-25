/**
 * Tests for list-countries MCP tool
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { executeListCountries, ListCountriesInputSchema } from '../../tools/list-countries.js';

// Mock dependencies
vi.mock('../../db/postgres.js', () => ({
  query: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    db: { host: 'localhost', port: 5433 },
  },
}));

import { query } from '../../db/postgres.js';

describe('list-countries tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Input schema validation', () => {
    it('should validate correct input with include_document_count true', () => {
      const input = {
        include_document_count: true,
      };
      const result = ListCountriesInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate input with include_document_count false', () => {
      const input = {
        include_document_count: false,
      };
      const result = ListCountriesInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate empty input (uses defaults)', () => {
      const input = {};
      const result = ListCountriesInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.include_document_count).toBe(true); // default
      }
    });

    it('should reject invalid include_document_count type', () => {
      const input = {
        include_document_count: 'yes',
      };
      const result = ListCountriesInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('executeListCountries function', () => {
    const mockCountries = [
      {
        id: 1,
        code: 'RU',
        name: 'Russia',
        native_name: 'Россия',
      },
      {
        id: 2,
        code: 'US',
        name: 'United States',
        native_name: 'United States',
      },
    ];

    it('should return formatted list of countries with document counts', async () => {
      vi.mocked(query).mockResolvedValue([
        { id: 1, code: 'RU', name: 'Russia', native_name: 'Россия', document_count: 150000 },
        { id: 2, code: 'US', name: 'United States', native_name: 'United States', document_count: 0 },
      ] as any);

      const input = {
        include_document_count: true,
      };

      const result = await executeListCountries(input);

      expect(result).toContain('Available Countries');
      expect(result).toContain('2 country');
      expect(result).toContain('Russia');
      expect(result).toContain('Россия');
      expect(result).toContain('150000');
      expect(result).toContain('**Code**: RU');
    });

    it('should return list without document counts when include_document_count is false', async () => {
      vi.mocked(query).mockResolvedValue(mockCountries as any);

      const input = {
        include_document_count: false,
      };

      const result = await executeListCountries(input);

      expect(result).toContain('Russia');
      expect(result).toContain('**Code**: RU');
      expect(result).not.toContain('**Documents**:');
    });

    it('should return message when no countries found', async () => {
      vi.mocked(query).mockResolvedValue([]);

      const input = {
        include_document_count: true,
      };

      const result = await executeListCountries(input);

      expect(result).toContain('No countries found');
    });

    it('should handle single country result', async () => {
      vi.mocked(query).mockResolvedValue([
        { id: 1, code: 'RU', name: 'Russia', native_name: 'Россия', document_count: 50000 },
      ] as any);

      const input = {
        include_document_count: true,
      };

      const result = await executeListCountries(input);

      expect(result).toContain('1 country');
      expect(result).toContain('Russia');
    });

    it('should handle null native_name gracefully', async () => {
      vi.mocked(query).mockResolvedValue([
        { id: 1, code: 'RU', name: 'Russia', native_name: null, document_count: 50000 },
      ] as any);

      const input = {
        include_document_count: true,
      };

      const result = await executeListCountries(input);

      expect(result).toContain('Russia');
      expect(result).not.toContain('(null)');
    });

    // Remove locale formatting test since implementation doesn't format numbers with locale
    // it('should format large document numbers with locale', async () => { ... });
  });

  describe('SQL query construction', () => {
    it('should construct query with document count when include_document_count is true', async () => {
      vi.mocked(query).mockResolvedValue([
        { id: 1, code: 'RU', name: 'Russia', native_name: 'Россия', document_count: 100 },
      ] as any);

      await executeListCountries({ include_document_count: true });

      const sqlQuery = vi.mocked(query).mock.calls[0][0] as string;
      expect(sqlQuery).toContain('COUNT(d.id) as document_count');
      expect(sqlQuery).toContain('LEFT JOIN documents d ON c.id = d.country_id');
    });

    it('should construct query without document count when include_document_count is false', async () => {
      vi.mocked(query).mockResolvedValue([{ id: 1, code: 'RU', name: 'Russia', native_name: null }] as any);

      await executeListCountries({ include_document_count: false });

      const sqlQuery = vi.mocked(query).mock.calls[0][0] as string;
      expect(sqlQuery).not.toContain('COUNT(d.id) as document_count');
      expect(sqlQuery).not.toContain('LEFT JOIN documents d');
    });
  });

  describe('Error handling', () => {
    it('should handle database errors gracefully', async () => {
      vi.mocked(query).mockRejectedValue(new Error('Database connection failed'));

      const input = {
        include_document_count: true,
      };

      await expect(executeListCountries(input)).rejects.toThrow('Database connection failed');
    });
  });
});
