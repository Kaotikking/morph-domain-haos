"""Vendored Serein Morph Engine for HACS installation."""

from .world_engine import (
    CORE_ORDER,
    ENGINE_FACETS,
    ENGINE_SCHEMA,
    WORLD_PLACES,
    describe_engine,
    project_for_frame,
    route_facet,
    validate_engine_state,
    validate_successor,
)

__all__ = [
    "CORE_ORDER", "ENGINE_FACETS", "ENGINE_SCHEMA", "WORLD_PLACES",
    "describe_engine", "project_for_frame", "route_facet",
    "validate_engine_state", "validate_successor",
]
