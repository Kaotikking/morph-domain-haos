"""DNAv1 repair reflex ledger: rails governing automatic Morph repair."""

from __future__ import annotations
from copy import deepcopy
from typing import Any

LEDGER_SCHEMA = "serein.morph-repair-reflex-ledger.v1"
NINE_CORES = ("platform", "root", "memory", "knowledge", "ui", "audio", "personality", "modular", "cloud")
IMMUTABLE_TRUTHS = (
    "morph_id", "lineage_capsule_digest", "parentage", "founder_ancestry",
    "device_birth_lineage", "generation", "earned_life", "chronicle", "custody",
)
DISPOSITIONS = {"AUTO_REPAIR", "ADMIN_REVIEW", "VOID_ISOLATION"}
REQUIRED = {
    "reflex_id", "detection_signature", "disposition", "permitted_effects",
    "preserved_truths", "rollback", "chronicle_kind", "acceptance_witness",
}
DEFAULT_REFLEXES = (
    {
        "reflex_id": "schema-representation-drift",
        "detection_signature": "KNOWN_SCHEMA+CANONICAL_MEANING+NONCANONICAL_REPRESENTATION",
        "disposition": "AUTO_REPAIR",
        "permitted_effects": ("canonicalize-representation",),
    },
    {
        "reflex_id": "missing-derived-presentation",
        "detection_signature": "VALID_DNA+MISSING_DERIVED_PRESENTATION",
        "disposition": "AUTO_REPAIR",
        "permitted_effects": ("regenerate-derived-presentation",),
    },
    {
        "reflex_id": "ambiguous-successor",
        "detection_signature": "MULTIPLE_VALID_SUCCESSORS|UNKNOWN_MIGRATION",
        "disposition": "ADMIN_REVIEW",
        "permitted_effects": (),
    },
    {
        "reflex_id": "immutable-conflict",
        "detection_signature": "IDENTITY|LINEAGE|PARENTAGE|BIRTH_DEVICE|AUTHORITY_CONFLICT",
        "disposition": "VOID_ISOLATION",
        "permitted_effects": ("freeze-life", "deny-breeding", "deny-transfer"),
    },
)


class RepairReflexError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_reflex(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or set(record) != REQUIRED:
        raise RepairReflexError("INVALID_REFLEX", "reflex fields are not exact")
    if record["disposition"] not in DISPOSITIONS:
        raise RepairReflexError("INVALID_REFLEX", "disposition is not admitted")
    if not isinstance(record["permitted_effects"], list):
        raise RepairReflexError("INVALID_REFLEX", "permitted effects must be a list")
    if set(record["preserved_truths"]) != set(IMMUTABLE_TRUTHS):
        raise RepairReflexError("IMMUTABLE_GUARD_MISSING", "every immutable truth must be guarded")
    for field in ("reflex_id", "detection_signature", "rollback", "chronicle_kind", "acceptance_witness"):
        if not isinstance(record[field], str) or not record[field]:
            raise RepairReflexError("INVALID_REFLEX", f"{field} is invalid")
    if record["disposition"] != "AUTO_REPAIR" and record["permitted_effects"] not in ([], ["freeze-life"], ["freeze-life", "deny-breeding", "deny-transfer"]):
        raise RepairReflexError("UNAUTHORIZED_EFFECT", "review/isolation cannot rewrite Morph state")
    return deepcopy(record)


def build_default_ledger() -> dict[str, Any]:
    records = []
    for base in DEFAULT_REFLEXES:
        records.append(validate_reflex({
            **base,
            "permitted_effects": list(base["permitted_effects"]),
            "preserved_truths": list(IMMUTABLE_TRUTHS),
            "rollback": "restore-predecessor-digest",
            "chronicle_kind": "repair-reflex",
            "acceptance_witness": "successor-validation+digest+authority-readback",
        }))
    return {"schema": LEDGER_SCHEMA, "nine_core_order": list(NINE_CORES), "kernel_present": False, "reflexes": records}


def classify(signature: str, ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    source = ledger or build_default_ledger()
    if source.get("schema") != LEDGER_SCHEMA or source.get("kernel_present") is not False:
        raise RepairReflexError("INVALID_LEDGER", "MorphDomain is nine-Core and has no Kernel")
    exact = [row for row in source["reflexes"] if row["detection_signature"] == signature]
    if exact:
        return deepcopy(exact[0])
    return {
        "reflex_id": "unknown-condition",
        "detection_signature": signature,
        "disposition": "VOID_ISOLATION",
        "permitted_effects": ["freeze-life", "deny-breeding", "deny-transfer"],
        "preserved_truths": list(IMMUTABLE_TRUTHS),
        "rollback": "no-write-required",
        "chronicle_kind": "unknown-isolation",
        "acceptance_witness": "admin-reviewed-canonical-successor",
    }
