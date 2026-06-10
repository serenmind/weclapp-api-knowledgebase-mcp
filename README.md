# weclapp API Knowledge MCP

A knowledge-first MCP server for researching the weclapp API while designing SmartAssist features.

It combines:

- **Offline API knowledge** from `data/openapi_v2.json`: entities, endpoints, fields, cross-schema relationships, filter syntax, and efficient read plans.
- **Bounded live probes** against one weclapp tenant: read-only GET requests that validate plans, inspect real response structure, and diagnose API errors.

This is not a CRUD wrapper. Its main job is to answer: *how should I communicate with the weclapp API, where does data live, and how do I fetch cross-schema data efficiently?*

## Tool Groups

Knowledge tools:

- `search_knowledge`
- `explain_entity`
- `explain_endpoint`
- `get_relationships`
- `plan_cross_entity_read`
- `explain_filter_syntax`
- `compare_approaches`

Live probe tools, all GET-only and bounded:

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

## Quick Start

Local development uses `uv`:

```bash
cd /Users/khum/Source_code/weclapp-api-knowledge-mcp
uv sync
uv run weclapp-build-indexes
uv run pytest
```

Run the MCP locally over stdio:

```bash
MCP_TRANSPORT=stdio uv run weclapp-api-knowledge-mcp
```

Run the Docker server:

```bash
cd /Users/khum/Source_code/weclapp-api-knowledge-mcp
cp .env.example .env
# Fill WECLAPP_BASE_URL and WECLAPP_API_KEY if you want live probes.
docker compose up --build
```

Cursor config via `mcp-remote`:

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

For stdio local development:

```bash
MCP_TRANSPORT=stdio uv run weclapp-api-knowledge-mcp
```

## Safety Model

- No write tools are exposed.
- Live probes only issue GET requests.
- List probes cap `pageSize` with `WECLAPP_MAX_PAGE_SIZE` (default: 10).
- Credentials are read from environment only.
- The OpenAPI file is local and can be refreshed when weclapp changes v2.
