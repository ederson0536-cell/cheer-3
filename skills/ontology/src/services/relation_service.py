"""Relation service - operations for entity relationships."""

from datetime import datetime, timezone

from ..utils.graph_loader import load_graph, append_op


def create_relation(from_id: str, rel_type: str, to_id: str, properties: dict, graph_path: str):
    """Create a relation between entities.
    
    Args:
        from_id: Source entity ID
        rel_type: Relation type
        to_id: Target entity ID
        properties: Relation properties
        graph_path: Path to the graph file
        
    Returns:
        The relation record dict
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        "op": "relate",
        "from": from_id,
        "rel": rel_type,
        "to": to_id,
        "properties": properties,
        "timestamp": timestamp
    }
    append_op(graph_path, record)
    return record


def get_related(entity_id: str, rel_type: str, graph_path: str, direction: str = "outgoing") -> list:
    """Get related entities.
    
    Args:
        entity_id: The entity ID to find relations for
        rel_type: Relation type filter (can be None for all)
        graph_path: Path to the graph file
        direction: "outgoing", "incoming", or "both"
        
    Returns:
        List of related entity dicts with relation info
    """
    entities, relations = load_graph(graph_path)
    results = []
    
    for rel in relations:
        if direction == "outgoing" and rel["from"] == entity_id:
            if not rel_type or rel["rel"] == rel_type:
                if rel["to"] in entities:
                    results.append({
                        "relation": rel["rel"],
                        "entity": entities[rel["to"]]
                    })
        elif direction == "incoming" and rel["to"] == entity_id:
            if not rel_type or rel["rel"] == rel_type:
                if rel["from"] in entities:
                    results.append({
                        "relation": rel["rel"],
                        "entity": entities[rel["from"]]
                    })
        elif direction == "both":
            if rel["from"] == entity_id or rel["to"] == entity_id:
                if not rel_type or rel["rel"] == rel_type:
                    other_id = rel["to"] if rel["from"] == entity_id else rel["from"]
                    if other_id in entities:
                        results.append({
                            "relation": rel["rel"],
                            "direction": "outgoing" if rel["from"] == entity_id else "incoming",
                            "entity": entities[other_id]
                        })
    
    return results
