/**
 * Trace Amendment History Tool
 * Track the amendment history for a specific article or code
 */

import { z } from 'zod';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import {
  getAmendmentChain,
  getAmendmentApplications,
  getCodeStructure,
} from '../db/consolidation_queries.js';

// Input schema for trace-amendment-history tool
export const TraceAmendmentHistoryInputSchema = z.object({
  code_id: z.string().describe('Code ID (e.g., "GK_RF", "TK_RF")'),
  article_number: z.string().optional().describe('Article number (e.g., "123"). If not provided, shows amendment history for entire code.'),
  include_details: z.boolean().optional().default(true).describe('Include detailed change information'),
  limit: z.number().optional().default(50).describe('Maximum number of amendments to show'),
});

export type TraceAmendmentHistoryInput = z.infer<typeof TraceAmendmentHistoryInputSchema>;

/**
 * Format date for display
 */
function formatDate(date: Date | string | null): string {
  if (!date) return 'N/A';
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('ru-RU');
}

/**
 * Format article amendment chain
 */
function formatArticleAmendmentChain(chain: any, includeDetails: boolean): string {
  const parts: string[] = [];

  parts.push(`# Amendment History: Article ${chain.article_number}`);
  parts.push('');
  parts.push(`**Code ID**: ${chain.code_id}`);
  parts.push(`**Total Versions**: ${chain.versions.length}`);
  parts.push('');

  if (chain.current_version) {
    parts.push(`**Current Version**: ${formatDate(chain.current_version.version_date)}`);
  } else {
    parts.push(`**Current Version**: None (article may be repealed)`);
  }

  parts.push('');
  parts.push('## Version History');
  parts.push('');

  // Show versions in reverse chronological order
  const sortedVersions = [...chain.versions].sort((a, b) =>
    new Date(b.version_date).getTime() - new Date(a.version_date).getTime()
  );

  for (const version of sortedVersions) {
    const isCurrent = version.is_current ? ' [CURRENT]' : '';
    const isRepealed = version.is_repealed ? ' [REPEALED]' : '';

    parts.push(`### ${formatDate(version.version_date)}${isCurrent}${isRepealed}`);
    parts.push('');

    if (version.amendment_eo_number) {
      parts.push(`- **Amendment**: ${version.amendment_eo_number}`);
      if (version.amendment_date) {
        parts.push(`- **Amendment Date**: ${formatDate(version.amendment_date)}`);
      }
    }

    if (version.article_title) {
      parts.push(`- **Title**: ${version.article_title}`);
    }

    parts.push(`- **Status**: ${version.is_current ? 'Current' : 'Historical'}`);

    if (version.is_repealed) {
      parts.push(`- **Repealed**: Yes${version.repealed_date ? ` (${formatDate(version.repealed_date)})` : ''}`);
    }

    // Show text diff if details requested
    if (includeDetails && version.article_text) {
      parts.push('');
      parts.push('**Text**:');
      const preview = version.article_text.substring(0, 300);
      if (version.article_text.length > 300) {
        parts.push(preview + '...');
      } else {
        parts.push(preview);
      }
    }

    parts.push('');
  }

  return parts.join('\n');
}

/**
 * Format code amendment applications
 */
