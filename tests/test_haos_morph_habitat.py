from datetime import UTC, datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components/morph_domain"

for name in (
    "voluptuous", "homeassistant", "homeassistant.components",
    "homeassistant.components.http", "homeassistant.core", "homeassistant.helpers",
    "homeassistant.helpers.storage", "homeassistant.helpers.event",
):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["voluptuous"].Invalid = ValueError
sys.modules["homeassistant.components.http"].HomeAssistantView = object
sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.helpers.storage"].Store = type("Store", (), {"__class_getitem__": classmethod(lambda cls, _: cls)})
sys.modules["homeassistant.helpers.event"].async_track_time_interval = lambda *args: None

package_name = "serein_gateway_test"
package = types.ModuleType(package_name)
package.__path__ = [str(PACKAGE)]
sys.modules[package_name] = package


def load(name):
    spec = importlib.util.spec_from_file_location(f"{package_name}.{name}", PACKAGE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


transfer = load("morph_transfer")
habitat = load("morph_habitat")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def snapshot(epoch=1_788_549_653):
    payload = {
        "saved_epoch_seconds": epoch, "behavior": "SETTLE", "arousal_q8": 128,
        "security_q8": 128, "curiosity_q8": 128, "social_q8": 128,
        "fatigue_q8": 40, "food_q8": 200, "water_q8": 200, "play_q8": 200,
        "rest_q8": 200, "attention_q8": 200, "memories": [],
    }
    return {"schema": transfer.LIFE_SCHEMA, "payload": payload,
            "sha256": hashlib.sha256(canonical(payload).encode()).hexdigest()}


def hosted(now):
    genome = "founder=PULSE\nbirth=1788549653\n"
    request = {
        "schema": transfer.API_SCHEMA, "transfer_id": "t1", "morph_id": "pulse",
        "founder_id": "PULSE", "device_birth_lineage": "lineage-pulse",
        "source_frame": "android-frame:v1:182b7920-d0e7-4e78-a321-1ac6722471da", "target_frame": "HAOS",
        "generation": 1, "predecessor_generation": 0,
        "created_at": now.isoformat(), "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "engine_version": transfer.ENGINE_VERSION, "genome": genome,
        "genome_sha256": hashlib.sha256(genome.encode()).hexdigest(), "snapshot": snapshot(int(now.timestamp())),
    }
    ledger = transfer.MorphTransferLedger.empty()
    prepared = ledger.prepare_inbound(request, now)
    ledger.commit_inbound("t1", prepared["snapshot_digest"], now)
    return ledger


def hosted_v3(now):
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    payload = morph["snapshot"]["payload"]
    extension_payload = {}
    payload["engine_extension"] = {
        "schema": transfer.ANDROID_EXTENSION_SCHEMA,
        "payload": extension_payload,
        "sha256": hashlib.sha256(canonical(extension_payload).encode()).hexdigest(),
    }
    payload["morph_core"] = {
        "schema": "serein.morph-core.v1",
        "identity": {"morph_id": "pulse", "founder_lineage": "founder:pulse",
                     "device_birth_lineage": morph["device_birth_lineage"],
                     "born_at": now.isoformat(), "generation": 0, "parent_ids": [],
                     "primitive_element": "AIR", "genome_version": "dnav1"},
        "life": {"growth_q16": 0, "care_counts": {}, "relationship_counts": {},
                 "journey_count": 0, "elemental_mastery_q16": {}},
        "state": {"place": "HORIZON", "authority": "HAOS_ACTIVE",
                  "active_frame": "haos-horizon",
                  "needs_q8": {"attention": payload["attention_q8"],
                               "energy": 255 - payload["fatigue_q8"],
                               "food": payload["food_q8"], "play": payload["play_q8"],
                               "rest": payload["rest_q8"], "water": payload["water_q8"]},
                  "mood": payload["behavior"].lower(), "expression": "legacy"},
        "embodiment": {"body_id": "haos-horizon", "body_class": "haos-habitat",
                       "capabilities": []},
        "chronicle": {"schema": "serein.living-code-chronicle.v1", "events": []},
    }
    morph["snapshot"]["schema"] = transfer.MORPH_CORE_LIFE_SCHEMA
    transfer.refresh_snapshot(morph)
    return ledger


def aligned_in_code_haven(now):
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    alignment_id = "auto-nine-core:test-pulse"
    core = morph["snapshot"]["payload"]["morph_core"]
    morph["snapshot"]["payload"]["morph_core"] = transfer.align_in_code_haven(
        core, morph["genome_sha256"], alignment_id, now.isoformat(),
        "haos-code-haven", "a" * 64,
    )
    transfer.refresh_snapshot(morph)
    ledger.data["operations"][alignment_id] = {
        "operation_kind": "AUTO_NINE_CORE_ALIGNMENT",
        "state": "ALIGNED_CODE_HAVEN", "morph_id": "pulse",
        "generation": morph["generation"], "transfer_id": "t1",
        "snapshot_digest": morph["snapshot_digest"],
    }
    return ledger, alignment_id


def test_untouched_auto_alignment_discharge_is_single_and_preserves_identity():
    now = datetime(2026, 9, 14, tzinfo=UTC)
    ledger, alignment_id = aligned_in_code_haven(now)
    morph = ledger.data["morphs"]["pulse"]
    original_identity = morph["snapshot"]["payload"]["morph_core"]["root"]["identity"].copy()
    changed, notices = habitat.run_automatic_reflexes(ledger, now)
    assert changed and not notices
    assert morph["authority"] == "HAOS"
    assert morph["generation"] == 1
    assert morph["snapshot"]["payload"]["morph_core"]["root"]["identity"] == original_identity
    assert morph["habitat"]["place"] == "HORIZON"
    assert ledger.data["operations"][alignment_id]["discharge_event_id"] == f"auto-discharge:{alignment_id}"
    digest = morph["snapshot_digest"]
    changed, notices = habitat.run_automatic_reflexes(ledger, now)
    assert not changed and not notices
    assert morph["snapshot_digest"] == digest


def test_changed_code_haven_snapshot_requires_operator_review():
    now = datetime(2026, 9, 14, tzinfo=UTC)
    ledger, alignment_id = aligned_in_code_haven(now)
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["operator_review"] = True
    transfer.refresh_snapshot(morph)
    changed, notices = habitat.run_automatic_reflexes(ledger, now)
    assert changed and notices[0]["kind"] == "INTERVENTION"
    assert morph["habitat"]["place"] == "CODE_HAVEN"
    assert "discharged_at" not in ledger.data["operations"][alignment_id]


def test_android_call_requires_committed_haos_horizon_morph():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    request = {
        "schema": habitat.HABITAT_SCHEMA,
        "call_id": "call-pulse-1",
        "morph_id": "pulse",
        "target_frame": ledger.data["morphs"]["pulse"]["source_frame"],
    }
    receipt = habitat.call_morph(ledger, request, now)
    assert receipt["state"] == "CALL_READY"
    assert receipt["authority"] == "HAOS"
    assert receipt["place"] == "HORIZON"
    assert receipt["transfer_required"] is True
    assert habitat.call_morph(ledger, request, now) == receipt

    changed = dict(request)
    changed["target_frame"] = "android-morph-habitat:other"
    try:
        habitat.call_morph(ledger, changed, now)
    except transfer.TransferError as err:
        assert err.code == "WRONG_FRAME_ALIAS"
    else:
        raise AssertionError("changed call replay was accepted")


def test_nursery_graduates_once_after_72_hours_and_preserves_identity():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "nursery-entry", "morph_id": "pulse", "place": "NURSERY"}, now)
    state = morph["habitat"]
    state["entered_at"] = (now - timedelta(hours=72)).isoformat()
    state["nursery_elapsed_seconds"] = 72 * 60 * 60
    before = (morph["morph_id"], morph["founder_id"], morph["device_birth_lineage"])

    changed, notices = habitat.run_automatic_reflexes(ledger, now)
    assert changed is True
    assert state["place"] == "HORIZON"
    assert notices == [{"id": notices[0]["id"], "kind": "GRADUATED", "morph_id": "pulse"}]
    assert before == (morph["morph_id"], morph["founder_id"], morph["device_birth_lineage"])

    changed_again, notices_again = habitat.run_automatic_reflexes(ledger, now + timedelta(seconds=1))
    assert changed_again is False
    assert notices_again == []


