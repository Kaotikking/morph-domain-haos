from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components/morph_domain/_vendor/morph_engine/morph_window.py"
spec = importlib.util.spec_from_file_location("morph_window_test", MODULE)
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)

NOW = datetime(2026, 9, 19, 20, 0, tzinfo=UTC)


def status(authority="HAOS"):
    return {
        "morph_id": "sentinel", "founder_id": "SENTINEL",
        "source_frame": "esp32-frame:v1:pet-frame-sentinel",
        "authority": authority, "place": "HORIZON", "custody_revision": 3,
        "lineage_generation": 0, "snapshot_digest": "a" * 64,
        "presentation": {"display_name": "Sentinel", "revision": 4},
        "life_call": {"active": {"schema": "serein.morph-life-call.v1",
                                    "call_id": "call-1", "need_class": "PLAY"}},
        "social": {"last_activity": {"kind": "REST", "expression": "GROUNDING",
                                      "participants": ["sentinel", "ember"]}},
        "life": {"behavior": "SETTLE", "morph_core": {"root": {"identity": {
            "primitive_element": "EARTH"}}}},
    }


def test_domain_window_is_elemental_pixel_snapshot_bound_to_custody():
    result = window.build_morph_window(status(), {}, NOW)
    assert result["schema"] == window.WINDOW_SCHEMA
    assert result["state"] == "DOMAIN_WINDOW"
    assert result["authority"] == "HAOS"
    assert result["avatar"]["element"] == "EARTH"
    assert result["avatar"]["palette"] == ["#00000000", "#91BD64", "#D7AD64"]
    assert len(result["avatar"]["rows"]) == 12
    assert all(len(row) == 12 and set(row) <= {"0", "1", "2"} for row in result["avatar"]["rows"])
    assert result["scene"] == {"kind": "REST", "expression": "GROUNDING", "companions": ["ember"]}
    assert result["life_call"]["call_id"] == "call-1"
    assert result["expires_at"] == "2026-09-19T20:05:00Z"


def test_window_is_deterministic_and_does_not_mutate_status_or_operations():
    current = status()
    operations = {"old": {"state": "FRAME_ACTIVE", "morph_id": "sentinel",
                           "operation_kind": "RETURN_TO_FRAME"}}
    before = deepcopy((current, operations))
    first = window.build_morph_window(current, operations, NOW)
    second = window.build_morph_window(current, operations, NOW)
    assert first == second
    assert (current, operations) == before
    assert len(first["window_digest"]) == 64
    assert len(first["avatar"]["avatar_digest"]) == 64


def test_window_distinguishes_returning_from_local_presence():
    active = {"return": {"state": "PREPARED", "morph_id": "sentinel",
                         "operation_kind": "RETURN_TO_FRAME"}}
    assert window.build_morph_window(status(), active, NOW)["state"] == "RETURNING_HOME"
    assert window.build_morph_window(
        status("esp32-frame:v1:pet-frame-sentinel"), {}, NOW)["state"] == "LOCAL_PRESENCE"


def test_pixel_identity_changes_with_presentation_revision_not_custody():
    first = status()
    changed = deepcopy(first)
    changed["presentation"]["revision"] = 5
    local = deepcopy(first)
    local["authority"] = local["source_frame"]
    assert window.build_morph_window(first, {}, NOW)["avatar"] == window.build_morph_window(local, {}, NOW)["avatar"]
    assert window.build_morph_window(first, {}, NOW)["avatar"] != window.build_morph_window(changed, {}, NOW)["avatar"]

