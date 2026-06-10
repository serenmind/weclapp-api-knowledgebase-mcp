# Client Setup

## Cursor

Start the Docker container:

```bash
docker compose up --build
```

Add the MCP server to Cursor using `mcp-remote`:

```json
{
  "mcpServers": {
    "weclapp-api-knowledge": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8080/sse",
        "--transport",
        "sse-first"
      ]
    }
  }
}
```

## Claude Desktop

Use the same remote endpoint via `mcp-remote`, or run stdio directly if Claude Desktop can spawn the local command:

```json
{
  "mcpServers": {
    "weclapp-api-knowledge": {
      "command": "weclapp-api-knowledge-mcp",
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

## Live Probes

Knowledge tools work without credentials. Live tools require:

```env
WECLAPP_BASE_URL=https://your-tenant.weclapp.com/webapp/api/v2
WECLAPP_API_KEY=...
```

Use a read-only token where possible.
