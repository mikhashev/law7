/**
 * Tests for get-law MCP tool
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { executeGetLaw, GetLawInputSchema } from '../../tools/get-law.js';

// Mock dependencies
vi.mock('../../db/postgres.js', () => ({
  getDocumentByEoNumber: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    db: { host: 'localhost', port: 5433 },
  },
}));

import { getDocumentByEoNumber } from '../../db/postgres.js';

describe('get-law tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Input schema validation', () => {
    it('should validate correct input with all fields', () => {
      const input = {
        eo_number: '0001202601170001',
        include_content: true,
      };
      const result = GetLawInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate input with only required field', () => {
      const input = {
        eo_number: '0001202601170001',
      };
      const result = GetLawInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.include_content).toBe(true); // default
      }
    });

    it('should reject input without eo_number', () => {
      const input = {
        include_content: true,
      };
      const result = GetLawInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject invalid eo_number type', () => {
      const input = {
        eo_number: 123456,
      };
      const result = GetLawInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject invalid include_content type', () => {
      const input = {
        eo_number: '0001202601170001',
        include_content: 'yes',
      };
      const result = GetLawInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('executeGetLaw function', () => {
    const mockDocument = {
      id: 'doc-id-1',
      eo_number: '0001202601170001',
      title: 'Test Law',
      complex_name: 'Тестовый закон',
      document_number: '123-ФЗ',
      document_date: new Date('2024-01-15'),
      publish_date: new Date('2024-01-20'),
      pages_count: 10,
      signatory_authority_id: 'auth-1',
      document_type_id: 'type-1',
      full_text: 'Full content of the law...',
      pdf_url: 'https://example.com/doc.pdf',
      html_url: 'https://example.com/doc.html',
      text_hash: 'abc123',
    };

    it('should return formatted document when found', async () => {
      vi.mocked(getDocumentByEoNumber).mockResolvedValue(mockDocument as any);

      const input = {
        eo_number: '0001202601170001',
        include_content: true,
      };

      const result = await executeGetLaw(input);

      // Implementation uses complex_name first, then title
      expect(result).toContain('Тестовый закон');
      expect(result).toContain('0001202601170001');
      expect(result).toContain('Full content of the law');
      expect(result).toContain('123-ФЗ');
      expect(getDocumentByEoNumber).toHaveBeenCalledWith('0001202601170001');
    });

    it('should return not found message when document does not exist', async () => {
      vi.mocked(getDocumentByEoNumber).mockResolvedValue(null);

      const input = {
        eo_number: '0001202601170001',
        include_content: true,
      };

      const result = await executeGetLaw(input);

      expect(result).toContain('Document not found');
      expect(result).toContain('0001202601170001');
    });

    it('should exclude content when include_content is false', async () => {
      vi.mocked(getDocumentByEoNumber).mockResolvedValue(mockDocument as any);

      const input = {
        eo_number: '0001202601170001',
        include_content: false,
      };

      const result = await executeGetLaw(input);

      // Implementation uses complex_name first, then title
      expect(result).toContain('Тестовый закон');
      expect(result).not.toContain('Full content of the law');
      expect(result).not.toContain('## Content');
    });

    it('should handle document with minimal fields', async () => {
      const minimalDocument = {
        id: 'doc-id-2',
        eo_number: '0001202601170002',
        title: 'Minimal Law',
        complex_name: null,
      };

      vi.mocked(getDocumentByEoNumber).mockResolvedValue(minimalDocument as any);

      const input = {
        eo_number: '0001202601170002',
        include_content: true,
      };

      const result = await executeGetLaw(input);

      expect(result).toContain('Minimal Law');
      expect(result).toContain('0001202601170002');
    });

    it('should format dates correctly in Russian locale', async () => {
      vi.mocked(getDocumentByEoNumber).mockResolvedValue(mockDocument as any);

      const input = {
        eo_number: '0001202601170001',
        include_content: true,
      };

      const result = await executeGetLaw(input);

      expect(result).toContain('15.01.2024');
    });

    it('should include links when available', async () => {
      vi.mocked(getDocumentByEoNumber).mockResolvedValue(mockDocument as any);

      const input = {
        eo_number: '0001202601170001',
        include_content: true,
      };

      const result = await executeGetLaw(input);

      expect(result).toContain('[PDF]');
      expect(result).toContain('https://example.com/doc.pdf');
      expect(result).toContain('[HTML View]');
      expect(result).toContain('https://example.com/doc.html');
    });

    it('should handle null optional fields gracefully', async () => {
      const documentWithNulls = {
        id: 'doc-id-3',
        eo_number: '0001202601170003',
        title: 'Partial Law',
        complex_name: null,
        document_number: null,
        document_date: null,
        full_text: null,
        pdf_url: null,
        html_url: null,
        text_hash: null,
      };

      vi.mocked(getDocumentByEoNumber).mockResolvedValue(documentWithNulls as any);

      const input = {
        eo_number: '0001202601170003',
        include_content: true,
      };

      const result = await executeGetLaw(input);

      expect(result).toContain('Partial Law');
      expect(result).toContain('0001202601170003');
      // Should not throw errors for null fields
    });
  });

  describe('Error handling', () => {
    it('should handle database errors gracefully', async () => {
      vi.mocked(getDocumentByEoNumber).mockRejectedValue(new Error('Database connection failed'));

      const input = {
        eo_number: '0001202601170001',
        include_content: true,
      };

      await expect(executeGetLaw(input)).rejects.toThrow('Database connection failed');
    });
  });
});
