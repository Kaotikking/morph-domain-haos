"""Local SERN + UMP + single-ledger reducer proof, not a live HAOS route."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from test_world_nine_core import aligned, transfer
from serein_gateway_test._vendor.morph_engine import event_reducer
from serein_gateway_test.sern import NINE_CORES, SCHEMA

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)


def event_for(ledger, ticket, *, action="GARDENS_OBJECT"):
    morph = ledger.data["morphs"]["pulse"]
    garden = action == "GARDENS_OBJECT"
    return {"schema": event_reducer.EVENT_SCHEMA, "ticket": ticket,
            "morph_id": "pulse", "generation": morph["generation"],
            "authority": "HAOS", "place": "SEREIN_GARDENS" if garden else "HORIZON",
            "event_class": "WORLD" if garden else "LIFE", "action": action,
            "expected_snapshot_digest": morph["snapshot_digest"],
            "time_source": "HAOS_VERIFIED",
            "payload": {"object_id": "quiet-pool", "participants": ["pulse", "OPERATOR"],
                        "willing": {"pulse": True, "OPERATOR": True}} if garden else {}}


def packet_for(event):
    cores = dict.fromkeys(NINE_CORES, {})
    cores["identity"] = {"morph_id": event["morph_id"], "generation": event["generation"]}
    cores["transport"] = {"ticket": event["ticket"],
                          "event_sha256": transfer.sha256_json(event)}
    return {"schema": SCHEMA, "message_id": event["ticket"],
            "message_type": "EVENT", "morph_id": event["morph_id"],
            "generation": event["generation"], "cores": cores}


def test_gardens_sern_ump_event_commits_once_with_nine_core_receipts():
    ledger = aligned()
    event = event_for(ledger, "md1")
    packet = packet_for(event)
    before = ledger.data["morphs"]["pulse"]["snapshot_digest"]
    card = event_reducer.reduce_local_event(ledger, event, packet, NOW)
    assert card["state"] == "COMMITTED" and card["before_digest"] == before
    assert card["after_digest"] != before and card["ump"]["reason"] == "RECIPROCAL_CONSENT"
    assert len(card["receipts"]) == 9
    assert {r["core"] for r in card["receipts"] if r["required"]} == {"memory", "knowledge"}
    assert ledger.data["morphs"]["pulse"]["snapshot_digest"] == card["after_digest"]
    assert event_reducer.reduce_local_event(ledger, event, packet, NOW) == card


def test_horizon_rest_is_ump_selected_and_keeps_single_ledger():
    ledger = aligned(place="HORIZON")
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["rest_q8"] = 40
    morph["snapshot"]["payload"]["morph_core"]["cloud"]["needs_q8"]["rest"] = 40
    transfer.refresh_snapshot(morph)
    event = event_for(ledger, "md1", action="HORIZON_REST")
    card = event_reducer.reduce_local_event(ledger, event, packet_for(event), NOW)
    assert card["state"] == "COMMITTED"
    assert card["ump"]["activity"] == "REST"
    assert {r["core"] for r in card["receipts"] if r["required"]} == {"memory", "cloud"}
    assert ledger.data["morphs"]["pulse"]["habitat"]["social"]["last_activity"]["expression"] == "AIR_CURRENTS"


def test_core_failure_retains_ticket_but_rolls_back_morph_and_replay():
    ledger = aligned()
    event = event_for(ledger, "md1")
    before = deepcopy(ledger.data["morphs"]["pulse"])
    card = event_reducer.reduce_local_event(ledger, event, packet_for(event), NOW,
                                             reject_core="knowledge")
    assert card["state"] == "REJECTED" and card["reason"] == "CORE_REJECTED"
    assert ledger.data["morphs"]["pulse"] == before
    assert ledger.data["event_reducer"]["next_number"] == 2
    with pytest.raises(transfer.TransferError) as err:
        event_reducer.reduce_local_event(ledger, event, packet_for(event), NOW)
    assert err.value.code == "REPLAY_CONFLICT"


def test_sern_or_ump_mismatch_does_not_change_morph():
    ledger = aligned()
    event = event_for(ledger, "md1")
    before = deepcopy(ledger.data["morphs"]["pulse"])
    packet = packet_for(event)
    packet["cores"]["transport"]["event_sha256"] = "0" * 64
    with pytest.raises(transfer.TransferError) as err:
        event_reducer.reduce_local_event(ledger, event, packet, NOW)
    assert err.value.code == "SERN_EVENT_MISMATCH"
    assert ledger.data["morphs"]["pulse"] == before
    event["payload"]["willing"]["OPERATOR"] = False
    with pytest.raises(transfer.TransferError) as err:
        event_reducer.reduce_local_event(ledger, event, packet_for(event), NOW)
    assert err.value.code == "UMP_NOT_ADMITTED"
    assert ledger.data["morphs"]["pulse"] == before


def test_installed_style_manager_durably_saves_one_ledger_and_restarts():
    import asyncio
    from types import SimpleNamespace
    from serein_gateway_test import morph_transfer

    class CapturingStore:
        def __init__(self):
            self.saved = None
            self.calls = 0

        async def async_save(self, value):
            self.saved = deepcopy(value)
            self.calls += 1

    ledger = aligned()
    event = event_for(ledger, "md1")
    manager = morph_transfer.MorphTransferManager.__new__(morph_transfer.MorphTransferManager)
    manager.hass = SimpleNamespace(data={}, config_entries=SimpleNamespace(async_entries=lambda domain: []))
    manager.store = CapturingStore()
    manager.ledger = ledger
    manager.lock = asyncio.Lock()
    manager.metrics = morph_transfer.MorphRuntimeMetrics()
    body = {"event": event, "sern_packet": packet_for(event)}
    card = asyncio.run(manager.handle_habitat("reduce-event", body))
    assert card["state"] == "COMMITTED" and manager.store.calls == 1
    restarted = morph_transfer.MorphTransferLedger(deepcopy(manager.store.saved))
    assert restarted.data["event_reducer"]["cards"]["md1"] == card
    assert restarted.data["morphs"]["pulse"]["snapshot_digest"] == card["after_digest"]
    assert asyncio.run(manager.handle_habitat("reduce-event", body)) == card
    assert manager.store.calls == 1


def test_installed_style_store_failure_never_acknowledges_or_changes_live_ledger():
    import asyncio
    from types import SimpleNamespace
    from serein_gateway_test import morph_transfer

    class FailingStore:
        async def async_save(self, value):
            raise RuntimeError("injected storage failure")

    ledger = aligned()
    event = event_for(ledger, "md1")
    before = deepcopy(ledger.data)
    manager = morph_transfer.MorphTransferManager.__new__(morph_transfer.MorphTransferManager)
    manager.hass = SimpleNamespace(data={}, config_entries=SimpleNamespace(async_entries=lambda domain: []))
    manager.store = FailingStore()
    manager.ledger = ledger
    manager.lock = asyncio.Lock()
    manager.metrics = morph_transfer.MorphRuntimeMetrics()
    with pytest.raises(RuntimeError, match="injected storage failure"):
        asyncio.run(manager.handle_habitat("reduce-event", {"event": event,
            "sern_packet": packet_for(event)}))
    assert manager.ledger.data == before
