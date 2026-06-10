# weclapp API Knowledge MCP

A standalone [Model Context Protocol](https://modelcontextprotocol.io/) server for researching the [weclapp](https://www.weclapp.com/) REST API v2. Use it from Cursor, Claude Desktop, or any MCP-compatible client to explore entities, endpoints, relationships, and filter syntax — and optionally validate read patterns against your own tenant.

**Not affiliated with weclapp.** This is an independent open-source project maintained by the community.

## What it does

It combines:

- **Offline API knowledge** from `data/openapi_v2.json`: entities, endpoints, fields, cross-schema relationships, filter syntax, and efficient read plans.
- **Bounded live probes** against one weclapp tenant: read-only GET requests that validate plans, inspect real response structure, and diagnose API errors.

This is not a CRUD wrapper. Its main job is to answer: *how should I communicate with the weclapp API, where does data live, and how do I fetch cross-schema data efficiently?*

Knowledge tools work without credentials. Live probe tools require a read-only weclapp API token.

## Tool groups

Knowledge tools:

- `search_knowledge`
- `explain_entity`
- `explain_endpoint`
- `get_relationships`
- `plan_cross_entity_read`
- `explain_filter_syntax`
- `compare_approaches`

Live probe tools (GET-only and bounded):

- `execute_read_plan`
- `probe_entity_sample`
- `probe_list_query`

Analysis and validation tools:

- `analyze_response_structure`
- `compare_to_schema`
- `validate_read_plan`
- `validate_filter`
- `diagnose_api_error`
- `check_field_presence`

See [docs/TOOLS.md](docs/TOOLS.md) for parameter details and usage notes.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Optional: Docker, for SSE transport via `mcp-remote`
- Optional: weclapp API credentials for live probes

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/serenmind/weclapp-api-knowledgebase-mcp.git
cd weclapp-api-knowledgebase-mcp
uv sync
```

### 2. Configure credentials (optional)

Live probe tools need a read-only weclapp token:

```bash
cp .env.example .env
# Edit .env and set WECLAPP_BASE_URL and WECLAPP_API_KEY
```

### 3. Run tests (optional)

```bash
uv run pytest
```

### 4. Connect your MCP client

**Recommended — stdio with Cursor**

Add to your Cursor MCP settings (`.cursor/mcp.json` or Cursor Settings → MCP):

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
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

Add `WECLAPP_BASE_URL` and `WECLAPP_API_KEY` to `env` if you want live probes.

**Alternative — Docker + SSE**

```bash
cp .env.example .env
docker compose up --build
```

Then connect via [mcp-remote](https://www.npmjs.com/package/mcp-remote):

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

More client examples: [docs/CLIENT_SETUP.md](docs/CLIENT_SETUP.md).

## Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `WECLAPP_BASE_URL` | For live probes | — | Tenant API base, e.g. `https://your-tenant.weclapp.com/webapp/api/v2` |
| `WECLAPP_API_KEY` | For live probes | — | Read-only API token |
| `WECLAPP_AUTH_HEADER` | No | `AuthenticationToken` | Auth header name |
| `WECLAPP_OPENAPI_PATH` | No | `data/openapi_v2.json` | Path to OpenAPI spec |
| `MCP_TRANSPORT` | No | `stdio` | `stdio` or `sse` |
| `MCP_HOST` | No | `0.0.0.0` | SSE bind host |
| `MCP_PORT` | No | `8080` | SSE bind port |
| `WECLAPP_MAX_PAGE_SIZE` | No | `10` | Max rows for list probes |
| `WECLAPP_REQUEST_TIMEOUT_SECONDS` | No | `30` | HTTP timeout for live probes |

## Safety model

- No write tools are exposed.
- Live probes only issue GET requests.
- List probes cap `pageSize` with `WECLAPP_MAX_PAGE_SIZE` (default: 10).
- Credentials are read from environment only.
- The bundled OpenAPI file can be refreshed when weclapp updates v2.

## Refreshing the OpenAPI spec

Replace `data/openapi_v2.json` with an updated weclapp v2 OpenAPI export, then restart the server. The MCP server reads and caches the spec directly at runtime.

## Development

```bash
uv sync
uv run pytest
uv run ruff check src tests
MCP_TRANSPORT=stdio uv run weclapp-api-knowledge-mcp
```

## License

MIT — see [LICENSE](LICENSE).
