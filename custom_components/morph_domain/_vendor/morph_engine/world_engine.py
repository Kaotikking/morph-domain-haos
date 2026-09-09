"""Morph Engine: one runtime, nine internal Core boundaries, one MorphDomain."""

from __future__ import annotations
from copy import deepcopy
from typing import Any

ENGINE_SCHEMA = "serein.morph-engine.v1"
CORE_ORDER = ("platform", "root", "memory", "knowledge", "ui", "audio", "personality", "modular", "cloud")
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
IMMUTABLE_ROOT = {
    "morph_id", "lineage_capsule_digest", "parentage", "founder_ancestry",
    "device_birth_lineage", "generation",
}


class MorphEngineError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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


def validate_engine_state(state: dict[str, Any]) -> dict[str, Any]:
    expected = {"schema", *CORE_ORDER}
    if not isinstance(state, dict) or set(state) != expected:
        raise MorphEngineError("INVALID_ENGINE_STATE", "nine exact Core records are required")
    if state["schema"] != ENGINE_SCHEMA:
        raise MorphEngineError("INCOMPATIBLE_ENGINE", "Morph Engine schema is not admitted")
    if "kernel" in state:
        raise MorphEngineError("KERNEL_PROHIBITED", "Morph Engine never carries a Kernel")
    for core in CORE_ORDER:
        if not isinstance(state[core], dict):
            raise MorphEngineError("INVALID_ENGINE_STATE", f"{core} Core must be an object")
    return deepcopy(state)


def route_facet(facet: str) -> tuple[str, ...]:
    if facet not in FACET_WRITES:
        raise MorphEngineError("UNKNOWN_FACET", "engine facet is not admitted")
    return tuple(core for core in CORE_ORDER if core in FACET_WRITES[facet])


def validate_successor(previous: dict[str, Any], candidate: dict[str, Any], facet: str) -> dict[str, Any]:
    old = validate_engine_state(previous)
    new = validate_engine_state(candidate)
    allowed = set(route_facet(facet))
    changed = {core for core in CORE_ORDER if old[core] != new[core]}
    if not changed.issubset(allowed):
        raise MorphEngineError("CROSS_CORE_WRITE", "facet attempted a write outside its Core boundary")
    old_root, new_root = old["root"], new["root"]
    for field in IMMUTABLE_ROOT:
        if field in old_root and new_root.get(field) != old_root[field]:
            raise MorphEngineError("IMMUTABLE_ROOT_CHANGED", f"{field} cannot be rewritten")
    return new


def project_for_frame(state: dict[str, Any], capabilities: list[str]) -> dict[str, Any]:
    """Gracefully project a Morph without deleting unsupported Core truth."""
    source = validate_engine_state(state)
    caps = set(capabilities)
    visible = {
        "identity": deepcopy(source["root"]),
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
