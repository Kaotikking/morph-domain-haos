"""Local single-ledger Morph event reduction proof.

The installed HAOS manager calls this reducer under its existing authority
lock. Existing bounded QOL functions propose a candidate; nine logical Core
reviews validate the slices before the sole ledger is replaced.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from ..morph_sdk.transfer import (MorphTransferLedger, TransferError,
                                  append_nine_core_event, refresh_snapshot,
                                  sha256_json)
from ..morph_sdk.morph_core import validate_morph_core, verify_successor
from ..morph_sdk.ump_world import choose_horizon_activity
from ...sern import SernEnvelopeError, validate_envelope
from .habitat import (HABITAT_SCHEMA, _habitat, care_for_morph,
                      interact_world_object)
from .world_objects import elemental_rest_scene

EVENT_SCHEMA = "serein.morph-domain-event.v1"
CORE_ORDER = ("platform", "root", "memory", "knowledge", "ui", "audio",
              "personality", "modular", "cloud")
REQUIRED = {
    ("LIFE", "HORIZON_REST"): frozenset({"memory", "cloud"}),
    ("WORLD", "GARDENS_OBJECT"): frozenset({"memory", "knowledge"}),
}
FIELDS = {"schema", "ticket", "morph_id", "generation", "authority", "place",
          "event_class", "action", "expected_snapshot_digest", "time_source", "payload"}


def _review(before: dict[str, Any], after: dict[str, Any], required: frozenset[str],
            reject_core: str | None, domain_runtime: Any = None,
            ticket: str = "") -> list[dict[str, Any]]:
    old = validate_morph_core(before)
    new = validate_morph_core(after)
    verify_successor(old, new)
    if domain_runtime is not None:
        from .domain_runtime import DomainDenied
        from .haos_runtime import review_event
        try:
            return review_event(domain_runtime, ticket=ticket, before=old, after=new,
                                required=required, reject_core=reject_core)
        except DomainDenied as err:
            raise TransferError(err.code, str(err)) from err
    receipts = []
    for core in CORE_ORDER:
        if core == reject_core:
            raise TransferError("CORE_REJECTED", f"{core} rejected the proposed event")
        changed = old[core] != new[core]
        if core in required and not changed:
            raise TransferError("REQUIRED_CORE_SILENT", f"{core} did not process the event")
        receipts.append({"core": core, "required": core in required,
                         "disposition": "ADMITTED" if changed else "PROCESSED_NO_CHANGE",
                         "before_sha256": sha256_json(old[core]),
                         "after_sha256": sha256_json(new[core])})
    return receipts


def reduce_local_event(ledger: MorphTransferLedger, event: dict[str, Any],
                       sern_packet: dict[str, Any], now: datetime,
                       *, reject_core: str | None = None,
                       domain_runtime: Any = None) -> dict[str, Any]:
    """Use one numbered ticket and commit all nine-Core effects or none."""
    if not isinstance(event, dict) or set(event) != FIELDS or event.get("schema") != EVENT_SCHEMA:
        raise TransferError("INVALID_EVENT", "event card shape is not admitted")
    if type(event["generation"]) is not int or not isinstance(event["payload"], dict):
        raise TransferError("INVALID_EVENT", "event generation or payload is invalid")
    try:
        envelope = validate_envelope(sern_packet)
    except SernEnvelopeError as err:
        raise TransferError(err.code, str(err)) from err
    transport = envelope.cores["transport"]
    if (envelope.message_type != "EVENT" or envelope.message_id != event["ticket"]
            or envelope.morph_id != event["morph_id"] or envelope.generation != event["generation"]
            or not isinstance(transport, dict)
            or transport != {"ticket": event["ticket"], "event_sha256": sha256_json(event)}):
        raise TransferError("SERN_EVENT_MISMATCH", "SERN control packet does not bind the event")
    key = (event["event_class"], event["action"])
    required = REQUIRED.get(key)
    if required is None:
        raise TransferError("INVALID_EVENT", "event class/action is not admitted")
    if event["authority"] != "HAOS" or event["time_source"] != "HAOS_VERIFIED":
        raise TransferError("AUTHORITY_CONFLICT", "HAOS reduction needs HAOS custody and time")
    state = ledger.data.setdefault("event_reducer", {"next_number": 1, "cards": {}})
    cards = state["cards"]
    ticket = event["ticket"]
    fingerprint = sha256_json(event)
    if ticket in cards:
        previous = cards[ticket]
        if previous["request_sha256"] != fingerprint:
            raise TransferError("REPLAY_CONFLICT", "ticket was reused with changed content")
        if previous["state"] != "COMMITTED":
            raise TransferError("REPLAY_CONFLICT", "failed ticket cannot be reused")
        return deepcopy(previous)
    if ticket != f"md{state['next_number']}":
        raise TransferError("TICKET_OUT_OF_ORDER", "next local ticket was not used")
    morph = ledger.data["morphs"].get(event["morph_id"])
    if morph is None or morph.get("authority") != "HAOS" or morph["generation"] != event["generation"]:
        raise TransferError("AUTHORITY_CONFLICT", "Morph custody/generation differs")
    if morph["snapshot_digest"] != event["expected_snapshot_digest"]:
        raise TransferError("STALE_PREDECESSOR", "event predecessor digest differs")
    if _habitat(morph, now)["place"] != event["place"]:
        raise TransferError("PLACE_CONFLICT", "event location differs from current Morph")
    # UMP weighs context before any Core proposal. It cannot grant custody.
    if key == ("LIFE", "HORIZON_REST"):
        if event["place"] != "HORIZON" or event["payload"]:
            raise TransferError("INVALID_EVENT", "Horizon rest has no client payload")
        life = morph["snapshot"]["payload"]
        ump = choose_horizon_activity({"morph_id": morph["morph_id"], "authority": "HAOS",
            "phase": morph.get("habitat", {}).get("phase", "JUVENILE"), "place": "HORIZON",
            "needs": {"food": life["food_q8"], "water": life["water_q8"],
                      "rest": life["rest_q8"], "play": life["play_q8"]}})
        if ump["decision"] != "ENCOUNTER" or ump["activity"] != "REST":
            raise TransferError("UMP_NOT_ADMITTED", "bounded needs do not select rest")
    else:
        payload = event["payload"]
        if (event["place"] != "SEREIN_GARDENS"
                or set(payload) != {"object_id", "participants", "willing"}
                or payload["participants"] != [event["morph_id"], "OPERATOR"]
                or payload["willing"] != {event["morph_id"]: True, "OPERATOR": True}):
            raise TransferError("UMP_NOT_ADMITTED", "Gardens requires reciprocal consent")
        ump = {"decision": "ENCOUNTER", "activity": "GARDENS_OBJECT",
               "reason": "RECIPROCAL_CONSENT"}
    candidate = MorphTransferLedger(deepcopy(ledger.data))
    before_morph = morph
    target = candidate.data["morphs"][event["morph_id"]]
    if key == ("LIFE", "HORIZON_REST"):
        scene = elemental_rest_scene(target["snapshot"]["payload"]["morph_core"])
        care_for_morph(candidate, {"schema": HABITAT_SCHEMA, "event_id": ticket,
                                   "morph_id": event["morph_id"], "action": "REST"}, now)
        target = candidate.data["morphs"][event["morph_id"]]
        append_nine_core_event(target, {"event_id": ticket, "kind": "horizon-rest",
            "observed_at": now.astimezone(UTC).isoformat(), "source": "haos-morph-engine",
            "place": "HORIZON", "frame": "haos-horizon", "evidence_digest": fingerprint})
        target["habitat"]["social"]["last_activity"] = {
            "at": now.astimezone(UTC).isoformat(), "kind": "REST", "partner": None,
            "place": "HORIZON", "expression": scene}
        refresh_snapshot(target)
    else:
        payload = event["payload"]
        outcome = interact_world_object(candidate, event_id=ticket, place="SEREIN_GARDENS",
            object_id=payload["object_id"], participants=tuple(payload["participants"]),
            willing=payload["willing"], now=now)
        if outcome["result"] != "ACCEPTED" or event["morph_id"] not in outcome.get("credited", []):
            raise TransferError("WORLD_NOT_ACCEPTED", "object interaction was not accepted")
        target = candidate.data["morphs"][event["morph_id"]]
    try:
        receipts = _review(before_morph["snapshot"]["payload"]["morph_core"],
                           target["snapshot"]["payload"]["morph_core"], required, reject_core,
                           domain_runtime, ticket)
    except TransferError as err:
        card = {"ticket": ticket, "state": "REJECTED", "request_sha256": fingerprint,
                "reason": err.code, "morph_id": event["morph_id"], "custody_changed": False}
        cards[ticket] = card
        state["next_number"] += 1
        return deepcopy(card)
    card = {"ticket": ticket, "state": "COMMITTED", "request_sha256": fingerprint,
            "morph_id": event["morph_id"], "event_class": event["event_class"],
            "action": event["action"], "place": event["place"],
            "ump": ump, "sern_digest": envelope.digest,
            "before_digest": before_morph["snapshot_digest"],
            "after_digest": target["snapshot_digest"], "receipts": receipts,
            "custody_changed": False}
    candidate.data["event_reducer"]["cards"][ticket] = card
    candidate.data["event_reducer"]["next_number"] += 1
    ledger.data = candidate.data
    return deepcopy(card)
