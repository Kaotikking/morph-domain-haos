"""DNAv1 repair-reflex ledger with enforceable effects, rollback, and witnesses."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

LEDGER_SCHEMA = "serein.morph-repair-reflex-ledger.v1"
NINE_CORES = (
    "platform", "root", "memory", "knowledge", "ui",
    "audio", "personality", "modular", "cloud",
)
IMMUTABLE_TRUTHS = (
    "morph_id", "lineage_capsule_digest", "parentage", "founder_ancestry",
    "device_birth_lineage", "generation", "earned_life", "chronicle", "custody",
)
DISPOSITIONS = {"AUTO_REPAIR", "ADMIN_REVIEW", "VOID_ISOLATION"}
AUTO_EFFECTS = {"canonicalize-representation", "regenerate-derived-presentation"}
ISOLATION_EFFECTS = {"freeze-life", "deny-breeding", "deny-transfer"}
REQUIRED = {
    "reflex_id", "detection_signature", "disposition", "permitted_effects",
    "preserved_truths", "rollback", "chronicle_kind", "acceptance_witness",
}
ROLLBACK_FIELDS = {"strategy", "predecessor_digest_required"}
WITNESS_FIELDS = {"required_checks"}
LEDGER_FIELDS = {"schema", "nine_core_order", "kernel_present", "reflexes"}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")

DEFAULT_REFLEXES = (
    {
        "reflex_id": "schema-representation-drift",
        "detection_signature": "KNOWN_SCHEMA+CANONICAL_MEANING+NONCANONICAL_REPRESENTATION",
        "disposition": "AUTO_REPAIR",
        "permitted_effects": ["canonicalize-representation"],
    },
    {
        "reflex_id": "missing-derived-presentation",
        "detection_signature": "VALID_DNA+MISSING_DERIVED_PRESENTATION",
        "disposition": "AUTO_REPAIR",
        "permitted_effects": ["regenerate-derived-presentation"],
    },
    {
        "reflex_id": "ambiguous-successor",
        "detection_signature": "MULTIPLE_VALID_SUCCESSORS|UNKNOWN_MIGRATION",
        "disposition": "ADMIN_REVIEW",
        "permitted_effects": [],
    },
    {
        "reflex_id": "immutable-conflict",
        "detection_signature": "IDENTITY|LINEAGE|PARENTAGE|BIRTH_DEVICE|AUTHORITY_CONFLICT",
        "disposition": "VOID_ISOLATION",
        "permitted_effects": ["freeze-life", "deny-breeding", "deny-transfer"],
    },
)


class RepairReflexError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _exact(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise RepairReflexError("INVALID_REFLEX", f"{label} fields are not exact")


def validate_reflex(record: dict[str, Any]) -> dict[str, Any]:
    _exact(record, REQUIRED, "reflex")
    for field in ("reflex_id", "detection_signature", "chronicle_kind"):
        if not isinstance(record[field], str) or not record[field]:
            raise RepairReflexError("INVALID_REFLEX", f"{field} is invalid")
    if record["disposition"] not in DISPOSITIONS:
        raise RepairReflexError("INVALID_REFLEX", "disposition is not admitted")
    effects = record["permitted_effects"]
    if not isinstance(effects, list) or len(effects) != len(set(effects)):
        raise RepairReflexError("INVALID_REFLEX", "permitted effects must be a unique list")
    if record["disposition"] == "AUTO_REPAIR" and (not effects or not set(effects).issubset(AUTO_EFFECTS)):
        raise RepairReflexError("UNAUTHORIZED_EFFECT", "automatic repair effect is not allowlisted")
    if record["disposition"] == "ADMIN_REVIEW" and effects:
        raise RepairReflexError("UNAUTHORIZED_EFFECT", "administrator review cannot mutate")
    if record["disposition"] == "VOID_ISOLATION" and not set(effects).issubset(ISOLATION_EFFECTS):
        raise RepairReflexError("UNAUTHORIZED_EFFECT", "Void isolation effect is not allowlisted")
    if record["preserved_truths"] != list(IMMUTABLE_TRUTHS):
        raise RepairReflexError("IMMUTABLE_GUARD_MISSING", "every immutable truth must be guarded in canonical order")

    rollback = record["rollback"]
    _exact(rollback, ROLLBACK_FIELDS, "rollback")
    if rollback["strategy"] not in {"restore-predecessor-digest", "no-write-required"}:
        raise RepairReflexError("INVALID_ROLLBACK", "rollback strategy is not executable")
    if type(rollback["predecessor_digest_required"]) is not bool:
        raise RepairReflexError("INVALID_ROLLBACK", "rollback digest requirement must be boolean")
    if effects and not rollback["predecessor_digest_required"]:
        raise RepairReflexError("INVALID_ROLLBACK", "every effect requires a predecessor digest")

    witness = record["acceptance_witness"]
    _exact(witness, WITNESS_FIELDS, "acceptance witness")
    checks = witness["required_checks"]
    if not isinstance(checks, list) or not checks or len(checks) != len(set(checks)):
        raise RepairReflexError("INVALID_WITNESS", "acceptance checks must be a nonempty unique list")
    if not all(isinstance(check, str) and check for check in checks):
        raise RepairReflexError("INVALID_WITNESS", "acceptance checks must be strings")
    return deepcopy(record)


def validate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    _exact(ledger, LEDGER_FIELDS, "ledger")
    if ledger["schema"] != LEDGER_SCHEMA:
        raise RepairReflexError("INVALID_LEDGER", "repair ledger schema is not admitted")
    if ledger["nine_core_order"] != list(NINE_CORES) or ledger["kernel_present"] is not False:
        raise RepairReflexError("INVALID_LEDGER", "exact nine-Core order and no Kernel are required")
    if not isinstance(ledger["reflexes"], list):
        raise RepairReflexError("INVALID_LEDGER", "reflexes must be a list")
    records = [validate_reflex(record) for record in ledger["reflexes"]]
    ids = [record["reflex_id"] for record in records]
    signatures = [record["detection_signature"] for record in records]
    if len(ids) != len(set(ids)) or len(signatures) != len(set(signatures)):
        raise RepairReflexError("AMBIGUOUS_LEDGER", "reflex IDs and signatures must be unique")
    return {**deepcopy(ledger), "reflexes": records}


def build_default_ledger() -> dict[str, Any]:
    records = []
    checks = ["successor-validation", "digest-readback", "authority-readback", "chronicle-append"]
    for base in DEFAULT_REFLEXES:
        effects = list(base["permitted_effects"])
        records.append({
            **deepcopy(base),
            "preserved_truths": list(IMMUTABLE_TRUTHS),
            "rollback": {
                "strategy": "restore-predecessor-digest" if effects else "no-write-required",
                "predecessor_digest_required": bool(effects),
            },
            "chronicle_kind": "repair-reflex" if effects else "repair-review",
            "acceptance_witness": {"required_checks": checks if effects else ["admin-decision-readback"]},
        })
    return validate_ledger({
        "schema": LEDGER_SCHEMA,
        "nine_core_order": list(NINE_CORES),
        "kernel_present": False,
        "reflexes": records,
    })


def classify(signature: str, ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(signature, str) or not signature:
        raise RepairReflexError("INVALID_SIGNATURE", "detection signature is required")
    source = validate_ledger(ledger or build_default_ledger())
    for record in source["reflexes"]:
        if record["detection_signature"] == signature:
            return deepcopy(record)
    return validate_reflex({
        "reflex_id": "unknown-condition",
        "detection_signature": signature,
        "disposition": "VOID_ISOLATION",
        "permitted_effects": ["freeze-life", "deny-breeding", "deny-transfer"],
        "preserved_truths": list(IMMUTABLE_TRUTHS),
        "rollback": {"strategy": "restore-predecessor-digest", "predecessor_digest_required": True},
        "chronicle_kind": "unknown-isolation",
        "acceptance_witness": {
            "required_checks": ["digest-readback", "authority-readback", "void-isolation-readback"],
        },
    })


def authorize_effects(
    reflex: dict[str, Any],
    predecessor_digest: str | None,
    observed_checks: dict[str, dict[str, Any]],
) -> list[str]:
    """Authorize only attributable PASS evidence bound to the rollback digest."""
    record = validate_reflex(reflex)
    rollback = record["rollback"]
    if rollback["predecessor_digest_required"]:
        if not isinstance(predecessor_digest, str) or _HEX_64.fullmatch(predecessor_digest) is None:
            raise RepairReflexError("ROLLBACK_NOT_BOUND", "valid predecessor digest is required before effects")
        if rollback["strategy"] != "restore-predecessor-digest":
            raise RepairReflexError("ROLLBACK_NOT_EXECUTABLE", "mutating effects require digest restoration")
    required = record["acceptance_witness"]["required_checks"]
    if not isinstance(observed_checks, dict) or set(observed_checks) != set(required):
        raise RepairReflexError("WITNESS_INCOMPLETE", "exact required acceptance evidence is missing")
    for name in required:
        evidence = observed_checks[name]
        if not isinstance(evidence, dict) or set(evidence) != {"result", "evidence_id", "predecessor_digest"}:
            raise RepairReflexError("INVALID_WITNESS", "witness evidence fields are not exact")
        if evidence["result"] != "PASS" or not isinstance(evidence["evidence_id"], str) or not evidence["evidence_id"]:
            raise RepairReflexError("WITNESS_FAILED", "acceptance evidence is not attributable PASS")
        expected = predecessor_digest if rollback["predecessor_digest_required"] else None
        if evidence["predecessor_digest"] != expected:
            raise RepairReflexError("WITNESS_DIGEST_MISMATCH", "acceptance evidence is not bound to rollback")
    return list(record["permitted_effects"])
