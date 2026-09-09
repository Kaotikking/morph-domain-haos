"""Strict DNAv1 contracts for the Morph Engine's nine internal Cores."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

ENGINE_SCHEMA = "serein.morph-engine.v1"
CORE_ORDER = (
    "platform", "root", "memory", "knowledge", "ui",
    "audio", "personality", "modular", "cloud",
)
CORE_FIELDS = {
    "platform": {"schema", "runtime", "storage", "clock", "life_schedule", "host_capabilities"},
    "root": {"schema", "identity", "lineage_capsule", "lineage_capsule_digest", "authority", "transaction"},
    "memory": {"schema", "chronicle", "family", "relationships", "experience"},
    "knowledge": {"schema", "environment", "preferences", "learned_patterns"},
    "ui": {"schema", "form", "elemental_render", "egg_render", "animation", "accessibility"},
    "audio": {"schema", "elemental_voice", "battle_cry", "audio_memory"},
    "personality": {"schema", "mood", "traits", "social_disposition", "compatibility"},
    "modular": {"schema", "combination", "frame_capabilities", "extensions"},
    "cloud": {"schema", "transfer", "custody", "reconciliation", "sern_capsule"},
}
CORE_SCHEMAS = {core: f"serein.morph-engine.{core}.v1" for core in CORE_ORDER}
IDENTITY_FIELDS = {
    "morph_id", "parentage", "founder_ancestry",
    "device_birth_lineage", "generation",
}
IMMUTABLE_ROOT_PATHS = (
    "root.identity.morph_id",
    "root.identity.parentage",
    "root.identity.founder_ancestry",
    "root.identity.device_birth_lineage",
    "root.identity.generation",
    "root.lineage_capsule",
    "root.lineage_capsule_digest",
)
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class CoreContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise CoreContractError("INVALID_CORE_STATE", f"{label} fields are not exact")
    return value


def _json_tree(value: Any, label: str) -> None:
    if value is None or type(value) in {str, int, float, bool}:
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_tree(item, f"{label}[{index}]")
        return
    if isinstance(value, dict) and all(isinstance(key, str) and key for key in value):
        for key, item in value.items():
            _json_tree(item, f"{label}.{key}")
        return
    raise CoreContractError("INVALID_CORE_STATE", f"{label} is not strict JSON")


def validate_engine_state(state: dict[str, Any]) -> dict[str, Any]:
    _exact_object(state, {"schema", *CORE_ORDER}, "Morph Engine")
    if state["schema"] != ENGINE_SCHEMA:
        raise CoreContractError("INCOMPATIBLE_ENGINE", "Morph Engine schema is not admitted")
    if "kernel" in state:
        raise CoreContractError("KERNEL_PROHIBITED", "Morph Engine never carries a Kernel")

    for core in CORE_ORDER:
        record = _exact_object(state[core], CORE_FIELDS[core], f"{core} Core")
        if record["schema"] != CORE_SCHEMAS[core]:
            raise CoreContractError("INCOMPATIBLE_CORE", f"{core} Core schema is not admitted")
        _json_tree(record, core)

    identity = _exact_object(state["root"]["identity"], IDENTITY_FIELDS, "Root identity")
    morph_id = identity["morph_id"]
    if not isinstance(morph_id, str) or not morph_id:
        raise CoreContractError("INVALID_IDENTITY", "morph_id is required")
    if type(identity["generation"]) is not int or identity["generation"] < 0:
        raise CoreContractError("INVALID_IDENTITY", "generation must be a nonnegative integer")
    for field in ("parentage", "founder_ancestry"):
        if not isinstance(identity[field], list) or not all(isinstance(item, str) and item for item in identity[field]):
            raise CoreContractError("INVALID_IDENTITY", f"{field} must be a string list")
    if not isinstance(identity["device_birth_lineage"], str) or not identity["device_birth_lineage"]:
        raise CoreContractError("INVALID_IDENTITY", "device birth lineage is required")
    digest = state["root"]["lineage_capsule_digest"]
    if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
        raise CoreContractError("INVALID_LINEAGE_DIGEST", "lineage capsule digest must be lowercase SHA-256")
    if not isinstance(state["memory"]["chronicle"], list):
        raise CoreContractError("INVALID_MEMORY", "Chronicle must be an append-only list")
    for field in ("family", "relationships", "experience"):
        if not isinstance(state["memory"][field], dict):
            raise CoreContractError("INVALID_MEMORY", f"{field} must be an object")
    return deepcopy(state)


def _path_value(state: dict[str, Any], path: str) -> Any:
    value: Any = state
    for part in path.split("."):
        value = value[part]
    return value


def _assert_monotonic_tree(previous: Any, candidate: Any, path: str) -> None:
    if type(previous) in {int, float}:
        if type(candidate) not in {int, float} or candidate < previous:
            raise CoreContractError("MEMORY_REGRESSION", f"{path} may not decrease")
        return
    if isinstance(previous, dict):
        if not isinstance(candidate, dict):
            raise CoreContractError("MEMORY_REGRESSION", f"{path} changed type")
        for key, value in previous.items():
            if key not in candidate:
                raise CoreContractError("MEMORY_REGRESSION", f"{path}.{key} was erased")
            _assert_monotonic_tree(value, candidate[key], f"{path}.{key}")
        return
    if isinstance(previous, list):
        if not isinstance(candidate, list) or candidate[:len(previous)] != previous:
            raise CoreContractError("MEMORY_REGRESSION", f"{path} must preserve its prefix")
        return
    if candidate != previous:
        raise CoreContractError("MEMORY_REGRESSION", f"{path} may not rewrite established truth")


def validate_successor(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    allowed_cores: set[str],
) -> dict[str, Any]:
    old = validate_engine_state(previous)
    new = validate_engine_state(candidate)
    if not allowed_cores.issubset(set(CORE_ORDER)):
        raise CoreContractError("UNKNOWN_CORE", "allowed Core set is invalid")
    changed = {core for core in CORE_ORDER if old[core] != new[core]}
    if not changed.issubset(allowed_cores):
        raise CoreContractError("CROSS_CORE_WRITE", "write escaped its admitted Core boundary")
    for path in IMMUTABLE_ROOT_PATHS:
        if _path_value(old, path) != _path_value(new, path):
            raise CoreContractError("IMMUTABLE_ROOT_CHANGED", f"{path} cannot be rewritten")
    if old["memory"] != new["memory"]:
        _assert_monotonic_tree(old["memory"]["chronicle"], new["memory"]["chronicle"], "memory.chronicle")
        _assert_monotonic_tree(old["memory"]["family"], new["memory"]["family"], "memory.family")
        _assert_monotonic_tree(old["memory"]["relationships"], new["memory"]["relationships"], "memory.relationships")
        _assert_monotonic_tree(old["memory"]["experience"], new["memory"]["experience"], "memory.experience")
    return new
