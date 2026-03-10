#!/usr/bin/env python3
"""Ontology graph operations CLI."""

import argparse
import json
from pathlib import Path

from src import (
    create_entity,
    get_entity,
    query_entities,
    list_entities,
    update_entity,
    delete_entity,
    create_relation,
    get_related,
    validate_graph,
    load_schema,
    append_schema,
    resolve_safe_path,
)

DEFAULT_GRAPH_PATH = "memory/ontology/graph.jsonl"
DEFAULT_SCHEMA_PATH = "memory/ontology/schema.yaml"


def main():
    parser = argparse.ArgumentParser(description="Ontology graph operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Create
    create_p = subparsers.add_parser("create", help="Create entity")
    create_p.add_argument("--type", "-t", required=True, help="Entity type")
    create_p.add_argument("--props", "-p", default="{}", help="Properties JSON")
    create_p.add_argument("--id", help="Entity ID (auto-generated if not provided)")
    create_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Get
    get_p = subparsers.add_parser("get", help="Get entity by ID")
    get_p.add_argument("--id", required=True, help="Entity ID")
    get_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Query
    query_p = subparsers.add_parser("query", help="Query entities")
    query_p.add_argument("--type", "-t", help="Entity type")
    query_p.add_argument("--where", "-w", default="{}", help="Filter JSON")
    query_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # List
    list_p = subparsers.add_parser("list", help="List entities")
    list_p.add_argument("--type", "-t", help="Entity type")
    list_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Update
    update_p = subparsers.add_parser("update", help="Update entity")
    update_p.add_argument("--id", required=True, help="Entity ID")
    update_p.add_argument("--props", "-p", required=True, help="Properties JSON")
    update_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Delete
    delete_p = subparsers.add_parser("delete", help="Delete entity")
    delete_p.add_argument("--id", required=True, help="Entity ID")
    delete_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Relate
    relate_p = subparsers.add_parser("relate", help="Create relation")
    relate_p.add_argument("--from", dest="from_id", required=True, help="From entity ID")
    relate_p.add_argument("--rel", "-r", required=True, help="Relation type")
    relate_p.add_argument("--to", dest="to_id", required=True, help="To entity ID")
    relate_p.add_argument("--props", "-p", default="{}", help="Relation properties JSON")
    relate_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Related
    related_p = subparsers.add_parser("related", help="Get related entities")
    related_p.add_argument("--id", required=True, help="Entity ID")
    related_p.add_argument("--rel", "-r", help="Relation type filter")
    related_p.add_argument("--dir", "-d", choices=["outgoing", "incoming", "both"], default="outgoing")
    related_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Validate
    validate_p = subparsers.add_parser("validate", help="Validate graph")
    validate_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    validate_p.add_argument("--schema", "-s", default=DEFAULT_SCHEMA_PATH)

    # Schema append
    schema_p = subparsers.add_parser("schema-append", help="Append/merge schema fragment")
    schema_p.add_argument("--schema", "-s", default=DEFAULT_SCHEMA_PATH)
    schema_p.add_argument("--data", "-d", help="Schema fragment as JSON")
    schema_p.add_argument("--file", "-f", help="Schema fragment file (YAML or JSON)")
    
    args = parser.parse_args()
    workspace_root = Path.cwd().resolve()

    if hasattr(args, "graph"):
        args.graph = str(
            resolve_safe_path(args.graph, root=workspace_root, label="graph path")
        )
    if hasattr(args, "schema"):
        args.schema = str(
            resolve_safe_path(args.schema, root=workspace_root, label="schema path")
        )
    if hasattr(args, "file") and args.file:
        args.file = str(
            resolve_safe_path(
                args.file, root=workspace_root, must_exist=True, label="schema file"
            )
        )
    
    if args.command == "create":
        props = json.loads(args.props)
        entity = create_entity(args.type, props, args.graph, args.id)
        print(json.dumps(entity, indent=2))
    
    elif args.command == "get":
        entity = get_entity(args.id, args.graph)
        if entity:
            print(json.dumps(entity, indent=2))
        else:
            print(f"Entity not found: {args.id}")
    
    elif args.command == "query":
        where = json.loads(args.where)
        results = query_entities(args.type, where, args.graph)
        print(json.dumps(results, indent=2))
    
    elif args.command == "list":
        results = list_entities(args.type, args.graph)
        print(json.dumps(results, indent=2))
    
    elif args.command == "update":
        props = json.loads(args.props)
        entity = update_entity(args.id, props, args.graph)
        if entity:
            print(json.dumps(entity, indent=2))
        else:
            print(f"Entity not found: {args.id}")
    
    elif args.command == "delete":
        if delete_entity(args.id, args.graph):
            print(f"Deleted: {args.id}")
        else:
            print(f"Entity not found: {args.id}")
    
    elif args.command == "relate":
        props = json.loads(args.props)
        rel = create_relation(args.from_id, args.rel, args.to_id, props, args.graph)
        print(json.dumps(rel, indent=2))
    
    elif args.command == "related":
        results = get_related(args.id, args.rel, args.graph, args.dir)
        print(json.dumps(results, indent=2))
    
    elif args.command == "validate":
        errors = validate_graph(args.graph, args.schema)
        if errors:
            print("Validation errors:")
            for err in errors:
                print(f"  - {err}")
        else:
            print("Graph is valid.")
    
    elif args.command == "schema-append":
        if not args.data and not args.file:
            raise SystemExit("schema-append requires --data or --file")
        
        incoming = {}
        if args.data:
            incoming = json.loads(args.data)
        else:
            path = Path(args.file)
            if path.suffix.lower() == ".json":
                with open(path) as f:
                    incoming = json.load(f)
            else:
                import yaml
                with open(path) as f:
                    incoming = yaml.safe_load(f) or {}
        
        merged = append_schema(args.schema, incoming, root=workspace_root)
        print(json.dumps(merged, indent=2))


if __name__ == "__main__":
    main()
