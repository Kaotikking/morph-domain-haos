from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain/_vendor"))

from morph_sdk.morph_core import (
    MORPH_NINE_CORE_SCHEMA,
    align_in_code_haven,
    awaken_inward_bloom,
    validate_morph_core,
    verify_successor,
)


def _legacy_core():
    return {
        "schema": "serein.morph-core.v1",
        "identity": {
            "morph_id": "morph-child:37ca6f7dfd4fbba83f43ab4e88f8bf90",
            "founder_lineage": "descendant",
            "device_birth_lineage": "nursery-lineage:37ca6f7dfd4fbba8",
            "born_at": "2026-09-08T00:00:00Z",
            "generation": 1,
            "parent_ids": ["founder:sentinel", "founder:breeze"],
            "primitive_element": "AIR",
            "genome_version": "dna-v1",
        },
        "life": {"growth_q16": 7, "care_counts": {}, "relationship_counts": {},
                 "journey_count": 0, "elemental_mastery_q16": {}},
        "state": {"place": "VOID", "authority": "HAOS_ACTIVE",
                  "active_frame": "haos-void", "needs_q8": {"food": 183},
                  "mood": "settle", "expression": "latent"},
        "embodiment": {"body_id": "nursery-newborn", "body_class": "morph-child",
                       "capabilities": ["render"]},
        "chronicle": {"schema": "serein.living-code-chronicle.v1", "events": []},
    }


def test_inward_bloom_is_deterministic_and_preserves_life_identity():
    before = _legacy_core()
    after = awaken_inward_bloom(
        deepcopy(before), "a" * 64, "dustdevil.inward-bloom.v1",
        datetime(2026, 9, 8, tzinfo=UTC).isoformat(), "haos-morphdomain", "b" * 64,
    )
    assert after["schema"] == MORPH_NINE_CORE_SCHEMA
    assert set(after) == {"schema", "platform", "root", "memory", "knowledge",
                          "ui", "audio", "personality", "modular", "cloud"}
    assert after["root"]["identity"] == before["identity"]
    assert after["memory"]["life"] == before["life"]
    assert after["cloud"]["place"] == "VOID"
    assert after["cloud"]["authority"] == "HAOS_ACTIVE"
    assert after["root"]["historic_role"] == "first-whole"
    assert after["personality"]["trait_stage"] == 0
    assert after["audio"] == awaken_inward_bloom(
        deepcopy(before), "a" * 64, "dustdevil.inward-bloom.v1",
        datetime(2026, 9, 8, tzinfo=UTC).isoformat(), "haos-morphdomain", "b" * 64,
    )["audio"]
    validate_morph_core(after)
    verify_successor(before, after)


def test_code_haven_alignment_preserves_truth_and_is_not_inward_bloom():
    before = _legacy_core()
    before["state"].update({"place": "HORIZON", "active_frame": "phone-frame",
                            "authority": "REMOTE_ACTIVE"})
    after = align_in_code_haven(before, "c" * 64, "auto-nine-core:1234",
                                "2026-09-08T00:00:00Z", "haos-code-haven", "d" * 64)
    assert after["root"]["identity"] == before["identity"]
    assert after["memory"]["life"] == before["life"]
    assert after["root"]["historic_role"] == "lineage-member"
    assert after["root"]["emergence_event"] == "transfer-alignment"
    assert after["cloud"]["place"] == "CODE_HAVEN"
    assert after["cloud"]["authority"] == "HAOS_ACTIVE"
    assert after["memory"]["chronicle"]["events"][-1]["kind"] == "nine-core-alignment"

