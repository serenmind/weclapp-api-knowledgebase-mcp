# Client Setup

This MCP server runs on your machine. Clone the repo, install dependencies, and point your client at the local process (stdio) or at a Docker container (SSE).

Repository: https://github.com/serenmind/weclapp-api-knowledgebase-mcp

## Prerequisites

```bash
git clone https://github.com/serenmind/weclapp-api-knowledgebase-mcp.git
cd weclapp-api-knowledgebase-mcp
uv sync
```

For live probe tools, copy and edit credentials:

```bash
cp .env.example .env
```

## Cursor (stdio, recommended)

Use an absolute path to your clone. Knowledge tools work without credentials; add weclapp env vars for live probes.

```json
{
  "mcpServers": {
    "weclapp-api-knowledge": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/weclapp-api-knowledgebase-mcp",
        "run",
        "weclapp-api-knowledge-mcp"
      ],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "WECLAPP_BASE_URL": "https://your-tenant.weclapp.com/webapp/api/v2",
        "WECLAPP_API_KEY": "your-read-only-token"
      }
    }
  }
}
```

If `uv` is not on your PATH for GUI apps, use the full path to the venv binary instead:

```json
{
  "mcpServers": {
    "weclapp-api-knowledge": {
      "command": "/absolute/path/to/weclapp-api-knowledgebase-mcp/.venv/bin/weclapp-api-knowledge-mcp",
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

## Cursor / Claude Desktop (Docker + SSE)

Start the container:

```bash
docker compose up --build
```

Connect with `mcp-remote`:

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

Credentials are loaded from `.env` in the project directory via `docker-compose.yml`.

## Claude Desktop (stdio)

If Claude Desktop can spawn a local command and `weclapp-api-knowledge-mcp` is on PATH (after `uv sync`):

```json
{
  "mcpServers": {
    "weclapp-api-knowledge": {
      "command": "weclapp-api-knowledge-mcp",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "WECLAPP_BASE_URL": "https://your-tenant.weclapp.com/webapp/api/v2",
        "WECLAPP_API_KEY": "your-read-only-token"
      }
    }
  }
}
```

On macOS, Claude Desktop config lives at `~/Library/Application Support/Claude/claude_desktop_config.json`.

## Live probes

Knowledge tools work without credentials. Live tools require:

```env
WECLAPP_BASE_URL=https://your-tenant.weclapp.com/webapp/api/v2
WECLAPP_API_KEY=...
```

Use a read-only token where possible.
