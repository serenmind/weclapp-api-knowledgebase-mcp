from __future__ import annotations

from typing import Any

from weclapp_api_knowledge_mcp.knowledge.openapi_loader import (
    COMMON_ENTITY_FIELDS,
    TEXT_SEARCH_HINTS,
    entity_summary,
    field_info,
    normalize_tokens,
    relationship_graph,
    resolve_entity_name,
    significant_tokens,
)

# Domain synonyms mapping goal vocabulary to schema vocabulary.
_ALIASES: dict[str, set[str]] = {
    "customer": {"customer", "party"},
    "supplier": {"supplier", "party"},
    "vendor": {"supplier", "party"},
    "product": {"article"},
    "item": {"article", "item"},
    "user": {"user", "creator", "responsible"},
    "warehouse": {"warehouse", "storage"},
    "delivery": {"shipment", "delivery"},
}


def _tokenize(text: str) -> set[str]:
    return significant_tokens(text)


def _relationship_relevance(rel: dict[str, Any], tokens: set[str], needs: list[str]) -> int:
    target_words = set(normalize_tokens(rel["target_entity"]))
    leaf_words = set(normalize_tokens(rel["field"]))
    strong_words = target_words | leaf_words
    # Words from intermediate path segments (e.g. "orderItems" in
    # orderItems[].picks[].x) are structural and only weak evidence.
    path_words = set(normalize_tokens(rel["path"])) - strong_words

    score = 3 * len(tokens & strong_words)
    score += len(tokens & path_words)

    for need in needs:
        need_words = _tokenize(need)
        rel_words = strong_words | path_words
        if need_words and need_words <= rel_words:
            score += 6
        elif need_words & rel_words:
            score += 2

    for token in tokens:
        aliases = _ALIASES.get(token)
        if aliases and aliases & strong_words:
            score += 3

    if score and not rel.get("nested"):
        score += 2
    return score


def plan_cross_entity_read(
    root_entity: str,
    goal: str,
    root_id: str | None = None,
    needs: list[str] | None = None,
) -> dict[str, Any]:
    root_entity = resolve_entity_name(root_entity)
    needs = needs or []
    tokens = _tokenize(goal + " " + " ".join(needs))
    summary = entity_summary(root_entity)
    fields = field_info(root_entity)
    relationships = relationship_graph().get(root_entity, [])

    # Root-entity words describe the root itself ("sales order ..."), not
    # relationship targets; keeping them floods nested paths with false hits.
    relationship_tokens = tokens - set(normalize_tokens(root_entity))

    scored = []
    for rel in relationships:
        score = _relationship_relevance(rel, relationship_tokens, needs)
        # Require at least one strong (target/leaf-field) match; a lone
        # structural path word is not evidence the goal needs this reference.
        if score >= 3:
            scored.append((score, rel))
    scored.sort(key=lambda item: (item[0], not item[1].get("nested")), reverse=True)
    selected = [rel for _, rel in scored[:8]]
    if not selected:
        # Vague goal: default to top-level references so one call still resolves them.
        selected = [rel for rel in relationships if not rel.get("nested")][:8]

    requested_fields = set(COMMON_ENTITY_FIELDS.get(root_entity, ["id"]))
    for field in fields:
        field_words = set(normalize_tokens(field))
        if field.lower() in tokens or (field_words and field_words <= tokens):
            requested_fields.add(field)
    for rel in selected:
        top_level = rel["path"].split(".")[0].replace("[]", "")
        if top_level in fields:
            requested_fields.add(top_level)
        if rel["field"] in fields:
            requested_fields.add(rel["field"])
    requested_fields = {field for field in requested_fields if field in fields}
    properties = sorted(requested_fields) or ["id"]

    include_paths = [rel["include_path"] for rel in selected]
    path = f"/{root_entity}/id/{{id}}" if root_id else f"/{root_entity}"
    if root_id:
        path = f"/{root_entity}/id/{root_id}"

    params: dict[str, Any] = {"properties": ",".join(properties)}
    if include_paths:
        params["includeReferencedEntities"] = ",".join(include_paths)
    if not root_id:
        hint = TEXT_SEARCH_HINTS.get(root_entity)
        params["pageSize"] = 10
        if hint and any(token in tokens for token in {"search", "find", "matching", "contains"}):
            params[f"{hint}-ilike"] = "%<query>%"

    plan = {
        "kind": "weclapp_read_plan",
        "source": "openapi_v2_relationship_graph",
        "goal": goal,
        "root_entity": root_entity,
        "recommended_strategy": "single_get_with_includeReferencedEntities"
        if root_id and include_paths
        else "bounded_list_with_projection",
        "request": {"method": "GET", "path": path, "params": params},
        "relationships_used": selected,
        "expected_call_count": 1,
        "how_to_read_result": [
            {
                "relationship": f"{root_entity}.{rel['path']} -> {rel['target_entity']}",
                "access_pattern": f"result.referencedEntities.{rel['target_entity']}[value at {rel['path']}]",
            }
            for rel in selected
        ],
        "anti_patterns": [
            "Do not fetch the root record and then loop one GET per related id when includeReferencedEntities can resolve it.",
            "Do not omit properties on large entities unless you intentionally need the full payload.",
        ],
        "fallbacks": [
            "If a relationship is not resolved by includeReferencedEntities, fetch the target entity in one bounded batch/filter, not one request per row.",
            "If the endpoint returns a 400 for a relationship path, rerun get_relationships and start with top-level references only.",
        ],
        "entity_context": {
            "field_count": summary["field_count"],
            "search_hint": summary["search_hint"],
            "common_projection": summary["common_projection"],
        },
    }
    return plan


def compare_approaches(root_entity: str, goal: str, needs: list[str] | None = None) -> dict[str, Any]:
    plan = plan_cross_entity_read(root_entity=root_entity, goal=goal, needs=needs)
    relationship_count = len(plan["relationships_used"])
    return {
        "root_entity": root_entity,
        "goal": goal,
        "naive": {
            "description": "Fetch root rows, then issue separate GET calls for each related id.",
            "estimated_calls": f"1 + N * {max(relationship_count, 1)}",
            "risks": ["N+1 latency", "rate limits", "inconsistent projections", "harder error handling"],
        },
        "recommended": {
            "description": "Use projection plus includeReferencedEntities where supported.",
            "estimated_calls": plan["expected_call_count"],
            "request": plan["request"],
            "relationships_used": plan["relationships_used"],
        },
        "decision_rule": "Prefer one projected request with includeReferencedEntities; use a second bounded list request only for data not modeled as a resolvable reference.",
    }
