import copy
import pytest

from custom_components.morph_domain._vendor.morph_sdk.dna_v1 import (
    DNAv1Error, LINEAGE_SCHEMA, LIFECYCLE_SCHEMA, SOCIAL_SCHEMA,
    capsule_digest, code_haven_backfill_plan, opaque_egg_projection,
    switch_awakened_expression, transition_lifecycle,
    validate_breeding_eligibility, validate_lifecycle, validate_social_edge,
)


def capsule():
    return {
        "schema": LINEAGE_SCHEMA,
        "morph_id": "morph:dustdevil",
        "birth_digest": "birth:one",
        "parent_ids": ["morph:breeze", "morph:sentinel"],
        "founder_ancestry": ["BREEZE", "SENTINEL"],
        "device_birth_lineage": "haos:nursery",
        "primitive_element": "AIR",
        "recessive_elements": ["ELECTRICITY", "METAL"],
        "primary_expression_path": ["BREATH", "BREEZE", "WIND", "JETSTREAM", "AURORA"],
        "awakened_expression_set": ["AURORA", "ELECTRICITY", "METAL"],
        "trait_seed": "seed:dd",
        "birth_event": {
            "egg_id": "egg:dd", "nursery_transaction_id": "nursery:one",
            "hatched_at": None, "hatch_pattern": "void-line",
            "twin_binding": None, "schema_version": "v1",
        },
        "genome_version": "dnav1",
    }


def lifecycle(phase="SEALED", tier=0):
    return {
        "schema": LIFECYCLE_SCHEMA, "phase": phase, "expression_tier": tier,
        "recessive_revealed": False, "awakened_active": None,
        "switch_available_at": None,
    }


def test_capsule_digest_is_deterministic_and_egg_is_opaque():
    first = capsule_digest(capsule())
    altered_order = dict(reversed(list(capsule().items())))
    assert capsule_digest(altered_order) == first
    egg = opaque_egg_projection(capsule())
    assert egg["lineage_revealed"] is False
    assert "element" not in egg and egg["mark"] == "SINGLE_WHITE_LINE"


def test_lifecycle_advances_one_step_and_never_regresses():
    assert transition_lifecycle(lifecycle(), "HATCHING")["phase"] == "HATCHING"
    with pytest.raises(DNAv1Error, match="exactly one"):
        transition_lifecycle(lifecycle("MATURE", 5), "JUVENILE")


def test_recessive_is_dormant_before_maturity():
    state = lifecycle("JUVENILE", 2)
    state["recessive_revealed"] = True
    with pytest.raises(DNAv1Error) as caught:
        validate_lifecycle(state)
    assert caught.value.code == "RECESSIVE_DORMANT"


def test_awakened_switch_is_lineage_bounded_and_cooled_down():
    state = lifecycle("AWAKENED", 5)
    changed = switch_awakened_expression(capsule(), state, "ELECTRICITY", 100, 60)
    assert changed["awakened_active"] == "ELECTRICITY"
    assert changed["switch_available_at"] == 160
    with pytest.raises(DNAv1Error) as caught:
        switch_awakened_expression(capsule(), changed, "METAL", 120, 60)
    assert caught.value.code == "EXPRESSION_COOLDOWN"


def test_social_edges_are_directional_five_state_records():
    edge = {"schema": SOCIAL_SCHEMA, "subject_id": "morph:a", "object_id": "morph:b",
            "state": "FAMILIAR", "evidence_count": 4}
    assert validate_social_edge(edge) == edge
    edge["object_id"] = "morph:a"
    with pytest.raises(DNAv1Error):
        validate_social_edge(edge)


def test_breeding_requires_mutual_maturity_familiarity_and_capacity():
    request = {
        "schema": "serein.morph-breeding-eligibility.v1",
        "parent_a": "morph:a", "parent_b": "morph:b",
        "parent_a_phase": "MATURE", "parent_b_phase": "AWAKENED",
        "parent_a_social": "FAMILIAR", "parent_b_social": "BONDED",
        "cooldown_clear": True, "nursery_capacity": 1, "consent_admitted": True,
    }
    assert validate_breeding_eligibility(request) == request
    request["parent_b_social"] = "AWARE"
    with pytest.raises(DNAv1Error) as caught:
        validate_breeding_eligibility(request)
    assert caught.value.code == "BREEDING_FAMILIARITY_REQUIRED"


def test_backfill_is_code_haven_plan_with_no_implicit_effect():
    core = {"identity": {"morph_id": "morph:dustdevil"}}
    plan = code_haven_backfill_plan(core, capsule())
    assert plan["required_place"] == "CODE_HAVEN"
    assert plan["effect"] == "NONE_UNTIL_COMMIT"
    assert "authority" in plan["preserve"]
