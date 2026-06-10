from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import requests

from weclapp_api_knowledge_mcp.config import Settings, get_settings


class LiveAccessNotConfigured(RuntimeError):
    pass


class WeclappReadClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.live_enabled:
            raise LiveAccessNotConfigured(
                "Live weclapp access is not configured. Set WECLAPP_BASE_URL and WECLAPP_API_KEY."
            )
        self.base_url = self.settings.base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                self.settings.auth_header: self.settings.api_key,
            }
        )

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        url = urljoin(self.base_url, endpoint)
        safe_params = self._safe_params(params or {})
        response = self.session.get(url, params=safe_params, timeout=self.settings.timeout_seconds)
        content_type = response.headers.get("content-type", "")
        payload: Any
        if "application/json" in content_type:
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = {"raw": response.text}
        else:
            payload = {"raw": response.text[:4000], "content_type": content_type}
        return {
            "status_code": response.status_code,
            "ok": response.ok,
            "url": response.url,
            "endpoint": endpoint,
            "params": safe_params,
            "payload": payload,
            "headers": {
                "content-type": content_type,
                "x-ratelimit-remaining": response.headers.get("x-ratelimit-remaining"),
            },
        }

    def _safe_params(self, params: dict[str, Any]) -> dict[str, Any]:
        safe = dict(params)
        page_size = int(safe.get("pageSize") or safe.get("page_size") or self.settings.max_page_size)
        page_size = min(max(page_size, 1), self.settings.max_page_size)
        safe.pop("page_size", None)
        safe["pageSize"] = page_size
        return safe


def params_from_filters(filters: list[dict[str, Any]] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in filters or []:
        field = item.get("field")
        op = item.get("op", "eq")
        value = item.get("value")
        if not field:
            continue
        key = f"{field}-{op}"
        if op in {"in", "notin"} and not isinstance(value, str):
            value = json.dumps(value)
        params[key] = value
    return params


def execute_read_plan(plan: dict[str, Any]) -> dict[str, Any]:
    request = plan.get("request", {})
    if request.get("method", "GET").upper() != "GET":
        raise ValueError("Only GET read plans can be executed.")
    endpoint = str(request.get("path", "")).lstrip("/")
    if not endpoint:
        raise ValueError("Read plan missing request.path")
    params = request.get("params") or {}
    client = WeclappReadClient()
    response = client.get(endpoint, params=params)
    return {"plan": plan, "response": response, "analysis_hint": "Run analyze_response_structure and validate_read_plan on this response."}


def probe_entity_sample(
    entity: str,
    entity_id: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    include_referenced_entities: list[str] | None = None,
) -> dict[str, Any]:
    endpoint = f"{entity}/id/{entity_id}" if entity_id else entity
    params = params_from_filters(filters)
    params["pageSize"] = 1
    if properties:
        params["properties"] = ",".join(properties)
    if include_referenced_entities:
        params["includeReferencedEntities"] = ",".join(include_referenced_entities)
    response = WeclappReadClient().get(endpoint, params=params)
    return {"entity": entity, "sample_kind": "single_entity" if entity_id else "filtered_list_first_page", "response": response}


def probe_list_query(
    entity: str,
    filters: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    page_size: int = 5,
) -> dict[str, Any]:
    settings = get_settings()
    params = params_from_filters(filters)
    params["pageSize"] = min(max(page_size, 1), settings.max_page_size)
    if properties:
        params["properties"] = ",".join(properties)
    response = WeclappReadClient(settings).get(entity, params=params)
    return {"entity": entity, "filters": filters or [], "response": response}
