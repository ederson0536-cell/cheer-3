"""Tests for graph loading utilities."""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.graph_loader import load_graph, append_op


class TestLoadGraph:
    """Test graph loading from JSONL."""
    
    def test_returns_empty_for_missing_file(self):
        """Should return empty structures for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entities, relations = load_graph(f"{tmpdir}/nonexistent.jsonl")
            assert entities == {}
            assert relations == []
    
    def test_loads_create_operations(self):
        """Should load entity creation operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            with open(graph_path, "w") as f:
                f.write(json.dumps({"op": "create", "entity": {"id": "p_001", "type": "Person", "properties": {"name": "Alice"}}}))
            
            entities, relations = load_graph(graph_path)
            assert "p_001" in entities
            assert entities["p_001"]["type"] == "Person"
    
    def test_applies_update_operations(self):
        """Should apply updates to entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            with open(graph_path, "w") as f:
                f.write(json.dumps({"op": "create", "entity": {"id": "p_001", "type": "Person", "properties": {"name": "Alice"}}}) + "\n")
                f.write(json.dumps({"op": "update", "id": "p_001", "properties": {"age": 30}}) + "\n")
            
            entities, relations = load_graph(graph_path)
            assert entities["p_001"]["properties"]["age"] == 30
    
    def test_applies_delete_operations(self):
        """Should remove deleted entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            with open(graph_path, "w") as f:
                f.write(json.dumps({"op": "create", "entity": {"id": "p_001", "type": "Person", "properties": {}}}) + "\n")
                f.write(json.dumps({"op": "delete", "id": "p_001"}) + "\n")
            
            entities, relations = load_graph(graph_path)
            assert "p_001" not in entities
    
    def test_loads_relate_operations(self):
        """Should load relation operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            with open(graph_path, "w") as f:
                f.write(json.dumps({"op": "relate", "from": "p_001", "rel": "knows", "to": "p_002"}) + "\n")
            
            entities, relations = load_graph(graph_path)
            assert len(relations) == 1
            assert relations[0]["from"] == "p_001"
    
    def test_removes_unrelate_operations(self):
        """Should remove relations on unrelate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            with open(graph_path, "w") as f:
                f.write(json.dumps({"op": "relate", "from": "p_001", "rel": "knows", "to": "p_002"}) + "\n")
                f.write(json.dumps({"op": "unrelate", "from": "p_001", "rel": "knows", "to": "p_002"}) + "\n")
            
            entities, relations = load_graph(graph_path)
            assert len(relations) == 0


class TestAppendOp:
    """Test appending operations to graph."""
    
    def test_creates_parent_directories(self):
        """Should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/deep/nested/graph.jsonl"
            append_op(graph_path, {"op": "create", "entity": {"id": "test"}})
            assert Path(graph_path).exists()
    
    def test_appends_record(self):
        """Should append record as JSON line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            record = {"op": "create", "entity": {"id": "p_001"}}
            append_op(graph_path, record)
            
            with open(graph_path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            assert json.loads(lines[0]) == record


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
