/**
 * Law7 MCP Server Entry Point
 * Start the Model Context Protocol server for legal document queries
 */

import { createServer } from './server.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { config, redactConfig } from './config.js';

/**
 * Main entry point
 */
async function main() {
  // Log configuration
  if (config.logging.level === 'debug') {
    // Never log the raw config: stderr is the client's log channel for a stdio
    // MCP server, and config carries DB/Redis passwords (js/clear-text-logging).
    console.error('Law7 MCP Server Configuration:', JSON.stringify(redactConfig(), null, 2));
  }

  // Create and start server
  const server = createServer();
  const transport = new StdioServerTransport();

  await server.connect(transport);

  console.error(`${config.server.name} v${config.server.version} running on stdio`);
}

// Start the server
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