def test_horizon_water_comes_from_spring_pool_not_timed_care_script():
    now = datetime(2026, 9, 8, 8, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["water_q8"] = 40
    morph["snapshot"]["payload"]["morph_core"]["state"]["needs_q8"]["water"] = 40
    transfer.refresh_snapshot(morph)

    changed, notices = habitat.run_automatic_reflexes(ledger, now)
    assert not changed and not notices
    assert morph["snapshot"]["payload"]["water_q8"] == 40
    assert habitat.run_social_reflexes(ledger, now)
    assert morph["snapshot"]["payload"]["water_q8"] == 102
    assert habitat.habitat_status(ledger, "pulse", now)["care_levels"]["water"] == 2
    activity = morph["habitat"]["social"]["last_activity"]
    assert activity["kind"] == "DRINK" and activity["object_id"] == "spring-pool"
    assert not habitat.run_social_reflexes(ledger, now)


def test_code_haven_intervention_notice_is_deduplicated():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    ledger = hosted(now)
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "haven-entry", "morph_id": "pulse", "place": "CODE_HAVEN"}, now)
    state = ledger.data["morphs"]["pulse"]["habitat"]

    changed, notices = habitat.run_automatic_reflexes(ledger, now)
    assert changed is True
    assert notices[0]["kind"] == "INTERVENTION"
    changed_again, notices_again = habitat.run_automatic_reflexes(ledger, now + timedelta(minutes=1))
    assert changed_again is False
    assert notices_again == []


