from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from weclapp_api_knowledge_mcp.config import get_settings

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
FILTER_OPERATORS = [
    "eq",
    "ne",
    "lt",
    "gt",
    "le",
    "ge",
    "null",
    "notnull",
    "like",
    "notlike",
    "ilike",
    "notilike",
    "in",
    "notin",
]

TEXT_SEARCH_HINTS = {
    "party": "company",
    "article": "name",
    "quotation": "quotationNumber",
    "salesOrder": "orderNumber",
    "salesInvoice": "invoiceNumber",
    "purchaseInvoice": "invoiceNumber",
    "purchaseOrder": "purchaseOrderNumber",
    "shipment": "shipmentNumber",
    "ticket": "subject",
    "task": "subject",
    "document": "name",
    "user": "login",
}

COMMON_ENTITY_FIELDS = {
    "party": ["id", "company", "customerNumber", "supplierNumber", "partyType", "email"],
    "article": ["id", "articleNumber", "name", "unitId", "articleCategoryId"],
    "salesOrder": ["id", "orderNumber", "customerId", "status", "orderItems"],
    "quotation": ["id", "quotationNumber", "customerId", "status", "quotationItems"],
    "salesInvoice": ["id", "invoiceNumber", "customerId", "status", "paid", "salesOrderId"],
    "purchaseInvoice": ["id", "invoiceNumber", "supplierId", "status", "purchaseOrderId"],
    "shipment": ["id", "shipmentNumber", "mainSalesOrderId", "recipientPartyId", "status"],
}


_WORD_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def split_words(name: str) -> list[str]:
    """Split camelCase/snake_case/path-like identifiers into lowercase words."""
    return [word.lower() for chunk in re.split(r"[^a-zA-Z0-9]+", name) for word in _WORD_RE.findall(chunk)]


def singularize(word: str) -> str:
    """Cheap English singularization good enough for API identifiers."""
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def normalize_tokens(text: str) -> list[str]:
    """Tokenize free text or identifiers into singular lowercase words."""
    return [singularize(word) for word in split_words(text)]


# Function words that carry no signal when ranking API identifiers.
# Tokens are singularized before lookup, hence forms like "doe" (does) and "ha" (has).
STOPWORDS = {
    "a", "all", "an", "and", "are", "by", "can", "doe", "do", "for", "from",
    "get", "ha", "have", "how", "i", "in", "is", "it", "its", "me", "my",
    "of", "on", "or", "that", "the", "their", "this", "to", "via", "want",
    "we", "what", "when", "where", "which", "who", "with", "you",
}


def significant_tokens(text: str) -> set[str]:
    """Normalized tokens with stopwords and single letters removed."""
    return {token for token in normalize_tokens(text) if len(token) > 1 and token not in STOPWORDS}


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_spec() -> dict[str, Any]:
    return _load_json(get_settings().openapi_path)


def resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    node: Any = spec
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def resolve_schema(spec: dict[str, Any], schema_name: str, seen: set[str] | None = None) -> dict[str, Any]:
    seen = seen or set()
    if schema_name in seen:
        return {"properties": {}}
    seen.add(schema_name)

    schema = spec.get("components", {}).get("schemas", {}).get(schema_name, {})
    if "$ref" in schema:
        return resolve_schema(spec, schema["$ref"].split("/")[-1], seen)

    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for part in schema["allOf"]:
            if "$ref" in part:
                sub = resolve_schema(spec, part["$ref"].split("/")[-1], seen)
                merged["properties"].update(sub.get("properties", {}))
                merged["required"].extend(sub.get("required", []))
            else:
                merged["properties"].update(part.get("properties", {}))
                merged["required"].extend(part.get("required", []))
        merged["required"] = sorted(set(merged["required"]))
        return merged

    return schema


