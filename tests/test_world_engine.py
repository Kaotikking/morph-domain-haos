from copy import deepcopy
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain/_vendor"))
from morph_engine.world_engine import (
    CORE_ORDER, MorphEngineError, describe_engine, project_for_frame,
    route_facet, validate_engine_state, validate_successor,
)

def state():
    value = {"schema": "serein.morph-engine.v1"}
    value.update({core: {} for core in CORE_ORDER})
    value["root"] = {"morph_id": "morph:a", "lineage_capsule_digest": "digest:a"}
    return value

def test_public_product_is_one_engine_without_kernel():
    info = describe_engine()
    assert info["public_name"] == "Morph Engine"
    assert info["world_contract"] == "MorphDomain"
    assert info["kernel_present"] is False
    assert info["core_order"] == list(CORE_ORDER)

def test_exact_nine_core_state_required():
    assert validate_engine_state(state()) == state()
    broken = state(); broken["kernel"] = {}
    with pytest.raises(MorphEngineError):
        validate_engine_state(broken)

def test_five_facets_have_bounded_core_writes():
    assert route_facet("life") == ("platform", "memory", "personality")
    assert route_facet("combination") == ("root", "memory", "modular")
    assert route_facet("reflex") == ("platform", "root", "memory", "cloud")

def test_cross_core_write_is_rejected():
    old = state(); new = deepcopy(old); new["ui"]["mark"] = "x"
    with pytest.raises(MorphEngineError) as caught:
        validate_successor(old, new, "life")
    assert caught.value.code == "CROSS_CORE_WRITE"

def test_root_identity_is_immutable_even_for_combination():
    old = state(); new = deepcopy(old); new["root"]["morph_id"] = "morph:b"
    with pytest.raises(MorphEngineError) as caught:
        validate_successor(old, new, "combination")
    assert caught.value.code == "IMMUTABLE_ROOT_CHANGED"

def test_frame_projection_degrades_without_deleting_truth():
    source = state(); source["audio"] = {"voice": "water"}; source["ui"] = {"form": "pulse"}
    projected = project_for_frame(source, ["display"])
    assert projected["visible"]["form"] == {"form": "pulse"}
    assert projected["visible"]["voice"]["mode"] == "remembered-not-rendered"
    assert projected["canonical_state_preserved"] is True
