"""Vendored Serein Morph Engine for HACS installation."""

from .core_contract import (
    CORE_FIELDS,
    CORE_ORDER,
    CORE_SCHEMAS,
    ENGINE_SCHEMA,
    IDENTITY_FIELDS,
    IMMUTABLE_ROOT_PATHS,
    CoreContractError,
)
from .world_engine import (
    ENGINE_FACETS,
    WORLD_PLACES,
    describe_engine,
    project_for_frame,
    route_facet,
    validate_engine_state,
    validate_successor,
)

__all__ = [
    "CORE_FIELDS", "CORE_ORDER", "CORE_SCHEMAS", "ENGINE_FACETS",
    "ENGINE_SCHEMA", "IDENTITY_FIELDS", "IMMUTABLE_ROOT_PATHS",
    "WORLD_PLACES", "CoreContractError", "describe_engine",
    "project_for_frame", "route_facet", "validate_engine_state",
    "validate_successor",
]
