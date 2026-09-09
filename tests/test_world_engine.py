from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain/_vendor"))

from morph_engine.core_contract import CORE_ORDER, CoreContractError
from morph_engine.world_engine import (
    describe_engine, project_for_frame, route_facet,
    validate_engine_state, validate_successor,
)


def state():
    capsule = {"schema": "capsule-v1"}
    digest = hashlib.sha256(json.dumps(capsule, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "serein.morph-engine.v1",
        "platform": {
            "schema": "serein.morph-engine.platform.v1",
            "runtime": {}, "storage": {}, "clock": {}, "life_schedule": {},
            "host_capabilities": [],
        },
        "root": {
            "schema": "serein.morph-engine.root.v1",
            "identity": {
                "morph_id": "morph:a", "parentage": [], "founder_ancestry": ["BREEZE"],
                "device_birth_lineage": "frame:a", "generation": 0,
            },
            "lineage_capsule": capsule,
            "lineage_capsule_digest": digest,
            "authority": {"owner": "HAOS"},
            "transaction": None,
        },
        "memory": {
            "schema": "serein.morph-engine.memory.v1",
            "chronicle": [{"event_id": "birth"}],
            "family": {"parents": []},
            "relationships": {"morph:b": {"state": 1}},
            "experience": {"growth": 5, "journeys": ["frame:a"]},
        },
        "knowledge": {
            "schema": "serein.morph-engine.knowledge.v1",
            "environment": {}, "preferences": {}, "learned_patterns": {},
        },
        "ui": {
            "schema": "serein.morph-engine.ui.v1",
            "form": {}, "elemental_render": {}, "egg_render": {},
            "animation": {}, "accessibility": {},
        },
        "audio": {
            "schema": "serein.morph-engine.audio.v1",
            "elemental_voice": {}, "battle_cry": {}, "audio_memory": {},
        },
        "personality": {
            "schema": "serein.morph-engine.personality.v1",
            "mood": {}, "traits": {}, "social_disposition": {}, "compatibility": {},
        },
        "modular": {
            "schema": "serein.morph-engine.modular.v1",
            "combination": {}, "frame_capabilities": {}, "extensions": {},
        },
        "cloud": {
            "schema": "serein.morph-engine.cloud.v1",
            "transfer": {}, "custody": {}, "reconciliation": {}, "sern_capsule": {},
        },
    }


def test_public_product_is_one_engine_without_kernel():
    info = describe_engine()
    assert info["public_name"] == "Morph Engine"
    assert info["world_contract"] == "MorphDomain"
    assert info["kernel_present"] is False
    assert info["core_order"] == list(CORE_ORDER)


def test_exact_nine_core_state_and_each_core_schema_are_required():
    assert validate_engine_state(state()) == state()
    broken = state()
    del broken["knowledge"]["preferences"]
    with pytest.raises(CoreContractError) as caught:
        validate_engine_state(broken)
    assert caught.value.code == "INVALID_CORE_STATE"


def test_five_facets_have_bounded_core_writes():
    assert route_facet("life") == ("platform", "memory", "personality")
    assert route_facet("social") == ("memory", "personality")
    assert route_facet("expression") == ("ui", "audio", "personality")
    assert route_facet("combination") == ("root", "memory", "modular")
    assert route_facet("reflex") == ("platform", "root", "memory", "cloud")


def test_cross_core_write_is_rejected():
    old = state()
    new = deepcopy(old)
    new["ui"]["form"]["mark"] = "x"
    with pytest.raises(CoreContractError) as caught:
        validate_successor(old, new, "life")
    assert caught.value.code == "CROSS_CORE_WRITE"


@pytest.mark.parametrize("mutation", [
    lambda value: value["root"]["identity"].update(morph_id="morph:b"),
    lambda value: value["root"]["identity"].update(generation=1),
    lambda value: value["root"].update(lineage_capsule_digest="b" * 64),
    lambda value: value["root"]["lineage_capsule"].update(schema="capsule-v2"),
])
def test_nested_root_identity_and_lineage_are_immutable(mutation):
    old = state()
    new = deepcopy(old)
    mutation(new)
    with pytest.raises(CoreContractError) as caught:
        validate_successor(old, new, "combination")
    assert caught.value.code in {"IMMUTABLE_ROOT_CHANGED", "INVALID_LINEAGE_DIGEST"}


def test_memory_chronicle_may_append_and_counters_may_increase():
    old = state()
    new = deepcopy(old)
    new["memory"]["chronicle"].append({"event_id": "care"})
    new["memory"]["experience"]["growth"] = 6
    assert validate_successor(old, new, "life") == new


@pytest.mark.parametrize("mutation", [
    lambda value: value["memory"]["chronicle"].clear(),
    lambda value: value["memory"]["experience"].update(growth=4),
    lambda value: value["memory"]["relationships"].pop("morph:b"),
])
def test_memory_truth_cannot_be_erased_reordered_or_decreased(mutation):
    old = state()
    new = deepcopy(old)
    mutation(new)
    with pytest.raises(CoreContractError) as caught:
        validate_successor(old, new, "life")
    assert caught.value.code == "MEMORY_REGRESSION"


def test_frame_projection_degrades_without_deleting_truth():
    source = state()
    source["audio"]["elemental_voice"] = {"voice": "water"}
    source["ui"]["form"] = {"shape": "pulse"}
    projected = project_for_frame(source, ["display"])
    assert projected["visible"]["form"]["form"] == {"shape": "pulse"}
    assert projected["visible"]["voice"]["mode"] == "remembered-not-rendered"
    assert projected["canonical_state_preserved"] is True


def test_memory_chronicle_cannot_be_reordered():
    old = state()
    old["memory"]["chronicle"].append({"event_id": "second"})
    new = deepcopy(old)
    new["memory"]["chronicle"].reverse()
    with pytest.raises(CoreContractError) as caught:
        validate_successor(old, new, "life")
    assert caught.value.code == "MEMORY_REGRESSION"


def test_nonfinite_and_bool_number_type_drift_fail_closed():
    bad = state()
    bad["knowledge"]["environment"]["temperature"] = float("nan")
    with pytest.raises(CoreContractError) as caught:
        validate_engine_state(bad)
    assert caught.value.code == "INVALID_CORE_STATE"

    old = state()
    new = deepcopy(old)
    old["memory"]["experience"]["growth"] = 1
    new["memory"]["experience"]["growth"] = True
    with pytest.raises(CoreContractError) as caught:
        validate_successor(old, new, "life")
    assert caught.value.code == "MEMORY_REGRESSION"


def test_lineage_capsule_digest_is_recomputed():
    bad = state()
    bad["root"]["lineage_capsule"]["schema"] = "tampered"
    with pytest.raises(CoreContractError) as caught:
        validate_engine_state(bad)
    assert caught.value.code == "INVALID_LINEAGE_DIGEST"
