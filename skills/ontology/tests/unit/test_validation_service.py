"""Tests for validation service."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from src.services.entity_service import create_entity
from src.services.relation_service import create_relation
from src.services.validation_service import validate_graph


class TestValidateGraph:
    """Test graph validation."""
    
    def test_valid_graph_has_no_errors(self):
        """Should return empty list for valid graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            create_entity("Person", {"name": "Alice"}, graph_path)
            
            errors = validate_graph(graph_path, schema_path)
            assert errors == []
    
    def test_detects_missing_required_property(self):
        """Should detect missing required properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            schema = {
                "types": {
                    "Person": {
                        "required": ["name"]
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            create_entity("Person", {"age": 30}, graph_path)
            
            errors = validate_graph(graph_path, schema_path)
            assert any("missing required property 'name'" in e for e in errors)
    
    def test_detects_forbidden_property(self):
        """Should detect forbidden properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            schema = {
                "types": {
                    "Person": {
                        "forbidden_properties": ["password"]
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            create_entity("Person", {"name": "Alice", "password": "secret"}, graph_path)
            
            errors = validate_graph(graph_path, schema_path)
            assert any("forbidden property 'password'" in e for e in errors)
    
    def test_detects_invalid_enum_value(self):
        """Should detect invalid enum values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            schema = {
                "types": {
                    "Task": {
                        "status_enum": ["open", "closed"]
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            create_entity("Task", {"status": "invalid"}, graph_path)
            
            errors = validate_graph(graph_path, schema_path)
            assert any("must be one of" in e for e in errors)
    
    def test_detects_relation_type_mismatch(self):
        """Should detect relation type mismatches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            schema = {
                "relations": {
                    "manages": {
                        "from_types": ["Manager"],
                        "to_types": ["Employee"]
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            create_entity("Person", {}, graph_path, "p_001")
            create_entity("Person", {}, graph_path, "p_002")
            create_relation("p_001", "manages", "p_002", {}, graph_path)
            
            errors = validate_graph(graph_path, schema_path)
            assert any("type" in e.lower() for e in errors)
    
    def test_detects_cardinality_violation(self):
        """Should detect cardinality violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            schema = {
                "relations": {
                    "spouse": {
                        "cardinality": "one_to_one"
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            create_entity("Person", {}, graph_path, "p_001")
            create_entity("Person", {}, graph_path, "p_002")
            create_entity("Person", {}, graph_path, "p_003")
            create_relation("p_001", "spouse", "p_002", {}, graph_path)
            create_relation("p_001", "spouse", "p_003", {}, graph_path)
            
            errors = validate_graph(graph_path, schema_path)
            assert any("cardinality" in e.lower() for e in errors)
    
    def test_detects_cyclic_dependency(self):
        """Should detect cyclic dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            schema_path = f"{tmpdir}/schema.yaml"
            
            schema = {
                "relations": {
                    "depends_on": {
                        "acyclic": True
                    }
                }
            }
            with open(schema_path, "w") as f:
                yaml.dump(schema, f)
            
            create_entity("Task", {}, graph_path, "t_001")
            create_entity("Task", {}, graph_path, "t_002")
            create_entity("Task", {}, graph_path, "t_003")
            create_relation("t_001", "depends_on", "t_002", {}, graph_path)
            create_relation("t_002", "depends_on", "t_003", {}, graph_path)
            create_relation("t_003", "depends_on", "t_001", {}, graph_path)  # Cycle!
            
            errors = validate_graph(graph_path, schema_path)
            assert any("cyclic" in e.lower() for e in errors)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
