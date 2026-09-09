from copy import deepcopy
import sys
from pathlib import Path

import pytest

SDK_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "morph_domain" / "_vendor" / "morph_sdk"
sys.path.insert(0, str(SDK_PATH))

import dna_v1
import elemental_expression as expression
import package_registry_v1 as registry


def capsule():
    return {
        "schema": dna_v1.LINEAGE_SCHEMA, "morph_id": "dustdevil", "birth_digest": "birth",
        "parent_ids": ["breeze", "sentinel"], "founder_ancestry": ["F-02", "F-03"],
        "device_birth_lineage": "NURSERY", "primitive_element": "AIR",
        "recessive_elements": ["EARTH"], "primary_expression_path": ["A", "B", "C", "D", "E"],
        "awakened_expression_set": ["A", "E"], "trait_seed": "INWARD_BLOOM",
        "birth_event": {"egg_id": "egg", "nursery_transaction_id": "tx", "hatched_at": None,
                        "hatch_pattern": "VOID_LINE", "twin_binding": None, "schema_version": "1"},
        "genome_version": "1",
    }


def elemental():
    return {
        "schema": expression.EXPRESSION_SCHEMA, "dominant_primitive": "AIR",
        "secondary_primitive": "EARTH", "recessive_potentials": [],
        "parent_locus_contributions": {"breeze": 5, "sentinel": 5}, "expression_level": 4,
        "compound_family": "DUST", "visual_expression": "dust-devil",
        "environment_selector": "weather.clear", "body_mode": "hover",
        "body_mode_lock": {"locked_mode": None, "replacement_mode": None, "reason": None},
        "origin_binding_digest": "a" * 64,
    }


def test_dual_primitive_expression_is_bound_to_immutable_lineage():
    bound = dna_v1.validate_lineage_expression_binding(capsule(), elemental())
    assert bound["expression"]["compound_family"] == "DUST"
    broken = elemental(); broken["secondary_primitive"] = "WATER"; broken["compound_family"] = "STORM"
    with pytest.raises(dna_v1.DNAv1Error, match="not birth-authorized"):
        dna_v1.validate_lineage_expression_binding(capsule(), broken)


def test_context_cannot_raise_permanent_mastery_without_care_and_social_evidence():
    old = elemental(); old["expression_level"] = 3; old["compound_family"] = None
    new = deepcopy(old); new["expression_level"] = 4; new["compound_family"] = "DUST"
    new["environment_selector"] = "weather.dust_storm"
    with pytest.raises(expression.ElementalExpressionError) as raised:
        expression.authorize_expression_successor(old, new, generation=1,
            parent_ids=["breeze", "sentinel"], care_level=3, social_level=5)
    assert raised.value.code == "MASTERY_NOT_EARNED"
    assert expression.authorize_expression_successor(old, new, generation=1,
        parent_ids=["breeze", "sentinel"], care_level=4, social_level=4) == new


def test_serein_is_optional_enrichment_not_a_life_dependency():
    assert registry.SEREIN_RUNTIME_DEPENDENCY == "OPTIONAL_ENRICHMENT"
    assert set(registry.LOCAL_FIRST_CAPABILITIES) == {
        "identity", "life", "care", "social", "expression", "movement",
        "code_haven", "chronicle", "presentation",
    }

