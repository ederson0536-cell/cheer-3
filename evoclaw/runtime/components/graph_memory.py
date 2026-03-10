#!/usr/bin/env python3
"""
Graph Memory System
Relationship-based knowledge graph for intelligent retrieval
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List, Set, Optional
from collections import defaultdict

WORKSPACE = str(resolve_workspace(__file__))
GRAPH_PATH = Path(WORKSPACE) / "memory" / "graph"


class GraphMemory:
    """Graph-based Memory System"""
    
    def __init__(self):
        GRAPH_PATH.mkdir(parents=True, exist_ok=True)
        self.entities_file = GRAPH_PATH / "entities.jsonl"
        self.relations_file = GRAPH_PATH / "relations.jsonl"
        
        # Initialize files
        if not self.entities_file.exists():
            self.entities_file.touch()
        if not self.relations_file.exists():
            self.relations_file.touch()
    
    def add_entity(
        self, 
        entity_type: str, 
        entity_id: str, 
        properties: Dict = None
    ) -> bool:
        """Add an entity to the graph"""
        
        entity = {
            "type": entity_type,
            "id": entity_id,
            "properties": properties or {},
            "created_at": datetime.now().isoformat()
        }
        
        with open(self.entities_file, "a") as f:
            f.write(json.dumps(entity, ensure_ascii=False) + "\n")
        
        return True
    
    def add_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        properties: Dict = None
    ) -> bool:
        """Add a relationship between entities"""
        
        relation = {
            "from": from_entity,
            "to": to_entity,
            "type": relation_type,
            "properties": properties or {},
            "created_at": datetime.now().isoformat()
        }
        
        with open(self.relations_file, "a") as f:
            f.write(json.dumps(relation, ensure_ascii=False) + "\n")
        
        return True
    
    def find_related(
        self, 
        entity_id: str, 
        relation_type: str = None,
        depth: int = 1
    ) -> List[Dict]:
        """Find related entities"""
        
        results = []
        visited = set()
        
        def traverse(eid: str, d: int):
            if d > depth or eid in visited:
                return
            
            visited.add(eid)
            
            # Find relations
            if self.relations_file.exists():
                with open(self.relations_file) as f:
                    for line in f:
                        r = json.loads(line)
                        
                        # Find outgoing relations
                        if r["from"] == eid:
                            if relation_type is None or r["type"] == relation_type:
                                results.append({
                                    "entity": r["to"],
                                    "relation": r["type"],
                                    "distance": d
                                })
                                traverse(r["to"], d + 1)
        
        traverse(entity_id, 1)
        return results
    
    def find_by_type(self, entity_type: str) -> List[Dict]:
        """Find all entities of a type"""
        
        results = []
        
        if self.entities_file.exists():
            with open(self.entities_file) as f:
                for line in f:
                    e = json.loads(line)
                    if e["type"] == entity_type:
                        results.append(e)
        
        return results
    
    def find_by_property(self, key: str, value: str) -> List[Dict]:
        """Find entities by property value"""
        
        results = []
        
        if self.entities_file.exists():
            with open(self.entities_file) as f:
                for line in f:
                    e = json.loads(line)
                    props = e.get("properties", {})
                    if props.get(key) == value:
                        results.append(e)
        
        return results
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity by ID"""
        
        if self.entities_file.exists():
            with open(self.entities_file) as f:
                for line in f:
                    e = json.loads(line)
                    if e["id"] == entity_id:
                        return e
        
        return None
    
    def search_by_context(self, context: Dict) -> List[Dict]:
        """Search entities by context (multi-hop query)"""
        
        results = []
        
        # Start with property matching
        candidates = []
        for key, value in context.items():
            candidates.extend(self.find_by_property(key, value))
        
        # Find relationships between candidates
        entity_ids = {e["id"] for e in candidates}
        
        for eid in entity_ids:
            relations = self.find_related(eid, depth=2)
            if relations:
                results.append({
                    "entity": self.get_entity(eid),
                    "related": relations
                })
        
        return results


# Predefined entity types and relation types
ENTITY_TYPES = [
    "TaskType",
    "SubtaskType", 
    "Scenario",
    "Rule",
    "Skill",
    "Experience",
    "Proposal",
    "KnowledgeCandidate",
    "FailureMode"
]

RELATION_TYPES = [
    {"from": "TaskType", "to": "Rule", "name": "requires"},
    {"from": "SubtaskType", "to": "Skill", "name": "prefers"},
    {"from": "Scenario", "to": "Rule", "name": "triggers"},
    {"from": "Skill", "to": "Experience", "name": "solved"},
    {"from": "Experience", "to": "Rule", "name": "improves"},
    {"from": "Proposal", "to": "Rule", "name": "modifies"},
    {"from": "FailureMode", "to": "Proposal", "name": "suggests"}
]


# Global instance
_graph_memory = None

def get_graph_memory() -> GraphMemory:
    """Get global graph memory instance"""
    global _graph_memory
    if _graph_memory is None:
        _graph_memory = GraphMemory()
    return _graph_memory


if __name__ == "__main__":
    import sys
    
    graph = get_graph_memory()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "add_entity":
            # add_entity <type> <id> [key=value...]
            entity_type = sys.argv[2]
            entity_id = sys.argv[3]
            props = {}
            for arg in sys.argv[4:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    props[k] = v
            graph.add_entity(entity_type, entity_id, props)
            print(f"Added: {entity_type}:{entity_id}")
        
        elif cmd == "add_relation":
            # add_relation <from> <to> <type>
            graph.add_relation(sys.argv[2], sys.argv[3], sys.argv[4])
            print(f"Relation added")
        
        elif cmd == "find":
            # find <entity_id> [depth]
            depth = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            results = graph.find_related(sys.argv[2], depth=depth)
            print(json.dumps(results, indent=2))
        
        elif cmd == "by_type":
            results = graph.find_by_type(sys.argv[2])
            print(f"Found {len(results)} entities")
            for e in results:
                print(f"  - {e['id']}")
    else:
        print("""
Graph Memory CLI
===============
add_entity <type> <id> [key=value...]
add_relation <from> <to> <type>
find <entity_id> [depth]
by_type <type>
""")
