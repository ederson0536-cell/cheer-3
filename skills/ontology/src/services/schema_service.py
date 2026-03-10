"""Schema service - YAML schema loading and manipulation."""

from pathlib import Path


def load_schema(schema_path: str) -> dict:
    """Load schema from YAML if it exists.
    
    Args:
        schema_path: Path to the schema file
        
    Returns:
        Schema dict (empty if file doesn't exist)
    """
    schema = {}
    schema_file = Path(schema_path)
    if schema_file.exists():
        import yaml
        with open(schema_file) as f:
            schema = yaml.safe_load(f) or {}
    return schema


def write_schema(schema_path: str, schema: dict, *, root: Path | None = None) -> None:
    """Write schema to YAML with path validation.
    
    Args:
        schema_path: Path to write the schema
        schema: Schema dict to write
        root: Root directory for path validation
    """
    from ..utils.path_utils import resolve_safe_path
    
    safe_root = (root or Path.cwd()).resolve()
    schema_file = resolve_safe_path(schema_path, root=safe_root, label="schema path")
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    with open(schema_file, "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False)


def merge_schema(base: dict, incoming: dict) -> dict:
    """Merge incoming schema into base, appending lists and deep-merging dicts.
    
    Args:
        base: Base schema dict
        incoming: Incoming schema to merge
        
    Returns:
        Merged schema dict
    """
    for key, value in (incoming or {}).items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = merge_schema(base[key], value)
        elif key in base and isinstance(base[key], list) and isinstance(value, list):
            base[key] = base[key] + [v for v in value if v not in base[key]]
        else:
            base[key] = value
    return base


def append_schema(schema_path: str, incoming: dict, *, root: Path | None = None) -> dict:
    """Append/merge schema fragment into existing schema.
    
    Args:
        schema_path: Path to the schema file
        incoming: Schema fragment to append
        root: Root directory for path validation
        
    Returns:
        Merged schema dict
    """
    safe_root = (root or Path.cwd()).resolve()
    base = load_schema(schema_path)
    merged = merge_schema(base, incoming)
    write_schema(schema_path, merged, root=safe_root)
    return merged