def test_android_call_rejects_every_non_horizon_or_unproven_morph():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    for place in ("VOID", "NURSERY", "SEREIN_GARDENS", "CODE_HAVEN"):
        ledger = hosted(now)
        request = {
            "schema": habitat.HABITAT_SCHEMA,
            "call_id": "call-pulse-2",
            "morph_id": "pulse",
            "target_frame": ledger.data["morphs"]["pulse"]["source_frame"],
        }
        ledger.data["morphs"]["pulse"]["habitat"] = {
            "schema": habitat.HABITAT_SCHEMA, "engine_version": habitat.HABITAT_ENGINE,
            "place": place, "entered_at": now.isoformat(), "last_tick_at": now.isoformat(),
            "void_locked_until": None, "nursery_elapsed_seconds": 0,
            "history": [], "event_ids": [],
            "environment": {"schema": habitat.ENVIRONMENT_SCHEMA,
                            "expression_q8": {element: 0 for element in habitat.ELEMENTS},
                            "exposure_seconds": {element: 0 for element in habitat.ELEMENTS},
                            "dominant": None, "last_sample": None},
        }
        try:
            habitat.call_morph(ledger, request, now)
        except transfer.TransferError as err:
            assert err.code == "CALL_REQUIRES_HORIZON"
        else:
            raise AssertionError(f"call from {place} was accepted")

    ledger = hosted(now)
    ledger.data["operations"].clear()
    try:
        habitat.call_morph(ledger, request, now)
    except transfer.TransferError as err:
        assert err.code == "TRANSFER_PROOF_REQUIRED"
    else:
        raise AssertionError("unproven Morph call was accepted")


