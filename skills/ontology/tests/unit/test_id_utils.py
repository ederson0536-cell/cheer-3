"""Tests for ID generation utilities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.id_utils import generate_id


class TestGenerateId:
    """Test ID generation."""
    
    def test_generates_unique_ids(self):
        """IDs should be unique."""
        id1 = generate_id("Person")
        id2 = generate_id("Person")
        assert id1 != id2
    
    def test_uses_type_prefix(self):
        """ID should start with type prefix."""
        id_val = generate_id("Person")
        assert id_val.startswith("pers_")
    
    def test_truncates_long_types(self):
        """Long type names should be truncated to 4 chars."""
        id_val = generate_id("Organization")
        assert id_val.startswith("orga_")
    
    def test_has_correct_format(self):
        """ID should have prefix + underscore + 8 hex chars."""
        id_val = generate_id("Task")
        parts = id_val.split("_")
        assert len(parts) == 2
        assert len(parts[0]) <= 4
        assert len(parts[1]) == 8


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
