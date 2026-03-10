"""Validation service - graph validation against schema constraints."""

from datetime import datetime
from pathlib import Path

from ..utils.graph_loader import load_graph
from .schema_service import load_schema


def validate_graph(graph_path: str, schema_path: str) -> list:
    """Validate graph against schema constraints.
    
    Args:
        graph_path: Path to the graph file
        schema_path: Path to the schema file
        
    Returns:
        List of validation error strings (empty if valid)
    """
    entities, relations = load_graph(graph_path)
    errors = []
    
    # Load schema if exists
    schema = load_schema(schema_path)
    
    type_schemas = schema.get("types", {})
    relation_schemas = schema.get("relations", {})
    global_constraints = schema.get("constraints", [])
    
    for entity_id, entity in entities.items():
        type_name = entity["type"]
        type_schema = type_schemas.get(type_name, {})
        
        # Check required properties
        required = type_schema.get("required", [])
        for prop in required:
            if prop not in entity["properties"]:
                errors.append(f"{entity_id}: missing required property '{prop}'")
        
        # Check forbidden properties
        forbidden = type_schema.get("forbidden_properties", [])
        for prop in forbidden:
            if prop in entity["properties"]:
                errors.append(f"{entity_id}: contains forbidden property '{prop}'")
        
        # Check enum values
        for prop, allowed in type_schema.items():
            if prop.endswith("_enum"):
                field = prop.replace("_enum", "")
                value = entity["properties"].get(field)
                if value and value not in allowed:
                    errors.append(f"{entity_id}: '{field}' must be one of {allowed}, got '{value}'")
    
    # Relation constraints (type + cardinality + acyclicity)
    rel_index = {}
    for rel in relations:
        rel_index.setdefault(rel["rel"], []).append(rel)
    
    for rel_type, rel_schema in relation_schemas.items():
        rels = rel_index.get(rel_type, [])
        from_types = rel_schema.get("from_types", [])
        to_types = rel_schema.get("to_types", [])
        cardinality = rel_schema.get("cardinality")
        acyclic = rel_schema.get("acyclic", False)
        
        # Type checks
        for rel in rels:
            from_entity = entities.get(rel["from"])
            to_entity = entities.get(rel["to"])
            if not from_entity or not to_entity:
                errors.append(f"{rel_type}: relation references missing entity ({rel['from']} -> {rel['to']})")
                continue
            if from_types and from_entity["type"] not in from_types:
                errors.append(
                    f"{rel_type}: from entity {rel['from']} type {from_entity['type']} not in {from_types}"
                )
            if to_types and to_entity["type"] not in to_types:
                errors.append(
                    f"{rel_type}: to entity {rel['to']} type {to_entity['type']} not in {to_types}"
                )
        
        # Cardinality checks
        if cardinality in ("one_to_one", "one_to_many", "many_to_one"):
            from_counts = {}
            to_counts = {}
            for rel in rels:
                from_counts[rel["from"]] = from_counts.get(rel["from"], 0) + 1
                to_counts[rel["to"]] = to_counts.get(rel["to"], 0) + 1
            
            if cardinality in ("one_to_one", "many_to_one"):
                for from_id, count in from_counts.items():
                    if count > 1:
                        errors.append(f"{rel_type}: from entity {from_id} violates cardinality {cardinality}")
            if cardinality in ("one_to_one", "one_to_many"):
                for to_id, count in to_counts.items():
                    if count > 1:
                        errors.append(f"{rel_type}: to entity {to_id} violates cardinality {cardinality}")
        
        # Acyclic checks
        if acyclic:
            graph = {}
            for rel in rels:
                graph.setdefault(rel["from"], []).append(rel["to"])
            
            visited = {}
            
            def dfs(node, stack):
                visited[node] = True
                stack.add(node)
                for nxt in graph.get(node, []):
                    if nxt in stack:
                        return True
                    if not visited.get(nxt, False):
                        if dfs(nxt, stack):
                            return True
                stack.remove(node)
                return False
            
            for node in graph:
                if not visited.get(node, False):
                    if dfs(node, set()):
                        errors.append(f"{rel_type}: cyclic dependency detected")
                        break
    
    # Global constraints (limited enforcement)
    for constraint in global_constraints:
        ctype = constraint.get("type")
        relation = constraint.get("relation")
        rule = (constraint.get("rule") or "").strip().lower()
        if ctype == "Event" and "end" in rule and "start" in rule:
            for entity_id, entity in entities.items():
                if entity["type"] != "Event":
                    continue
                start = entity["properties"].get("start")
                end = entity["properties"].get("end")
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start)
                        end_dt = datetime.fromisoformat(end)
                        if end_dt < start_dt:
                            errors.append(f"{entity_id}: end must be >= start")
                    except ValueError:
                        errors.append(f"{entity_id}: invalid datetime format in start/end")
        if relation and rule == "acyclic":
            # Already enforced above via relations schema
            continue
    
    return errors