def test_x4_alias_and_presentation_are_bound_to_current_habitat_state():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    status = habitat.habitat_status(ledger, "pulse", now)
    binding = status["presentation_binding"]
    assert binding["habitat_alias"] == ledger.data["morphs"]["pulse"]["source_frame"]
    assert binding["source_frame"] == ledger.data["morphs"]["pulse"]["source_frame"]
    assert binding["morph_id"] == status["morph_id"]
    assert binding["generation"] == status["generation"]
    assert binding["snapshot_digest"] == status["snapshot_digest"]
    assert binding["presentation_revision"] == status["presentation"]["revision"]

    request = {"schema": habitat.HABITAT_SCHEMA, "call_id": "wrong-alias",
               "morph_id": "pulse", "target_frame": "android-morph-habitat:other"}
    try:
        habitat.call_morph(ledger, request, now)
    except transfer.TransferError as err:
        assert err.code == "WRONG_FRAME_ALIAS"
    else:
        raise AssertionError("unbound Android habitat alias was accepted")


def test_horizon_ticks_only_while_haos_is_authority():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    assert habitat.advance_morph(morph, now)
    before = morph["snapshot_digest"]
    assert habitat.advance_morph(morph, now + timedelta(seconds=60))
    assert morph["snapshot"]["payload"]["food_q8"] == 198
    assert morph["snapshot_digest"] != before
    morph["authority"] = morph["source_frame"]
    frozen = morph["snapshot_digest"]
    assert not habitat.advance_morph(morph, now + timedelta(seconds=120))
    assert morph["snapshot_digest"] == frozen


def test_void_stasis_and_24_hour_withdrawal_lock():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "p1", "morph_id": "pulse", "place": "VOID"}, now)
    morph = ledger.data["morphs"]["pulse"]
    frozen = morph["snapshot_digest"]
    assert not habitat.advance_morph(morph, now + timedelta(hours=12))
    assert morph["snapshot_digest"] == frozen
    try:
        habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "p2", "morph_id": "pulse", "place": "HORIZON"}, now + timedelta(hours=23))
    except transfer.TransferError as err:
        assert err.code == "VOID_LOCKED"
    else:
        raise AssertionError("Void lock bypassed")
    status = habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "p2", "morph_id": "pulse", "place": "HORIZON"}, now + timedelta(hours=24))
    assert status["place"] == "HORIZON"


def test_operator_care_advances_two_levels_and_is_idempotent():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    request = {"schema": habitat.HABITAT_SCHEMA, "event_id": "care-1", "morph_id": "pulse", "action": "PLAY"}
    first = habitat.care_for_morph(ledger, request, now)
    second = habitat.care_for_morph(ledger, request, now + timedelta(seconds=1))
    assert first["life"] == second["life"]
    assert first["life"]["play_q8"] == 255
    assert first["care_levels"]["play"] == 5
    assert first["life"]["attention_q8"] == 218
    assert first["life"]["arousal_q8"] == 148
    assert first["life"]["behavior"] == "PLAY"
    assert first["life"]["memories"][-1] == {"code": "PLAY", "age_ms": 0, "weight": 220}


def test_care_labels_distinguish_operator_and_horizon_and_cap_at_five():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["food_q8"] = 0
    transfer.refresh_snapshot(morph)
    assert habitat.habitat_status(ledger, "pulse", now)["care_levels"]["food"] == 1
    request = {"schema": habitat.HABITAT_SCHEMA, "event_id": "operator-meal",
               "morph_id": "pulse", "action": "FEED"}
    status = habitat.care_for_morph(ledger, request, now)
    assert status["care_levels"]["food"] == 3
    assert habitat.care_for_morph(ledger, request, now)["care_levels"]["food"] == 3
    assert morph["habitat"]["history"][-1]["origin"] == "OPERATOR"
    morph["snapshot"]["payload"]["food_q8"] = 0
    transfer.refresh_snapshot(morph)
    environment = {**request, "event_id": "horizon-grove"}
    status = habitat.care_for_morph(ledger, environment, now, origin="ENVIRONMENT")
    assert status["care_levels"]["food"] == 2
    assert habitat.care_for_morph(ledger, environment, now, origin="ENVIRONMENT")["care_levels"]["food"] == 2
    assert morph["habitat"]["history"][-1]["origin"] == "ENVIRONMENT"
    for index in range(3):
        status = habitat.care_for_morph(ledger, {**environment,
                 "event_id": f"horizon-grove-{index}"}, now, origin="ENVIRONMENT")
    assert status["care_levels"]["food"] == 5


