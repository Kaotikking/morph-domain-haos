"""MorphDomain DNAv1 immutable lineage and bounded lifecycle contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

LINEAGE_SCHEMA = "serein.morph-lineage-capsule.v1"
LIFECYCLE_SCHEMA = "serein.morph-lifecycle.v1"
SOCIAL_SCHEMA = "serein.morph-social-edge.v1"
BREEDING_SCHEMA = "serein.morph-breeding-eligibility.v1"

LIFECYCLE = ("SEALED", "HATCHING", "JUVENILE", "MATURE", "AWAKENED")
SOCIAL_STATES = ("UNFAMILIAR", "AWARE", "FAMILIAR", "BONDED", "RESONANT")
PRIMITIVES = {"FIRE", "AIR", "EARTH", "WATER"}
FAMILY_ROLES = {"PARENT", "CHILD", "SIBLING", "TWIN"}
CAPSULE_FIELDS = {
    "schema", "morph_id", "birth_digest", "parent_ids", "founder_ancestry",
    "device_birth_lineage", "primitive_element", "recessive_elements",
    "primary_expression_path", "awakened_expression_set", "trait_seed",
    "birth_event", "genome_version",
}
BIRTH_FIELDS = {
    "egg_id", "nursery_transaction_id", "hatched_at", "hatch_pattern",
    "twin_binding", "schema_version",
}


class DNAv1Error(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _exact(value: Any, fields: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise DNAv1Error("INVALID_DNAV1", f"{name} fields are not exact")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise DNAv1Error("INVALID_DNAV1", f"{name} is invalid")
    return value


def capsule_digest(capsule: dict[str, Any]) -> str:
    clean = validate_lineage_capsule(capsule)
    return hashlib.sha256(_canonical(clean)).hexdigest()


def validate_lineage_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    _exact(capsule, CAPSULE_FIELDS, "lineage capsule")
    if capsule["schema"] != LINEAGE_SCHEMA:
        raise DNAv1Error("INCOMPATIBLE_DNAV1", "lineage capsule schema is not admitted")
    for field in ("morph_id", "birth_digest", "device_birth_lineage", "trait_seed", "genome_version"):
        _text(capsule[field], field)
    parents = capsule["parent_ids"]
    if not isinstance(parents, list) or len(parents) > 2:
        raise DNAv1Error("INVALID_DNAV1", "parent_ids must contain zero to two identities")
    for parent in parents:
        _text(parent, "parent_id")
    ancestry = capsule["founder_ancestry"]
    if not isinstance(ancestry, list) or not 1 <= len(ancestry) <= 4 or len(set(ancestry)) != len(ancestry):
        raise DNAv1Error("INVALID_DNAV1", "founder ancestry is invalid")
    for founder in ancestry:
        _text(founder, "founder")
    if capsule["primitive_element"] not in PRIMITIVES:
        raise DNAv1Error("INVALID_DNAV1", "primitive element is invalid")
    recessives = capsule["recessive_elements"]
    if not isinstance(recessives, list) or len(recessives) > 4 or len(set(recessives)) != len(recessives):
        raise DNAv1Error("INVALID_DNAV1", "recessive elements are invalid")
    for element in recessives:
        _text(element, "recessive element")
    path = capsule["primary_expression_path"]
    if not isinstance(path, list) or len(path) != 5:
        raise DNAv1Error("INVALID_DNAV1", "exactly five ordered primary expressions are required")
    for index, expression in enumerate(path):
        _text(expression, f"primary_expression_path[{index}]")
    if len(set(path)) != 5:
        raise DNAv1Error("INVALID_DNAV1", "primary expressions must be unique")
    awakened = capsule["awakened_expression_set"]
    if not isinstance(awakened, list) or not awakened or len(awakened) > 5:
        raise DNAv1Error("INVALID_DNAV1", "awakened expression set is invalid")
    for index, expression in enumerate(awakened):
        _text(expression, f"awakened_expression_set[{index}]")
    if not set(awakened).issubset(set(path) | set(recessives)):
        raise DNAv1Error("LINEAGE_EXPRESSION_CONFLICT", "awakened expression is outside birth lineage")
    _exact(capsule["birth_event"], BIRTH_FIELDS, "birth event")
    birth = capsule["birth_event"]
    for field in ("egg_id", "nursery_transaction_id", "hatch_pattern", "schema_version"):
        _text(birth[field], field)
    if birth["hatched_at"] is not None:
        try:
            value = datetime.fromisoformat(str(birth["hatched_at"]).replace("Z", "+00:00"))
        except ValueError as err:
            raise DNAv1Error("INVALID_DNAV1", "hatched_at is invalid") from err
        if value.tzinfo is None:
            raise DNAv1Error("INVALID_DNAV1", "hatched_at requires timezone")
        value.astimezone(UTC)
    if birth["twin_binding"] is not None:
        _text(birth["twin_binding"], "twin_binding")
    return deepcopy(capsule)


def opaque_egg_projection(capsule: dict[str, Any]) -> dict[str, Any]:
    """Return a lineage-safe public egg: black silhouette and one white line."""
    clean = validate_lineage_capsule(capsule)
    return {
        "schema": "serein.morph-egg-projection.v1",
        "egg_id": clean["birth_event"]["egg_id"],
        "phase": "SEALED",
        "silhouette": "VOID_BLACK",
        "mark": "SINGLE_WHITE_LINE",
        "lineage_revealed": False,
    }


def validate_lifecycle(state: dict[str, Any]) -> dict[str, Any]:
    fields = {"schema", "phase", "expression_tier", "recessive_revealed", "awakened_active", "switch_available_at"}
    _exact(state, fields, "lifecycle")
    if state["schema"] != LIFECYCLE_SCHEMA or state["phase"] not in LIFECYCLE:
        raise DNAv1Error("INVALID_LIFECYCLE", "lifecycle state is invalid")
    tier = state["expression_tier"]
    if type(tier) is not int or not 0 <= tier <= 5:
        raise DNAv1Error("INVALID_LIFECYCLE", "expression tier must be 0..5")
    if type(state["recessive_revealed"]) is not bool:
        raise DNAv1Error("INVALID_LIFECYCLE", "recessive_revealed must be boolean")
    active = state["awakened_active"]
    if active is not None:
        _text(active, "awakened_active")
    available = state["switch_available_at"]
    if available is not None and (type(available) is not int or available < 0):
        raise DNAv1Error("INVALID_LIFECYCLE", "switch_available_at must be a nonnegative integer or null")
    if state["phase"] in {"SEALED", "HATCHING"} and tier != 0:
        raise DNAv1Error("LIFECYCLE_EXPRESSION_CONFLICT", "an egg cannot expose expression tiers")
    if state["recessive_revealed"] and state["phase"] not in {"MATURE", "AWAKENED"}:
        raise DNAv1Error("RECESSIVE_DORMANT", "recessive expression remains dormant before maturity")
    if state["awakened_active"] is not None and state["phase"] != "AWAKENED":
        raise DNAv1Error("AWAKENED_REQUIRED", "expression switching requires AWAKENED")
    return deepcopy(state)


def transition_lifecycle(state: dict[str, Any], destination: str) -> dict[str, Any]:
    current = validate_lifecycle(state)
    if destination not in LIFECYCLE:
        raise DNAv1Error("INVALID_LIFECYCLE", "destination phase is invalid")
    if LIFECYCLE.index(destination) != LIFECYCLE.index(current["phase"]) + 1:
        raise DNAv1Error("LIFECYCLE_ORDER", "lifecycle may advance exactly one phase and never regress")
    result = deepcopy(current)
    result["phase"] = destination
    return validate_lifecycle(result)


def switch_awakened_expression(
    capsule: dict[str, Any], lifecycle: dict[str, Any], expression: str,
    now_epoch_seconds: int, cooldown_seconds: int = 3600,
) -> dict[str, Any]:
    lineage = validate_lineage_capsule(capsule)
    state = validate_lifecycle(lifecycle)
    if state["phase"] != "AWAKENED":
        raise DNAv1Error("AWAKENED_REQUIRED", "Morph is not awakened")
    if expression not in lineage["awakened_expression_set"]:
        raise DNAv1Error("LINEAGE_EXPRESSION_CONFLICT", "expression is not birth-authorized")
    available = int(state["switch_available_at"] or 0)
    if now_epoch_seconds < available:
        raise DNAv1Error("EXPRESSION_COOLDOWN", "expression switch remains on cooldown")
    result = deepcopy(state)
    result["awakened_active"] = expression
    result["switch_available_at"] = now_epoch_seconds + cooldown_seconds
    return validate_lifecycle(result)


def validate_social_edge(edge: dict[str, Any]) -> dict[str, Any]:
    _exact(edge, {"schema", "subject_id", "object_id", "state", "evidence_count"}, "social edge")
    if edge["schema"] != SOCIAL_SCHEMA or edge["state"] not in SOCIAL_STATES:
        raise DNAv1Error("INVALID_SOCIAL_EDGE", "social state is invalid")
    _text(edge["subject_id"], "subject_id")
    _text(edge["object_id"], "object_id")
    if edge["subject_id"] == edge["object_id"]:
        raise DNAv1Error("INVALID_SOCIAL_EDGE", "social edge must be directional between two Morphs")
    if type(edge["evidence_count"]) is not int or edge["evidence_count"] < 0:
        raise DNAv1Error("INVALID_SOCIAL_EDGE", "evidence count is invalid")
    return deepcopy(edge)


def validate_family_link(link: dict[str, Any]) -> dict[str, Any]:
    _exact(link, {"subject_id", "relative_id", "role", "birth_digest"}, "family link")
    if link["role"] not in FAMILY_ROLES:
        raise DNAv1Error("INVALID_FAMILY_LINK", "family role is invalid")
    for field in ("subject_id", "relative_id", "birth_digest"):
        _text(link[field], field)
    return deepcopy(link)


def validate_breeding_eligibility(request: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "schema", "parent_a", "parent_b", "parent_a_phase", "parent_b_phase",
        "parent_a_social", "parent_b_social", "cooldown_clear",
        "nursery_capacity", "consent_admitted",
    }
    _exact(request, fields, "breeding eligibility")
    if request["schema"] != BREEDING_SCHEMA:
        raise DNAv1Error("INVALID_BREEDING", "breeding schema is not admitted")
    for field in ("parent_a", "parent_b"):
        _text(request[field], field)
    if request["parent_a"] == request["parent_b"]:
        raise DNAv1Error("INVALID_BREEDING", "two distinct parents are required")
    if request["parent_a_phase"] not in {"MATURE", "AWAKENED"} or request["parent_b_phase"] not in {"MATURE", "AWAKENED"}:
        raise DNAv1Error("BREEDING_MATURITY_REQUIRED", "both parents must be mature")
    minimum = SOCIAL_STATES.index("FAMILIAR")
    if SOCIAL_STATES.index(request["parent_a_social"]) < minimum or SOCIAL_STATES.index(request["parent_b_social"]) < minimum:
        raise DNAv1Error("BREEDING_FAMILIARITY_REQUIRED", "mutual familiarity is required")
    if type(request["cooldown_clear"]) is not bool or type(request["consent_admitted"]) is not bool:
        raise DNAv1Error("INVALID_BREEDING", "cooldown_clear and consent_admitted must be boolean")
    if not request["cooldown_clear"] or not request["consent_admitted"]:
        raise DNAv1Error("BREEDING_NOT_ADMITTED", "cooldown and consent must pass atomically")
    if type(request["nursery_capacity"]) is not int or request["nursery_capacity"] < 1:
        raise DNAv1Error("NURSERY_FULL", "Nursery capacity is required; overflow belongs in Void")
    return deepcopy(request)


def code_haven_backfill_plan(existing_core: dict[str, Any], capsule: dict[str, Any]) -> dict[str, Any]:
    """Create a no-effect migration plan; applying it is a separate Code Haven transaction."""
    lineage = validate_lineage_capsule(capsule)
    morph_id = existing_core.get("root", {}).get("identity", {}).get("morph_id")
    if morph_id is None:
        morph_id = existing_core.get("identity", {}).get("morph_id")
    if morph_id != lineage["morph_id"]:
        raise DNAv1Error("IDENTITY_CONFLICT", "capsule does not belong to existing Morph")
    return {
        "schema": "serein.morph-code-haven-backfill-plan.v1",
        "morph_id": morph_id,
        "required_place": "CODE_HAVEN",
        "capsule_digest": capsule_digest(lineage),
        "preserve": [
            "identity", "lineage", "life", "growth", "mastery", "chronicle",
            "generation", "authority", "custody",
        ],
        "effect": "NONE_UNTIL_COMMIT",
    }
