"""Morph Engine: one runtime, nine strict Core boundaries, one MorphDomain."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core_contract import (
    CORE_ORDER,
    ENGINE_SCHEMA,
    CoreContractError,
    validate_engine_state,
    validate_successor as validate_core_successor,
)

WORLD_PLACES = ("VOID", "CODE_HAVEN", "HORIZON", "NURSERY", "SEREIN_GARDENS")
ENGINE_FACETS = ("life", "social", "expression", "combination", "reflex")
CORE_OWNERSHIP = {
    "platform": ("life.clock", "life.storage", "life.runtime"),
    "root": ("identity", "lineage", "authority", "transactions"),
    "memory": ("chronicle", "family", "relationships", "experience"),
    "knowledge": ("environment", "preferences", "learned-patterns"),
    "ui": ("form", "elemental-render", "egg-render", "accessibility"),
    "audio": ("elemental-voice", "battle-cry", "audio-memory"),
    "personality": ("mood", "traits", "social-disposition", "compatibility"),
    "modular": ("combination", "frame-capabilities", "extensions"),
    "cloud": ("transfer", "custody", "reconciliation", "sern-capsule"),
}
FACET_WRITES = {
    "life": {"platform", "memory", "personality"},
    "social": {"memory", "personality"},
    "expression": {"ui", "audio", "personality"},
    "combination": {"root", "memory", "modular"},
    "reflex": {"platform", "root", "memory", "cloud"},
}


class MorphEngineError(CoreContractError):
    pass


def describe_engine() -> dict[str, Any]:
    return {
        "schema": ENGINE_SCHEMA,
        "public_name": "Morph Engine",
        "world_contract": "MorphDomain",
        "kernel_present": False,
        "core_order": list(CORE_ORDER),
        "places": list(WORLD_PLACES),
        "facets": list(ENGINE_FACETS),
        "core_ownership": {key: list(value) for key, value in CORE_OWNERSHIP.items()},
    }


def route_facet(facet: str) -> tuple[str, ...]:
    if facet not in FACET_WRITES:
        raise MorphEngineError("UNKNOWN_FACET", "engine facet is not admitted")
    return tuple(core for core in CORE_ORDER if core in FACET_WRITES[facet])


def validate_successor(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    facet: str,
) -> dict[str, Any]:
    return validate_core_successor(previous, candidate, set(route_facet(facet)))


def project_for_frame(state: dict[str, Any], capabilities: list[str]) -> dict[str, Any]:
    """Project a Morph without deleting truth unsupported by the destination."""
    source = validate_engine_state(state)
    if not isinstance(capabilities, list) or not all(isinstance(item, str) and item for item in capabilities):
        raise MorphEngineError("INVALID_CAPABILITIES", "capabilities must be a string list")
    caps = set(capabilities)
    visible = {
        "identity": deepcopy(source["root"]["identity"]),
        "life": deepcopy(source["platform"]),
        "memory": deepcopy(source["memory"]),
        "personality": deepcopy(source["personality"]),
        "form": deepcopy(source["ui"]) if "display" in caps else {"mode": "remembered-not-rendered"},
        "voice": deepcopy(source["audio"]) if "audio" in caps else {"mode": "remembered-not-rendered"},
    }
    return {
        "schema": "serein.morph-frame-projection.v1",
        "capabilities": sorted(caps),
        "visible": visible,
        "canonical_state_preserved": True,
    }