def test_remote_morph_cannot_be_placed_or_cared_for():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    ledger.data["morphs"]["pulse"]["authority"] = "android-frame:v1:182b7920-d0e7-4e78-a321-1ac6722471da"
    for request, call in (
        ({"schema": habitat.HABITAT_SCHEMA, "event_id": "p", "morph_id": "pulse", "place": "HORIZON"}, habitat.place_morph),
        ({"schema": habitat.HABITAT_SCHEMA, "event_id": "c", "morph_id": "pulse", "action": "REST"}, habitat.care_for_morph),
    ):
        try:
            call(ledger, request, now)
        except transfer.TransferError as err:
            assert err.code == "AUTHORITY_CONFLICT"
        else:
            raise AssertionError("remote Morph mutated")


def test_five_places_and_history_are_closed_and_bounded():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    assert habitat.PLACES == {"VOID", "NURSERY", "SEREIN_GARDENS", "HORIZON", "CODE_HAVEN"}
    ledger = hosted(now)
    for index, place in enumerate(("NURSERY", "SEREIN_GARDENS", "HORIZON", "CODE_HAVEN")):
        status = habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": f"p{index}", "morph_id": "pulse", "place": place}, now + timedelta(seconds=index))
        assert status["place"] == place
    history = habitat.habitat_history(ledger, "pulse", now)
    assert [row["to"] for row in history["events"]] == ["NURSERY", "SEREIN_GARDENS", "HORIZON", "CODE_HAVEN"]


def test_return_keeps_birth_lineage_after_habitat_care():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    habitat.care_for_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "care", "morph_id": "pulse", "action": "FEED"}, now)
    returned = ledger.prepare_return({"schema": transfer.API_SCHEMA, "return_id": "r1", "morph_id": "pulse", "target_frame": "android-frame:v1:182b7920-d0e7-4e78-a321-1ac6722471da", "expires_at": (now + timedelta(minutes=5)).isoformat()}, now)
    assert returned["device_birth_lineage"] == "lineage-pulse"
    final = ledger.commit_return("r1", returned["snapshot_digest"], now)
    assert final["authority"] == "android-frame:v1:182b7920-d0e7-4e78-a321-1ac6722471da"
    assert ledger.data["morphs"]["pulse"]["device_birth_lineage"] == "lineage-pulse"


def test_environment_advances_expression_without_rewriting_dna_or_snapshot_schema():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    habitat.advance_morph(morph, now)
    genome = morph["genome"]
    lineage = morph["device_birth_lineage"]
    snapshot_keys = set(morph["snapshot"]["payload"])
    sample = {
        "observed_at": now.isoformat(), "weather": "rainy", "sun": "above_horizon",
        "temperature_f": 90.0, "humidity_percent": 60.0, "wind_mph": 18.0,
        "active_motion_entities": ["binary_sensor.room_motion"],
        "sources": {"weather": "weather.kigm"},
    }
    assert habitat.advance_morph(morph, now + timedelta(seconds=60), sample)
    expression = morph["habitat"]["environment"]["expression_q8"]
    assert expression == {"FIRE": 6, "WATER": 6, "AIR": 6, "EARTH": 0}
    assert morph["genome"] == genome
    assert morph["device_birth_lineage"] == lineage
    assert set(morph["snapshot"]["payload"]) == snapshot_keys


