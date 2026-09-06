"""Founder-agnostic elemental expression contracts for MorphDomain."""

from copy import deepcopy

EXPRESSION_SCHEMA = "morph-domain.elemental-expression.v1"
PRIMITIVES = {"AIR", "EARTH", "FIRE", "WATER"}
LEVELS = {"LATENT": 1, "AWAKENED": 2, "BLENDED": 3, "COMPOUND": 4, "HARMONIC": 5}
COMPOUNDS = {frozenset(("AIR", "WATER")): "STORM"}


class ElementalExpressionError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def resolve_compound(primitives, level):
    if not isinstance(primitives, list) or not 1 <= len(primitives) <= 2 or len(set(primitives)) != len(primitives):
        raise ElementalExpressionError("INVALID_ANCESTRY", "one or two unique primitives are required")
    if any(item not in PRIMITIVES for item in primitives):
        raise ElementalExpressionError("INVALID_ANCESTRY", "unknown primitive")
    if type(level) is not int or not 1 <= level <= 5:
        raise ElementalExpressionError("INVALID_EXPRESSION_LEVEL", "expression level must be 1..5")
    if len(primitives) == 1 or level < LEVELS["COMPOUND"]:
        return None
    family = COMPOUNDS.get(frozenset(primitives))
    if family is None:
        raise ElementalExpressionError("UNADMITTED_COMPOUND", "primitive pairing has no admitted contract")
    return family


def validate_expression(value, *, generation, parent_ids):
    fields = {"schema", "dominant_primitive", "secondary_primitive", "recessive_potentials",
              "parent_locus_contributions", "expression_level", "compound_family",
              "visual_expression", "environment_selector", "body_mode", "body_mode_lock",
              "origin_binding_digest"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ElementalExpressionError("INVALID_ELEMENTAL_EXPRESSION", "fields are not exact")
    if value["schema"] != EXPRESSION_SCHEMA:
        raise ElementalExpressionError("INCOMPATIBLE_ELEMENTAL_EXPRESSION", "schema is not admitted")
    primitives = [value["dominant_primitive"]]
    if value["secondary_primitive"] is not None:
        primitives.append(value["secondary_primitive"])
    recessives = value["recessive_potentials"]
    if not isinstance(recessives, list) or len(recessives) > 2 or len(set(recessives)) != len(recessives):
        raise ElementalExpressionError("INVALID_RECESSIVES", "recessive potentials are invalid")
    contributions = value["parent_locus_contributions"]
    if generation == 0:
        if parent_ids or contributions:
            raise ElementalExpressionError("INVALID_ORIGIN_ANCESTRY", "generation zero cannot have parent loci")
    elif len(parent_ids) != 2 or not isinstance(contributions, dict) or set(contributions) != set(parent_ids) or any(type(n) is not int or n != 5 for n in contributions.values()):
        raise ElementalExpressionError("INVALID_INHERITANCE", "each of two parents must contribute exactly five loci")
    compound = resolve_compound(primitives, value["expression_level"])
    if value["compound_family"] != compound:
        raise ElementalExpressionError("COMPOUND_CONFLICT", "compound family does not match ancestry and level")
    for key in ("visual_expression", "environment_selector", "body_mode"):
        if not isinstance(value[key], str) or not value[key]:
            raise ElementalExpressionError("INVALID_PRESENTATION", f"{key} is required")
    digest = value["origin_binding_digest"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ElementalExpressionError("INVALID_ORIGIN_BINDING", "origin binding digest is invalid")
    lock = value["body_mode_lock"]
    if not isinstance(lock, dict) or set(lock) != {"locked_mode", "replacement_mode", "reason"}:
        raise ElementalExpressionError("INVALID_BODY_MODE_LOCK", "body lock fields are not exact")
    if (lock["locked_mode"] is None) != (lock["replacement_mode"] is None):
        raise ElementalExpressionError("INVALID_BODY_MODE_LOCK", "lock and replacement change together")
    return deepcopy(value)


def verify_expression_successor(previous, candidate, *, generation, parent_ids):
    old = validate_expression(previous, generation=generation, parent_ids=parent_ids)
    new = validate_expression(candidate, generation=generation, parent_ids=parent_ids)
    immutable = {"schema", "dominant_primitive", "secondary_primitive", "recessive_potentials",
                 "parent_locus_contributions", "origin_binding_digest"}
    if any(old[key] != new[key] for key in immutable):
        raise ElementalExpressionError("LINEAGE_REWRITE", "elemental lineage changed")
    if new["expression_level"] < old["expression_level"]:
        raise ElementalExpressionError("EXPRESSION_REGRESSION", "earned expression level regressed")

