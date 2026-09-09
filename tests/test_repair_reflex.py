from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain/_vendor"))
from morph_sdk.repair_reflex import (
    IMMUTABLE_TRUTHS, NINE_CORES, RepairReflexError, build_default_ledger,
    classify, validate_reflex,
)

def test_morphdomain_has_nine_cores_and_no_kernel():
    ledger = build_default_ledger()
    assert ledger["nine_core_order"] == list(NINE_CORES)
    assert ledger["kernel_present"] is False
    assert "kernel" not in ledger["nine_core_order"]

def test_every_reflex_guards_every_immutable_truth():
    for reflex in build_default_ledger()["reflexes"]:
        assert set(reflex["preserved_truths"]) == set(IMMUTABLE_TRUTHS)
        assert reflex["rollback"]
        assert reflex["acceptance_witness"]

def test_known_deterministic_drift_is_automatic():
    reflex = classify("KNOWN_SCHEMA+CANONICAL_MEANING+NONCANONICAL_REPRESENTATION")
    assert reflex["disposition"] == "AUTO_REPAIR"
    assert reflex["permitted_effects"] == ["canonicalize-representation"]

def test_ambiguity_requires_admin():
    assert classify("MULTIPLE_VALID_SUCCESSORS|UNKNOWN_MIGRATION")["disposition"] == "ADMIN_REVIEW"

def test_unknown_condition_isolated_without_rewrite():
    reflex = classify("SOMETHING_NEW")
    assert reflex["disposition"] == "VOID_ISOLATION"
    assert "freeze-life" in reflex["permitted_effects"]
    assert reflex["rollback"] == "no-write-required"

def test_missing_guard_is_rejected():
    record = build_default_ledger()["reflexes"][0]
    record["preserved_truths"].pop()
    with pytest.raises(RepairReflexError) as caught:
        validate_reflex(record)
    assert caught.value.code == "IMMUTABLE_GUARD_MISSING"
