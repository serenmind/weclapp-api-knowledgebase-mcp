from __future__ import annotations

import json
from pathlib import Path

from weclapp_api_knowledge_mcp.knowledge.openapi_loader import (
    build_endpoint_catalog,
    entity_names,
    field_info,
    relationship_graph,
)


def main() -> None:
    out_dir = Path.cwd() / "knowledge"
    out_dir.mkdir(exist_ok=True)
    payloads = {
        "entity_index.json": entity_names(),
        "endpoint_catalog.json": build_endpoint_catalog(),
        "field_index.json": {entity: field_info(entity) for entity in entity_names()},
        "relationship_graph.json": relationship_graph(),
    }
    for filename, payload in payloads.items():
        (out_dir / filename).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(payloads)} index files to {out_dir}")


if __name__ == "__main__":
    main()