def test_void_blocks_environmental_expression():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "void", "morph_id": "pulse", "place": "VOID"}, now)
    morph = ledger.data["morphs"]["pulse"]
    before = dict(morph["habitat"]["environment"]["expression_q8"])
    assert not habitat.advance_morph(morph, now + timedelta(hours=1), {"weather": "rainy"})
    assert morph["habitat"]["environment"]["expression_q8"] == before


def test_existing_habitat_is_upgraded_without_identity_change():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    habitat.advance_morph(morph, now)
    del morph["habitat"]["environment"]
    identity = (morph["morph_id"], morph["device_birth_lineage"], morph["snapshot_digest"])
    status = habitat.habitat_status(ledger, "pulse", now)
    assert status["environment"]["expression_q8"] == {element: 0 for element in habitat.ELEMENTS}
    assert (morph["morph_id"], morph["device_birth_lineage"], morph["snapshot_digest"]) == identity


def test_founder_axis_registers_at_zero_only_in_code_haven_then_uses_one_to_five():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    ledger = hosted(now)
    morph = ledger.data["morphs"]["pulse"]
    original_snapshot = morph["snapshot_digest"]
    request = {"schema": habitat.HABITAT_SCHEMA, "event_id": "axis-register",
               "morph_id": "pulse", "axis_id": "battle_expression",
               "source_definition": {"primitive": "WATER", "recessive": "SOUND"}}
    try:
        habitat.register_founder_axis(ledger, request, now)
    except transfer.TransferError as err:
        assert err.code == "CODE_HAVEN_REQUIRED"
    else:
        raise AssertionError("founder axis registered outside Code Haven")

    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "to-haven",
                                 "morph_id": "pulse", "place": "CODE_HAVEN"}, now)
    after_place = morph["snapshot_digest"]
    axis = habitat.register_founder_axis(ledger, request, now)
    assert axis["source_tier"] == 0
    assert axis["current_tier"] == 0
    assert axis["founder_line"] == "PULSE"
    assert habitat.register_founder_axis(ledger, request, now) == axis
    assert morph["snapshot_digest"] == after_place
    assert original_snapshot == after_place

    step = {"schema": habitat.HABITAT_SCHEMA, "event_id": "axis-activate",
            "morph_id": "pulse", "axis_id": "battle_expression", "delta": 1}
    activated = habitat.advance_founder_axis(ledger, step, now)
    assert activated["current_tier"] == 1
    assert habitat.advance_founder_axis(ledger, step, now)["current_tier"] == 1
    assert habitat.advance_founder_axis(ledger, step, now)["current_tier"] == 1
    step["event_id"] = "axis-advance"
    assert habitat.advance_founder_axis(ledger, step, now)["current_tier"] == 2
    assert morph["snapshot_digest"] == after_place


def test_founder_axis_source_is_immutable_and_unknown_axes_fail_closed():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    ledger = hosted(now)
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "haven",
                                 "morph_id": "pulse", "place": "CODE_HAVEN"}, now)
    request = {"schema": habitat.HABITAT_SCHEMA, "event_id": "axis-one", "morph_id": "pulse",
               "axis_id": "recognition", "source_definition": {"primitive": "WATER"}}
    habitat.register_founder_axis(ledger, request, now)
    conflict = dict(request)
    conflict["event_id"] = "axis-conflict"
    conflict["source_definition"] = {"primitive": "FIRE"}
    try:
        habitat.register_founder_axis(ledger, conflict, now)
    except transfer.TransferError as err:
        assert err.code == "FOUNDER_AXIS_CONFLICT"
    else:
        raise AssertionError("founder source was rewritten")
    try:
        habitat.advance_founder_axis(ledger, {"schema": habitat.HABITAT_SCHEMA,
            "event_id": "missing", "morph_id": "pulse", "axis_id": "unknown", "delta": 1}, now)
    except transfer.TransferError as err:
        assert err.code == "FOUNDER_AXIS_NOT_FOUND"
    else:
        raise AssertionError("unknown founder axis advanced")


