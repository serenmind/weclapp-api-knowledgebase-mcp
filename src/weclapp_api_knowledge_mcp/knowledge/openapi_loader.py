from __future__ import annotations

import json
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
    spec = spec or load_spec()
    entities = set()
    for path in spec.get("paths", {}):
        first = path.strip("/").split("/")[0]
        if first and not first.startswith("{"):
            entities.add(first)
    return sorted(entities)


def build_endpoint_catalog(spec: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    spec = spec or load_spec()
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
    spec = spec or load_spec()
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
    spec = spec or load_spec()
    graph: dict[str, list[dict[str, Any]]] = {}
    for entity in entity_names(spec):
        if entity not in spec.get("components", {}).get("schemas", {}):
            graph[entity] = []
            continue
        schema = resolve_schema(spec, entity)
        graph[entity] = _walk_relationships(spec, schema, "", {entity})
    return graph


def entity_summary(entity: str, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = spec or load_spec()
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
    if entity not in entity_names():
        raise ValueError(f"Unknown weclapp entity '{entity}'. Use search_knowledge first.")
