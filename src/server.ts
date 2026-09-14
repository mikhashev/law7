/**
 * Law7 MCP Server
 * Model Context Protocol server for querying legal documents
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import type { ZodTypeAny, z } from 'zod';

// Import tools
import { queryLawsTool, executeQueryLaws, QueryLawsInputSchema } from './tools/query-laws.js';
import { getLawTool, executeGetLaw, GetLawInputSchema } from './tools/get-law.js';
import { listCountriesTool, executeListCountries, ListCountriesInputSchema } from './tools/list-countries.js';
import { getStatisticsTool, executeGetStatistics, GetStatisticsInputSchema } from './tools/get-statistics.js';

// Import consolidation tools
import { getCodeStructureTool, executeGetCodeStructure, GetCodeStructureInputSchema } from './tools/get-code-structure.js';
import { getArticleVersionTool, executeGetArticleVersion, GetArticleVersionInputSchema } from './tools/get-article-version.js';
import { traceAmendmentHistoryTool, executeTraceAmendmentHistory, TraceAmendmentHistoryInputSchema } from './tools/trace-amendment-history.js';

// Import Phase 7C tools
import { searchRegionalLawTool, executeSearchRegionalLaw, SearchRegionalLawInputSchema } from './tools/search-regional-law.js';
import { getRegionalKoapArticleTool, executeGetRegionalKoapArticle, GetRegionalKoapArticleInputSchema } from './tools/get-regional-koap-article.js';
import { searchCourtDecisionsTool, executeSearchCourtDecisions, SearchCourtDecisionsInputSchema } from './tools/search-court-decisions.js';
import { getSupremeCourtResolutionTool, executeGetSupremeCourtResolution, GetSupremeCourtResolutionInputSchema } from './tools/get-supreme-court-resolution.js';
import { searchInterpretationsTool, executeSearchInterpretations, SearchInterpretationsInputSchema } from './tools/search-interpretations.js';

// Import on-demand ingestion tool
import { fetchAndIngestTool, executeFetchAndIngest, FetchAndIngestInputSchema } from './tools/fetch-and-ingest.js';

// Import config
import { config } from './config.js';

/**
 * A tool handler pairs a tool's zod input schema with its execute function.
 *
 * Arguments arriving over the wire are UNTRUSTED and untyped. Running them
 * through the zod schema is what applies the documented defaults (e.g.
 * `include_content: true` for get-law, `limit: 50` for trace-amendment-history)
 * and rejects wrong types - the previous `args as any` cast did neither, so a
 * caller that omitted an optional argument got `undefined` instead of the
 * default the tool description promised.
 */
interface ToolHandler<S extends ZodTypeAny> {
  schema: S;
  execute: (input: z.infer<S>) => Promise<string>;
}

/**
 * Schema-erased view of a handler, so handlers for different schemas can live in
 * one registry (`ToolHandler<S>` is invariant in `S` and cannot be widened).
 */
interface AnyToolHandler {
  schema: ZodTypeAny;
  execute: (input: any) => Promise<string>;
}

function handler<S extends ZodTypeAny>(
  schema: S,
  execute: (input: z.infer<S>) => Promise<string>
): ToolHandler<S> {
  return { schema, execute };
}

/** Registry of every callable tool, keyed by its MCP tool name. */
const TOOL_HANDLERS: Record<string, AnyToolHandler> = {
  'query-laws': handler(QueryLawsInputSchema, executeQueryLaws),
  'get-law': handler(GetLawInputSchema, executeGetLaw),
  'list-countries': handler(ListCountriesInputSchema, executeListCountries),
  'get-statistics': handler(GetStatisticsInputSchema, executeGetStatistics),

  // Consolidation tools
  'get-code-structure': handler(GetCodeStructureInputSchema, executeGetCodeStructure),
  'get-article-version': handler(GetArticleVersionInputSchema, executeGetArticleVersion),
  'trace-amendment-history': handler(TraceAmendmentHistoryInputSchema, executeTraceAmendmentHistory),

  // Phase 7C tools
  'search-regional-law': handler(SearchRegionalLawInputSchema, executeSearchRegionalLaw),
  'get-regional-koap-article': handler(GetRegionalKoapArticleInputSchema, executeGetRegionalKoapArticle),
  'search-court-decisions': handler(SearchCourtDecisionsInputSchema, executeSearchCourtDecisions),
  'get-supreme-court-resolution': handler(GetSupremeCourtResolutionInputSchema, executeGetSupremeCourtResolution),
  'search-interpretations': handler(SearchInterpretationsInputSchema, executeSearchInterpretations),

  // On-demand ingestion
  'fetch-and-ingest': handler(FetchAndIngestInputSchema, executeFetchAndIngest),
};

/**
 * Render zod issues as one readable line per problem.
 */
function formatZodIssues(issues: { path: (string | number)[]; message: string }[]): string {
  return issues
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join('.') : '(root)';
      return `  - ${path}: ${issue.message}`;
    })
    .join('\n');
}

/**
 * Create and configure the MCP server
 */
export function createServer(): Server {
  const server = new Server(
    {
      name: config.server.name,
      version: config.server.version,
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        queryLawsTool,
        getLawTool,
        listCountriesTool,
        getStatisticsTool,
        // Consolidation tools
        getCodeStructureTool,
        getArticleVersionTool,
        traceAmendmentHistoryTool,
        // Phase 7C tools
        searchRegionalLawTool,
        getRegionalKoapArticleTool,
        searchCourtDecisionsTool,
        getSupremeCourtResolutionTool,
        searchInterpretationsTool,
        // On-demand ingestion
        fetchAndIngestTool,
      ],
    };
  });

  // Handle tool execution
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    const toolHandler = TOOL_HANDLERS[name];

    if (!toolHandler) {
      return {
        content: [
          {
            type: 'text',
            text: `Error: Unknown tool: ${name}`,
          },
        ],
        isError: true,
      };
    }

    // Validate and apply schema defaults before touching the database.
    // `args` may legitimately be absent for tools whose arguments are all
    // optional (list-countries, get-statistics), so parse `{}` in that case and
    // let the schema decide whether that is acceptable.
    const parsed = toolHandler.schema.safeParse(args ?? {});

    if (!parsed.success) {
      return {
        content: [
          {
            type: 'text',
            text:
              `Error: Invalid arguments for tool "${name}":\n` +
              formatZodIssues(parsed.error.issues as { path: (string | number)[]; message: string }[]),
          },
        ],
        isError: true,
      };
    }

    try {
      const result = await toolHandler.execute(parsed.data);

      return {
        content: [
          {
            type: 'text',
            text: result,
          },
        ],
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: 'text',
            text: `Error: ${errorMessage}`,
          },
        ],
        isError: true,
      };
    }
  });

  return server;
}
