/**
 * Law7 MCP Server - HTTP/SSO Entry Point
 * Model Context Protocol server with HTTP/SSE transport for remote access
 */

import { createServer } from './server.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { createMcpExpressApp } from '@modelcontextprotocol/sdk/server/express.js';
import { IncomingMessage, ServerResponse } from 'node:http';
import { config } from './config.js';

// Create Express app pre-configured for MCP
const app = createMcpExpressApp({
  host: '0.0.0.0', // Allow connections from any host (ngrok, etc.)
});

// Store active transports by session ID
const transports = new Map<string, SSEServerTransport>();

// MCP SSE endpoint - GET for establishing SSE stream
app.get('/sse', async (req: IncomingMessage, res: ServerResponse) => {
  console.error('[HTTP] Received SSE connection request');

  try {
    // Create SSE transport with POST endpoint
    const transport = new SSEServerTransport('/messages', res);
    const sessionId = transport.sessionId;

    // Store transport for later message handling
    transports.set(sessionId, transport);

    // Clean up transport on close
    transport.onclose = () => {
      console.error(`[HTTP] SSE transport closed for session ${sessionId}`);
      transports.delete(sessionId);
    };

    // Create and connect MCP server to this transport
    const server = createServer();
    await server.connect(transport);

    console.error(`[HTTP] SSE stream established for session ${sessionId}`);
  } catch (error) {
    console.error('[HTTP] Error establishing SSE stream:', error);
    if (!res.headersSent) {
      res.statusCode = 500;
      res.end('Error establishing SSE stream');
    }
  }
});

// MCP messages endpoint - POST for client messages
app.post('/messages', async (req: any, res: any) => {
  const sessionId = req.query.sessionId as string;

  if (!sessionId) {
    console.error('[HTTP] No session ID provided');
    res.statusCode = 400;
    res.json({ error: 'Missing sessionId parameter' });
    return;
  }

  const transport = transports.get(sessionId);
  if (!transport) {
    console.error(`[HTTP] No active transport for session ${sessionId}`);
    res.statusCode = 404;
    res.json({ error: 'Session not found' });
    return;
  }

  try {
    await transport.handlePostMessage(req, res, req.body);
  } catch (error) {
    console.error('[HTTP] Error handling message:', error);
    if (!res.headersSent) {
      res.statusCode = 500;
      res.json({ error: 'Error handling message' });
    }
  }
});

// Health check endpoint
app.get('/health', (_req: any, res: any) => {
  res.json({
    name: config.server.name,
    version: config.server.version,
    status: 'healthy',
    activeSessions: transports.size
  });
});

/**
 * Start HTTP server
 */
async function main() {
  const port = parseInt(process.env.PORT || '3000', 10);

  app.listen(port, '0.0.0.0', () => {
    console.error(`${config.server.name} v${config.server.version} HTTP server listening on port ${port}`);
    console.error(`[HTTP] SSE endpoint: http://localhost:${port}/sse`);
    console.error(`[HTTP] Health check: http://localhost:${port}/health`);
  });

  // Handle graceful shutdown
  process.on('SIGINT', async () => {
    console.error('[HTTP] Shutting down server...');
    for (const [sessionId, transport] of transports.entries()) {
      try {
        console.error(`[HTTP] Closing transport for session ${sessionId}`);
        await transport.close();
      } catch (error) {
        console.error(`[HTTP] Error closing transport for session ${sessionId}:`, error);
      }
    }
    transports.clear();
    console.error('[HTTP] Server shutdown complete');
    process.exit(0);
  });
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
