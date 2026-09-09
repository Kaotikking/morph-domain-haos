from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain/_vendor"))

from morph_sdk.repair_reflex import (
    IMMUTABLE_TRUTHS, NINE_CORES, RepairReflexError, authorize_effects,
    build_default_ledger, classify, validate_ledger, validate_reflex,
)


def test_morph_engine_has_exact_nine_cores_and_no_kernel():
    ledger = build_default_ledger()
    assert ledger["nine_core_order"] == list(NINE_CORES)
    assert ledger["kernel_present"] is False
    assert "kernel" not in ledger["nine_core_order"]


def test_every_reflex_guards_every_immutable_truth():
    for reflex in build_default_ledger()["reflexes"]:
        assert reflex["preserved_truths"] == list(IMMUTABLE_TRUTHS)
        assert reflex["rollback"]["strategy"]
        assert reflex["acceptance_witness"]["required_checks"]


def test_known_deterministic_drift_is_automatic_and_allowlisted():
    reflex = classify("KNOWN_SCHEMA+CANONICAL_MEANING+NONCANONICAL_REPRESENTATION")
    assert reflex["disposition"] == "AUTO_REPAIR"
    assert reflex["permitted_effects"] == ["canonicalize-representation"]


def test_ambiguity_requires_admin_and_has_no_effect():
    reflex = classify("MULTIPLE_VALID_SUCCESSORS|UNKNOWN_MIGRATION")
    assert reflex["disposition"] == "ADMIN_REVIEW"
    assert reflex["permitted_effects"] == []


def test_unknown_condition_isolated_without_rewrite():
    reflex = classify("SOMETHING_NEW")
    assert reflex["disposition"] == "VOID_ISOLATION"
    assert set(reflex["permitted_effects"]) == {"freeze-life", "deny-breeding", "deny-transfer"}


def test_missing_guard_is_rejected():
    record = build_default_ledger()["reflexes"][0]
    record["preserved_truths"].pop()
    with pytest.raises(RepairReflexError) as caught:
        validate_reflex(record)
    assert caught.value.code == "IMMUTABLE_GUARD_MISSING"


def test_arbitrary_automatic_effect_is_rejected():
    record = build_default_ledger()["reflexes"][0]
    record["permitted_effects"] = ["rewrite-lineage"]
    with pytest.raises(RepairReflexError) as caught:
        validate_reflex(record)
    assert caught.value.code == "UNAUTHORIZED_EFFECT"


def test_custom_ledger_requires_exact_core_order_and_unique_signatures():
    ledger = build_default_ledger()
    ledger["nine_core_order"][0], ledger["nine_core_order"][1] = (
        ledger["nine_core_order"][1], ledger["nine_core_order"][0]
    )
    with pytest.raises(RepairReflexError) as caught:
        validate_ledger(ledger)
    assert caught.value.code == "INVALID_LEDGER"

    duplicate = build_default_ledger()
    duplicate["reflexes"].append(deepcopy(duplicate["reflexes"][0]))
    with pytest.raises(RepairReflexError) as caught:
        classify("UNKNOWN", duplicate)
    assert caught.value.code == "AMBIGUOUS_LEDGER"


def test_effects_require_bound_rollback_and_complete_witness():
    reflex = classify("VALID_DNA+MISSING_DERIVED_PRESENTATION")
    with pytest.raises(RepairReflexError) as caught:
        authorize_effects(reflex, None, reflex["acceptance_witness"]["required_checks"])
    assert caught.value.code == "ROLLBACK_NOT_BOUND"

    with pytest.raises(RepairReflexError) as caught:
        authorize_effects(reflex, "a" * 64, ["successor-validation"])
    assert caught.value.code == "WITNESS_INCOMPLETE"

    checks = {
        name: {"result": "PASS", "evidence_id": f"evidence:{name}", "predecessor_digest": "a" * 64}
        for name in reflex["acceptance_witness"]["required_checks"]
    }
    assert authorize_effects(reflex, "a" * 64, checks) == ["regenerate-derived-presentation"]

    tampered = deepcopy(checks)
    tampered["digest-readback"]["predecessor_digest"] = "b" * 64
    with pytest.raises(RepairReflexError) as caught:
        authorize_effects(reflex, "a" * 64, tampered)
    assert caught.value.code == "WITNESS_DIGEST_MISMATCH"
