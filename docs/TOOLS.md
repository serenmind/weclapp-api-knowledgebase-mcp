# Tools

Input conventions:

- Entity names are resolved tolerantly: `salesOrder`, `SalesOrder`, `sales-order`, `sales_orders`, and `sales orders` all resolve to the canonical `salesOrder`. Unknown names raise an error with close-match suggestions.
- Endpoint paths accept concrete values in parameterized segments: `/salesOrder/id/12345` resolves to `/salesOrder/id/{id}`.
- Field paths may be nested and are validated through the schema graph, e.g. `orderItems.articleId`.

## Knowledge

`search_knowledge(query, limit=10)` searches entities, fields, endpoints, and relationships.

`explain_entity(entity)` explains endpoints, fields, references, and efficient read notes for one entity.

`explain_endpoint(path, method="GET")` explains an OpenAPI endpoint and its params.

`get_relationships(entity, include_inbound=false)` returns `*Id` and nested relationship paths discovered from `x-weclapp.entity`.

`plan_cross_entity_read(root_entity, goal, root_id=null, needs=null)` creates an efficient API request strategy using `properties` and `includeReferencedEntities` where possible.

`explain_filter_syntax(entity=null)` explains weclapp v2 filter styles and examples.

`compare_approaches(root_entity, goal, needs=null)` compares naive N+1 reads with the recommended plan.

## Live Read Probes

`execute_read_plan(plan)` runs a plan returned by `plan_cross_entity_read`.

`probe_entity_sample(entity, entity_id=null, filters=null, properties=null, include_referenced_entities=null)` fetches one bounded sample.

`probe_list_query(entity, filters=null, properties=null, page_size=5)` tests a bounded list query.

## Analysis And Validation

`analyze_response_structure(response)` walks JSON and summarizes field paths, nested arrays, nulls, and references.

`compare_to_schema(entity, response)` compares live payload fields to OpenAPI fields.

`validate_read_plan(plan, response)` checks whether the plan achieved expected relationships and anti-N+1 behavior.

`validate_filter(entity, filters)` validates filter shape and field existence before a live call.

`diagnose_api_error(error)` explains weclapp errors from status/body text.

`check_field_presence(entity, field_path, response=null)` checks OpenAPI and optional live payload presence.
