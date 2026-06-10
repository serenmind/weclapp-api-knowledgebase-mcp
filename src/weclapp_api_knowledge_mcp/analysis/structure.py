from __future__ import annotations

from collections import Counter
from typing import Any

from weclapp_api_knowledge_mcp.knowledge.openapi_loader import field_info, resolve_entity_name


def _payload(response: Any) -> Any:
    if isinstance(response, dict) and "response" in response:
        response = response["response"]
    if isinstance(response, dict) and "payload" in response:
        return response["payload"]
    return response


def _walk(value: Any, prefix: str = "", max_items: int = 3) -> tuple[list[str], list[str], list[str], Counter]:
    paths: list[str] = []
    arrays: list[str] = []
    nulls: list[str] = []
    types: Counter = Counter()

    if isinstance(value, dict):
        types["object"] += 1
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.append(path)
            if child is None:
                nulls.append(path)
            sub_paths, sub_arrays, sub_nulls, sub_types = _walk(child, path, max_items)
            paths.extend(sub_paths)
            arrays.extend(sub_arrays)
            nulls.extend(sub_nulls)
            types.update(sub_types)
    elif isinstance(value, list):
        types["array"] += 1
        arrays.append(f"{prefix}[] len={len(value)}")
        for item in value[:max_items]:
            sub_paths, sub_arrays, sub_nulls, sub_types = _walk(item, f"{prefix}[]", max_items)
            paths.extend(sub_paths)
            arrays.extend(sub_arrays)
            nulls.extend(sub_nulls)
            types.update(sub_types)
    else:
        types[type(value).__name__] += 1
    return paths, arrays, nulls, types


def analyze_response_structure(response: Any) -> dict[str, Any]:
    payload = _payload(response)
    paths, arrays, nulls, types = _walk(payload)
    referenced = None
    if isinstance(payload, dict):
        referenced = payload.get("referencedEntities")
        if referenced is None and isinstance(payload.get("result"), dict):
            referenced = payload["result"].get("referencedEntities")
    return {
        "path_count": len(set(paths)),
        "sample_paths": sorted(set(paths))[:120],
        "arrays": arrays[:80],
        "null_fields_sample": nulls[:80],
        "type_counts": dict(types),
        "referenced_entities_present": bool(referenced),
        "referenced_entity_types": sorted(referenced.keys()) if isinstance(referenced, dict) else [],
        "notes": [
            "Use compare_to_schema(entity, response) to identify fields not described by OpenAPI.",
            "Use validate_read_plan(plan, response) to check expected referencedEntities resolution.",
        ],
    }


def compare_to_schema(entity: str, response: Any) -> dict[str, Any]:
    entity = resolve_entity_name(entity)
    payload = _payload(response)
    if isinstance(payload, dict) and "result" in payload:
        result = payload["result"]
    elif isinstance(payload, dict) and "result" in payload.get("payload", {}):
        result = payload["payload"]["result"]
    else:
        result = payload
    if isinstance(result, list):
        result = result[0] if result else {}
    if isinstance(result, dict) and "result" in result and isinstance(result["result"], list):
        result = result["result"][0] if result["result"] else {}
    schema_fields = set(field_info(entity).keys())
    live_fields = set(result.keys()) if isinstance(result, dict) else set()
    return {
        "entity": entity,
        "schema_field_count": len(schema_fields),
        "live_field_count": len(live_fields),
        "fields_in_live_not_schema": sorted(live_fields - schema_fields),
        "schema_fields_missing_from_live_sample": sorted(schema_fields - live_fields)[:100],
        "matching_fields_sample": sorted(schema_fields & live_fields)[:100],
        "interpretation": "Missing schema fields in one payload are normal when projection/properties are used or fields are null/unset.",
    }


def explain_data_location(response: Any, field_name: str) -> dict[str, Any]:
    payload = _payload(response)
    paths, _, _, _ = _walk(payload)
    matches = [path for path in sorted(set(paths)) if field_name.lower() in path.lower()]
    return {
        "field_name": field_name,
        "matches": matches[:100],
        "guidance": "If the path is under referencedEntities, request it with includeReferencedEntities. If it is nested under a line array, include the array field in properties.",
    }
