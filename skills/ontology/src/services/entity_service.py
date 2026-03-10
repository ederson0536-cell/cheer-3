"""Entity service - CRUD operations for ontology entities."""

from datetime import datetime, timezone
from pathlib import Path

from ..utils.id_utils import generate_id
from ..utils.graph_loader import load_graph, append_op


def create_entity(type_name: str, properties: dict, graph_path: str, entity_id: str = None) -> dict:
    """Create a new entity.
    
    Args:
        type_name: The entity type
        properties: Entity properties dict
        graph_path: Path to the graph file
        entity_id: Optional explicit ID (auto-generated if not provided)
        
    Returns:
        The created entity dict
    """
    entity_id = entity_id or generate_id(type_name)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    entity = {
        "id": entity_id,
        "type": type_name,
        "properties": properties,
        "created": timestamp,
        "updated": timestamp
    }
    
    record = {"op": "create", "entity": entity, "timestamp": timestamp}
    append_op(graph_path, record)
    
    return entity


def get_entity(entity_id: str, graph_path: str) -> dict | None:
    """Get entity by ID.
    
    Args:
        entity_id: The entity ID
        graph_path: Path to the graph file
        
    Returns:
        The entity dict or None if not found
    """
    entities, _ = load_graph(graph_path)
    return entities.get(entity_id)


def query_entities(type_name: str, where: dict, graph_path: str) -> list:
    """Query entities by type and properties.
    
    Args:
        type_name: Entity type to filter by (can be None for all types)
        where: Property filters dict
        graph_path: Path to the graph file
        
    Returns:
        List of matching entity dicts
    """
    entities, _ = load_graph(graph_path)
    results = []
    
    for entity in entities.values():
        if type_name and entity["type"] != type_name:
            continue
        
        match = True
        for key, value in where.items():
            if entity["properties"].get(key) != value:
                match = False
                break
        
        if match:
            results.append(entity)
    
    return results


def list_entities(type_name: str, graph_path: str) -> list:
    """List all entities of a type.
    
    Args:
        type_name: Entity type to filter by (can be None for all)
        graph_path: Path to the graph file
        
    Returns:
        List of entity dicts
    """
    entities, _ = load_graph(graph_path)
    if type_name:
        return [e for e in entities.values() if e["type"] == type_name]
    return list(entities.values())


def update_entity(entity_id: str, properties: dict, graph_path: str) -> dict | None:
    """Update entity properties.
    
    Args:
        entity_id: The entity ID
        properties: New properties to merge
        graph_path: Path to the graph file
        
    Returns:
        The updated entity dict or None if not found
    """
    entities, _ = load_graph(graph_path)
    if entity_id not in entities:
        return None
    
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {"op": "update", "id": entity_id, "properties": properties, "timestamp": timestamp}
    append_op(graph_path, record)
    
    entities[entity_id]["properties"].update(properties)
    entities[entity_id]["updated"] = timestamp
    return entities[entity_id]


def delete_entity(entity_id: str, graph_path: str) -> bool:
    """Delete an entity.
    
    Args:
        entity_id: The entity ID
        graph_path: Path to the graph file
        
    Returns:
        True if deleted, False if not found
    """
    entities, _ = load_graph(graph_path)
    if entity_id not in entities:
        return False
    
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {"op": "delete", "id": entity_id, "timestamp": timestamp}
    append_op(graph_path, record)
    return True
