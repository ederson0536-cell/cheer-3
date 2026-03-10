"""Tests for relation service."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.entity_service import create_entity
from src.services.relation_service import create_relation, get_related


class TestCreateRelation:
    """Test relation creation."""
    
    def test_creates_relation(self):
        """Should create relation between entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            rel = create_relation("p_001", "knows", "p_002", {"since": "2020"}, graph_path)
            
            assert rel["from"] == "p_001"
            assert rel["rel"] == "knows"
            assert rel["to"] == "p_002"
            assert rel["properties"]["since"] == "2020"
    
    def test_persists_relation(self):
        """Should persist relation to graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            # Create entities first (relations need entities to exist)
            from src.services.entity_service import create_entity
            create_entity("Person", {}, graph_path, "p_001")
            create_entity("Person", {}, graph_path, "p_002")
            
            create_relation("p_001", "knows", "p_002", {}, graph_path)
            related = get_related("p_001", None, graph_path, "outgoing")
            
            assert len(related) == 1


class TestGetRelated:
    """Test getting related entities."""
    
    def test_gets_outgoing_relations(self):
        """Should get outgoing relations by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            # Create entities first
            alice = create_entity("Person", {"name": "Alice"}, graph_path, "p_001")
            bob = create_entity("Person", {"name": "Bob"}, graph_path, "p_002")
            
            create_relation("p_001", "knows", "p_002", {}, graph_path)
            
            related = get_related("p_001", None, graph_path, "outgoing")
            assert len(related) == 1
            assert related[0]["entity"]["id"] == "p_002"
    
    def test_gets_incoming_relations(self):
        """Should get incoming relations when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            alice = create_entity("Person", {"name": "Alice"}, graph_path, "p_001")
            bob = create_entity("Person", {"name": "Bob"}, graph_path, "p_002")
            
            create_relation("p_001", "knows", "p_002", {}, graph_path)
            
            related = get_related("p_002", None, graph_path, "incoming")
            assert len(related) == 1
            assert related[0]["entity"]["id"] == "p_001"
    
    def test_gets_both_directions(self):
        """Should get both directions when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            alice = create_entity("Person", {"name": "Alice"}, graph_path, "p_001")
            bob = create_entity("Person", {"name": "Bob"}, graph_path, "p_002")
            
            create_relation("p_001", "knows", "p_002", {}, graph_path)
            
            related = get_related("p_001", None, graph_path, "both")
            assert len(related) == 1
            assert "direction" in related[0]
    
    def test_filters_by_relation_type(self):
        """Should filter by relation type when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            
            alice = create_entity("Person", {"name": "Alice"}, graph_path, "p_001")
            bob = create_entity("Person", {"name": "Bob"}, graph_path, "p_002")
            charlie = create_entity("Person", {"name": "Charlie"}, graph_path, "p_003")
            
            create_relation("p_001", "knows", "p_002", {}, graph_path)
            create_relation("p_001", "works_with", "p_003", {}, graph_path)
            
            related = get_related("p_001", "knows", graph_path, "outgoing")
            assert len(related) == 1
            assert related[0]["relation"] == "knows"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
