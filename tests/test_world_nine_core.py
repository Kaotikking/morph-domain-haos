"""Local persistence and authority proof for the nine-Core Pet World path."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from test_haos_morph_habitat import hosted_v3, habitat, transfer
from serein_gateway_test._vendor.morph_engine import habitat as engine_habitat
from serein_gateway_test._vendor.morph_sdk.morph_core import (
    MORPH_NINE_CORE_SCHEMA, align_in_code_haven, validate_morph_core,
)


NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)


def aligned(morph_id="pulse", place="SEREIN_GARDENS"):
    ledger = hosted_v3(NOW)
    morph = ledger.data["morphs"].pop("pulse")
    morph["morph_id"] = morph_id
    morph["snapshot"]["payload"]["morph_core"]["identity"]["morph_id"] = morph_id
    morph["snapshot"]["payload"]["morph_core"]["state"]["place"] = "CODE_HAVEN"
    core = align_in_code_haven(morph["snapshot"]["payload"]["morph_core"], "a" * 64,
                              f"align-{morph_id}", NOW.isoformat(), "haos-code-haven", "b" * 64)
    morph["snapshot"]["payload"]["morph_core"] = core
    morph["snapshot"]["payload"]["morph_core"]["cloud"]["place"] = place
    morph["habitat"] = engine_habitat._habitat(morph, NOW)
    morph["habitat"]["place"] = place
    transfer.refresh_snapshot(morph)
    ledger.data["morphs"][morph_id] = morph
    return ledger


def test_operator_object_play_writes_knowledge_and_append_only_memory():
    ledger = aligned()
    before = deepcopy(ledger.data["morphs"]["pulse"])
    result = engine_habitat.interact_world_object(ledger, event_id="garden-play-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert result["result"] == "ACCEPTED"
    after = ledger.data["morphs"]["pulse"]
    core = validate_morph_core(after["snapshot"]["payload"]["morph_core"])
    assert core["schema"] == MORPH_NINE_CORE_SCHEMA
    assert core["knowledge"]["learned"]["world_objects"]["counts"] == {"quiet-pool": 1}
    assert core["knowledge"]["learned"]["world_objects"]["preferences"] == []
    assert core["memory"]["chronicle"]["events"][-1]["event_id"] == "garden-play-1"
    assert core["root"] == before["snapshot"]["payload"]["morph_core"]["root"]
    digest = after["snapshot_digest"]
    restarted = transfer.MorphTransferLedger(deepcopy(ledger.data))
    assert engine_habitat.interact_world_object(restarted, event_id="garden-play-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)["result"] == "REPLAY"
    assert restarted.data["morphs"]["pulse"]["snapshot_digest"] == digest


def test_decline_does_not_write_either_nine_core():
    first, second = aligned("pulse"), aligned("ember")
    first.data["morphs"].update(second.data["morphs"])
    before = {key: value["snapshot_digest"] for key, value in first.data["morphs"].items()}
    result = engine_habitat.interact_world_object(first, event_id="declined",
        place="SEREIN_GARDENS", object_id="shared-chimes",
        participants=("pulse", "ember"), willing={"pulse": True, "ember": False}, now=NOW)
    assert result["result"] == "DECLINED" and result["credited"] == []
    assert {key: value["snapshot_digest"] for key, value in first.data["morphs"].items()} == before


def test_legacy_core_cannot_gain_untracked_object_memory():
    ledger = hosted_v3(NOW)
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA,
        "event_id": "to-gardens", "morph_id": "pulse", "place": "SEREIN_GARDENS"}, NOW)
    with pytest.raises(transfer.TransferError) as err:
        engine_habitat.interact_world_object(ledger, event_id="legacy-play",
            place="SEREIN_GARDENS", object_id="play-orb",
            participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert err.value.code == "NINE_CORE_REQUIRED"


def test_horizon_rest_expression_follows_primary_element_without_dna_change():
    from serein_gateway_test._vendor.morph_engine.world_objects import elemental_rest_scene
    expected = {"AIR": "AIR_CURRENTS", "WATER": "SWIM",
                "FIRE": "EMBER_WARMTH", "EARTH": "GROUNDING"}
    for element, scene in expected.items():
        ledger = aligned(f"rest-{element.lower()}", "HORIZON")
        morph = ledger.data["morphs"][f"rest-{element.lower()}"]
        core = morph["snapshot"]["payload"]["morph_core"]
        core["root"]["identity"]["primitive_element"] = element
        morph["snapshot"]["payload"]["rest_q8"] = 40
        engine_habitat._sync_morph_core_state(morph)
        transfer.refresh_snapshot(morph)
        assert elemental_rest_scene(core) == scene
        assert engine_habitat.run_social_reflexes(ledger, NOW)
        activity = ledger.data["morphs"][morph["morph_id"]]["habitat"]["social"]["last_activity"]
        assert activity["kind"] == "REST" and activity["expression"] == scene
        assert core["root"]["identity"]["primitive_element"] == element
        updated = ledger.data["morphs"][morph["morph_id"]]["snapshot"]["payload"]["morph_core"]
        history = updated["knowledge"]["learned"]["world_objects"]
        assert sum(history["counts"].values()) == 1
        assert updated["memory"]["chronicle"]["events"][-1]["kind"] == "world-object"


def test_horizon_pair_automatically_shares_one_object_with_replay_guard():
    ledger = aligned("pulse", "HORIZON")
    ledger.data["morphs"].update(aligned("ember", "HORIZON").data["morphs"])
    original = {name: deepcopy(morph["snapshot"]["payload"]["morph_core"]["root"])
                for name, morph in ledger.data["morphs"].items()}
    assert engine_habitat.run_social_reflexes(ledger, NOW)
    for name, morph in ledger.data["morphs"].items():
        core = morph["snapshot"]["payload"]["morph_core"]
        history = core["knowledge"]["learned"]["world_objects"]
        assert sum(history["counts"].values()) == 1
        assert core["root"] == original[name]
        assert core["memory"]["chronicle"]["events"][-1]["kind"] == "world-object"
    before = {name: morph["snapshot_digest"] for name, morph in ledger.data["morphs"].items()}
    assert not engine_habitat.run_social_reflexes(ledger, NOW)
    assert {name: morph["snapshot_digest"] for name, morph in ledger.data["morphs"].items()} == before


def test_six_morph_horizon_soak_keeps_legacy_member_active():
    names = ("dustdevil", "starter-water", "sentinel", "breeze", "pulse")
    ledger = aligned(names[0], "HORIZON")
    for name in names[1:]:
        ledger.data["morphs"].update(aligned(name, "HORIZON").data["morphs"])
    legacy = hosted_v3(NOW).data["morphs"]["pulse"]
    legacy["morph_id"] = "ember"
    legacy["snapshot"]["payload"]["morph_core"]["identity"]["morph_id"] = "ember"
    transfer.refresh_snapshot(legacy)
    ledger.data["morphs"]["ember"] = legacy
    before = {name: (morph["generation"], morph["authority"])
              for name, morph in ledger.data["morphs"].items()}
    assert engine_habitat.run_social_reflexes(ledger, NOW)
    assert len(ledger.data["morphs"]) == 6
    for name, morph in ledger.data["morphs"].items():
        assert (morph["generation"], morph["authority"]) == before[name]
        assert morph["snapshot"]["payload"]["morph_core"]["schema"] == (
            "serein.morph-core.v1" if name == "ember" else MORPH_NINE_CORE_SCHEMA)
    assert not engine_habitat.run_social_reflexes(ledger, NOW)


def test_live_ledger_world_play_continues_after_portable_budget_and_survives_restart():
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    core = morph["snapshot"]["payload"]["morph_core"]
    core["memory"]["chronicle"]["events"] = [
        {"event_id": f"prior-{n}", "kind": "observed", "observed_at": NOW.isoformat(),
         "source": "haos-morph-engine", "place": "SEREIN_GARDENS", "frame": "haos-serein-gardens",
         "evidence_digest": "a" * 64} for n in range(engine_habitat.PORTABLE_CHRONICLE_EVENT_LIMIT)
    ]
    transfer.refresh_snapshot(morph)
    original_root = deepcopy(core["root"])
    first = engine_habitat.interact_world_object(ledger, event_id="overflow-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert first["result"] == "ACCEPTED"
    morph = ledger.data["morphs"]["pulse"]
    core = validate_morph_core(morph["snapshot"]["payload"]["morph_core"])
    assert len(core["memory"]["chronicle"]["events"]) == engine_habitat.PORTABLE_CHRONICLE_EVENT_LIMIT
    assert core["knowledge"]["learned"]["chronicle_archive"]["count"] == 1
    assert morph["habitat"]["chronicle_archive"]["rows"][0]["event"]["event_id"] == "overflow-1"
    assert core["root"] == original_root
    restarted = transfer.MorphTransferLedger(deepcopy(ledger.data))
    second = engine_habitat.interact_world_object(restarted, event_id="overflow-2",
        place="SEREIN_GARDENS", object_id="shared-chimes",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert second["result"] == "ACCEPTED"
    assert restarted.data["morphs"]["pulse"]["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["chronicle_archive"]["count"] == 2


def test_live_ledger_missing_or_tampered_archive_fails_without_life_write():
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    core = morph["snapshot"]["payload"]["morph_core"]
    core["memory"]["chronicle"]["events"] = [
        {"event_id": f"prior-{n}", "kind": "observed", "observed_at": NOW.isoformat(),
         "source": "haos-morph-engine", "place": "SEREIN_GARDENS", "frame": "haos-serein-gardens",
         "evidence_digest": "a" * 64} for n in range(engine_habitat.PORTABLE_CHRONICLE_EVENT_LIMIT)
    ]
    transfer.refresh_snapshot(morph)
    engine_habitat.interact_world_object(ledger, event_id="overflow-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    morph = ledger.data["morphs"]["pulse"]
    morph["habitat"]["chronicle_archive"]["rows"][0]["event"]["kind"] = "forged"
    before = deepcopy(ledger.data)
    with pytest.raises(transfer.TransferError) as err:
        engine_habitat.interact_world_object(ledger, event_id="overflow-2",
            place="SEREIN_GARDENS", object_id="shared-chimes",
            participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert err.value.code == "ARCHIVE_INTEGRITY_FAILED"
    assert ledger.data == before


def test_live_ledger_archives_early_when_other_nine_core_data_uses_budget():
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    core = morph["snapshot"]["payload"]["morph_core"]
    core["knowledge"]["learned"]["large_local_context"] = "x" * 100000
    transfer.refresh_snapshot(morph)
    before_events = len(core["memory"]["chronicle"]["events"])
    result = engine_habitat.interact_world_object(ledger, event_id="budget-overflow",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert result["result"] == "ACCEPTED"
    updated = ledger.data["morphs"]["pulse"]
    core = validate_morph_core(updated["snapshot"]["payload"]["morph_core"])
    assert len(core["memory"]["chronicle"]["events"]) == before_events
    assert core["knowledge"]["learned"]["chronicle_archive"]["count"] == 1
    assert updated["habitat"]["chronicle_archive"]["rows"][0]["event"]["event_id"] == "budget-overflow"
    continued = engine_habitat.interact_world_object(ledger, event_id="budget-overflow-2",
        place="SEREIN_GARDENS", object_id="shared-chimes",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    assert continued["result"] == "ACCEPTED"
    page = engine_habitat.chronicle_page(ledger, "pulse", 0, 1, NOW)
    assert page["total"] == 2 and page["next_sequence"] == 1
    assert page["rows"][0]["event"]["event_id"] == "budget-overflow"
    assert page["custody_changed"] is False
    assert engine_habitat.chronicle_page(ledger, "pulse", 1, 1, NOW)["rows"][0]["event"]["event_id"] == "budget-overflow-2"


def test_archive_page_is_read_only_and_detects_tamper():
    from serein_gateway_test.http_policy import action_is_read, action_requires_admin
    assert action_is_read("habitat", "chronicle-page")
    assert action_requires_admin("habitat", "chronicle-page")
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["large_local_context"] = "x" * 100000
    transfer.refresh_snapshot(morph)
    engine_habitat.interact_world_object(ledger, event_id="archived-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    before = deepcopy(ledger.data)
    first = engine_habitat.chronicle_page(ledger, "pulse", 0, 32, NOW)
    assert engine_habitat.chronicle_page(ledger, "pulse", 0, 32, NOW) == first
    assert ledger.data == before
    current = ledger.data["morphs"]["pulse"]
    assert first["head_sha256"] == current["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["chronicle_archive"]["head_sha256"]
    with pytest.raises(transfer.TransferError) as err:
        engine_habitat.chronicle_page(ledger, "pulse", 2, 1, NOW)
    assert err.value.code == "INVALID_PAGE"
    ledger.data["morphs"]["pulse"]["habitat"]["chronicle_archive"]["rows"][0]["event"]["kind"] = "forged"
    with pytest.raises(transfer.TransferError) as err:
        engine_habitat.chronicle_page(ledger, "pulse", 0, 1, NOW)
    assert err.value.code == "ARCHIVE_INTEGRITY_FAILED"


def test_local_sern_gateway_sern_return_sequence_preserves_single_authority():
    """Control packets stay small; history is fetched before custody commit."""
    from datetime import timedelta
    from serein_gateway_test.sern import NINE_CORES, validate_envelope
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["large_local_context"] = "x" * 100000
    transfer.refresh_snapshot(morph)
    engine_habitat.interact_world_object(ledger, event_id="journey-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    morph = ledger.data["morphs"]["pulse"]
    destination_id = morph["source_frame"]
    return_id = "destination-owned-return-1"
    def packet(message_id, message_type, digest):
        cores = dict.fromkeys(NINE_CORES, {})
        cores["identity"] = {"morph_id": "pulse", "generation": morph["generation"]}
        cores["transport"] = {"return_id": return_id, "snapshot_digest": digest,
                              "archive_head": morph["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["chronicle_archive"]["head_sha256"]}
        return validate_envelope({"schema": "sern.morph_domain.v1", "message_id": message_id,
            "message_type": message_type, "morph_id": "pulse", "generation": morph["generation"], "cores": cores})
    start = packet("start-1", "OPEN_TRANSPORT", morph["snapshot_digest"])
    assert len(start.as_dict()["cores"]) == 9
    prepared = ledger.prepare_return({"schema": transfer.API_SCHEMA, "return_id": return_id,
        "morph_id": "pulse", "target_frame": destination_id,
        "expires_at": (NOW + timedelta(minutes=5)).isoformat()}, NOW)
    assert ledger.data["morphs"]["pulse"]["authority"] == "FROZEN_FOR_RETURN"
    before = deepcopy(ledger.data)
    page = engine_habitat.chronicle_page(ledger, "pulse", 0, 32, NOW)
    assert page["total"] == 1 and page["head_sha256"] == start.as_dict()["cores"]["transport"]["archive_head"]
    assert ledger.data == before
    assert prepared["snapshot_digest"] != "" and prepared["snapshot_digest"] == ledger.data["morphs"]["pulse"]["snapshot_digest"]
    receipt = packet("confirm-1", "RECEIPT", prepared["snapshot_digest"])
    assert receipt.as_dict()["cores"]["transport"]["return_id"] == return_id
    assert ledger.data["morphs"]["pulse"]["authority"] == "FROZEN_FOR_RETURN"
    final = ledger.commit_return(return_id, prepared["snapshot_digest"], NOW)
    assert final["authority"] == destination_id
    assert ledger.status(return_id)["authority"] == destination_id


def test_shared_archive_writer_keeps_code_haven_and_hatch_events_portable_bounded():
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    core = morph["snapshot"]["payload"]["morph_core"]
    core["knowledge"]["learned"]["large_local_context"] = "x" * 100000
    transfer.refresh_snapshot(morph)
    before_count = len(core["memory"]["chronicle"]["events"])
    for number, kind in enumerate(("starter-hatch", "lineage-correction"), 1):
        transfer.append_nine_core_event(morph, {"event_id": f"boundary-{number}",
            "kind": kind, "observed_at": NOW.isoformat(), "source": "haos-code-haven",
            "place": "CODE_HAVEN", "frame": "haos-code-haven", "evidence_digest": "a" * 64})
        transfer.refresh_snapshot(morph)
    assert len(core["memory"]["chronicle"]["events"]) == before_count
    assert core["knowledge"]["learned"]["chronicle_archive"]["count"] == 2
    page = engine_habitat.chronicle_page(ledger, "pulse", 0, 2, NOW)
    assert [row["event"]["kind"] for row in page["rows"]] == ["starter-hatch", "lineage-correction"]


def test_installed_style_habitat_route_pages_without_storage_write():
    import asyncio
    from types import SimpleNamespace
    from serein_gateway_test import morph_transfer
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["morph_core"]["knowledge"]["learned"]["large_local_context"] = "x" * 100000
    transfer.refresh_snapshot(morph)
    engine_habitat.interact_world_object(ledger, event_id="api-page-1",
        place="SEREIN_GARDENS", object_id="quiet-pool",
        participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True}, now=NOW)
    class NoWriteStore:
        async def async_save(self, value):
            raise AssertionError("read route attempted a write")
    manager = morph_transfer.MorphTransferManager.__new__(morph_transfer.MorphTransferManager)
    manager.hass = SimpleNamespace(data={})
    manager.store = NoWriteStore()
    manager.ledger = ledger
    manager.lock = asyncio.Lock()
    manager.metrics = morph_transfer.MorphRuntimeMetrics()
    before = deepcopy(ledger.data)
    body = {"morph_id": "pulse", "after_sequence": 0, "limit": 1}
    result = asyncio.run(manager.handle_habitat("chronicle-page", body))
    assert result["rows"][0]["event"]["event_id"] == "api-page-1"
    assert manager.ledger.data == before


def test_haos_clock_never_advances_frame_owned_life():
    from datetime import timedelta
    ledger = aligned()
    morph = ledger.data["morphs"]["pulse"]
    morph["authority"] = morph["source_frame"]
    before = deepcopy(morph)
    assert engine_habitat.advance_morph(morph, NOW + timedelta(days=7), None) is False
    assert morph == before


def test_archive_download_requires_haos_admin_even_though_it_is_read_only():
    import asyncio
    from types import SimpleNamespace
    from serein_gateway_test import morph_habitat
    class Request(dict):
        def __init__(self, is_admin):
            super().__init__({"hass_user": SimpleNamespace(is_admin=is_admin, id="user-1")})
            self.app = {"hass": SimpleNamespace(data={})}
        async def json(self):
            raise AssertionError("denied caller must not reach request parsing")
    view = morph_habitat.MorphHabitatView()
    view.json = lambda body, status_code=200: (status_code, body)
    status, response = asyncio.run(view.post(Request(False), "chronicle-page"))
    assert status == 403 and response["error"]["code"] == "ADMIN_REQUIRED"
