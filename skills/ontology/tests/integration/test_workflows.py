"""Integration tests for complete ontology workflows."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from src.services.entity_service import create_entity, get_entity, query_entities
from src.services.relation_service import create_relation, get_related
from src.services.validation_service import validate_graph


class TestCompleteWorkflow:
    """Test end-to-end workflows."""
    
    def test_create_and_query_entities(self):
        """Should create and query entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            # Create entities
            alice = create_entity("Person", {"name": "Alice", "age": 30}, graph_path)
            bob = create_entity("Person", {"name": "Bob", "age": 25}, graph_path)
            task = create_entity("Task", {"title": "Important work"}, graph_path)
            
            # Query all people
            people = query_entities("Person", {}, graph_path)
            assert len(people) == 2
            
            # Query by age
            thirty_year_olds = query_entities("Person", {"age": 30}, graph_path)
            assert len(thirty_year_olds) == 1
            assert thirty_year_olds[0]["properties"]["name"] == "Alice"
    
    def test_create_relations_and_traverse(self):
        """Should create relations and traverse graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            # Create project and tasks
            project = create_entity("Project", {"name": "Website"}, graph_path, "proj_001")
            task1 = create_entity("Task", {"title": "Design"}, graph_path, "task_001")
            task2 = create_entity("Task", {"title": "Develop"}, graph_path, "task_002")
            
            # Create relations
            create_relation("proj_001", "has_task", "task_001", {"priority": "high"}, graph_path)
            create_relation("proj_001", "has_task", "task_002", {"priority": "medium"}, graph_path)
            
            # Traverse from project to tasks
            tasks = get_related("proj_001", "has_task", graph_path, "outgoing")
            assert len(tasks) == 2
            
            # Traverse from task to project (incoming)
            projects = get_related("task_001", "has_task", graph_path, "incoming")
            assert len(projects) == 1
            assert projects[0]["entity"]["id"] == "proj_001"
    
    def test_full_validation_workflow(self):
        """Should validate complete graph against schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            # Define schema
            schema = {
                "types": {
                    "Person": {
                        "required": ["name", "email"],
                        "forbidden_properties": ["password"]
                    },
                    "Project": {
                        "required": ["name"]
                    }
                },
                "relations": {
                    "manages": {
                        "from_types": ["Person"],
                        "to_types": ["Person"],
                        "cardinality": "one_to_many"
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            # Create valid entities
            create_entity("Person", {"name": "Alice", "email": "alice@example.com"}, graph_path, "p_001")
            create_entity("Person", {"name": "Bob", "email": "bob@example.com"}, graph_path, "p_002")
            create_entity("Project", {"name": "Website"}, graph_path, "proj_001")
            
            # Create valid relation
            create_relation("p_001", "manages", "p_002", {}, graph_path)
            
            # Should validate successfully
            errors = validate_graph(graph_path, schema_path)
            assert errors == []
            
            # Add invalid entity (missing required field)
            create_entity("Person", {"name": "Charlie"}, graph_path, "p_003")
            
            errors = validate_graph(graph_path, schema_path)
            assert any("missing required property 'email'" in e for e in errors)
    
    def test_graph_persistence(self):
        """Should persist across multiple sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            # Session 1: Create entities
            alice = create_entity("Person", {"name": "Alice"}, graph_path)
            alice_id = alice["id"]
            
            # Session 2: Read and update
            loaded = get_entity(alice_id, graph_path)
            assert loaded is not None
            
            from src.services.entity_service import update_entity
            update_entity(alice_id, {"age": 31}, graph_path)
            
            # Session 3: Verify update persisted
            updated = get_entity(alice_id, graph_path)
            assert updated["properties"]["age"] == 31


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