def test_v3_tick_and_care_keep_outer_and_core_state_identical():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    habitat.advance_morph(morph, now)
    assert habitat.advance_morph(morph, now + timedelta(seconds=60))
    core_state = morph["snapshot"]["payload"]["morph_core"]["state"]
    assert core_state["needs_q8"]["food"] == morph["snapshot"]["payload"]["food_q8"]
    assert core_state["needs_q8"]["energy"] == 255 - morph["snapshot"]["payload"]["fatigue_q8"]
    transfer.validate_snapshot(morph["snapshot"])
    habitat.care_for_morph(ledger, {"schema": habitat.HABITAT_SCHEMA, "event_id": "v3-care",
                                    "morph_id": "pulse", "action": "PLAY"}, now + timedelta(seconds=61))
    assert core_state["mood"] == "play"
    assert core_state["needs_q8"]["play"] == morph["snapshot"]["payload"]["play_q8"]
    transfer.validate_snapshot(morph["snapshot"])


def test_v3_code_haven_to_horizon_syncs_place_frame_and_remains_returnable():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    for index, place in enumerate(("CODE_HAVEN", "HORIZON")):
        habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA,
            "event_id": f"v3-place-{index}", "morph_id": "pulse", "place": place},
            now + timedelta(seconds=index))
        state = morph["snapshot"]["payload"]["morph_core"]["state"]
        assert state["place"] == place
        assert state["active_frame"] == f"haos-{place.lower().replace('_', '-')}"
        transfer.validate_snapshot(morph["snapshot"])
    habitat.advance_morph(morph, now + timedelta(seconds=60))
    transfer.validate_snapshot(morph["snapshot"])

    returned = ledger.prepare_return({"schema": transfer.API_SCHEMA, "return_id": "v3-return",
        "morph_id": "pulse", "target_frame": morph["source_frame"],
        "expires_at": (now + timedelta(minutes=5)).isoformat()}, now + timedelta(seconds=61))
    assert returned["authority"] == "FROZEN_FOR_RETURN"
    assert returned["snapshot"]["payload"]["morph_core"]["state"]["authority"] == "FROZEN"
    assert returned["snapshot_digest"] == morph["snapshot_digest"]
    transfer.validate_snapshot(returned["snapshot"])


def test_expired_v3_return_restores_haos_core_authority_with_valid_digest():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    ledger.prepare_return({"schema": transfer.API_SCHEMA, "return_id": "v3-expire",
        "morph_id": "pulse", "target_frame": morph["source_frame"],
        "expires_at": (now + timedelta(seconds=1)).isoformat()}, now)
    assert ledger.reconcile_expired(now + timedelta(seconds=2))
    assert morph["authority"] == "HAOS"
    assert morph["snapshot"]["payload"]["morph_core"]["state"]["authority"] == "HAOS_ACTIVE"
    transfer.validate_snapshot(morph["snapshot"])


def test_hatch_notification_never_masquerades_as_code_haven_intervention():
    hatch = transfer.reflex_notice_content({"kind": "HATCHED", "morph_id": "water-egg"})
    graduation = transfer.reflex_notice_content({"kind": "GRADUATED", "morph_id": "water-egg"})
    intervention = transfer.reflex_notice_content({"kind": "INTERVENTION", "morph_id": "water-egg"})
    assert hatch[0] == "Morph hatched"
    assert "Code Haven" not in hatch[0] + hatch[1]
    assert graduation[0] == "Morph graduated"
    assert intervention[0] == "Morph needs Code Haven review"
    try:
        transfer.reflex_notice_content({"kind": "UNKNOWN", "morph_id": "water-egg"})
    except ValueError:
        pass
    else:
        raise AssertionError("unknown reflex kind generated a notification")
