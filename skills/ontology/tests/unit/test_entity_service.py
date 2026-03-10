"""Tests for entity service."""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.entity_service import (
    create_entity, get_entity, query_entities, 
    list_entities, update_entity, delete_entity
)


class TestCreateEntity:
    """Test entity creation."""
    
    def test_creates_entity_with_auto_id(self):
        """Should auto-generate ID if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            entity = create_entity("Person", {"name": "Alice"}, graph_path)
            assert "id" in entity
            assert entity["type"] == "Person"
            assert entity["properties"]["name"] == "Alice"
    
    def test_uses_provided_id(self):
        """Should use provided ID if given."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            entity = create_entity("Person", {"name": "Alice"}, graph_path, entity_id="custom_001")
            assert entity["id"] == "custom_001"
    
    def test_persists_to_graph(self):
        """Should persist entity to graph file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            entity = create_entity("Person", {"name": "Alice"}, graph_path)
            
            # Load and verify
            loaded_entity = get_entity(entity["id"], graph_path)
            assert loaded_entity is not None
            assert loaded_entity["properties"]["name"] == "Alice"


class TestGetEntity:
    """Test entity retrieval."""
    
    def test_returns_entity_if_exists(self):
        """Should return entity if it exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            created = create_entity("Person", {"name": "Alice"}, graph_path)
            
            entity = get_entity(created["id"], graph_path)
            assert entity is not None
            assert entity["properties"]["name"] == "Alice"
    
    def test_returns_none_if_not_exists(self):
        """Should return None if entity doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            entity = get_entity("nonexistent", graph_path)
            assert entity is None


class TestQueryEntities:
    """Test entity querying."""
    
    def test_filters_by_type(self):
        """Should filter by entity type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            create_entity("Person", {"name": "Alice"}, graph_path)
            create_entity("Task", {"title": "Do work"}, graph_path)
            
            results = query_entities("Person", {}, graph_path)
            assert len(results) == 1
            assert results[0]["type"] == "Person"
    
    def test_filters_by_properties(self):
        """Should filter by property values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            create_entity("Person", {"name": "Alice", "age": 30}, graph_path)
            create_entity("Person", {"name": "Bob", "age": 25}, graph_path)
            
            results = query_entities("Person", {"age": 30}, graph_path)
            assert len(results) == 1
            assert results[0]["properties"]["name"] == "Alice"
    
    def test_returns_all_types_when_type_none(self):
        """Should return all types when type is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            create_entity("Person", {}, graph_path)
            create_entity("Task", {}, graph_path)
            
            results = query_entities(None, {}, graph_path)
            assert len(results) == 2


class TestListEntities:
    """Test entity listing."""
    
    def test_lists_all_when_no_type(self):
        """Should list all entities when no type filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            create_entity("Person", {}, graph_path)
            create_entity("Task", {}, graph_path)
            
            results = list_entities(None, graph_path)
            assert len(results) == 2
    
    def test_filters_by_type(self):
        """Should filter by type when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            create_entity("Person", {}, graph_path)
            create_entity("Task", {}, graph_path)
            
            results = list_entities("Person", graph_path)
            assert len(results) == 1
            assert results[0]["type"] == "Person"


class TestUpdateEntity:
    """Test entity updates."""
    
    def test_updates_properties(self):
        """Should merge new properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            created = create_entity("Person", {"name": "Alice"}, graph_path)
            
            updated = update_entity(created["id"], {"age": 30}, graph_path)
            assert updated["properties"]["name"] == "Alice"
            assert updated["properties"]["age"] == 30
    
    def test_returns_none_for_missing_entity(self):
        """Should return None if entity doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            result = update_entity("nonexistent", {"age": 30}, graph_path)
            assert result is None
    
    def test_persists_update(self):
        """Should persist update to graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            created = create_entity("Person", {"name": "Alice"}, graph_path)
            update_entity(created["id"], {"age": 30}, graph_path)
            
            loaded = get_entity(created["id"], graph_path)
            assert loaded["properties"]["age"] == 30


class TestDeleteEntity:
    """Test entity deletion."""
    
    def test_deletes_existing_entity(self):
        """Should delete existing entity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            created = create_entity("Person", {}, graph_path)
            
            result = delete_entity(created["id"], graph_path)
            assert result is True
            assert get_entity(created["id"], graph_path) is None
    
    def test_returns_false_for_missing_entity(self):
        """Should return False if entity doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = f"{tmpdir}/graph.jsonl"
            result = delete_entity("nonexistent", graph_path)
            assert result is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
