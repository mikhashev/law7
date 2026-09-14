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
  getAmendmentApplicationCount: vi.fn(),
  getCodeArticleCount: vi.fn(),
  getCodeStructure: vi.fn(),
  getCorpusSnapshotDate: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    db: { host: 'localhost', port: 5433 },
  },
}));

import {
  getCurrentArticleVersion,
  getArticleVersionOnDate,
  getAmendmentChain,
  getAmendmentApplicationCount,
  getCodeArticleCount,
  getCodeStructure,
  getCorpusSnapshotDate,
} from '../../db/consolidation_queries.js';

describe('get-article-version tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // amendment_applications is empty in the live database.
    vi.mocked(getAmendmentApplicationCount).mockResolvedValue(0);
    // Default: the code IS imported (GK_RF holds 551 article rows live).
    vi.mocked(getCodeArticleCount).mockResolvedValue(551);
    // The live corpus is frozen at max(documents.publish_date) = 2026-02-06.
    vi.mocked(getCorpusSnapshotDate).mockResolvedValue('2026-02-06');
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

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

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

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('Amendment History');
      expect(result).toContain('2 version');
      expect(getAmendmentChain).toHaveBeenCalledWith('GK_RF', '420');
    });

    it('should refuse with "Article not found" and the code article count for an absent number', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue(null);
      vi.mocked(getCodeArticleCount).mockResolvedValue(551);
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

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## Article not found');
      expect(result).toContain('- **article_found**: false');
      expect(result).toContain('- **code_available**: true');
      expect(result).toContain('- **articles_imported**: 551');
      // The count is what lets the reader tell "absent from our data" from "does not exist".
      expect(result).toContain('does NOT establish');
      expect(result).not.toContain('## Code not imported');
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

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

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

    it('should return article version as of specific date when real history exists', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(mockHistoricalArticle as any);
      // Two stored versions + applied amendments = genuine history.
      vi.mocked(getAmendmentApplicationCount).mockResolvedValue(150);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '420',
        code_id: 'GK_RF',
        versions: [
          mockHistoricalArticle,
          { ...mockHistoricalArticle, id: '2', version_date: new Date('2023-01-15'), is_current: true },
        ],
        current_version: null,
      } as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        as_of_date: '2020-06-01',
        include_amendment_chain: false,
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('Article 420');
      expect(result).toContain('[HISTORICAL]');
      expect(result).toContain('Historical text from 2020');
      expect(getArticleVersionOnDate).toHaveBeenCalledWith('GK_RF', '420', '2020-06-01');
    });

    it('should refuse a historical query for an absent article number, naming the code article count', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(null);
      vi.mocked(getCodeArticleCount).mockResolvedValue(551);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '999',
        code_id: 'GK_RF',
        versions: [],
        current_version: null,
      } as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '999',
        as_of_date: '2020-01-01',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## Article not found');
      expect(result).toContain('- **article_found**: false');
      expect(result).toContain('- **articles_imported**: 551');
      expect(result).toContain('- **requested_date**: 2020-01-01');
      expect(result).not.toContain('## Code not imported');
    });

    it('should refuse with "Code not imported" when the code holds no articles at all', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue({
        code: {
          code: 'KAS_RF',
          name: 'Кодекс административного судопроизводства',
          short_name: 'КАС РФ',
        },
      } as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(null);
      // KAS_RF is registered in consolidated_codes but has 0 imported articles.
      vi.mocked(getCodeArticleCount).mockResolvedValue(0);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '1',
        code_id: 'KAS_RF',
        versions: [],
        current_version: null,
      } as any);

      const input = {
        code_id: 'KAS_RF',
        article_number: '1',
        as_of_date: '2015-01-01',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## Code not imported');
      expect(result).toContain('- **code_available**: false');
      expect(result).toContain('- **code_id**: KAS_RF');
      expect(result).toContain('Кодекс административного судопроизводства');
      expect(result).toContain('- **articles_imported**: 0');
      expect(result).toContain('get-code-structure');
      // It must NOT claim anything about the article itself.
      expect(result).not.toContain('## Article not found');
      expect(result).not.toContain('article_found');
    });

    it('should validate date format', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);

      const input = {
        code_id: 'GK_RF',
        article_number: '420',
        as_of_date: 'invalid-date',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('Invalid date format');
      expect(result).toContain('invalid-date');
      expect(result).toContain('YYYY-MM-DD');
    });

    it('should accept valid date formats', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getArticleVersionOnDate).mockResolvedValue(mockHistoricalArticle as any);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '420',
        code_id: 'GK_RF',
        versions: [mockHistoricalArticle],
        current_version: null,
      } as any);

      const validDates = ['2020-01-01', '2024-12-31', '2000-06-15'];

      for (const date of validDates) {
        const input = {
          code_id: 'GK_RF',
          article_number: '420',
          as_of_date: date,
        };

        const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

        expect(result).not.toContain('Invalid date format');
      }
    });
  });

  describe('Historical queries without real history (tool honesty)', () => {
    const mockCodeStructure = {
      code: {
        code: 'UK_RF',
        name: 'Уголовный кодекс',
        short_name: 'УК РФ',
      },
    };

    const singleSnapshot = {
      id: '1',
      code_id: 'UK_RF',
      article_number: '105',
      version_date: new Date('2023-11-30'),
      article_text: 'Current text of article 105...',
      article_title: 'Убийство',
      amendment_eo_number: null,
      amendment_date: null,
      is_current: true,
      is_repealed: false,
      repealed_date: null,
      text_hash: 'abc',
      created_at: new Date('2024-01-01'),
    };

    it('should refuse an as_of_date query when only one version and no amendments exist', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getAmendmentApplicationCount).mockResolvedValue(0);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '105',
        code_id: 'UK_RF',
        versions: [singleSnapshot],
        current_version: singleSnapshot,
      } as any);

      const input = {
        code_id: 'UK_RF',
        article_number: '105',
        as_of_date: '2015-01-01',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## No historical version available');
      expect(result).toContain('**history_available**: false');
      // The refusal names the oldest version we hold and the amendment count.
      expect(result).toContain('**oldest_version_date**: 2023-11-30');
      expect(result).toContain('**amendments_applied**: 0');
      expect(result).toContain('History has NOT been generated for UK_RF');
      // Crucially: no article text, no [CURRENT] badge.
      expect(result).not.toContain('[CURRENT]');
      expect(result).not.toContain('Current text of article 105');
      expect(getArticleVersionOnDate).not.toHaveBeenCalled();
    });

    it('should refuse when the requested date precedes the oldest version held', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getAmendmentApplicationCount).mockResolvedValue(12);
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '105',
        code_id: 'UK_RF',
        versions: [
          singleSnapshot,
          { ...singleSnapshot, id: '2', version_date: new Date('2024-06-01') },
        ],
        current_version: singleSnapshot,
      } as any);

      const input = {
        code_id: 'UK_RF',
        article_number: '105',
        as_of_date: '2015-01-01',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## No historical version available');
      expect(result).toContain('is EARLIER than the oldest version law7 holds');
      expect(result).toContain('**oldest_version_date**: 2023-11-30');
      expect(result).not.toContain('[CURRENT]');
      expect(getArticleVersionOnDate).not.toHaveBeenCalled();
    });

    it('should still return the current text when no as_of_date is supplied', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getAmendmentApplicationCount).mockResolvedValue(0);
      vi.mocked(getCurrentArticleVersion).mockResolvedValue(singleSnapshot as any);

      const input = {
        code_id: 'UK_RF',
        article_number: '105',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('[CURRENT]');
      expect(result).toContain('Current text of article 105');
      expect(result).not.toContain('## No historical version available');
    });

    it('should give the frozen-corpus reason when the requested date is after the snapshot', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getAmendmentApplicationCount).mockResolvedValue(0);
      vi.mocked(getCorpusSnapshotDate).mockResolvedValue('2026-02-06');
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '105',
        code_id: 'UK_RF',
        versions: [singleSnapshot],
        current_version: singleSnapshot,
      } as any);

      const input = {
        code_id: 'UK_RF',
        article_number: '105',
        as_of_date: '2026-12-31',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## No historical version available');
      expect(result).toContain('- **corpus_snapshot_date**: 2026-02-06');
      // Both true reasons must be stated, not only the missing-history one.
      expect(result).toContain("is LATER than law7's corpus snapshot");
      expect(result).toContain('frozen at that date');
      expect(result).toContain('History has NOT been generated for UK_RF');
      expect(result).not.toContain('Current text of article 105');
    });

    it('should not claim a frozen corpus when the requested date is before the snapshot', async () => {
      vi.mocked(getCodeStructure).mockResolvedValue(mockCodeStructure as any);
      vi.mocked(getAmendmentApplicationCount).mockResolvedValue(0);
      vi.mocked(getCorpusSnapshotDate).mockResolvedValue('2026-02-06');
      vi.mocked(getAmendmentChain).mockResolvedValue({
        article_number: '105',
        code_id: 'UK_RF',
        versions: [singleSnapshot],
        current_version: singleSnapshot,
      } as any);

      const input = {
        code_id: 'UK_RF',
        article_number: '105',
        as_of_date: '2015-01-01',
      };

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

      expect(result).toContain('## No historical version available');
      expect(result).not.toContain("is LATER than law7's corpus snapshot");
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

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

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

      const result = await executeGetArticleVersion(GetArticleVersionInputSchema.parse(input));

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

      await expect(executeGetArticleVersion(GetArticleVersionInputSchema.parse(input))).rejects.toThrow('Database connection failed');
    });
  });
});
