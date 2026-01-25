/**
 * Tests for get-article-version MCP tool
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { executeGetArticleVersion, GetArticleVersionInputSchema } from '../../tools/get-article-version.js';

// Mock dependencies
vi.mock('../../db/consolidation_queries.js', () => ({
  getCurrentArticleVersion: vi.fn(),
  getArticleVersionOnDate: vi.fn(),
  getAmendmentChain: vi.fn(),
  getCodeStructure: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    db: { host: 'localhost', port: 5433 },
  },
}));

import { getCurrentArticleVersion, getArticleVersionOnDate, getAmendmentChain, getCodeStructure } from '../../db/consolidation_queries.js';

describe('get-article-version tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Input schema validation', () => {
    it('should validate correct input with all fields', () => {
      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        as_of_date: '2020-01-01',
        include_amendment_chain: true,
      };
      const result = GetArticleVersionInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate input with required fields only', () => {
      const input = {
        code_id: 'TK_RF',
        article_number: '80',
      };
      const result = GetArticleVersionInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.include_amendment_chain).toBe(false); // default
      }
    });

    it('should reject input without code_id', () => {
      const input = {
        article_number: '80',
      };
      const result = GetArticleVersionInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject input without article_number', () => {
      const input = {
        code_id: 'GK_RF',
      };
      const result = GetArticleVersionInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject invalid include_amendment_chain type', () => {
      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        include_amendment_chain: 'yes',
      };
      const result = GetArticleVersionInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('executeGetArticleVersion function - Current version', () => {
    const mockCodeStructure = {
      code: {
        code: 'GK_RF',
        name: 'Гражданский кодекс',
        short_name: 'ГК РФ',
        description: null,
        original_eo_number: '0001200111300001',
        original_date: new Date('2001-11-30'),
        official_url: null,
        last_amended_date: new Date('2024-01-15'),
        total_amendments: 150,
        is_consolidated: true,
        last_consolidated_at: new Date('2024-01-20'),
        created_at: new Date('2024-01-01'),
        updated_at: new Date('2024-01-20'),
      },
    };

    const mockCurrentArticle = {
      id: '1',
      code_id: 'GK_RF',
      article_number: '420',
      version_date: new Date('2023-01-15'),
      article_text: 'Article 420 full text about termination of obligation...',
      article_title: 'Прекращение обязательства',
      amendment_eo_number: '0001202212300001',
      amendment_date: new Date('2022-12-30'),
      is_current: true,
      is_repealed: false,
      repealed_date: null,
      text_hash: 'abc123',
      created_at: new Date('2024-01-01'),
    };

    it('should return current article version', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue(mockCurrentArticle as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        as_of_date: undefined,
        include_amendment_chain: false,
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Гражданский кодекс');
      expect(result).toContain('Article 420');
      expect(result).toContain('[CURRENT]');
      expect(result).toContain('Прекращение обязательства');
      expect(result).toContain('Article 420 full text');
      expect(getCurrentArticleVersion).toHaveBeenCalledWith('GK_RF', '420');
    });

    it('should include amendment chain when requested', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue(mockCurrentArticle as any);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '420',
        code_id: 'GK_RF',
        versions: [
          mockCurrentArticle,
          {
            ...mockCurrentArticle,
            id: '2',
            version_date: new Date('2020-01-01'),
            is_current: false,
            amendment_eo_number: '0001201912300001',
          },
        ],
        current_version: mockCurrentArticle,
      });

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        include_amendment_chain: true,
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Amendment History');
      expect(result).toContain('2 version');
      expect(getAmendmentChain).toHaveBeenCalledWith('GK_RF', '420');
    });

    it('should return not found for non-existent article', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue(null);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '999',
        code_id: 'GK_RF',
        versions: [],
        current_version: null,
      });

      const input = {
        code_id: 'GK_RF',
        article_number: '999',
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Article not found: GK_RF Article 999');
    });

    it('should return helpful message for repealed articles without current version', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue(null);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '80',
        code_id: 'TK_RF',
        versions: [
          {
            ...mockCurrentArticle,
            article_number: '80',
            is_current: false,
            is_repealed: true,
            version_date: new Date('2020-01-01'),
            repealed_date: new Date('2023-01-01'),
          },
        ],
        current_version: null,
      });

      const input = {
        code_id: 'TK_RF',
        article_number: '80',
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Article 80 exists but has no current version');
      expect(result).toContain('may be repealed');
      expect(result).toContain('Available versions: 1');
    });
  });

  describe('executeGetArticleVersion function - Historical version', () => {
    const mockCodeStructure = {
      code: {
        code: 'GK_RF',
        name: 'Гражданский кодекс',
        short_name: 'ГК РФ',
        description: null,
        original_eo_number: null,
        original_date: null,
        official_url: null,
        last_amended_date: null,
        total_amendments: 0,
        is_consolidated: true,
        last_consolidated_at: null,
        created_at: new Date('2024-01-01'),
        updated_at: new Date('2024-01-01'),
      },
    };

    const mockHistoricalArticle = {
      id: '1',
      code_id: 'GK_RF',
      article_number: '420',
      version_date: new Date('2020-01-15'),
      article_text: 'Historical text from 2020...',
      article_title: 'Old title',
      amendment_eo_number: '0001201912300001',
      amendment_date: new Date('2019-12-30'),
      is_current: false,
      is_repealed: false,
      repealed_date: null,
      text_hash: 'def456',
      created_at: new Date('2024-01-01'),
    };

    it('should return article version as of specific date', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(mockHistoricalArticle as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        as_of_date: '2020-06-01',
        include_amendment_chain: false,
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Article 420');
      expect(result).toContain('[HISTORICAL]');
      expect(result).toContain('Historical text from 2020');
      expect(getArticleVersionOnDate).toHaveBeenCalledWith('GK_RF', '420', '2020-06-01');
    });

    it('should return not found for historical query with no results', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(null);

      const input = {
        code_id: 'GK_RF',
        article_number: '999',
        as_of_date: '2020-01-01',
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Article not found: GK_RF Article 999 as of 2020-01-01');
    });

    it('should validate date format', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        as_of_date: 'invalid-date',
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('Invalid date format');
      expect(result).toContain('invalid-date');
      expect(result).toContain('YYYY-MM-DD');
    });

    it('should accept valid date formats', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(mockHistoricalArticle as any);

      const validDates = ['2020-01-01', '2024-12-31', '2000-06-15'];

      for (const date of validDates) {
        const input = {
          code_id: 'GK_RF',
          article_number: '420',
          as_of_date: date,
        };

        const result = await executeGetArticleVersion(input);

        expect(result).not.toContain('Invalid date format');
      }
    });
  });

  describe('Article status badges', () => {
    const mockCodeStructure = {
      code: {
        code: 'GK_RF',
        name: 'Гражданский кодекс',
        short_name: 'ГК РФ',
        description: null,
        original_eo_number: null,
        original_date: null,
        official_url: null,
        last_amended_date: null,
        total_amendments: 0,
        is_consolidated: true,
        last_consolidated_at: null,
        created_at: new Date('2024-01-01'),
        updated_at: new Date('2024-01-01'),
      },
    };

    it('should show [REPEALED] badge for repealed articles', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue({
        id: '1',
        code_id: 'GK_RF',
        article_number: '80',
        version_date: new Date('2020-01-01'),
        article_text: 'Old text',
        article_title: null,
        amendment_eo_number: null,
        amendment_date: null,
        is_current: false,
        is_repealed: true,
        repealed_date: new Date('2023-01-01'),
        text_hash: null,
        created_at: new Date('2024-01-01'),
      } as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '80',
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('[REPEALED]');
      expect(result).toContain('repealed on');
    });

    it('should show [CURRENT] badge for current articles', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue({
        id: '1',
        code_id: 'GK_RF',
        article_number: '420',
        version_date: new Date('2023-01-01'),
        article_text: 'Current text',
        article_title: null,
        amendment_eo_number: null,
        amendment_date: null,
        is_current: true,
        is_repealed: false,
        repealed_date: null,
        text_hash: null,
        created_at: new Date('2024-01-01'),
      } as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
      };

      const result = await executeGetArticleVersion(input);

      expect(result).toContain('[CURRENT]');
    });
  });

  describe('Error handling', () => {
    it('should handle database errors gracefully', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue({
        code: {
          code: 'GK_RF',
          name: 'Гражданский кодекс',
          short_name: 'ГК РФ',
          description: null,
          original_eo_number: null,
          original_date: null,
          official_url: null,
          last_amended_date: null,
          total_amendments: 0,
          is_consolidated: true,
          last_consolidated_at: null,
          created_at: new Date('2024-01-01'),
          updated_at: new Date('2024-01-01'),
        },
      } as any);
      vi.mocked(getCurrentArticleVersion).mockRejectedValue(new Error('Database connection failed'));

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
      };

      await expect(executeGetArticleVersion(input)).rejects.toThrow('Database connection failed');
    });
  });
});