def resolve_schema_node(spec: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        return resolve_schema(spec, node["$ref"].split("/")[-1])
    return node


def entity_names(spec: dict[str, Any] | None = None) -> list[str]:
    if spec is None:
        return _entity_names_cached()
    return _entity_names(spec)


@lru_cache(maxsize=1)
def _entity_names_cached() -> list[str]:
    return _entity_names(load_spec())


def _entity_names(spec: dict[str, Any]) -> list[str]:
    entities = set()
    for path in spec.get("paths", {}):
        first = path.strip("/").split("/")[0]
        if first and not first.startswith("{"):
            entities.add(first)
    return sorted(entities)


def resolve_entity_name(entity: str) -> str:
    """Resolve a user-provided entity name to the canonical OpenAPI name.

    Tolerates casing, separators (sales-order, sales_order, "sales order"),
    and plural forms. Raises ValueError with suggestions when unresolvable.
    """
    names = entity_names()
    if entity in names:
        return entity
    by_compact = {compact(name): name for name in names}
    key = compact(entity)
    if key in by_compact:
        return by_compact[key]
    # Normalize plurals on both sides: "sales_orders" and "salesOrder" both
    # reduce to "saleorder".
    by_singular = {"".join(normalize_tokens(name)): name for name in names}
    singular_key = "".join(normalize_tokens(entity))
    if singular_key in by_singular:
        return by_singular[singular_key]
    suggestions = difflib.get_close_matches(key, by_compact.keys(), n=5, cutoff=0.6)
    suggested_names = [by_compact[s] for s in suggestions]
    raise ValueError(
        f"Unknown weclapp entity '{entity}'."
        + (f" Did you mean: {', '.join(suggested_names)}?" if suggested_names else "")
        + " Use search_knowledge to discover entity names."
    )


def build_endpoint_catalog(spec: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    if spec is None:
        return _endpoint_catalog_cached()
    return _build_endpoint_catalog(spec)


@lru_cache(maxsize=1)
def _endpoint_catalog_cached() -> dict[str, list[dict[str, Any]]]:
    return _build_endpoint_catalog(load_spec())


def _build_endpoint_catalog(spec: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = {}
    for path, operations in spec.get("paths", {}).items():
        parts = path.strip("/").split("/")
        if not parts or not parts[0]:
            continue
        entity = parts[0]
        for method, operation in operations.items():
            if method not in HTTP_METHODS:
                continue
            parameters = []
            for param in operation.get("parameters", []):
                if "$ref" in param:
                    param = resolve_ref(spec, param["$ref"])
                parameters.append(
                    {
                        "name": param.get("name"),
                        "in": param.get("in"),
                        "schema": param.get("schema", {}),
                        "description": param.get("description", ""),
                    }
                )
            catalog.setdefault(entity, []).append(
                {
                    "path": path,
                    "method": method.upper(),
                    "summary": operation.get("summary") or operation.get("description") or "",
                    "parameters": parameters,
                    "tags": operation.get("tags", []),
                }
            )
    return catalog


def field_info(entity: str, spec: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    if spec is None:
        return _field_info_cached(entity)
    return _field_info(entity, spec)


@lru_cache(maxsize=None)
def _field_info_cached(entity: str) -> dict[str, dict[str, Any]]:
    return _field_info(entity, load_spec())


def _field_info(entity: str, spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schema = resolve_schema(spec, entity)
    fields: dict[str, dict[str, Any]] = {}
    for name, prop in schema.get("properties", {}).items():
        xw = prop.get("x-weclapp", {})
        field_type = prop.get("type")
        if not field_type and "$ref" in prop:
            field_type = prop["$ref"].split("/")[-1]
        if field_type == "array" and isinstance(prop.get("items"), dict):
            item = prop["items"]
            if "$ref" in item:
                field_type = f"array[{item['$ref'].split('/')[-1]}]"
            elif item.get("type"):
                field_type = f"array[{item.get('type')}]"
        fields[name] = {
            "type": field_type or "object",
            "description": prop.get("description", ""),
            "required": bool(xw.get("required")),
            "x_weclapp": xw,
        }
    return fields


def _walk_relationships(
    spec: dict[str, Any],
    schema_node: dict[str, Any],
    path_prefix: str,
    seen_refs: set[str],
    max_depth: int = 2,
) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    if max_depth < 0:
        return relationships

    schema_node = resolve_schema_node(spec, schema_node)
    for field, prop in schema_node.get("properties", {}).items():
        field_path = f"{path_prefix}.{field}" if path_prefix else field
        xw = prop.get("x-weclapp", {})
        target = xw.get("entity") or xw.get("service")
        if target and (field.endswith("Id") or field.endswith("Ids") or xw.get("entity")):
            relationships.append(
                {
                    "path": field_path,
                    "field": field,
                    "target_entity": target,
                    "include_path": field_path.replace("[]", ""),
                    "nested": "[]" in field_path,
                }
            )

        if prop.get("type") == "array" and isinstance(prop.get("items"), dict):
            item = prop["items"]
            ref_name = item.get("$ref", "").split("/")[-1]
            if ref_name and ref_name not in seen_refs:
                seen_refs.add(ref_name)
                child_schema = resolve_schema(spec, ref_name)
                relationships.extend(
                    _walk_relationships(
                        spec,
                        child_schema,
                        f"{field_path}[]",
                        seen_refs,
                        max_depth=max_depth - 1,
                    )
                )
    return relationships


def relationship_graph(spec: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    if spec is None:
        return _relationship_graph_cached()
    return _relationship_graph(spec)


@lru_cache(maxsize=1)
def _relationship_graph_cached() -> dict[str, list[dict[str, Any]]]:
    return _relationship_graph(load_spec())


def _relationship_graph(spec: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    graph: dict[str, list[dict[str, Any]]] = {}
    for entity in entity_names(spec):
        if entity not in spec.get("components", {}).get("schemas", {}):
            graph[entity] = []
            continue
        schema = resolve_schema(spec, entity)
        graph[entity] = _walk_relationships(spec, schema, "", {entity})
    return graph


def entity_summary(entity: str, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    endpoints = build_endpoint_catalog(spec).get(entity, [])
    fields = field_info(entity, spec)
    relationships = relationship_graph(spec).get(entity, [])
    operations = {
        "list": next((e for e in endpoints if e["method"] == "GET" and e["path"] == f"/{entity}"), None),
        "get_by_id": next(
            (e for e in endpoints if e["method"] == "GET" and e["path"] == f"/{entity}/id/{{id}}"),
            None,
        ),
        "count": next((e for e in endpoints if e["method"] == "GET" and e["path"] == f"/{entity}/count"), None),
    }
    return {
        "source": "openapi_v2",
        "entity": entity,
        "field_count": len(fields),
        "fields": fields,
        "relationships": relationships,
        "endpoints": endpoints,
        "operations": operations,
        "search_hint": TEXT_SEARCH_HINTS.get(entity),
        "common_projection": COMMON_ENTITY_FIELDS.get(entity, list(fields.keys())[:8]),
    }


def normalize_properties(entity: str, requested: list[str] | None = None) -> list[str]:
    fields = field_info(entity)
    base = requested or COMMON_ENTITY_FIELDS.get(entity) or ["id"]
    return [field for field in base if field in fields]


def known_entities_or_raise(entity: str) -> None:
    resolve_entity_name(entity)


_ARRAY_TYPE_RE = re.compile(r"array\[(\w+)\]")


def resolve_field_path(entity: str, field_path: str) -> dict[str, Any]:
    """Walk a dotted field path (e.g. orderItems.articleId) through OpenAPI schemas.

    Follows array item schemas and referenced schema types so nested paths can be
    validated precisely instead of only checking the top-level field.
    """
    segments = [segment.replace("[]", "") for segment in field_path.split(".") if segment]
    current_schema = entity
    walked: list[dict[str, Any]] = []
    for segment in segments:
        fields = field_info(current_schema)
        info = fields.get(segment)
        if info is None:
            suggestions = difflib.get_close_matches(segment, fields.keys(), n=5, cutoff=0.6)
            return {
                "resolved": False,
                "failed_at": segment,
                "failed_in_schema": current_schema,
                "walked": walked,
                "suggestions": suggestions,
            }
        walked.append({"schema": current_schema, "field": segment, "type": info["type"]})
        field_type = info["type"] or ""
        array_match = _ARRAY_TYPE_RE.fullmatch(field_type)
        current_schema = array_match.group(1) if array_match else field_type
    return {
        "resolved": True,
        "walked": walked,
        "leaf_type": walked[-1]["type"] if walked else None,
    }
