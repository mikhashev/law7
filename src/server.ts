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

// Import tools
import { queryLawsTool, executeQueryLaws } from './tools/query-laws.js';
import { getLawTool, executeGetLaw } from './tools/get-law.js';
import { listCountriesTool, executeListCountries } from './tools/list-countries.js';
import { getStatisticsTool, executeGetStatistics } from './tools/get-statistics.js';

// Import consolidation tools
import { getCodeStructureTool, executeGetCodeStructure } from './tools/get-code-structure.js';
import { getArticleVersionTool, executeGetArticleVersion } from './tools/get-article-version.js';
import { traceAmendmentHistoryTool, executeTraceAmendmentHistory } from './tools/trace-amendment-history.js';

// Import config
import { config } from './config.js';

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
      ],
    };
  });

  // Handle tool execution
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (!args) {
      return {
        content: [
          {
            type: 'text',
            text: `Error: No arguments provided for tool: ${name}`,
          },
        ],
        isError: true,
      };
    }

    try {
      let result: string;

      switch (name) {
        case 'query-laws':
          result = await executeQueryLaws(args as any);
          break;

        case 'get-law':
          result = await executeGetLaw(args as any);
          break;

        case 'list-countries':
          result = await executeListCountries(args as any);
          break;

        case 'get-statistics':
          result = await executeGetStatistics(args as any);
          break;

        // Consolidation tools
        case 'get-code-structure':
          result = await executeGetCodeStructure(args as any);
          break;

        case 'get-article-version':
          result = await executeGetArticleVersion(args as any);
          break;

        case 'trace-amendment-history':
          result = await executeTraceAmendmentHistory(args as any);
          break;

        default:
          throw new Error(`Unknown tool: ${name}`);
      }

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
