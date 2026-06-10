from __future__ import annotations

import re
from typing import Any

from weclapp_api_knowledge_mcp.knowledge.openapi_loader import (
    FILTER_OPERATORS,
    build_endpoint_catalog,
    entity_names,
    entity_summary,
    field_info,
    relationship_graph,
)


def search_knowledge(query: str, limit: int = 10) -> dict[str, Any]:
    q = query.lower().strip()
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", q)
    endpoints = build_endpoint_catalog()
    graph = relationship_graph()
    results: list[dict[str, Any]] = []

    for entity in entity_names():
        score = 0
        reasons = []
        if q in entity.lower():
            score += 10
            reasons.append("entity name")
        token_entity_hits = [token for token in tokens if token in entity.lower()]
        if token_entity_hits:
            score += 3 * len(token_entity_hits)
            reasons.append(f"entity tokens: {', '.join(token_entity_hits)}")

        fields = field_info(entity)
        matching_fields = [
            name for name in fields if q in name.lower() or any(token in name.lower() for token in tokens)
        ]
        if matching_fields:
            score += min(5, len(matching_fields))
            reasons.append(f"fields: {', '.join(matching_fields[:6])}")

        matching_paths = [
            ep["path"]
            for ep in endpoints.get(entity, [])
            if q in ep["path"].lower() or any(token in ep["path"].lower() for token in tokens)
        ]
        if matching_paths:
            score += min(4, len(matching_paths))
            reasons.append(f"endpoints: {', '.join(matching_paths[:4])}")

        matching_refs = [
            rel
            for rel in graph.get(entity, [])
            if q in rel["target_entity"].lower()
            or q in rel["path"].lower()
            or any(token in rel["target_entity"].lower() or token in rel["path"].lower() for token in tokens)
        ]
        if matching_refs:
            score += min(4, len(matching_refs))
            reasons.append(
                "relationships: "
                + ", ".join(f"{r['path']}->{r['target_entity']}" for r in matching_refs[:4])
            )

        if score:
            results.append(
                {
                    "entity": entity,
                    "score": score,
                    "reasons": reasons,
                    "field_matches": matching_fields[:12],
                    "relationship_matches": matching_refs[:8],
                    "endpoint_matches": matching_paths[:8],
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "total_matches": len(results), "results": results[:limit]}


def explain_entity(entity: str) -> dict[str, Any]:
    summary = entity_summary(entity)
    fields = summary["fields"]
    endpoints = summary["endpoints"]
    relationships = summary["relationships"]
    return {
        "source": "openapi_v2",
        "entity": entity,
        "field_count": len(fields),
        "common_projection": summary["common_projection"],
        "search_hint": summary["search_hint"],
        "operations": {
            key: value and {"method": value["method"], "path": value["path"], "summary": value["summary"]}
            for key, value in summary["operations"].items()
        },
        "relationships": relationships[:50],
        "fields": fields,
        "notes": [
            "Use properties to keep payloads small.",
            "Use includeReferencedEntities for related *Id fields when the endpoint supports it.",
            "Use field-op filters such as company-ilike or id-eq for simple filters.",
        ],
        "endpoint_count": len(endpoints),
    }


def explain_endpoint(path: str, method: str = "GET") -> dict[str, Any]:
    method = method.upper()
    endpoints = build_endpoint_catalog()
    for entity, entity_endpoints in endpoints.items():
        for endpoint in entity_endpoints:
            if endpoint["path"] == path and endpoint["method"] == method:
                return {"source": "openapi_v2", "entity": entity, **endpoint}
    raise ValueError(f"Endpoint not found: {method} {path}")


def get_relationships(entity: str, include_inbound: bool = False) -> dict[str, Any]:
    graph = relationship_graph()
    outbound = graph.get(entity, [])
    inbound = []
    if include_inbound:
        for source, relationships in graph.items():
            for rel in relationships:
                if rel["target_entity"] == entity:
                    inbound.append({"source_entity": source, **rel})
    return {
        "source": "openapi_v2",
        "entity": entity,
        "outbound": outbound,
        "inbound": inbound,
        "how_to_use": "Pass outbound include_path values to includeReferencedEntities when fetching this entity.",
    }


def explain_filter_syntax(entity: str | None = None) -> dict[str, Any]:
    examples = [
        "company-ilike=%Simpli%",
        "id-eq=12345",
        "createdDate-ge=2026-01-01T00:00:00Z",
        'customerNumber-in=["1006","1007"]',
        'filter=(company ilike "%simpli%") and (partyType = "ORGANIZATION")',
    ]
    entity_fields = None
    search_hint = None
    if entity:
        summary = entity_summary(entity)
        entity_fields = list(summary["fields"].keys())
        search_hint = summary["search_hint"]
    return {
        "source": "weclapp_api_v2_docs_and_openapi",
        "entity": entity,
        "operators": FILTER_OPERATORS,
        "simple_filter_pattern": "<field>-<operator>=<value>",
        "combination_rule": "Multiple simple filter query parameters are ANDed.",
        "projection": "Use properties=id,fieldA,fieldB to reduce payload size.",
        "references": "Use includeReferencedEntities=customerId,orderItems.articleId to resolve related entities.",
        "examples": examples,
        "entity_search_hint": search_hint,
        "entity_field_sample": entity_fields[:40] if entity_fields else None,
    }
