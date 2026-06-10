from __future__ import annotations

from typing import Any

from weclapp_api_knowledge_mcp.analysis.structure import analyze_response_structure
from weclapp_api_knowledge_mcp.knowledge.openapi_loader import FILTER_OPERATORS, field_info


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
    fields = field_info(entity)
    checks = []
    for item in filters:
        field = item.get("field")
        op = item.get("op", "eq")
        checks.append(
            {
                "filter": item,
                "field_known": field in fields,
                "operator_known": op in FILTER_OPERATORS,
                "query_param": f"{field}-{op}" if field else None,
            }
        )
    return {
        "entity": entity,
        "verdict": "valid" if all(c["field_known"] and c["operator_known"] for c in checks) else "review",
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
    return {
        "status": status,
        "diagnoses": diagnoses or ["No specific pattern detected; inspect the raw response and endpoint params."],
        "raw_excerpt": text[:2000],
    }


def check_field_presence(entity: str, field_path: str, response: Any | None = None) -> dict[str, Any]:
    fields = field_info(entity)
    top_field = field_path.split(".")[0].replace("[]", "")
    result: dict[str, Any] = {
        "entity": entity,
        "field_path": field_path,
        "openapi_top_field_present": top_field in fields,
        "openapi_top_field_info": fields.get(top_field),
    }
    if response is not None:
        analysis = analyze_response_structure(response)
        result["live_path_matches"] = [
            path for path in analysis["sample_paths"] if field_path.lower() in path.lower()
        ]
    return result
