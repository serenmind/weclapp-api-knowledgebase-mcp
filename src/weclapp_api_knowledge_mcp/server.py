from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from weclapp_api_knowledge_mcp.analysis.structure import (
    analyze_response_structure as analyze_response_structure_impl,
    compare_to_schema as compare_to_schema_impl,
    explain_data_location as explain_data_location_impl,
)
from weclapp_api_knowledge_mcp.config import get_settings
from weclapp_api_knowledge_mcp.knowledge.planner import (
    compare_approaches as compare_approaches_impl,
    plan_cross_entity_read as plan_cross_entity_read_impl,
)
from weclapp_api_knowledge_mcp.knowledge.search import (
    explain_endpoint as explain_endpoint_impl,
    explain_entity as explain_entity_impl,
    explain_filter_syntax as explain_filter_syntax_impl,
    get_relationships as get_relationships_impl,
    search_knowledge as search_knowledge_impl,
)
from weclapp_api_knowledge_mcp.live.client import (
    execute_read_plan as execute_read_plan_impl,
    probe_entity_sample as probe_entity_sample_impl,
    probe_list_query as probe_list_query_impl,
)
from weclapp_api_knowledge_mcp.validation.validators import (
    check_field_presence as check_field_presence_impl,
    diagnose_api_error as diagnose_api_error_impl,
    validate_filter as validate_filter_impl,
    validate_read_plan as validate_read_plan_impl,
)

settings = get_settings()
mcp = FastMCP(
    "weclapp-api-knowledge",
    instructions=(
        "Knowledge-first weclapp API MCP. Use knowledge tools to plan API communication, "
        "then bounded live probe tools to validate read-only assumptions against a tenant."
    ),
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.tool()
def search_knowledge(query: str, limit: int = 10) -> dict[str, Any]:
    """Search weclapp API knowledge across entities, fields, endpoints, and relationships."""
    return search_knowledge_impl(query=query, limit=limit)


@mcp.tool()
def explain_entity(entity: str) -> dict[str, Any]:
    """Explain one weclapp entity: fields, endpoints, references, projections, and read notes."""
    return explain_entity_impl(entity)


@mcp.tool()
def explain_endpoint(path: str, method: str = "GET") -> dict[str, Any]:
    """Explain one OpenAPI endpoint by path and method."""
    return explain_endpoint_impl(path=path, method=method)


@mcp.tool()
def get_relationships(entity: str, include_inbound: bool = False) -> dict[str, Any]:
    """Return cross-schema relationships discovered from x-weclapp.entity references."""
    return get_relationships_impl(entity=entity, include_inbound=include_inbound)


@mcp.tool()
def plan_cross_entity_read(
    root_entity: str,
    goal: str,
    root_id: str | None = None,
    needs: list[str] | None = None,
) -> dict[str, Any]:
    """Plan an efficient read using properties and includeReferencedEntities where possible."""
    return plan_cross_entity_read_impl(root_entity=root_entity, goal=goal, root_id=root_id, needs=needs)


@mcp.tool()
def explain_filter_syntax(entity: str | None = None) -> dict[str, Any]:
    """Explain weclapp v2 filters, projection, includeReferencedEntities, and examples."""
    return explain_filter_syntax_impl(entity=entity)


@mcp.tool()
def compare_approaches(root_entity: str, goal: str, needs: list[str] | None = None) -> dict[str, Any]:
    """Compare naive N+1 API research with the recommended efficient read plan."""
    return compare_approaches_impl(root_entity=root_entity, goal=goal, needs=needs)


@mcp.tool()
def execute_read_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Execute a GET-only read plan against production to validate a knowledge-layer recommendation."""
    return execute_read_plan_impl(plan)


@mcp.tool()
def probe_entity_sample(
    entity: str,
    entity_id: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    include_referenced_entities: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch one bounded sample from production for structure research and validation."""
    return probe_entity_sample_impl(
        entity=entity,
        entity_id=entity_id,
        filters=filters,
        properties=properties,
        include_referenced_entities=include_referenced_entities,
    )


@mcp.tool()
def probe_list_query(
    entity: str,
    filters: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    page_size: int = 5,
) -> dict[str, Any]:
    """Probe a bounded list query against production. GET-only, capped page size."""
    return probe_list_query_impl(entity=entity, filters=filters, properties=properties, page_size=page_size)


@mcp.tool()
def analyze_response_structure(response: dict[str, Any]) -> dict[str, Any]:
    """Analyze live or sample JSON: paths, arrays, nulls, referencedEntities, and types."""
    return analyze_response_structure_impl(response)


@mcp.tool()
def compare_to_schema(entity: str, response: dict[str, Any]) -> dict[str, Any]:
    """Compare a live payload with the OpenAPI schema fields for an entity."""
    return compare_to_schema_impl(entity=entity, response=response)


@mcp.tool()
def explain_data_location(response: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Find where a field appears in a response and whether it is nested or referenced."""
    return explain_data_location_impl(response=response, field_name=field_name)


@mcp.tool()
def validate_read_plan(plan: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Validate that a read plan produced the expected cross-schema resolution."""
    return validate_read_plan_impl(plan=plan, response=response)


@mcp.tool()
def validate_filter(entity: str, filters: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate filter shape and field/operator names before probing or coding."""
    return validate_filter_impl(entity=entity, filters=filters)


@mcp.tool()
def diagnose_api_error(error: dict[str, Any] | str) -> dict[str, Any]:
    """Explain common weclapp API errors and likely fixes."""
    return diagnose_api_error_impl(error=error)


@mcp.tool()
def check_field_presence(
    entity: str,
    field_path: str,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check whether a field path exists in OpenAPI and optionally in a live payload."""
    return check_field_presence_impl(entity=entity, field_path=field_path, response=response)


@mcp.resource("weclapp://entities/{entity}")
def entity_resource(entity: str) -> str:
    """Browsable entity knowledge resource."""
    import json

    return json.dumps(explain_entity_impl(entity), indent=2, sort_keys=True)


@mcp.resource("weclapp://relationships/{entity}")
def relationships_resource(entity: str) -> str:
    """Browsable relationship graph resource."""
    import json

    return json.dumps(get_relationships_impl(entity, include_inbound=True), indent=2, sort_keys=True)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", settings.mcp_transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
