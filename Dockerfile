FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    MCP_TRANSPORT=sse \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data
COPY docs ./docs

RUN uv sync --frozen --no-dev --no-editable

EXPOSE 8080
CMD ["/app/.venv/bin/weclapp-api-knowledge-mcp"]
