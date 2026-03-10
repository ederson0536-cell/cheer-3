"""Tests for schema service."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from src.services.schema_service import load_schema, write_schema, merge_schema, append_schema


class TestLoadSchema:
    """Test schema loading."""
    
    def test_returns_empty_for_missing_file(self):
        """Should return empty dict for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = f"{tmpdir}/nonexistent.yaml"
            schema = load_schema(schema_path)
            assert schema == {}
    
    def test_loads_existing_yaml(self):
        """Should load existing YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = f"{tmpdir}/schema.yaml"
            data = {"types": {"Person": {"required": ["name"]}}}
            with open(schema_path, "w") as f:
                yaml.dump(data, f)
            
            schema = load_schema(schema_path)
            assert schema["types"]["Person"]["required"] == ["name"]


class TestWriteSchema:
    """Test schema writing."""
    
    def test_writes_yaml_file(self):
        """Should write schema to YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = f"{tmpdir}/schema.yaml"
            data = {"types": {"Person": {}}}
            
            write_schema(schema_path, data, root=Path(tmpdir))
            
            with open(schema_path) as f:
                loaded = yaml.safe_load(f)
            assert loaded["types"]["Person"] == {}
    
    def test_creates_parent_directories(self):
        """Should create parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = f"{tmpdir}/deep/nested/schema.yaml"
            data = {"types": {}}
            
            write_schema(schema_path, data, root=Path(tmpdir))
            
            assert Path(schema_path).exists()


class TestMergeSchema:
    """Test schema merging."""
    
    def test_adds_new_keys(self):
        """Should add keys from incoming."""
        base = {"types": {"Person": {}}}
        incoming = {"relations": {"knows": {}}}
        
        merged = merge_schema(base, incoming)
        assert "types" in merged
        assert "relations" in merged
    
    def test_merges_nested_dicts(self):
        """Should recursively merge nested dicts."""
        base = {"types": {"Person": {"required": ["name"]}}}
        incoming = {"types": {"Person": {"forbidden": ["password"]}}}
        
        merged = merge_schema(base, incoming)
        assert "required" in merged["types"]["Person"]
        assert "forbidden" in merged["types"]["Person"]
    
    def test_appends_lists(self):
        """Should append lists without duplicates."""
        base = {"types": {"Person": {"tags": ["human"]}}}
        incoming = {"types": {"Person": {"tags": ["mortal", "human"]}}}
        
        merged = merge_schema(base, incoming)
        assert "human" in merged["types"]["Person"]["tags"]
        assert "mortal" in merged["types"]["Person"]["tags"]
        assert merged["types"]["Person"]["tags"].count("human") == 1


class TestAppendSchema:
    """Test schema appending."""
    
    def test_appends_to_existing(self):
        """Should merge into existing schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = f"{tmpdir}/schema.yaml"
            initial = {"types": {"Person": {}}}
            with open(schema_path, "w") as f:
                yaml.dump(initial, f)
            
            incoming = {"relations": {"knows": {}}}
            merged = append_schema(schema_path, incoming, root=Path(tmpdir))
            
            assert "types" in merged
            assert "relations" in merged
    
    def test_creates_new_if_missing(self):
        """Should create new file if doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = f"{tmpdir}/new_schema.yaml"
            incoming = {"types": {"Person": {}}}
            
            merged = append_schema(schema_path, incoming, root=Path(tmpdir))
            
            assert merged["types"]["Person"] == {}
            assert Path(schema_path).exists()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
