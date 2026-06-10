from weclapp_api_knowledge_mcp.knowledge.planner import plan_cross_entity_read
from weclapp_api_knowledge_mcp.knowledge.search import explain_entity, get_relationships, search_knowledge
from weclapp_api_knowledge_mcp.validation.validators import validate_filter


def test_openapi_knowledge_finds_sales_order():
    result = search_knowledge("salesOrder customer", limit=5)
    assert result["results"]
    assert any(item["entity"] == "salesOrder" for item in result["results"])


def test_relationship_graph_contains_sales_order_customer():
    result = get_relationships("salesOrder")
    assert any(rel["path"] == "customerId" and rel["target_entity"] == "party" for rel in result["outbound"])


def test_entity_explanation_has_fields_and_operations():
    result = explain_entity("party")
    assert result["field_count"] > 0
    assert result["operations"]["list"]["path"] == "/party"


def test_plan_cross_entity_read_uses_referenced_entities():
    plan = plan_cross_entity_read(
        root_entity="salesOrder",
        root_id="12345",
        goal="sales order with customer company and article numbers on line items",
    )
    assert plan["request"]["method"] == "GET"
    assert "includeReferencedEntities" in plan["request"]["params"]
    assert "customerId" in plan["request"]["params"]["includeReferencedEntities"]


def test_validate_filter_checks_known_fields():
    result = validate_filter("party", [{"field": "company", "op": "ilike", "value": "%Simpli%"}])
    assert result["verdict"] == "valid"
