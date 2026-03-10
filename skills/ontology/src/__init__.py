"""Ontology graph operations - main entry point."""

from .services.entity_service import (
    create_entity,
    get_entity,
    query_entities,
    list_entities,
    update_entity,
    delete_entity,
)
from .services.relation_service import (
    create_relation,
    get_related,
)
from .services.validation_service import validate_graph
from .services.schema_service import load_schema, write_schema, append_schema
from .utils.path_utils import resolve_safe_path
from .utils.id_utils import generate_id
from .utils.graph_loader import load_graph, append_op

__all__ = [
    # Entity operations
    "create_entity",
    "get_entity",
    "query_entities",
    "list_entities",
    "update_entity",
    "delete_entity",
    # Relation operations
    "create_relation",
    "get_related",
    # Validation
    "validate_graph",
    # Schema
    "load_schema",
    "write_schema",
    "append_schema",
    # Utils
    "resolve_safe_path",
    "generate_id",
    "load_graph",
    "append_op",
]

__version__ = "1.0.0"
