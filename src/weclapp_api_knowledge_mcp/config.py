from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parent


def _default_openapi_path() -> Path:
    candidates = [
        Path.cwd() / "data" / "openapi_v2.json",
        REPO_ROOT / "data" / "openapi_v2.json",
        Path("/app/data/openapi_v2.json"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_OPENAPI_PATH = _default_openapi_path()


@dataclass(frozen=True)
class Settings:
    openapi_path: Path = Path(os.getenv("WECLAPP_OPENAPI_PATH", DEFAULT_OPENAPI_PATH))
    base_url: str | None = os.getenv("WECLAPP_BASE_URL")
    api_key: str | None = os.getenv("WECLAPP_API_KEY")
    auth_header: str = os.getenv("WECLAPP_AUTH_HEADER", "AuthenticationToken")
    max_page_size: int = int(os.getenv("WECLAPP_MAX_PAGE_SIZE", "10"))
    timeout_seconds: int = int(os.getenv("WECLAPP_REQUEST_TIMEOUT_SECONDS", "30"))
    mcp_transport: str = os.getenv("MCP_TRANSPORT", "stdio")
    mcp_host: str = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port: int = int(os.getenv("MCP_PORT", "8080"))

    @property
    def live_enabled(self) -> bool:
        return bool(self.base_url and self.api_key)


def get_settings() -> Settings:
    return Settings()
