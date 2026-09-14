/**
 * Tests for get-statistics MCP tool
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { executeGetStatistics, GetStatisticsInputSchema } from '../../tools/get-statistics.js';

// Mock dependencies
vi.mock('../../db/postgres.js', () => ({
  query: vi.fn(),
  getDocumentCount: vi.fn(),
  getCountryIdFromCode: vi.fn(),
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

import { query, getDocumentCount, getCountryIdFromCode } from '../../db/postgres.js';
import { getPointCount } from '../../db/qdrant.js';

/**
 * The corpus-facts row returned by the single combined freshness/consolidation
 * query (identified by the `snapshot_date` alias).
 */
const FACTS_ROW = {
  snapshot_date: '2026-02-06',
  corpus_last_write_at: new Date(2026, 1, 11, 1, 23, 45),
  content_length_p50: 447,
  content_length_p90: 877,
  content_length_max: 5565,
  documents_over_long_text: 1n,
  article_versions_total: 6232n,
  amendments_applied: 0n,
  codes_with_applied_amendments: 0n,
  codes_in_scope: 23n,
};

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
        country_code: 'RU',
        include_vector_stats: true,
      };
      const result = GetStatisticsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate input with only country_code', () => {
      const input = {
        country_code: 'RU',
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

    it('should reject invalid country_code type', () => {
      const input = {
        country_code: 42,
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
      vi.mocked(getCountryIdFromCode).mockResolvedValue(1);
      vi.mocked(query).mockImplementation((text: string) => {
        // The combined facts query must be matched before the plain
        // document_content count: both mention document_content.
        if (text.includes('snapshot_date')) {
          return Promise.resolve([{ ...FACTS_ROW }]);
        }
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

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ include_vector_stats: true })
      );

      expect(result).toContain('Legal Document Database Statistics');
      expect(result).toContain('**Total Documents**');
      // One number format everywhere: en-US thousands separators.
      expect(result).toContain('157,730');
      expect(result).toContain('**Documents with Content**');
      expect(result).toContain('145,500');
      expect(result).toContain('92.2'); // coverage percentage
      expect(result).toContain('**Vector Chunks**');
      expect(result).toContain('450,000');
    });

    it('should report corpus freshness without naming a sync that leaves no record', async () => {
      setupMocks();

      const result = await executeGetStatistics(GetStatisticsInputSchema.parse({}));

      expect(result).toContain('### Freshness');
      expect(result).toContain('**Snapshot Date** (max documents.publish_date): 2026-02-06');
      expect(result).toContain('**corpus_last_write_at** (max documents.updated_at): 2026-02-11 01:23:45');
      expect(result).toContain('**sync_log**: none (no record of sync runs exists yet)');
      expect(result).toContain('NOT the time a sync');
      // The old name claimed a process that leaves no trace.
      expect(result).not.toContain('**Last Sync At**');
    });

    it('should report the content length distribution, not a single body-text cutoff', async () => {
      setupMocks();

      const result = await executeGetStatistics(GetStatisticsInputSchema.parse({}));

      expect(result).toContain('### Document Content Length');
      expect(result).toContain('**document_content length p50**: 447 chars');
      expect(result).toContain('**document_content length p90**: 877 chars');
      expect(result).toContain('**document_content length max**: 5,565 chars');
      expect(result).toContain('**Rows longer than 5,000 chars**: 1');
      expect(result).toContain('arbitrary cut');
      expect(result).toContain('annotation-level text');
      // The 5,000-char count must no longer be presented as "documents with body text".
      expect(result).not.toContain('Documents with Body Text');
    });

    it('should scope the consolidation counters and report codes_with_applied_amendments', async () => {
      setupMocks();

      const result = await executeGetStatistics(GetStatisticsInputSchema.parse({}));

      expect(result).toContain('### Consolidated Codes');
      expect(result).toContain('**Codes in Scope** (rows in consolidated_codes): 23');
      expect(result).toContain(
        '**Article Versions Total** (code_article_versions for codes in scope): 6,232'
      );
      expect(result).toContain(
        '**Amendments Applied** (amendment_applications for codes in scope): 0'
      );
      expect(result).toContain('**codes_with_applied_amendments**: 0 of 23');
      expect(result).toContain(
        '**history_available** (derived): false - 0 of 23 codes have any applied amendment'
      );
      expect(result).toContain('No amendment has ever been applied');
    });

    it('should scope article_versions_total and amendments_applied through consolidated_codes', async () => {
      setupMocks();

      await executeGetStatistics(GetStatisticsInputSchema.parse({ country_code: 'RU' }));

      const factsSql = vi
        .mocked(query)
        .mock.calls.map((call) => String(call[0]))
        .find((sql) => sql.includes('snapshot_date'));

      expect(factsSql).toBeDefined();
      expect(factsSql).toContain('FROM code_article_versions cav');
      expect(factsSql).toContain('JOIN consolidated_codes cc ON cc.code = cav.code_id');
      expect(factsSql).toContain('FROM amendment_applications aa');
      expect(factsSql).toContain('JOIN consolidated_codes cc ON cc.code = aa.code_id');
    });

    it('should state that country_code does not narrow the code counters', async () => {
      setupMocks();

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ country_code: 'RU' })
      );

      expect(result).toContain('carry no country column');
      expect(result).toContain('NOT narrowed by `country_code`');
    });

    it('should report history_available: true when a code has applied amendments', async () => {
      setupMocks();
      vi.mocked(query).mockImplementation((text: string) => {
        if (text.includes('snapshot_date')) {
          return Promise.resolve([
            {
              ...FACTS_ROW,
              amendments_applied: 1234n,
              codes_with_applied_amendments: 7n,
            },
          ]);
        }
        if (text.includes('document_content')) {
          return Promise.resolve([{ count: 145500n }]);
        }
        return Promise.resolve([]);
      });

      const result = await executeGetStatistics(GetStatisticsInputSchema.parse({}));

      expect(result).toContain(
        '**Amendments Applied** (amendment_applications for codes in scope): 1,234'
      );
      expect(result).toContain('**codes_with_applied_amendments**: 7 of 23');
      expect(result).toContain(
        '**history_available** (derived): true - 7 of 23 codes have any applied amendment'
      );
      expect(result).not.toContain('No amendment has ever been applied');
    });

    it('should filter statistics by country_code when provided', async () => {
      setupMocks();
      vi.mocked(getDocumentCount).mockResolvedValue(50000);

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ country_code: 'RU', include_vector_stats: false })
      );

      expect(result).toContain('**Country Code**: RU');
      expect(result).toContain('50,000');
      expect(getDocumentCount).toHaveBeenCalledWith(undefined, 'RU');
      expect(getCountryIdFromCode).toHaveBeenCalledWith('RU');
    });

    it('should exclude vector stats when include_vector_stats is false', async () => {
      setupMocks();

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ include_vector_stats: false })
      );

      expect(result).toContain('**Total Documents**');
      expect(result).not.toContain('**Vector Chunks**');
      expect(getPointCount).not.toHaveBeenCalled();
    });

    it('should handle Qdrant errors gracefully', async () => {
      setupMocks();
      vi.mocked(getPointCount).mockRejectedValue(new Error('Qdrant connection failed'));

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ include_vector_stats: true })
      );

      // Should still return other stats
      expect(result).toContain('**Total Documents**');
      expect(result).toContain('157,730');
      // Vector count should be 0 when Qdrant fails
      expect(result).toContain('**Vector Chunks**: 0');
    });

    it('should show documents by country', async () => {
      setupMocks();

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ include_vector_stats: true })
      );

      expect(result).toContain('Documents by Country');
      expect(result).toContain('Russia');
      expect(result).toContain('157,730');
    });

    it('should show documents by publication block', async () => {
      setupMocks();

      const result = await executeGetStatistics(
        GetStatisticsInputSchema.parse({ include_vector_stats: true })
      );

      expect(result).toContain('Documents by Publication Block');
      expect(result).toContain('Pravitelstvo');
      expect(result).toContain('50,000');
      expect(result).toContain('Sovet Federacii');
      expect(result).toContain('30,000');
    });

    it('should handle zero documents gracefully', async () => {
      vi.mocked(getDocumentCount).mockResolvedValue(0);
      vi.mocked(getPointCount).mockResolvedValue(0);
      vi.mocked(query).mockImplementation((text: string) => {
        if (text.includes('snapshot_date')) {
          return Promise.resolve([
            {
              snapshot_date: null,
              corpus_last_write_at: null,
              content_length_p50: null,
              content_length_p90: null,
              content_length_max: null,
              documents_over_long_text: 0n,
              article_versions_total: 0n,
              amendments_applied: 0n,
              codes_with_applied_amendments: 0n,
              codes_in_scope: 0n,
            },
          ]);
        }
        return Promise.resolve([{ count: 0n }]);
      });

      const result = await executeGetStatistics(GetStatisticsInputSchema.parse({}));

      expect(result).toContain('**Total Documents**: 0');
      expect(result).toContain('**Content Coverage**: 0%');
      expect(result).toContain('**Snapshot Date** (max documents.publish_date): never');
      expect(result).toContain('**corpus_last_write_at** (max documents.updated_at): never');
      // An empty scope must not be rendered as a length of 0 characters.
      expect(result).toContain('**document_content length p50**: n/a');
      expect(result).toContain('**codes_with_applied_amendments**: 0 of 0');
    });

    it('should calculate coverage percentage correctly', async () => {
      setupMocks();
      vi.mocked(getDocumentCount).mockResolvedValue(200000);
      vi.mocked(query).mockImplementation((text: string) => {
        if (text.includes('snapshot_date')) {
          return Promise.resolve([{ ...FACTS_ROW }]);
        }
        return Promise.resolve([{ count: 150000n }]);
      });

      const result = await executeGetStatistics(GetStatisticsInputSchema.parse({}));

      expect(result).toContain('75.0'); // 150000/200000 = 75%
    });
  });

  describe('Error handling', () => {
    it('should handle database errors gracefully', async () => {
      vi.mocked(getDocumentCount).mockRejectedValue(new Error('Database connection failed'));

      await expect(
        executeGetStatistics(GetStatisticsInputSchema.parse({ include_vector_stats: true }))
      ).rejects.toThrow('Database connection failed');
    });
  });
});
