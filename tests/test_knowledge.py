import pytest

from weclapp_api_knowledge_mcp.knowledge.openapi_loader import (
    normalize_tokens,
    resolve_entity_name,
    resolve_field_path,
    split_words,
)
from weclapp_api_knowledge_mcp.knowledge.planner import plan_cross_entity_read
from weclapp_api_knowledge_mcp.knowledge.search import (
    explain_endpoint,
    explain_entity,
    get_relationships,
    search_knowledge,
)
from weclapp_api_knowledge_mcp.validation.validators import (
    check_field_presence,
    diagnose_api_error,
    validate_filter,
)


def test_openapi_knowledge_finds_sales_order():
    result = search_knowledge("salesOrder customer", limit=5)
    assert result["results"]
    assert any(item["entity"] == "salesOrder" for item in result["results"])


def test_search_natural_language_ranks_exact_entity_first():
    result = search_knowledge("sales order", limit=5)
    assert result["results"][0]["entity"] == "salesOrder"


def test_search_exact_entity_name_is_top_result():
    result = search_knowledge("salesInvoice", limit=5)
    assert result["results"][0]["entity"] == "salesInvoice"


def test_search_handles_plurals():
    result = search_knowledge("sales invoices", limit=5)
    assert result["results"][0]["entity"] == "salesInvoice"


def test_search_finds_entity_by_field_name():
    result = search_knowledge("customerNumber", limit=10)
    assert any(item["entity"] == "party" for item in result["results"])


def test_relationship_graph_contains_sales_order_customer():
    result = get_relationships("salesOrder")
    assert any(rel["path"] == "customerId" and rel["target_entity"] == "party" for rel in result["outbound"])


def test_entity_explanation_has_fields_and_operations():
    result = explain_entity("party")
    assert result["field_count"] > 0
    assert result["operations"]["list"]["path"] == "/party"


def test_entity_name_resolution_is_tolerant():
    assert resolve_entity_name("SalesOrder") == "salesOrder"
    assert resolve_entity_name("sales-order") == "salesOrder"
    assert resolve_entity_name("sales_orders") == "salesOrder"
    assert explain_entity("SalesOrder")["entity"] == "salesOrder"


def test_entity_name_resolution_suggests_close_matches():
    with pytest.raises(ValueError) as excinfo:
        resolve_entity_name("salseOrdr")
    assert "salesOrder" in str(excinfo.value)


def test_explain_endpoint_resolves_concrete_id_path():
    result = explain_endpoint("/salesOrder/id/12345")
    assert result["path"] == "/salesOrder/id/{id}"
    assert result["method"] == "GET"


def test_explain_endpoint_reports_available_methods():
    with pytest.raises(ValueError) as excinfo:
        explain_endpoint("/salesOrder/count", method="POST")
    assert "GET" in str(excinfo.value)


def test_explain_endpoint_suggests_close_paths():
    with pytest.raises(ValueError) as excinfo:
        explain_endpoint("/salesOrdr")
    assert "/salesOrder" in str(excinfo.value)


def test_plan_cross_entity_read_uses_referenced_entities():
    plan = plan_cross_entity_read(
        root_entity="salesOrder",
        root_id="12345",
        goal="sales order with customer company and article numbers on line items",
    )
    assert plan["request"]["method"] == "GET"
    assert "includeReferencedEntities" in plan["request"]["params"]
    assert "customerId" in plan["request"]["params"]["includeReferencedEntities"]


def test_plan_honors_explicit_needs():
    plan = plan_cross_entity_read(
        root_entity="salesOrder",
        root_id="12345",
        goal="resolve references",
        needs=["customerId"],
    )
    assert "customerId" in plan["request"]["params"]["includeReferencedEntities"]


def test_validate_filter_checks_known_fields():
    result = validate_filter("party", [{"field": "company", "op": "ilike", "value": "%Simpli%"}])
    assert result["verdict"] == "valid"


def test_validate_filter_suggests_close_field_names():
    result = validate_filter("party", [{"field": "compny", "op": "eq", "value": "x"}])
    assert result["verdict"] == "review"
    assert "company" in result["checks"][0]["field_suggestions"]


def test_validate_filter_warns_on_type_mismatch():
    result = validate_filter("salesInvoice", [{"field": "paid", "op": "ilike", "value": "%true%"}])
    assert result["verdict"] == "review"
    assert result["checks"][0]["warnings"]


def test_validate_filter_resolves_nested_paths():
    result = validate_filter("salesOrder", [{"field": "orderItems.articleId", "op": "eq", "value": "1"}])
    assert result["checks"][0]["field_known"] is True


def test_resolve_field_path_walks_nested_schemas():
    result = resolve_field_path("salesOrder", "orderItems.articleId")
    assert result["resolved"] is True
    assert result["walked"][0]["field"] == "orderItems"

    missing = resolve_field_path("salesOrder", "orderItems.articelId")
    assert missing["resolved"] is False
    assert "articleId" in missing["suggestions"]


def test_check_field_presence_supports_nested_paths():
    result = check_field_presence("salesOrder", "orderItems.articleId")
    assert result["openapi_path_present"] is True


def test_diagnose_api_error_covers_server_errors():
    result = diagnose_api_error({"status_code": 503, "body": "service unavailable"})
    assert any("server-side" in d for d in result["diagnoses"])


def test_tokenization_helpers():
    assert split_words("salesOrderItem") == ["sales", "order", "item"]
    assert normalize_tokens("sales orders") == ["sale", "order"]
    assert normalize_tokens("purchase-invoices") == ["purchase", "invoice"]
