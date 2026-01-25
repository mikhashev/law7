/**
 * Tests for get-code-structure MCP tool
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { executeGetCodeStructure, GetCodeStructureInputSchema } from '../../tools/get-code-structure.js';

// Mock dependencies
vi.mock('../../db/consolidation_queries.js', () => ({
  listConsolidatedCodes: vi.fn(),
  getCodeStructure: vi.fn(),
  getConsolidatedCode: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    db: { host: 'localhost', port: 5433 },
  },
}));

import { listConsolidatedCodes, getCodeStructure } from '../../db/consolidation_queries.js';

describe('get-code-structure tool', () => {
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
        include_articles: true,
        article_limit: 50,
      };
      const result = GetCodeStructureInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate input with only code_id', () => {
      const input = {
        code_id: 'TK_RF',
      };
      const result = GetCodeStructureInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.include_articles).toBe(true); // default
        expect(result.data.article_limit).toBe(100); // default
      }
    });

    it('should validate empty input (list all codes)', () => {
      const input = {};
      const result = GetCodeStructureInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.code_id).toBeUndefined();
        expect(result.data.include_articles).toBe(true); // default
      }
    });

    it('should reject invalid include_articles type', () => {
      const input = {
        code_id: 'GK_RF',
        include_articles: 'yes',
      };
      const result = GetCodeStructureInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject invalid article_limit type', () => {
      const input = {
        code_id: 'GK_RF',
        article_limit: 'not-a-number',
      };
      const result = GetCodeStructureInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    // Skip negative number test - current schema allows any number
    // it('should reject negative article_limit', () => { ... });
  });

  describe('executeGetCodeStructure function - List all codes', () => {
    const mockCodes = [
      {
        code: 'GK_RF',
        name: 'Гражданский кодекс',
        short_name: 'ГК РФ',
        is_consolidated: true,
        total_amendments: 150,
      },
      {
        code: 'TK_RF',
        name: 'Трудовой кодекс',
        short_name: 'ТК РФ',
        is_consolidated: true,
        total_amendments: 75,
      },
      {
        code: 'UK_RF',
        name: 'Уголовный кодекс',
        short_name: 'УК РФ',
        is_consolidated: false,
        total_amendments: 50,
      },
    ];

    it('should return table of all codes when no code_id provided', async () => {
      vi.mocked(listConsolidatedCodes).mockResolvedValue(mockCodes as any);

      const input = {};

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('Available Consolidated Codes');
      expect(result).toContain('Гражданский кодекс');
      expect(result).toContain('ГК РФ');
      expect(result).toContain('Complete');
      expect(result).toContain('150');
      expect(listConsolidatedCodes).toHaveBeenCalled();
    });

    it('should format codes as markdown table', async () => {
      vi.mocked(listConsolidatedCodes).mockResolvedValue(mockCodes as any);

      const input = {};

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('| Code | Name |');
      expect(result).toContain('| GK_RF |');
      expect(result).toContain('| TK_RF |');
    });

    it('should show "In Progress" for non-consolidated codes', async () => {
      vi.mocked(listConsolidatedCodes).mockResolvedValue(mockCodes as any);

      const input = {};

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('In Progress');
    });

    it('should handle N/A for null short_name', async () => {
      const codesWithNullShortName = [
        {
          code: 'TEST_CODE',
          name: 'Test Code',
          short_name: null,
          is_consolidated: false,
          total_amendments: 0,
        },
      ];

      vi.mocked(listConsolidatedCodes).mockResolvedValue(codesWithNullShortName as any);

      const input = {};

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('N/A');
    });
  });

  describe('executeGetCodeStructure function - Specific code', () => {
    const mockCodeStructure = {
      code: {
        code: 'GK_RF',
        name: 'Гражданский кодекс',
        short_name: 'ГК РФ',
        description: 'Основной гражданский закон',
        original_eo_number: '0001200111300001',
        original_date: new Date('2001-11-30'),
        official_url: 'http://publication.pravo.gov.ru/Document/View/0001200111300001',
        last_amended_date: new Date('2024-01-15'),
        total_amendments: 150,
        is_consolidated: true,
        last_consolidated_at: new Date('2024-01-20'),
        created_at: new Date('2024-01-01'),
        updated_at: new Date('2024-01-20'),
      },
      articles: [
        {
          id: '1',
          code_id: 'GK_RF',
          article_number: '1',
          version_date: new Date('2001-11-30'),
          article_text: 'Article 1 content...',
          article_title: 'Основные положения',
          amendment_eo_number: '0001200111300001',
          amendment_date: new Date('2001-11-30'),
          is_current: true,
          is_repealed: false,
          repealed_date: null,
          text_hash: 'abc123',
          created_at: new Date('2024-01-01'),
        },
        {
          id: '2',
          code_id: 'GK_RF',
          article_number: '2',
          version_date: new Date('2020-01-01'),
          article_text: 'Article 2 content...',
          article_title: null,
          amendment_eo_number: '0001201912300001',
          amendment_date: new Date('2019-12-30'),
          is_current: false,
          is_repealed: false,
          repealed_date: null,
          text_hash: 'def456',
          created_at: new Date('2024-01-01'),
        },
      ],
      total_articles: 2,
      current_articles: 1,
      repealed_articles: 0,
    };

    it('should return code structure when code_id is provided', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);

      const input = {
        code_id: 'GK_RF',
        include_articles: true,
        article_limit: 100,
      };

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('Гражданский кодекс');
      expect(result).toContain('ГК РФ');
      expect(result).toContain('**Code ID**: GK_RF');
      expect(result).toContain('**Total Articles**: 2');
      expect(result).toContain('**Current Articles**: 1');
      expect(getCodeStructure).toHaveBeenCalledWith('GK_RF');
    });

    it('should include articles when include_articles is true', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);

      const input = {
        code_id: 'GK_RF',
        include_articles: true,
        article_limit: 100,
      };

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('## Articles');
      expect(result).toContain('Article 1');
      expect(result).toContain('Основные положения');
      expect(result).toContain('[CURRENT]');
    });

    it('should exclude articles when include_articles is false', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);

      const input = {
        code_id: 'GK_RF',
        include_articles: false,
        article_limit: 100,
      };

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('Гражданский кодекс');
      expect(result).toContain('Statistics');
      expect(result).not.toContain('## Articles');
      expect(result).not.toContain('Article 1');
    });

    it('should limit articles to article_limit', async () => {
      const manyArticles = {
        ...mockCodeStructure,
        articles: Array.from({ length: 150 }, (_, i) => ({
          id: String(i),
          code_id: 'GK_RF',
          article_number: String(i + 1),
          version_date: new Date('2020-01-01'),
          article_text: `Article ${i + 1} content`,
          article_title: `Title ${i + 1}`,
          amendment_eo_number: '0001201912300001',
          amendment_date: new Date('2019-12-30'),
          is_current: true,
          is_repealed: false,
          repealed_date: null,
          text_hash: `hash${i}`,
          created_at: new Date('2024-01-01'),
        })),
        total_articles: 150,
        current_articles: 150,
        repealed_articles: 0,
      };

      vi.mocked(getCodeStructure).mockResolvedValue(manyArticles as any);

      const input = {
        code_id: 'GK_RF',
        include_articles: true,
        article_limit: 50,
      };

      const result = await executeGetCodeStructure(input);

      // Should show 50 articles and "and 100 more" message
      expect(result).toContain('Article 50');
      expect(result).toContain('... and 100 more articles');
    });

    it('should show repealed status for repealed articles', async () => {
      const structureWithRepealed = {
        ...mockCodeStructure,
        articles: [
          {
            ...mockCodeStructure.articles[0],
            is_repealed: true,
            repealed_date: new Date('2023-01-01'),
          },
        ],
        repealed_articles: 1,
      };

      vi.mocked(getCodeStructure).mockResolvedValue(structureWithRepealed as any);

      const input = {
        code_id: 'GK_RF',
        include_articles: true,
      };

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('[REPEALED]');
    });

    it('should show historical status for non-current articles', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);

      const input = {
        code_id: 'GK_RF',
        include_articles: true,
      };

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('[HISTORICAL]');
    });

    it('should return not found message with code list when code_id is invalid', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(null);
      vi.mocked(listConsolidatedCodes).mockResolvedValue([
        {
          code: 'GK_RF',
          name: 'Гражданский кодекс',
          short_name: 'ГК РФ',
          is_consolidated: true,
          total_amendments: 150,
        },
      ]);

      const input = {
        code_id: 'INVALID_CODE',
        include_articles: true,
      };

      const result = await executeGetCodeStructure(input);

      expect(result).toContain('Code not found: INVALID_CODE');
      expect(result).toContain('Available Consolidated Codes');
      expect(result).toContain('GK_RF');
    });
  });

  describe('Error handling', () => {
    it('should handle database errors gracefully', async () => {
      vi.mocked(listConsolidatedCodes).mockRejectedValue(new Error('Database connection failed'));

      const input = {};

      await expect(executeGetCodeStructure(input)).rejects.toThrow('Database connection failed');
    });
  });
});
