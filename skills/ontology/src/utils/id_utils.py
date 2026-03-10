"""ID generation utilities."""

import uuid


def generate_id(type_name: str) -> str:
    """Generate a unique ID for an entity.
    
    Args:
        type_name: The entity type name
        
    Returns:
        A unique ID string with type prefix
    """
    prefix = type_name.lower()[:4]
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"
