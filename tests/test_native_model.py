from pathlib import Path
import importlib.util


PATH = Path(__file__).parents[1] / "custom_components/morph_domain/native_model.py"
SPEC = importlib.util.spec_from_file_location("morph_native_model_test", PATH)
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


def morph(authority="HAOS", place="HORIZON"):
    return {
        "morph_id": "morph:test",
        "founder_id": "PULSE",
        "device_birth_lineage": "lineage:test",
        "authority": authority,
        "place": place,
        "habitat_engine_state": "ACTIVE",
        "generation": 3,
        "lineage_generation": 0,
        "presentation": {"display_name": "Pulse"},
        "life": {"morph_core": {
            "platform": {"runtime": "frame-kernel-v1", "embodiment": {"body_class": "pet-frame", "body_id": "frame:test", "capabilities": ["display"]}},
            "root": {"identity": {"primitive_element": "WATER"}},
            "memory": {"life": {"journey_count": 4}, "chronicle": {"events": [{"event_id": "one"}]}},
            "knowledge": {"learned": {"song": True}},
            "ui": {"expression": "water", "expression_stage": 2, "visual_seed": "seed"},
            "audio": {"element_voice": "water", "render_model": "voice-v1", "expression_level": 2},
            "personality": {"mood": "play", "active_trait": "inward-bloom", "trait_stage": 1},
            "modular": {"capabilities": ["hatch", "battle-ready"]},
            "cloud": {"place": place, "authority": "HAOS_ACTIVE", "reconciliation": "local-first"},
        }},
    }


def test_native_identity_and_area_are_custody_aware():
    row = morph()
    assert MODEL.display_name(row) == "Pulse"
    assert MODEL.custody_state(row) == "HORIZON"
    assert MODEL.native_area(row) == "Horizon"
    remote = morph("esp32-frame:v1:sentinel", "HORIZON")
    assert MODEL.custody_state(remote) == "FRAME"
    assert MODEL.native_area(remote) is None


def test_all_nine_cores_have_bounded_native_projections():
    row = morph()
    values = {core: MODEL.core_projection(row, core) for core in MODEL.CORE_ORDER}
    assert tuple(values) == MODEL.CORE_ORDER
    assert values["platform"][0] == "pet-frame"
    assert values["root"][1]["primitive_element"] == "WATER"
    assert values["memory"][0] == 1
    assert values["knowledge"][0] == 1
    assert values["ui"][0] == 2
    assert values["audio"][0] == "water"
    assert values["personality"][0] == "play"
    assert values["modular"][0] == 2
    assert values["cloud"][0] == "HORIZON"


def test_unknowns_remain_unknown_without_blocking_device_projection():
    row = {"morph_id": "morph:unknown", "founder_id": "DESCENDANT", "authority": "HAOS", "place": "VOID", "life": {}}
    assert MODEL.native_area(row) == "Void"
    assert MODEL.core_projection(row, "platform")[0] == "UNKNOWN"
    assert MODEL.core_projection(row, "cloud")[0] == "VOID"

