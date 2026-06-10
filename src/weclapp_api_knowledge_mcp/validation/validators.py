from __future__ import annotations

import difflib
from typing import Any

from weclapp_api_knowledge_mcp.analysis.structure import analyze_response_structure
from weclapp_api_knowledge_mcp.knowledge.openapi_loader import (
    FILTER_OPERATORS,
    field_info,
    resolve_entity_name,
    resolve_field_path,
)

_STRING_OPS = {"like", "notlike", "ilike", "notilike"}
_ORDERING_OPS = {"lt", "gt", "le", "ge"}
_SET_OPS = {"in", "notin"}
_NULL_OPS = {"null", "notnull"}


def validate_read_plan(plan: dict[str, Any], response: Any) -> dict[str, Any]:
    analysis = analyze_response_structure(response)
    include = plan.get("request", {}).get("params", {}).get("includeReferencedEntities", "")
    expected_paths = [item for item in include.split(",") if item]
    referenced_types = set(analysis.get("referenced_entity_types") or [])
    relationships = plan.get("relationships_used", [])
    checks = []
    checks.append(
        {
            "check": "single_round_trip_plan",
            "passed": plan.get("expected_call_count") == 1,
            "details": plan.get("request"),
        }
    )
    checks.append(
        {
            "check": "referenced_entities_present_when_expected",
            "passed": not expected_paths or bool(referenced_types),
            "expected_include_paths": expected_paths,
            "referenced_entity_types": sorted(referenced_types),
        }
    )
    for rel in relationships:
        checks.append(
            {
                "check": f"target_reference_available:{rel['target_entity']}",
                "passed": rel["target_entity"] in referenced_types or not expected_paths,
                "relationship": rel,
            }
        )
    failed = [check for check in checks if not check["passed"]]
    return {
        "verdict": "valid" if not failed else "needs_adjustment",
        "checks": checks,
        "recommendations": [
            "If referencedEntities is missing, test a simpler includeReferencedEntities value with only top-level ids.",
            "If nested array references are missing, confirm the array field is included in properties.",
            "Avoid replacing this with one GET per related id; prefer a bounded second query when one-call resolution is unavailable.",
        ],
    }


def validate_filter(entity: str, filters: list[dict[str, Any]]) -> dict[str, Any]:
    entity = resolve_entity_name(entity)
    checks = []
    for item in filters:
        field = item.get("field") or ""
        op = item.get("op", "eq")
        value = item.get("value")

        resolution = resolve_field_path(entity, field) if field else {"resolved": False, "suggestions": []}
        leaf_type = resolution.get("leaf_type")
        operator_known = op in FILTER_OPERATORS

        warnings: list[str] = []
        if leaf_type:
            if op in _STRING_OPS and leaf_type != "string":
                warnings.append(f"Operator '{op}' targets string fields; '{field}' is type '{leaf_type}'.")
            if op in _ORDERING_OPS and leaf_type == "boolean":
                warnings.append(f"Ordering operator '{op}' makes no sense for boolean field '{field}'.")
        if op in _SET_OPS and not isinstance(value, (list, str)):
            warnings.append('in/notin expects a JSON array value, e.g. ["1006","1007"].')
        if op in _NULL_OPS and value not in (None, ""):
            warnings.append(f"Operator '{op}' takes no value; drop the value for '{field}'.")
        if op in _STRING_OPS and isinstance(value, str) and "%" not in value:
            warnings.append("like/ilike without % wildcards behaves like equality; add % for contains searches.")

        check: dict[str, Any] = {
            "filter": item,
            "field_known": bool(resolution.get("resolved")),
            "field_type": leaf_type,
            "operator_known": operator_known,
            "warnings": warnings,
            "query_param": f"{field}-{op}" if field else None,
        }
        if not resolution.get("resolved") and resolution.get("suggestions"):
            check["field_suggestions"] = resolution["suggestions"]
            check["failed_at"] = resolution.get("failed_at")
        if not operator_known:
            check["operator_suggestions"] = difflib.get_close_matches(op, FILTER_OPERATORS, n=3, cutoff=0.5)
        checks.append(check)

    all_clean = all(c["field_known"] and c["operator_known"] and not c["warnings"] for c in checks)
    return {
        "entity": entity,
        "verdict": "valid" if all_clean else "review",
        "checks": checks,
        "notes": [
            "weclapp silently ignores filters for unknown or non-filterable properties in some cases; validate with probe_list_query before coding.",
            "Use ilike/like with % wildcards for contains searches.",
        ],
    }


def diagnose_api_error(error: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(error, str):
        text = error
        status = None
    else:
        status = error.get("status_code") or error.get("status")
        text = str(error.get("payload") or error.get("body") or error)
    lower = text.lower()
    diagnoses = []
    if status == 401 or "authentication" in lower or "token" in lower:
        diagnoses.append("Authentication/token problem. Check WECLAPP_API_KEY and header name.")
    if status == 403 or "permission" in lower or "forbidden" in lower:
        diagnoses.append("Permission problem. The API token user likely lacks access to this entity or action.")
    if status == 404 or "not found" in lower:
        diagnoses.append("Endpoint or id not found. Check API version (/webapp/api/v2), entity name, and id path.")
    if status == 400 or "validation" in lower or "invalid" in lower:
        diagnoses.append("Validation/query problem. Check field names, filter operator syntax, and request payload/params.")
    if status == 409 or "optimistic" in lower or "version" in lower:
        diagnoses.append("Optimistic locking/version conflict. For writes, refresh the entity version before updating.")
    if status == 429 or "rate" in lower:
        diagnoses.append("Rate limiting. Reduce pageSize, add backoff, and avoid N+1 request plans.")
    if status == 405 or "method not allowed" in lower:
        diagnoses.append("Method not allowed. Check the endpoint with explain_endpoint; this path may not support the method.")
    if isinstance(status, int) and status >= 500:
        diagnoses.append("weclapp server-side error. Retry with backoff; if persistent, simplify the query (fewer includeReferencedEntities paths, smaller pageSize).")
    return {
        "status": status,
        "diagnoses": diagnoses or ["No specific pattern detected; inspect the raw response and endpoint params."],
        "raw_excerpt": text[:2000],
    }


def check_field_presence(entity: str, field_path: str, response: Any | None = None) -> dict[str, Any]:
    entity = resolve_entity_name(entity)
    fields = field_info(entity)
    top_field = field_path.split(".")[0].replace("[]", "")
    resolution = resolve_field_path(entity, field_path)
    result: dict[str, Any] = {
        "entity": entity,
        "field_path": field_path,
        "openapi_path_present": bool(resolution.get("resolved")),
        "openapi_path_resolution": resolution,
        "openapi_top_field_present": top_field in fields,
        "openapi_top_field_info": fields.get(top_field),
    }
    if response is not None:
        analysis = analyze_response_structure(response)
        result["live_path_matches"] = [
            path for path in analysis["sample_paths"] if field_path.lower() in path.lower()
        ]
    return result