function formatCodeAmendmentHistory(
  applications: any[],
  codeName: string,
  includeDetails: boolean
): string {
  const parts: string[] = [];

  parts.push(`# Amendment History: ${codeName}`);
  parts.push('');
  parts.push(`**Total Amendment Applications**: ${applications.length}`);
  parts.push('');

  // Group by status
  const applied = applications.filter(a => a.status === 'applied');
  const pending = applications.filter(a => a.status === 'pending');
  const failed = applications.filter(a => a.status === 'failed');
  const conflict = applications.filter(a => a.status === 'conflict');

  parts.push('## Summary');
  parts.push(`- **Applied**: ${applied.length}`);
  parts.push(`- **Pending**: ${pending.length}`);
  parts.push(`- **Failed**: ${failed.length}`);
  parts.push(`- **Conflict**: ${conflict.length}`);
  parts.push('');

  parts.push('## Amendment Applications');
  parts.push('');

  for (const app of applications) {
    const statusIndicators: Record<string, string> = {
      applied: '[APPLIED]',
      pending: '[PENDING]',
      failed: '[FAILED]',
      conflict: '[CONFLICT]',
    };
    const statusIndicator = statusIndicators[app.status] || '[UNKNOWN]';

    parts.push(`### ${statusIndicator} ${app.amendment_eo_number}`);
    parts.push('');

    parts.push(`- **Status**: ${app.status.toUpperCase()}`);
    if (app.amendment_date) {
      parts.push(`- **Amendment Date**: ${formatDate(app.amendment_date)}`);
    }
    if (app.amendment_type) {
      parts.push(`- **Type**: ${app.amendment_type}`);
    }
    if (app.applied_at) {
      parts.push(`- **Applied At**: ${formatDate(app.applied_at)}`);
    }

    // Articles affected
    const affectedCount = app.articles_affected?.length || 0;
    const addedCount = app.articles_added?.length || 0;
    const modifiedCount = app.articles_modified?.length || 0;
    const repealedCount = app.articles_repealed?.length || 0;

    if (includeDetails && affectedCount > 0) {
      parts.push('');
      parts.push(`**Articles Affected**: ${affectedCount}`);
      if (addedCount > 0) parts.push(`  - Added: ${addedCount}`);
      if (modifiedCount > 0) parts.push(`  - Modified: ${modifiedCount}`);
      if (repealedCount > 0) parts.push(`  - Repealed: ${repealedCount}`);

      // List affected articles
      if (app.articles_affected && app.articles_affected.length > 0) {
        parts.push(`  - Articles: ${app.articles_affected.slice(0, 10).join(', ')}${app.articles_affected.length > 10 ? '...' : ''}`);
      }
    }

    if (app.error_message) {
      parts.push('');
      parts.push(`**Error**: ${app.error_message}`);
    }

    parts.push('');
  }

  return parts.join('\n');
}

/**
 * Execute the trace-amendment-history tool
 */
export async function executeTraceAmendmentHistory(input: TraceAmendmentHistoryInput): Promise<string> {
  const { code_id, article_number, include_details, limit } = input;

  // Get code info for context
  const codeStructure = await getCodeStructure(code_id);

  if (!codeStructure) {
    return `Code not found: ${code_id}`;
  }

  if (article_number) {
    // Get amendment chain for specific article
    const chain = await getAmendmentChain(code_id, article_number);

    if (chain.versions.length === 0) {
      return `No amendment history found for ${code_id} Article ${article_number}`;
    }

    return formatArticleAmendmentChain(chain, include_details);
  } else {
    // Get amendment applications for entire code
    const applications = await getAmendmentApplications(code_id);

    if (applications.length === 0) {
      return `No amendment history found for ${codeStructure.code.name} (${code_id})`;
    }

    // Limit results
    const limitedApplications = applications.slice(0, limit);

    return formatCodeAmendmentHistory(
      limitedApplications,
      codeStructure.code.name,
      include_details
    );
  }
}

/**
 * Tool definition for MCP server
 */
export const traceAmendmentHistoryTool: Tool = {
  name: 'trace-amendment-history',
  description: `Track the amendment history for a Russian legal code or specific article.

This tool provides a complete history of amendments applied to a code or article,
including:
- Chronological list of amendments
- Status of each amendment (applied, pending, failed, conflict)
- Articles affected by each amendment
- Version history for specific articles

Args:
  code_id: Code ID (e.g., "GK_RF", "TK_RF")
  article_number: Article number (e.g., "123"). Optional - if not provided, shows history for entire code.
  include_details: Include detailed change information (default: true)
  limit: Maximum number of amendments to show (default: 50)

Available codes:
  - GK_RF: Civil Code (Гражданский кодекс)
  - UK_RF: Criminal Code (Уголовный кодекс)
  - TK_RF: Labor Code (Трудовой кодекс)
  - NK_RF: Tax Code (Налоговый кодекс)
  - KoAP_RF: Administrative Code (КоАП РФ)
  - SK_RF: Family Code (Семейный кодекс)
  - ZhK_RF: Housing Code (Жилищный кодекс)
  - ZK_RF: Land Code (Земельный кодекс)

Examples:
  Trace history of entire Labor Code:
  { "code_id": "TK_RF" }

  Trace history of specific article:
  { "code_id": "TK_RF", "article_number": "80" }

  Trace with limited results:
  { "code_id": "TK_RF", "limit": 20 }`,
  inputSchema: {
    type: 'object',
    properties: {
      code_id: {
        type: 'string',
        description: 'Code ID (e.g., "GK_RF", "TK_RF")',
      },
      article_number: {
        type: 'string',
        description: 'Article number (e.g., "123"). If not provided, shows amendment history for entire code.',
      },
      include_details: {
        type: 'boolean',
        description: 'Include detailed change information',
        default: true,
      },
      limit: {
        type: 'number',
        description: 'Maximum number of amendments to show',
        default: 50,
      },
    },
    required: ['code_id'],
  },
};
