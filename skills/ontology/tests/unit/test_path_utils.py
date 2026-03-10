"""Tests for path utilities."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.utils.path_utils import resolve_safe_path


class TestResolveSafePath:
    """Test path resolution with security checks."""
    
    def test_resolves_relative_path(self):
        """Should resolve relative paths against root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_safe_path("test.txt", root=Path(tmpdir))
            assert result == Path(tmpdir) / "test.txt"
    
    def test_resolves_absolute_path_within_root(self):
        """Should accept absolute paths within root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_safe_path(f"{tmpdir}/test.txt", root=Path(tmpdir))
            assert result == Path(tmpdir) / "test.txt"
    
    def test_rejects_path_traversal(self):
        """Should reject paths outside root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SystemExit):
                resolve_safe_path("../outside.txt", root=Path(tmpdir))
    
    def test_rejects_empty_path(self):
        """Should reject empty paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SystemExit):
                resolve_safe_path("", root=Path(tmpdir))
    
    def test_requires_existence_when_flag_set(self):
        """Should check existence when must_exist=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SystemExit):
                resolve_safe_path("nonexistent.txt", root=Path(tmpdir), must_exist=True)
    
    def test_allows_nonexistent_when_flag_not_set(self):
        """Should allow non-existent paths when must_exist=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_safe_path("nonexistent.txt", root=Path(tmpdir), must_exist=False)
            assert result == Path(tmpdir) / "nonexistent.txt"
    
    def test_expands_user_path(self):
        """Should expand ~ to home directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use the temp dir as root so ~ expansion stays within it
            result = resolve_safe_path("~/test.txt", root=Path.home())
            assert str(result).startswith(str(Path.home()))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
