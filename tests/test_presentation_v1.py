import pytest
from presentation_v1 import *


def card(branch="L1-04", owner="ANDROID:X4"):
    result = {"schema": SCHEMA}
    result.update({name: {} for name in CORES})
    result["identity"] = {"morph_id": "pulse"}
    result["lineage"] = {"branch_id": branch}
    result["authority"] = {"active_owner": owner}
    return result


def test_stable_branch_grammar_and_sorted_composites():
    assert validate_branch_id("F-01") == "F-01"
    assert validate_branch_id("L1-04") == "L1-04"
    assert validate_branch_id("E-03") == "E-03"
    assert validate_branch_id("L2-02.03") == "L2-02.03"
    with pytest.raises(ValueError): validate_branch_id("L2-03.02")


def test_charging_alone_does_not_fabricate_expression_care():
    resolved = resolve_care({"SUS": 5, "ATT": 0, "PLY": 0, "SOC": 0, "AFF": 0})
    assert resolved["earned_stage"] == 1
    assert resolved["active_branch"] == "PENDING"


def test_later_care_can_reach_same_endpoint_without_regression():
    recovered = resolve_care({key: 5 for key in CARE_KEYS}, earned_stage=1)
    maintained = resolve_care({key: 5 for key in CARE_KEYS}, earned_stage=5)
    assert recovered["earned_stage"] == maintained["earned_stage"] == 5


def test_capability_changes_visible_recipe_at_equal_care():
    base = dict(element="FIRE", care_branch="ATTUNED", trait_polarity=0, origin_signature="PUBLIC", context="HOME")
    assert presentation_recipe(capability_path="MOVEMENT", **base) != presentation_recipe(capability_path="PROJECTION", **base)


def test_import_suppresses_starter_and_horizon_only_unlocks_knowledge():
    assert onboarding_decision(imported_morph=True, existing_starter=False) == "IMPORT_PRESERVED_NO_STARTER"
    assert horizon_discovery(legendary_present=True, lineage_known=False, evidence=5) == {"blueprint_unlocked": True, "creates_morph": False}


def test_id_card_is_nine_core_digestible_and_fail_closed():
    compact = compact_card(card())
    assert compact["morph_id"] == "pulse" and len(compact["digest"]) == 64
    broken = card(); del broken["memory"]
    with pytest.raises(ValueError): validate_id_card(broken)


def test_one_active_owner_is_required():
    with pytest.raises(ValueError): validate_id_card(card(owner=""))

