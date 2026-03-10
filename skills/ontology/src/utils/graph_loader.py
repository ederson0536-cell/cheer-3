"""Graph loading and persistence utilities."""

import json
from pathlib import Path


def load_graph(path: str) -> tuple[dict, list]:
    """Load entities and relations from graph file.
    
    Args:
        path: Path to the graph file (JSONL format)
        
    Returns:
        Tuple of (entities dict, relations list)
    """
    entities = {}
    relations = []
    
    graph_path = Path(path)
    if not graph_path.exists():
        return entities, relations
    
    with open(graph_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            op = record.get("op")
            
            if op == "create":
                entity = record["entity"]
                entities[entity["id"]] = entity
            elif op == "update":
                entity_id = record["id"]
                if entity_id in entities:
                    entities[entity_id]["properties"].update(record.get("properties", {}))
                    entities[entity_id]["updated"] = record.get("timestamp")
            elif op == "delete":
                entity_id = record["id"]
                entities.pop(entity_id, None)
            elif op == "relate":
                relations.append({
                    "from": record["from"],
                    "rel": record["rel"],
                    "to": record["to"],
                    "properties": record.get("properties", {})
                })
            elif op == "unrelate":
                new_relations = []
                for r in relations:
                    if r["from"] == record["from"] and r["rel"] == record["rel"] and r["to"] == record["to"]:
                        continue
                    new_relations.append(r)
                relations = new_relations
    
    return entities, relations


def append_op(path: str, record: dict):
    """Append an operation to the graph file.
    
    Args:
        path: Path to the graph file
        record: The operation record to append
    """
    graph_path = Path(path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(graph_path, "a") as f:
        f.write(json.dumps(record) + "\n")
