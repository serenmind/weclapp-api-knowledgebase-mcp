from __future__ import annotations

import difflib
import re
from typing import Any

from weclapp_api_knowledge_mcp.knowledge.openapi_loader import (
    FILTER_OPERATORS,
    build_endpoint_catalog,
    compact,
    entity_names,
    entity_summary,
    field_info,
    normalize_tokens,
    relationship_graph,
    resolve_entity_name,
    significant_tokens,
)


def search_knowledge(query: str, limit: int = 10) -> dict[str, Any]:
    q_compact = compact(query)
    tokens = significant_tokens(query)
    endpoints = build_endpoint_catalog()
    graph = relationship_graph()
    results: list[dict[str, Any]] = []

    if not q_compact:
        return {"query": query, "tokens": [], "total_matches": 0, "results": []}

    for entity in entity_names():
        entity_words = set(normalize_tokens(entity))
        entity_compact = compact(entity)
        score = 0.0
        reasons: list[str] = []

        # Tier 1: the query is the entity name (any casing/separators/plural).
        if q_compact == entity_compact or (tokens and tokens == entity_words):
            score += 100
            reasons.append("exact entity name match")
        elif tokens:
            exact_hits = tokens & entity_words
            substring_hits = {t for t in tokens - exact_hits if t in entity_compact}
            if exact_hits:
                score += 8 * len(exact_hits)
                # Whole query describes this entity ("sales order" -> salesOrder).
                if tokens <= entity_words:
                    score += 20
                # Entity name fully covered by the query.
                if entity_words <= tokens:
                    score += 10
                reasons.append(f"entity name words: {', '.join(sorted(exact_hits))}")
            if substring_hits:
                score += 2 * len(substring_hits)
                reasons.append(f"entity name contains: {', '.join(sorted(substring_hits))}")

        fields = field_info(entity)
        exact_field_matches: list[str] = []
        partial_field_matches: list[str] = []
        covered_tokens: set[str] = set()
        for name in fields:
            field_words = set(normalize_tokens(name))
            covered_tokens |= tokens & field_words
            if q_compact == compact(name):
                exact_field_matches.insert(0, name)
                score += 15
                reasons.append(f"exact field name: {name}")
            elif tokens and tokens <= field_words:
                exact_field_matches.append(name)
            elif tokens & field_words:
                partial_field_matches.append(name)
        covered_tokens |= tokens & entity_words
        if len(covered_tokens) >= 2:
            # Entity covers several distinct query concepts across its fields.
            score += 3 * len(covered_tokens)
            reasons.append(f"covers query concepts: {', '.join(sorted(covered_tokens))}")
        if exact_field_matches:
            score += min(10, 3 * len(exact_field_matches))
            reasons.append(f"fields matching all query words: {', '.join(exact_field_matches[:6])}")
        if partial_field_matches:
            score += min(3, 0.5 * len(partial_field_matches))
            reasons.append(f"fields matching some query words: {', '.join(partial_field_matches[:6])}")

        matching_paths: list[str] = []
        for ep in endpoints.get(entity, []):
            haystack_words = set(normalize_tokens(ep["path"])) | set(normalize_tokens(ep.get("summary", "")))
            if tokens and tokens <= haystack_words:
                matching_paths.append(ep["path"])
        if matching_paths:
            score += min(4, len(matching_paths))
            reasons.append(f"endpoints: {', '.join(dict.fromkeys(matching_paths))[:200]}")

        matching_refs = []
        for rel in graph.get(entity, []):
            rel_words = set(normalize_tokens(rel["path"])) | set(normalize_tokens(rel["target_entity"]))
            if tokens and tokens <= rel_words:
                matching_refs.append(rel)
        if matching_refs:
            score += min(4, len(matching_refs))
            reasons.append(
                "relationships: "
                + ", ".join(f"{r['path']}->{r['target_entity']}" for r in matching_refs[:4])
            )

        if score > 0:
            field_matches = exact_field_matches + partial_field_matches
            results.append(
                {
                    "entity": entity,
                    "score": round(score, 1),
                    "reasons": reasons,
                    "field_matches": field_matches[:12],
                    "relationship_matches": matching_refs[:8],
                    "endpoint_matches": list(dict.fromkeys(matching_paths))[:8],
                }
            )

    results.sort(key=lambda item: (-item["score"], item["entity"]))
    return {
        "query": query,
        "tokens": sorted(tokens),
        "total_matches": len(results),
        "results": results[:limit],
    }


def explain_entity(entity: str) -> dict[str, Any]:
    entity = resolve_entity_name(entity)
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


def _path_pattern(template: str) -> str:
    parts = re.split(r"(\{[^}]*\})", template)
    return "".join("[^/]+" if part.startswith("{") else re.escape(part) for part in parts if part)


def explain_endpoint(path: str, method: str = "GET") -> dict[str, Any]:
    method = method.upper()
    normalized = "/" + path.strip().strip("/")
    endpoints = build_endpoint_catalog()
    flattened = [(entity, ep) for entity, eps in endpoints.items() for ep in eps]

    for entity, ep in flattened:
        if ep["path"].lower() == normalized.lower() and ep["method"] == method:
            return {"source": "openapi_v2", "entity": entity, **ep}

    # Tolerate concrete values in parameterized segments, e.g. /salesOrder/id/12345.
    for entity, ep in flattened:
        if ep["method"] != method:
            continue
        if re.fullmatch(_path_pattern(ep["path"]), normalized, flags=re.IGNORECASE):
            return {
                "source": "openapi_v2",
                "entity": entity,
                **ep,
                "matched_from": normalized,
                "note": f"Resolved '{normalized}' to parameterized path '{ep['path']}'.",
            }

    available_methods = sorted(
        {ep["method"] for _, ep in flattened if ep["path"].lower() == normalized.lower()}
    )
    if available_methods:
        raise ValueError(
            f"Method {method} is not available for {normalized}. "
            f"Available methods: {', '.join(available_methods)}."
        )

    all_paths = sorted({ep["path"] for _, ep in flattened})
    suggestions = difflib.get_close_matches(normalized, all_paths, n=5, cutoff=0.5)
    raise ValueError(
        f"Endpoint not found: {method} {normalized}."
        + (f" Did you mean: {', '.join(suggestions)}?" if suggestions else "")
    )


def get_relationships(entity: str, include_inbound: bool = False) -> dict[str, Any]:
    entity = resolve_entity_name(entity)
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
        entity = resolve_entity_name(entity)
        summary = entity_summary(entity)
        entity_fields = list(summary["fields"].keys())
        search_hint = summary["search_hint"]
    return {
        "source": "weclapp_api_v2_docs_and_openapi",
        "entity": entity,
        "operators": FILTER_OPERATORS,
        "simple_filter_pattern": "<field>-<operator>=<value>",
        "combination_rule": "Multiple simple filter query parameters are ANDed.",
        "operator_notes": {
            "eq/ne/lt/gt/le/ge": "Comparison operators; dates use ISO-8601 strings.",
            "like/notlike/ilike/notilike": "String fields only; use % wildcards. ilike is case-insensitive.",
            "in/notin": 'Value must be a JSON array, e.g. customerNumber-in=["1006","1007"].',
            "null/notnull": "No value needed, e.g. customerId-null.",
        },
        "projection": "Use properties=id,fieldA,fieldB to reduce payload size.",
        "references": "Use includeReferencedEntities=customerId,orderItems.articleId to resolve related entities.",
        "examples": examples,
        "entity_search_hint": search_hint,
        "entity_field_sample": entity_fields[:40] if entity_fields else None,
    }
