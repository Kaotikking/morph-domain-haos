"""HAOS-hosted Morph habitat layered on the transfer authority ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import uuid
from typing import Any


from ..morph_sdk.transfer import (
    MAX_SNAPSHOT_BYTES,
    MorphTransferLedger,
    TransferError,
    _exact,
    canonical_json,
    refresh_snapshot,
    append_nine_core_event,
)
from ..morph_sdk.morph_core import (MAX_CHRONICLE_EVENTS, MORPH_NINE_CORE_SCHEMA,
                                   validate_morph_core, verify_successor)
from ..morph_sdk.gen1_origin import ORIGIN_SCHEMA, hatch_starter
from ..morph_sdk.dna_v1 import SOCIAL_SCHEMA, SOCIAL_STATES
from ..morph_sdk.ump_world import decide_pair, choose_horizon_activity
from .garden_games import GardenGameError, start_game, move as game_move, public_state
from .world_objects import (HORIZON_ACTIVITY_OBJECTS, OBJECTS, WorldObjectError, affinity_from_nine_core,
                            compact_history,
                            elemental_rest_scene,
                            interact as object_interact, new_history)
from ..morph_sdk.presentation import (
    PresentationError, bind_presentation, change_presentation, neutral_presentation,
)
from .living_truth import FiveTierAxis, LivingTruthError

HABITAT_SCHEMA = "serein.morph-habitat.v1"
HABITAT_ENGINE = "haos-morph-habitat.v1"
HABITAT_DATA_KEY = "morph_domain_habitat_registered"
PLACES = {"VOID", "NURSERY", "SEREIN_GARDENS", "HORIZON", "CODE_HAVEN"}
ACTIVE_PLACES = {"NURSERY", "SEREIN_GARDENS", "HORIZON"}
CARE_ACTIONS = {"FEED", "WATER", "PLAY", "REST", "EXPLORE"}
VOID_LOCK = timedelta(hours=24)
HISTORY_CAPACITY = 128
PORTABLE_CHRONICLE_EVENT_LIMIT = 128
PORTABLE_SNAPSHOT_RESERVE_BYTES = 32768
TICK_INTERVAL = timedelta(seconds=30)
NURSERY_GRADUATION = timedelta(hours=72)
GAME_REWARD_INTERVAL = timedelta(hours=8)
SOCIAL_WINDOW_SECONDS = 2 * 60 * 60
HORIZON_WINDOW_SECONDS = 5 * 60
SOCIAL_NEED_FLOOR = 64
REFLEX_SCHEMA = "serein.morph-reflex.v1"
CARE_FIELDS = ("food_q8", "water_q8", "play_q8", "rest_q8", "attention_q8")
CARE_LEVEL_CEILINGS = (51, 102, 153, 204, 255)


def care_level(value: int) -> int:
    """Project an existing q8 need onto the public, founder-safe 1..5 scale."""
    return min(5, 1 + max(0, min(255, int(value))) * 5 // 256)


def _raise_care(payload: dict[str, Any], field: str, steps: int) -> tuple[int, int]:
    before = care_level(payload[field])
    after = min(5, before + steps)
    payload[field] = max(int(payload[field]), CARE_LEVEL_CEILINGS[after - 1])
    return before, after
# Deployment-specific frame bindings are configured by each installation.
FRAME_ALIASES: dict[str, str] = {}
ELEMENTS = ("FIRE", "WATER", "AIR", "EARTH")
ENVIRONMENT_SCHEMA = "serein.morph-environment.v1"
WEATHER_WATER_STATES = {"rainy", "pouring", "lightning-rainy", "snowy-rainy"}
ENVIRONMENT_ENTITIES = {
    "sun": "sun.sun",
}


def _iso(now: datetime) -> str:
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sync_morph_core_state(morph: dict[str, Any], *, sync_place: bool = False) -> None:
    """Keep v3's shared outer state and Morph Core view identical."""
    snapshot = morph["snapshot"]
    if snapshot["schema"] != "serein.morph-life-state.v3":
        return
    payload = snapshot["payload"]
    core = payload["morph_core"]
    if core.get("schema") == MORPH_NINE_CORE_SCHEMA:
        state = core["cloud"]
        personality = core["personality"]
    else:
        state = core["state"]
        personality = None
    state["needs_q8"] = {
        "attention": payload["attention_q8"],
        "energy": 255 - payload["fatigue_q8"],
        "food": payload["food_q8"],
        "play": payload["play_q8"],
        "rest": payload["rest_q8"],
        "water": payload["water_q8"],
    }
    if personality is None:
        state["mood"] = payload["behavior"].lower()
    else:
        personality["mood"] = payload["behavior"].lower()
    state["authority"] = "HAOS_ACTIVE"
    if sync_place:
        place = morph["habitat"]["place"]
        state["place"] = place
        state["active_frame"] = f"haos-{place.lower().replace('_', '-')}"


def _habitat(morph: dict[str, Any], now: datetime) -> dict[str, Any]:
    habitat = morph.get("habitat")
    if not isinstance(habitat, dict):
        core = morph.get("snapshot", {}).get("payload", {}).get("morph_core", {})
        initial_place = core.get("cloud", {}).get("place", "HORIZON")
        habitat = {
            "schema": HABITAT_SCHEMA,
            "engine_version": HABITAT_ENGINE,
            "place": initial_place,
            "entered_at": _iso(now),
            "last_tick_at": _iso(now),
            "void_locked_until": None,
            "nursery_elapsed_seconds": 0,
            "history": [],
            "event_ids": [],
            "environment": {
                "schema": ENVIRONMENT_SCHEMA,
                "expression_q8": {element: 0 for element in ELEMENTS},
                "exposure_seconds": {element: 0 for element in ELEMENTS},
                "dominant": None,
                "last_sample": None,
            },
            "founder_axes": {},
            "social": {"edges": {}, "event_ids": [], "last_activity": None},
            "games": {"sessions": {}, "last_reward_window": None},
            "reflex": {
                "schema": REFLEX_SCHEMA,
                "last_care_window": None,
                "graduated_at": None,
                "notice_ids": [],
            },
        }
        morph["habitat"] = habitat
    habitat.setdefault("environment", {
        "schema": ENVIRONMENT_SCHEMA,
        "expression_q8": {element: 0 for element in ELEMENTS},
        "exposure_seconds": {element: 0 for element in ELEMENTS},
        "dominant": None,
        "last_sample": None,
    })
    habitat.setdefault("presentation", neutral_presentation(morph["morph_id"]))
    habitat.setdefault("invalidated_event_ids", [])
    habitat.setdefault("founder_axes", {})
    habitat.setdefault("social", {"edges": {}, "event_ids": [], "last_activity": None})
    habitat.setdefault("games", {"sessions": {}, "last_reward_window": None})
    habitat.setdefault("reflex", {
        "schema": REFLEX_SCHEMA,
        "last_care_window": None,
        "graduated_at": None,
        "notice_ids": [],
    })
    return habitat


def register_founder_axis(
    ledger: MorphTransferLedger, request: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Register a schema-stable founder capability at source tier 0 in Code Haven."""
    _exact(
        request,
        {"schema", "event_id", "morph_id", "axis_id", "source_definition"},
        "founder axis request",
    )
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "founder axis request schema is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    if habitat["place"] != "CODE_HAVEN":
        raise TransferError("CODE_HAVEN_REQUIRED", "founder axes may be registered only in Code Haven")
    axis_id = str(request["axis_id"])
    event_id = str(request["event_id"])
    previous = next((row for row in habitat["history"] if row.get("event_id") == event_id), None)
    if previous is not None:
        if (previous.get("type") != "FOUNDER_AXIS_REGISTERED"
                or previous.get("axis_id") != axis_id
                or previous.get("source_definition") != request["source_definition"]):
            raise TransferError("REPLAY_CONFLICT", "founder axis event id payload changed")
        return deepcopy(previous["result"])
    try:
        candidate = FiveTierAxis(
            axis_id=axis_id,
            founder_line=str(morph["founder_id"]),
            source_definition=deepcopy(request["source_definition"]),
        ).machine_record()
    except LivingTruthError as err:
        raise TransferError(err.code, str(err)) from err
    existing = habitat["founder_axes"].get(axis_id)
    if existing is not None and existing != candidate:
        raise TransferError("FOUNDER_AXIS_CONFLICT", "founder axis source cannot be rewritten")
    habitat["founder_axes"].setdefault(axis_id, candidate)
    result = deepcopy(habitat["founder_axes"][axis_id])
    _record(habitat, {
        "event_id": event_id, "at": _iso(now),
        "type": "FOUNDER_AXIS_REGISTERED", "axis_id": axis_id, "source_tier": 0,
        "source_definition": deepcopy(request["source_definition"]), "result": result,
    })
    return result


def advance_founder_axis(
    ledger: MorphTransferLedger, request: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Activate 0→1 or move one lived tier while preserving founder provenance."""
    _exact(request, {"schema", "event_id", "morph_id", "axis_id", "delta"}, "axis step request")
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "axis step schema is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    axis_id = str(request["axis_id"])
    event_id = str(request["event_id"])
    previous = next((row for row in habitat["history"] if row.get("event_id") == event_id), None)
    if previous is not None:
        if (previous.get("type") != "FOUNDER_AXIS_STEP"
                or previous.get("axis_id") != axis_id
                or previous.get("delta") != request["delta"]):
            raise TransferError("REPLAY_CONFLICT", "founder axis step event id payload changed")
        return deepcopy(previous["result"])
    record = habitat["founder_axes"].get(axis_id)
    if record is None:
        raise TransferError("FOUNDER_AXIS_NOT_FOUND", "founder axis is not registered")
    try:
        axis = FiveTierAxis(
            axis_id=record["axis_id"], founder_line=record["founder_line"],
            source_definition=deepcopy(record["source_definition"]),
            current_tier=record["current_tier"],
        )
        axis.transition(request["delta"])
    except LivingTruthError as err:
        raise TransferError(err.code, str(err)) from err
    habitat["founder_axes"][axis_id] = axis.machine_record()
    result = deepcopy(habitat["founder_axes"][axis_id])
    _record(habitat, {
        "event_id": event_id, "at": _iso(now), "type": "FOUNDER_AXIS_STEP",
        "axis_id": axis_id, "delta": request["delta"], "current_tier": axis.current_tier,
        "result": result,
    })
    return result


def _number(state: Any) -> float | None:
    try:
        value = float(state)
        return value if value == value else None
    except (TypeError, ValueError):
        return None


def read_environment(hass: Any, now: datetime) -> dict[str, Any]:
    """Read only admitted HAOS entities and retain their exact provenance."""
    rows = {name: hass.states.get(entity_id) for name, entity_id in ENVIRONMENT_ENTITIES.items()}
    motion = sorted(
        state.entity_id for state in hass.states.async_all("binary_sensor")
        if state.state == "on" and any(word in state.entity_id for word in ("motion", "occupancy", "presence"))
    )
    return {
        "observed_at": _iso(now),
        "weather": rows["weather"].state if rows.get("weather") else None,
        "sun": rows["sun"].state if rows.get("sun") else None,
        "temperature_f": _number(rows["temperature"].state if rows.get("temperature") else None),
        "humidity_percent": _number(rows["humidity"].state if rows.get("humidity") else None),
        "wind_mph": _number(rows["wind"].state if rows.get("wind") else None),
        "active_motion_entities": motion,
        "sources": {name: entity_id for name, entity_id in ENVIRONMENT_ENTITIES.items()},
    }


def elemental_influence(sample: dict[str, Any]) -> dict[str, int]:
    """Convert weather truth into small bounded primitive influences."""
    temperature = sample.get("temperature_f")
    humidity = sample.get("humidity_percent")
    wind = sample.get("wind_mph")
    motion = bool(sample.get("active_motion_entities"))
    result = {element: 0 for element in ELEMENTS}
    result["FIRE"] = int(temperature is not None and temperature >= 85) + int(sample.get("sun") == "above_horizon") + int(motion)
    result["WATER"] = int(humidity is not None and humidity >= 50) + 2 * int(sample.get("weather") in WEATHER_WATER_STATES)
    result["AIR"] = int(wind is not None and wind >= 5) + int(wind is not None and wind >= 15) + int(motion)
    result["EARTH"] = int(not motion) + int(wind is not None and wind < 5) + int(sample.get("weather") not in WEATHER_WATER_STATES)
    return result


def _record(habitat: dict[str, Any], event: dict[str, Any]) -> None:
    habitat["history"].append(deepcopy(event))
    del habitat["history"][:-HISTORY_CAPACITY]


def _append_world_chronicle(morph: dict[str, Any], event: dict[str, Any], now: datetime) -> None:
    """Keep portable life bounded while the one HAOS ledger retains later events."""
    _habitat(morph, now)
    append_nine_core_event(morph, event)


def _require_haos(morph: dict[str, Any]) -> None:
    if morph.get("authority") != "HAOS":
        raise TransferError("AUTHORITY_CONFLICT", "HAOS is not active authority")


def advance_morph(morph: dict[str, Any], now: datetime, environment: dict[str, Any] | None = None) -> bool:
    """Advance only HAOS-owned life; stasis and diagnostics never tick."""
    if morph.get("authority") != "HAOS":
        return False
    created = "habitat" not in morph
    habitat = _habitat(morph, now)
    if habitat["place"] not in ACTIVE_PLACES:
        habitat["last_tick_at"] = _iso(now)
        return created
    payload = morph["snapshot"]["payload"]
    core = payload.get("morph_core")
    if isinstance(core, dict) and core.get("schema") == MORPH_NINE_CORE_SCHEMA:
        world_history = core.get("knowledge", {}).get("learned", {}).get("world_objects")
        if isinstance(world_history, dict):
            compact_history(world_history)
    saved = int(payload["saved_epoch_seconds"])
    current = int(now.timestamp())
    elapsed = min(240, max(0, current - saved))
    steps = elapsed // 30
    if steps <= 0:
        return created
    for field in CARE_FIELDS:
        payload[field] = max(0, int(payload[field]) - steps)
    memories = []
    for memory in payload["memories"]:
        age = int(memory["age_ms"]) + steps * 30_000
        if age <= 120_000:
            memories.append({**memory, "age_ms": age})
    payload["memories"] = memories
    payload["saved_epoch_seconds"] = current
    if habitat["place"] == "NURSERY":
        habitat["nursery_elapsed_seconds"] += steps * 30
    if environment is not None:
        influence = elemental_influence(environment)
        elemental = habitat["environment"]
        for element in ELEMENTS:
            elemental["expression_q8"][element] = min(255, int(elemental["expression_q8"][element]) + influence[element] * steps)
            if influence[element]:
                elemental["exposure_seconds"][element] += steps * 30
        elemental["dominant"] = max(ELEMENTS, key=lambda item: (elemental["expression_q8"][item], -ELEMENTS.index(item)))
        elemental["last_sample"] = deepcopy(environment)
    habitat["last_tick_at"] = _iso(now)
    _sync_morph_core_state(morph)
    refresh_snapshot(morph)
    return True


def run_automatic_reflexes(
    ledger: MorphTransferLedger, now: datetime
) -> tuple[bool, list[dict[str, Any]]]:
    """Apply only proven, deterministic MorphDomain maintenance reflexes."""
    changed = False
    notices: list[dict[str, Any]] = []
    for morph_id in sorted(ledger.data["morphs"]):
        morph = ledger.data["morphs"][morph_id]
        if morph.get("authority") != "HAOS":
            continue
        habitat = _habitat(morph, now)
        reflex = habitat["reflex"]

        # Only the untouched result of the inbound Code Haven alignment may
        # leave automatically. A later repair or an Operator placement changes
        # the digest, so genuine diagnostic holds remain in Code Haven.
        if habitat["place"] == "CODE_HAVEN":
            for operation_id, operation in ledger.data["operations"].items():
                if (operation.get("operation_kind") != "AUTO_NINE_CORE_ALIGNMENT"
                        or operation.get("state") != "ALIGNED_CODE_HAVEN"
                        or operation.get("morph_id") != morph_id
                        or operation.get("generation") != morph["generation"]
                        or operation.get("snapshot_digest") != morph["snapshot_digest"]
                        or operation.get("discharged_at") is not None):
                    continue
                inbound = ledger.data["operations"].get(operation.get("transfer_id"), {})
                if inbound.get("state") != "ACTIVE_HAOS":
                    continue
                event_id = f"auto-discharge:{operation_id}"
                place_morph(ledger, {
                    "schema": HABITAT_SCHEMA, "event_id": event_id,
                    "morph_id": morph_id, "place": "HORIZON",
                }, now)
                operation["discharged_at"] = _iso(now)
                operation["discharge_event_id"] = event_id
                changed = True
                break

        # A sealed egg stays in Nursery until the canonical hatch transaction.
        # The 72-hour clock triggers that transaction before Horizon graduation.
        core = morph.get("snapshot", {}).get("payload", {}).get("morph_core", {})
        embodiment = core.get("platform", {}).get("embodiment", {})
        if not embodiment:
            embodiment = core.get("embodiment", {})
        sealed_egg = embodiment.get("body_class") == "morph-egg"
        starter = str(morph.get("founder_id", "")) in {"L1-01", "L1-02", "L1-03", "L1-04"}
        elapsed_ready = int(habitat["nursery_elapsed_seconds"]) >= int(NURSERY_GRADUATION.total_seconds())
        if habitat["place"] == "NURSERY" and starter and sealed_egg and elapsed_ready:
            hatch_id = f"auto-hatch:{morph_id}"
            hatch_starter(ledger, {
                "schema": ORIGIN_SCHEMA, "event_id": hatch_id, "morph_id": morph_id,
            }, now)
            notices.append({"id": hatch_id, "kind": "HATCHED", "morph_id": morph_id})
            changed = True
            sealed_egg = False

        if (habitat["place"] == "NURSERY" and not sealed_egg and elapsed_ready):
            event_id = f"auto-graduate:{morph_id}:{habitat['entered_at']}"
            if event_id not in habitat["event_ids"]:
                previous = habitat["place"]
                habitat["place"] = "HORIZON"
                habitat["entered_at"] = _iso(now)
                habitat["last_tick_at"] = _iso(now)
                habitat["void_locked_until"] = None
                habitat["event_ids"].append(event_id)
                del habitat["event_ids"][:-HISTORY_CAPACITY]
                reflex["graduated_at"] = _iso(now)
                _record(habitat, {
                    "event_id": event_id, "at": _iso(now), "type": "AUTO_GRADUATION",
                    "from": previous, "to": "HORIZON",
                })
                _sync_morph_core_state(morph, sync_place=True)
                refresh_snapshot(morph)
                notices.append({"id": event_id, "kind": "GRADUATED", "morph_id": morph_id})
                changed = True

        if habitat["place"] == "CODE_HAVEN":
            notice_id = f"code-haven:{morph_id}:{habitat['entered_at']}"
            if notice_id not in reflex["notice_ids"]:
                reflex["notice_ids"].append(notice_id)
                del reflex["notice_ids"][:-16]
                notices.append({"id": notice_id, "kind": "INTERVENTION", "morph_id": morph_id})
                changed = True
    return changed, notices


def _social_subject(morph: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    """Only a live, embodied HAOS Morph may take part in world activity."""
    if morph.get("authority") != "HAOS" or morph.get("engine_state") != "ACTIVE_DEFERRED_TICK":
        return None
    habitat = _habitat(morph, now)
    if habitat["place"] not in {"HORIZON", "SEREIN_GARDENS"}:
        return None
    payload = morph.get("snapshot", {}).get("payload", {})
    core = payload.get("morph_core", {})
    if not isinstance(core, dict):
        return None
    embodiment = core.get("platform", {}).get("embodiment", core.get("embodiment", {}))
    if not isinstance(embodiment, dict) or not embodiment or embodiment.get("body_class") == "morph-egg":
        return None
    needs = {key: payload.get(f"{key}_q8") for key in ("food", "water", "rest", "play")}
    if any(type(value) is not int or not 0 <= value <= 255 for value in needs.values()):
        return None
    return {"morph_id": morph["morph_id"], "authority": "HAOS", "place": habitat["place"],
            "phase": "JUVENILE", "needs": needs}


def _edge(habitat: dict[str, Any], subject: str, partner: str) -> dict[str, Any]:
    previous = habitat["social"]["edges"].get(partner)
    if previous is None:
        return {"schema": SOCIAL_SCHEMA, "subject_id": subject, "object_id": partner,
                "state": "UNFAMILIAR", "evidence_count": 0}
    return deepcopy(previous)


def _kinship_score(first: dict[str, Any], second: dict[str, Any]) -> int:
    """Prefer known family for encounters; kinship never creates social evidence."""
    def identity(morph: dict[str, Any]) -> dict[str, Any]:
        core = morph.get("snapshot", {}).get("payload", {}).get("morph_core", {})
        return core.get("identity", {}) if isinstance(core, dict) else {}

    a, b = identity(first), identity(second)
    a_parents, b_parents = a.get("parent_ids"), b.get("parent_ids")
    if not isinstance(a_parents, list) or not isinstance(b_parents, list):
        return 0
    if a.get("morph_id") in b_parents or b.get("morph_id") in a_parents:
        return 3
    if set(a_parents) & set(b_parents):
        return 2
    if a.get("founder_lineage") and a.get("founder_lineage") == b.get("founder_lineage"):
        return 1
    return 0


def run_social_reflexes(ledger: MorphTransferLedger, now: datetime) -> bool:
    """Make bounded, reciprocal world encounters once per pair/window.

    Pairing creates a real joint engine event; co-location by itself writes nothing.
    Care and object history may update the portable snapshot, but DNA, custody,
    and breeding authority do not change here.
    """
    window = int(now.timestamp()) // SOCIAL_WINDOW_SECONDS
    horizon_window = int(now.timestamp()) // HORIZON_WINDOW_SECONDS
    candidates: dict[str, dict[str, Any]] = {}
    for morph_id, morph in ledger.data["morphs"].items():
        subject = _social_subject(morph, now)
        if subject is not None:
            candidates[morph_id] = subject
    # Rotate ordering by window so one fixed alphabetical partner cannot monopolize play.
    from hashlib import sha256
    ids = sorted(candidates, key=lambda item: sha256(f"{window}:{item}".encode()).digest())
    changed = False
    paired: set[str] = set()
    for first_id in ids:
        if first_id in paired:
            continue
        first = candidates[first_id]
        social_prefix = f"world-social:{first['place']}:{window}:"
        first_habitat = _habitat(ledger.data["morphs"][first_id], now)
        if any(event.startswith(social_prefix) for event in first_habitat["social"]["event_ids"]):
            last = first_habitat["social"].get("last_activity") or {}
            if (last.get("kind") == "SHARED_PLAY" and
                    int(datetime.fromisoformat(last["at"].replace("Z", "+00:00")).timestamp())
                    // HORIZON_WINDOW_SECONDS == horizon_window):
                paired.add(first_id)
            continue
        if min(first["needs"].values()) < SOCIAL_NEED_FLOOR:
            continue
        eligible = [item for item in ids if item not in paired and item != first_id
                    and candidates[item]["place"] == first["place"]
                    and min(candidates[item]["needs"].values()) >= SOCIAL_NEED_FLOOR
                    and not any(event.startswith(social_prefix) for event in
                                _habitat(ledger.data["morphs"][item], now)["social"]["event_ids"])]
        # Every third window uses rotated order alone so family preference does
        # not permanently exclude unrelated Morphs from public-space meetings.
        partner_id = (max(eligible, key=lambda item: _kinship_score(
            ledger.data["morphs"][first_id], ledger.data["morphs"][item]))
            if eligible and window % 3 else eligible[0] if eligible else None)
        if partner_id is None:
            continue
        second = candidates[partner_id]
        first_morph = ledger.data["morphs"][first_id]
        second_morph = ledger.data["morphs"][partner_id]
        first_habitat = _habitat(first_morph, now)
        second_habitat = _habitat(second_morph, now)
        event_id = f"world-social:{first['place']}:{window}:{':'.join(sorted((first_id, partner_id)))}"
        if event_id in first_habitat["social"]["event_ids"] or event_id in second_habitat["social"]["event_ids"]:
            continue
        a_edge = _edge(first_habitat, first_id, partner_id)
        b_edge = _edge(second_habitat, partner_id, first_id)
        decision = decide_pair(first, second, a_edge, b_edge, reciprocal_event=True)
        if decision["decision"] not in {"ENCOUNTER", "GARDENS_READY"}:
            continue
        if first["place"] == "SEREIN_GARDENS" and decision["decision"] != "GARDENS_READY":
            continue
        # A reciprocal event must have a real effect on both lives. The outer
        # manager persists the cloned ledger atomically after this whole tick.
        for subject_id in (first_id, partner_id):
            apply_environment_interaction(
                ledger, morph_id=subject_id, event_id=f"{event_id}:play:{subject_id}",
                activity="PLAY", now=now)
        for subject_id, partner, habitat, edge in (
            (first_id, partner_id, first_habitat, a_edge),
            (partner_id, first_id, second_habitat, b_edge),
        ):
            count = edge["evidence_count"] + 1
            cap = 2 if first["place"] == "HORIZON" else 4
            tier = min(cap, 1 if count < 3 else 2 if count < 6 else 3 if count < 10 else 4)
            edge["evidence_count"] = count
            edge["state"] = SOCIAL_STATES[tier]
            habitat["social"]["edges"][partner] = edge
            habitat["social"]["event_ids"].append(event_id)
            del habitat["social"]["event_ids"][:-HISTORY_CAPACITY]
            habitat["social"]["last_activity"] = {
                "at": _iso(now), "kind": "SHARED_PLAY", "partner": partner,
                "place": first["place"], "ump": decision["decision"],
            }
            _record(habitat, {"event_id": event_id, "at": _iso(now),
                              "type": "SOCIAL_INTERACTION", "partner": partner,
                              "place": first["place"], "ump": decision["decision"]})
        cores = [ledger.data["morphs"][identity]["snapshot"]["payload"].get("morph_core", {})
                 for identity in (first_id, partner_id)]
        if all(core.get("schema") == MORPH_NINE_CORE_SCHEMA for core in cores):
            a_affinity = affinity_from_nine_core(cores[0], first["place"])
            b_affinity = affinity_from_nine_core(cores[1], first["place"])
            objects = OBJECTS[first["place"]]
            object_id = max(objects, key=lambda item: (
                min(a_affinity[item], b_affinity[item]),
                a_affinity[item] + b_affinity[item], -objects.index(item)))
            object_event_id = "world-object:" + sha256(event_id.encode()).hexdigest()[:24]
            interact_world_object(ledger, event_id=object_event_id,
                                  place=first["place"], object_id=object_id,
                                  participants=(first_id, partner_id),
                                  willing={first_id: True, partner_id: True}, now=now)
        paired.update((first_id, partner_id))
        changed = True
    # Alone in Horizon, a Morph can still have a bounded, visible activity.
    for morph_id in ids:
        if morph_id in paired or candidates[morph_id]["place"] != "HORIZON":
            continue
        habitat = _habitat(ledger.data["morphs"][morph_id], now)
        event_id = f"world-solo:{morph_id}:{horizon_window}"
        if event_id in habitat["social"]["event_ids"]:
            continue
        decision = choose_horizon_activity(candidates[morph_id], window=horizon_window)
        if decision["decision"] != "ENCOUNTER":
            continue
        choices = HORIZON_ACTIVITY_OBJECTS[decision["activity"]]
        core = ledger.data["morphs"][morph_id]["snapshot"]["payload"].get("morph_core", {})
        if core.get("schema") == MORPH_NINE_CORE_SCHEMA:
            affinities = affinity_from_nine_core(core, "HORIZON")
            object_id = max(choices, key=lambda item: (affinities[item], -choices.index(item)))
        else:
            object_id = choices[0]
        expression = None
        if decision["activity"] == "REST":
            try:
                expression = elemental_rest_scene(
                    ledger.data["morphs"][morph_id]["snapshot"]["payload"]["morph_core"])
            except (KeyError, WorldObjectError):
                # Unknown element is not permission to invent a rest scene.
                continue
        apply_environment_interaction(
            ledger, morph_id=morph_id, event_id=f"{event_id}:environment",
            activity=decision["activity"], now=now)
        habitat["social"]["event_ids"].append(event_id)
        del habitat["social"]["event_ids"][:-HISTORY_CAPACITY]
        habitat["social"]["last_activity"] = {"at": _iso(now), "kind": decision["activity"],
                                                 "partner": None, "place": "HORIZON",
                                                 "object_id": object_id, "expression": expression}
        _record(habitat, {"event_id": event_id, "at": _iso(now), "type": "SOLO_ACTIVITY",
                          "activity": decision["activity"], "object_id": object_id,
                          "expression": expression})
        core = ledger.data["morphs"][morph_id]["snapshot"]["payload"].get("morph_core", {})
        if core.get("schema") == MORPH_NINE_CORE_SCHEMA:
            object_event_id = "world-object:" + sha256(event_id.encode()).hexdigest()[:24]
            interact_world_object(ledger, event_id=object_event_id,
                                  place="HORIZON", object_id=object_id,
                                  participants=(morph_id,), willing={morph_id: True}, now=now)
        changed = True
    return changed


def interact_world_object(ledger: MorphTransferLedger, *, event_id: str, place: str,
                          object_id: str, participants: tuple[str, ...],
                          willing: dict[str, bool], now: datetime) -> dict[str, Any]:
    """Local nine-Core object transaction; no public API route is admitted yet."""
    if place not in OBJECTS or object_id not in OBJECTS[place]:
        raise TransferError("INVALID_OBJECT", "object is not in the named place")
    morph_ids = [identity for identity in participants if identity != "OPERATOR"]
    candidates: dict[str, dict[str, Any]] = {}
    histories: dict[str, dict[str, Any]] = {}
    for morph_id in morph_ids:
        morph = ledger.data["morphs"].get(morph_id)
        if morph is None or _social_subject(morph, now) is None or _habitat(morph, now)["place"] != place:
            raise TransferError("WORLD_SUBJECT_REQUIRED", "living Morph in named place required")
        core = morph["snapshot"]["payload"].get("morph_core")
        if not isinstance(core, dict) or core.get("schema") != MORPH_NINE_CORE_SCHEMA:
            raise TransferError("NINE_CORE_REQUIRED", "Code Haven alignment required before world-object play")
        try:
            validate_morph_core(core)
            affinity_from_nine_core(core, place)
        except (WorldObjectError, ValueError) as err:
            raise TransferError("INVALID_WORLD_SOURCE", str(err)) from err
        candidates[morph_id] = deepcopy(morph)
        histories[morph_id] = deepcopy(core["knowledge"]["learned"].get("world_objects", new_history(morph_id)))
    try:
        outcome = object_interact(histories, event_id=event_id, place=place,
                                  object_id=object_id, participants=participants, willing=willing)
    except WorldObjectError as err:
        raise TransferError("INVALID_WORLD_EVENT", str(err)) from err
    if outcome["result"] != "ACCEPTED":
        return outcome
    evidence = {"event_id": event_id, "place": place, "object_id": object_id,
                "participants": list(participants)}
    evidence_digest = sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    for morph_id in morph_ids:
        candidate = candidates[morph_id]
        old_core = ledger.data["morphs"][morph_id]["snapshot"]["payload"]["morph_core"]
        core = candidate["snapshot"]["payload"]["morph_core"]
        core["knowledge"]["learned"]["world_objects"] = histories[morph_id]
        _append_world_chronicle(candidate, {
            "event_id": event_id, "kind": "world-object", "observed_at": _iso(now),
            "source": "haos-morph-engine", "place": place,
            "frame": f"haos-{place.lower().replace('_', '-')}",
            "evidence_digest": evidence_digest,
        }, now)
        verify_successor(old_core, core)
        refresh_snapshot(candidate)
        _record(candidate["habitat"], {"event_id": event_id, "at": _iso(now),
                                        "type": "WORLD_OBJECT", "object_id": object_id,
                                        "participants": list(participants)})
    for morph_id in morph_ids:
        ledger.data["morphs"][morph_id] = candidates[morph_id]
    return outcome


def start_garden_game(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Start one operator game for a living HAOS Morph in Gardens."""
    _exact(request, {"schema", "game_id", "morph_id", "operator_id", "game"}, "game start")
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "game schema is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph or _social_subject(morph, now) is None or _habitat(morph, now)["place"] != "SEREIN_GARDENS":
        raise TransferError("GARDENS_REQUIRED", "an active embodied Gardens Morph is required")
    habitat = _habitat(morph, now)
    sessions = habitat["games"]["sessions"]
    game_id = request["game_id"]
    if not isinstance(game_id, str) or not game_id:
        raise TransferError("INVALID_GAME", "game id is required")
    if game_id in sessions:
        previous = sessions[game_id]
        if any(previous[key] != request[key] for key in ("morph_id", "operator_id", "game")):
            raise TransferError("REPLAY_CONFLICT", "game id payload changed")
        return public_state(previous)
    for item in sessions.values():
        if not item["finished"] and now - datetime.fromisoformat(item["started_at"].replace("Z", "+00:00")) > timedelta(minutes=15):
            item["finished"] = True
            item["expired"] = True
    if any(not item["finished"] for item in sessions.values()):
        raise TransferError("GAME_ALREADY_ACTIVE", "finish the current game first")
    try:
        session = start_game(game_id=game_id, morph_id=morph["morph_id"],
                             operator_id=request["operator_id"], game=request["game"],
                             started_at=_iso(now))
    except GardenGameError as err:
        raise TransferError("INVALID_GAME", str(err)) from err
    sessions[game_id] = session
    while len(sessions) > 8:
        oldest = next(iter(sessions))
        if oldest != game_id:
            del sessions[oldest]
    _record(habitat, {"event_id": game_id, "at": _iso(now), "type": "GAME_STARTED",
                      "game": request["game"], "operator_id": request["operator_id"]})
    return public_state(session)


def play_garden_game(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Apply one game turn and at most one bounded completion reward/window."""
    _exact(request, {"schema", "game_id", "morph_id", "operator_id", "move_id", "choice"}, "game move")
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "game schema is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph or morph.get("authority") != "HAOS":
        raise TransferError("AUTHORITY_CONFLICT", "HAOS Morph authority is required")
    habitat = _habitat(morph, now)
    if habitat["place"] != "SEREIN_GARDENS" or _social_subject(morph, now) is None:
        raise TransferError("GARDENS_REQUIRED", "game must remain in Gardens")
    session = habitat["games"]["sessions"].get(str(request["game_id"]))
    if session is None or session["operator_id"] != request["operator_id"]:
        raise TransferError("GAME_NOT_FOUND", "game is not bound to this operator")
    if session.get("expired"):
        raise TransferError("GAME_EXPIRED", "start a new Gardens game")
    repeated = request["move_id"] in session["move_ids"]
    try:
        result = game_move(session, move_id=request["move_id"], choice=request["choice"])
    except GardenGameError as err:
        raise TransferError("INVALID_MOVE", str(err)) from err
    if repeated:
        return result
    if session["finished"]:
        window = int(now.timestamp()) // int(GAME_REWARD_INTERVAL.total_seconds())
        if habitat["games"]["last_reward_window"] != window:
            payload = morph["snapshot"]["payload"]
            payload["play_q8"] = min(255, int(payload["play_q8"]) + 12)
            payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 8)
            payload["behavior"] = "PLAY"
            payload["memories"] = (payload["memories"] + [{"code": "PLAY", "age_ms": 0, "weight": 80}])[-8:]
            payload["saved_epoch_seconds"] = int(now.timestamp())
            _sync_morph_core_state(morph)
            refresh_snapshot(morph)
            habitat["games"]["last_reward_window"] = window
            session["rewarded"] = True
        _record(habitat, {"event_id": session["game_id"], "at": _iso(now),
                          "type": "GAME_COMPLETED", "game": session["game"],
                          "score": session["score"], "rewarded": session["rewarded"]})
    result = {**result, "rewarded": session["rewarded"]}
    session["responses"][request["move_id"]] = deepcopy(result)
    return result


def habitat_status(ledger: MorphTransferLedger, morph_id: str, now: datetime) -> dict[str, Any]:
    morph = ledger.data["morphs"].get(str(morph_id))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    habitat = _habitat(morph, now)
    alias = next((name for name, frame in FRAME_ALIASES.items() if frame == morph["source_frame"]), morph["source_frame"])
    public_presentation = deepcopy(habitat["presentation"])
    name_record = morph.get("presentation")
    display_name = name_record.get("display_name") if isinstance(name_record, dict) else None
    if not isinstance(display_name, str) or not display_name.strip():
        # Older hatch generations durably retained the generated name in the
        # hatch receipt but exposed only the neutral visual presentation.  A
        # read may recover that public label without rewriting Morph life.
        display_name = next((
            operation.get("result", {}).get("display_name")
            for operation in ledger.data["operations"].values()
            if operation.get("operation_kind") == "GEN1_STARTER_HATCH"
            and operation.get("morph_id") == morph["morph_id"]
            and isinstance(operation.get("result", {}).get("display_name"), str)
        ), None)
    if isinstance(display_name, str) and display_name.strip():
        public_presentation["display_name"] = display_name.strip()
    committed_inbound = any(
        operation.get("morph_id") == morph["morph_id"]
        and operation.get("state") == "ACTIVE_HAOS"
        and operation.get("generation") == morph["generation"]
        for operation in ledger.data["operations"].values()
    )
    source_frame = str(morph["source_frame"])
    dedicated_frame = bool(source_frame and source_frame.lower() != "unknown"
                           and not source_frame.lower().startswith("haos-"))
    result = {
        "schema": HABITAT_SCHEMA,
        "morph_id": morph["morph_id"],
        "founder_id": morph["founder_id"],
        "device_birth_lineage": morph["device_birth_lineage"],
        "source_frame": morph["source_frame"],
        "authority": morph["authority"],
        "generation": morph["generation"],
        "custody_revision": morph["generation"],
        "lineage_generation": (
            morph["snapshot"]["payload"].get("morph_core", {}).get("root", {}).get("identity", {}).get("generation",
            morph["snapshot"]["payload"].get("morph_core", {}).get("identity", {}).get("generation"))
        ),
        "snapshot_digest": morph["snapshot_digest"],
        "engine_state": morph["engine_state"],
        "habitat_engine_state": "ACTIVE" if morph["authority"] == "HAOS" and habitat["place"] in ACTIVE_PLACES else "STASIS" if habitat["place"] == "VOID" else "DIAGNOSTIC_HOLD" if habitat["place"] == "CODE_HAVEN" else "REMOTE",
        "place": habitat["place"],
        "entered_at": habitat["entered_at"],
        "last_tick_at": habitat["last_tick_at"],
        "void_locked_until": habitat["void_locked_until"],
        "nursery_elapsed_seconds": habitat["nursery_elapsed_seconds"],
        "environment": deepcopy(habitat["environment"]),
        "presentation": public_presentation,
        "frame_return": {
            "dedicated": dedicated_frame,
            "target_frame": source_frame if dedicated_frame else None,
            "call_available": bool(dedicated_frame and committed_inbound
                                   and morph["authority"] == "HAOS"
                                   and habitat["place"] == "HORIZON"),
            "recall_available": bool(dedicated_frame and morph["authority"] == source_frame),
        },
        "founder_axes": deepcopy(habitat["founder_axes"]),
        "social": deepcopy(habitat["social"]),
        "games": [public_state(session) for session in habitat["games"]["sessions"].values()],
        "automatic_reflex": deepcopy(habitat["reflex"]),
        "life": deepcopy(morph["snapshot"]["payload"]),
    }
    life = result["life"]
    result["care_levels"] = {
        "energy": care_level(255 - int(life["fatigue_q8"])),
        "food": care_level(life["food_q8"]),
        "water": care_level(life["water_q8"]),
        "play": care_level(life["play_q8"]),
        "rest": care_level(life["rest_q8"]),
    }
    result["presentation_binding"] = bind_presentation(
        presentation=habitat["presentation"], source_frame=morph["source_frame"],
        habitat_alias=alias, generation=morph["generation"],
        snapshot_digest=morph["snapshot_digest"], place=habitat["place"],
        authority=morph["authority"],
    )
    return result


def place_morph(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    _exact(request, {"schema", "event_id", "morph_id", "place"}, "place request")
    if request["schema"] != HABITAT_SCHEMA or request["place"] not in PLACES:
        raise TransferError("INVALID_PLACE", "place is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    event_id = str(request["event_id"])
    if event_id in habitat["event_ids"]:
        return habitat_status(ledger, morph["morph_id"], now)
    if habitat["place"] == "VOID" and request["place"] != "VOID":
        locked_until = datetime.fromisoformat(habitat["void_locked_until"].replace("Z", "+00:00"))
        if now.astimezone(UTC) < locked_until:
            raise TransferError("VOID_LOCKED", "Void withdrawal lock remains active")
    previous = habitat["place"]
    habitat["place"] = request["place"]
    habitat["entered_at"] = _iso(now)
    habitat["last_tick_at"] = _iso(now)
    habitat["void_locked_until"] = _iso(now + VOID_LOCK) if request["place"] == "VOID" else None
    habitat["event_ids"].append(event_id)
    del habitat["event_ids"][:-HISTORY_CAPACITY]
    _record(habitat, {"event_id": event_id, "at": _iso(now), "type": "PLACE", "from": previous, "to": request["place"]})
    _sync_morph_core_state(morph, sync_place=True)
    evidence = {
        "schema": HABITAT_SCHEMA,
        "event_id": event_id,
        "morph_id": morph["morph_id"],
        "from": previous,
        "to": request["place"],
        "observed_at": _iso(now),
    }
    # Legacy v2 fixtures remain movable, but only an admitted nine-core Morph
    # has a portable chronicle. The inbound alignment reflex upgrades those
    # Morphs before they can claim nine-core movement history.
    if isinstance(morph.get("snapshot", {}).get("payload", {}).get("morph_core"), dict):
        _append_world_chronicle(morph, {
            "event_id": event_id,
            "kind": "habitat-place",
            "observed_at": _iso(now),
            "source": "haos-morph-engine",
            "place": request["place"],
            "frame": f"haos-{request['place'].lower().replace('_', '-')}",
            "evidence_digest": sha256(canonical_json(evidence).encode()).hexdigest(),
        }, now)
    refresh_snapshot(morph)
    return habitat_status(ledger, morph["morph_id"], now)


def _apply_life_gain(morph: dict[str, Any], action: str, steps: int) -> tuple[int, int, dict[str, Any]]:
    """Apply one bounded need gain; callers define its attributable source."""
    payload = morph["snapshot"]["payload"]
    if action == "FEED":
        before, after = _raise_care(payload, "food_q8", steps)
        payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 8)
        payload["behavior"] = "FOOD"
        memory = {"code": "SOCIAL", "age_ms": 0, "weight": 80}
    elif action == "WATER":
        before, after = _raise_care(payload, "water_q8", steps)
        payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 6)
        payload["behavior"] = "WATER"
        memory = {"code": "SOCIAL", "age_ms": 0, "weight": 72}
    elif action == "PLAY":
        before, after = _raise_care(payload, "play_q8", steps)
        payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 18)
        payload["arousal_q8"] = min(255, int(payload["arousal_q8"]) + 20)
        payload["behavior"] = "PLAY"
        memory = {"code": "PLAY", "age_ms": 0, "weight": 220}
    elif action == "EXPLORE":
        before, after = _raise_care(payload, "attention_q8", steps)
        payload["arousal_q8"] = min(255, int(payload["arousal_q8"]) + 4)
        payload["behavior"] = "INVESTIGATE"
        memory = {"code": "NOVEL", "age_ms": 0, "weight": 40}
    else:
        before, after = _raise_care(payload, "rest_q8", steps)
        payload["fatigue_q8"] = max(0, int(payload["fatigue_q8"]) - 40)
        payload["arousal_q8"] = max(0, int(payload["arousal_q8"]) - 24)
        payload["behavior"] = "DOZE"
        memory = {"code": "REST", "age_ms": 0, "weight": 220}
    return before, after, memory


def apply_environment_interaction(ledger: MorphTransferLedger, *, morph_id: str,
                                  event_id: str, activity: str, now: datetime) -> dict[str, Any]:
    """Record a Morph-chosen world interaction (+1); this is not operator care."""
    action = {"EAT": "FEED", "DRINK": "WATER", "REST": "REST",
              "PLAY": "PLAY", "EXPLORE": "EXPLORE"}.get(activity)
    if action is None:
        raise TransferError("INVALID_ENVIRONMENT_INTERACTION", "world activity is not admitted")
    morph = ledger.data["morphs"].get(str(morph_id))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    if habitat["place"] not in {"HORIZON", "SEREIN_GARDENS"}:
        raise TransferError("PLACE_REJECTS_INTERACTION", "current place has no active world interaction")
    if event_id in habitat["event_ids"]:
        return habitat_status(ledger, morph_id, now)
    before, after, memory = _apply_life_gain(morph, action, 1)
    payload = morph["snapshot"]["payload"]
    payload["saved_epoch_seconds"] = int(now.timestamp())
    payload["memories"] = (payload["memories"] + [memory])[-8:]
    habitat["last_tick_at"] = _iso(now)
    habitat["event_ids"].append(event_id)
    del habitat["event_ids"][:-HISTORY_CAPACITY]
    _record(habitat, {"event_id": event_id, "at": _iso(now),
                      "type": "ENVIRONMENT_INTERACTION", "activity": activity,
                      "level_before": before, "level_after": after})
    _sync_morph_core_state(morph)
    refresh_snapshot(morph)
    return habitat_status(ledger, morph_id, now)


def care_for_morph(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    _exact(request, {"schema", "event_id", "morph_id", "action"}, "care request")
    if request["schema"] != HABITAT_SCHEMA or request["action"] not in CARE_ACTIONS:
        raise TransferError("INVALID_CARE", "care action is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    if habitat["place"] in {"VOID", "CODE_HAVEN"}:
        raise TransferError("PLACE_REJECTS_CARE", "current place does not permit ordinary care")
    event_id = str(request["event_id"])
    if event_id in habitat["event_ids"]:
        return habitat_status(ledger, morph["morph_id"], now)
    payload = morph["snapshot"]["payload"]
    action = request["action"]
    before, after, memory = _apply_life_gain(morph, action, 2)
    payload["saved_epoch_seconds"] = int(now.timestamp())
    payload["memories"] = (payload["memories"] + [memory])[-8:]
    habitat["last_tick_at"] = _iso(now)
    habitat["event_ids"].append(event_id)
    del habitat["event_ids"][:-HISTORY_CAPACITY]
    _record(habitat, {"event_id": event_id, "at": _iso(now), "type": "CARE", "action": action,
                      "origin": "OPERATOR", "level_before": before, "level_after": after})
    _sync_morph_core_state(morph)
    refresh_snapshot(morph)
    return habitat_status(ledger, morph["morph_id"], now)


def update_presentation(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Change mutable reference presentation only inside Code Haven."""
    _exact(request, {"schema", "event_id", "morph_id", "presentation"}, "presentation request")
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "presentation request schema is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    event_id = str(request["event_id"])
    if event_id in habitat["event_ids"]:
        return habitat_status(ledger, morph["morph_id"], now)
    try:
        receipt = change_presentation(
            habitat["presentation"], request["presentation"], place=habitat["place"]
        )
    except PresentationError as err:
        raise TransferError(err.code, str(err)) from err
    habitat["presentation"] = receipt["presentation"]
    habitat["event_ids"].append(event_id)
    del habitat["event_ids"][:-HISTORY_CAPACITY]
    _record(habitat, {"event_id": event_id, "at": _iso(now), "type": "PRESENTATION",
                      "before_digest": receipt["before_digest"],
                      "after_digest": receipt["after_digest"]})
    return {**habitat_status(ledger, morph["morph_id"], now), "receipt": receipt}


def habitat_history(ledger: MorphTransferLedger, morph_id: str, now: datetime) -> dict[str, Any]:
    morph = ledger.data["morphs"].get(str(morph_id))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    habitat = _habitat(morph, now)
    return {"schema": HABITAT_SCHEMA, "morph_id": morph["morph_id"], "events": deepcopy(habitat["history"])}


def chronicle_page(ledger: MorphTransferLedger, morph_id: str, after_sequence: int,
                   limit: int, now: datetime) -> dict[str, Any]:
    """Read an integrity-checked archive page without moving Morph custody."""
    if type(after_sequence) is not int or after_sequence < 0 or type(limit) is not int or not 1 <= limit <= 32:
        raise TransferError("INVALID_PAGE", "archive cursor or page limit is invalid")
    morph = ledger.data["morphs"].get(morph_id)
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    core = morph["snapshot"]["payload"].get("morph_core")
    if not core:
        raise TransferError("NINE_CORE_REQUIRED", "Morph has no nine-core history")
    events = core["memory"]["chronicle"]["events"]
    archive = morph.get("habitat", {}).get("chronicle_archive")
    marker = core["knowledge"]["learned"].get("chronicle_archive")
    base_digest = sha256(json.dumps(events, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if archive is None:
        if marker is not None:
            raise TransferError("ARCHIVE_INTEGRITY_FAILED", "archive history is missing")
        rows = []
    else:
        if archive.get("schema") != "serein.morph-chronicle-archive.v1" or archive.get("base_digest") != base_digest:
            raise TransferError("ARCHIVE_INTEGRITY_FAILED", "archive base differs from portable life")
        rows = archive.get("rows")
        if not isinstance(rows, list):
            raise TransferError("ARCHIVE_INTEGRITY_FAILED", "archive rows are invalid")
    previous = base_digest
    seen = {event["event_id"] for event in events}
    for sequence, row in enumerate(rows, 1):
        payload = row.get("event")
        if not isinstance(payload, dict) or payload.get("event_id") in seen:
            raise TransferError("ARCHIVE_INTEGRITY_FAILED", "archive event is invalid")
        digest = sha256((previous + "\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()
        if row.get("sequence") != sequence or row.get("previous_digest") != previous or row.get("digest") != digest:
            raise TransferError("ARCHIVE_INTEGRITY_FAILED", "archive chain is invalid")
        seen.add(payload["event_id"])
        previous = digest
    expected_marker = {"count": len(rows), "head_sha256": previous} if rows else None
    if marker != expected_marker:
        raise TransferError("ARCHIVE_INTEGRITY_FAILED", "portable archive marker differs")
    if after_sequence > len(rows):
        raise TransferError("INVALID_PAGE", "archive cursor exceeds head")
    selected = rows[after_sequence:after_sequence + limit]
    return {"schema": "serein.morph-chronicle-page.v1", "morph_id": morph_id,
            "generation": morph["generation"], "snapshot_digest": morph["snapshot_digest"],
            "base_digest": base_digest, "head_sha256": previous, "total": len(rows),
            "after_sequence": after_sequence, "next_sequence": after_sequence + len(selected),
            "rows": deepcopy(selected), "custody_changed": False}


def habitat_list(ledger: MorphTransferLedger, now: datetime) -> dict[str, Any]:
    return {"schema": HABITAT_SCHEMA, "morphs": [habitat_status(ledger, morph_id, now) for morph_id in sorted(ledger.data["morphs"])]}


def call_morph(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Create an attributable Android call receipt without transferring authority."""
    _exact(request, {"schema", "call_id", "morph_id", "target_frame"}, "call request")
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "call schema is not admitted")
    call_id = str(request["call_id"])
    target_frame = str(request["target_frame"])
    if not call_id or not target_frame:
        raise TransferError("INVALID_ATTRIBUTION", "call id and target frame are required")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "only a Morph already transferred into HAOS may be called")
    if FRAME_ALIASES.get(target_frame, target_frame) != morph["source_frame"]:
        raise TransferError("WRONG_FRAME_ALIAS", "habitat alias is not bound to the retained source frame")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    if habitat["place"] != "HORIZON":
        raise TransferError("CALL_REQUIRES_HORIZON", "only a HAOS-owned Morph in Horizon may be called")
    admitted = any(
        op.get("morph_id") == morph["morph_id"]
        and op.get("state") == "ACTIVE_HAOS"
        and op.get("generation") == morph["generation"]
        for op in ledger.data["operations"].values()
    )
    if not admitted:
        raise TransferError("TRANSFER_PROOF_REQUIRED", "Morph lacks a committed HAOS transfer receipt")
    previous = next((event for event in habitat["history"] if event.get("event_id") == call_id), None)
    if previous:
        if previous.get("type") != "CALL" or previous.get("target_frame") != target_frame:
            raise TransferError("REPLAY_CONFLICT", "call id payload changed")
    else:
        habitat["event_ids"].append(call_id)
        del habitat["event_ids"][:-HISTORY_CAPACITY]
        _record(habitat, {
            "event_id": call_id,
            "at": _iso(now),
            "type": "CALL",
            "target_frame": target_frame,
        })
    return {
        "schema": HABITAT_SCHEMA,
        "call_id": call_id,
        "morph_id": morph["morph_id"],
        "founder_id": morph["founder_id"],
        "device_birth_lineage": morph["device_birth_lineage"],
        "generation": morph["generation"],
        "snapshot_digest": morph["snapshot_digest"],
        "authority": "HAOS",
        "place": "HORIZON",
        "target_frame": target_frame,
        "state": "CALL_READY",
        "transfer_required": True,
    }


def correct_habitat_event(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Append an attributable Code Haven correction without erasing history."""
    _exact(request, {"schema", "event_id", "morph_id", "invalid_event_id", "reason"}, "history correction request")
    if request["schema"] != HABITAT_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "correction schema is not admitted")
    morph = ledger.data["morphs"].get(str(request["morph_id"]))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not hosted")
    _require_haos(morph)
    habitat = _habitat(morph, now)
    if habitat["place"] != "CODE_HAVEN":
        raise TransferError("CODE_HAVEN_REQUIRED", "Chronicle corrections are Code Haven-only")
    invalid_event_id = str(request["invalid_event_id"])
    invalid = next((row for row in habitat["history"] if row.get("event_id") == invalid_event_id), None)
    if not invalid:
        raise TransferError("EVENT_NOT_FOUND", "invalidated Chronicle event was not found")
    correction_id = str(request["event_id"])
    previous = next((row for row in habitat["history"] if row.get("event_id") == correction_id), None)
    correction = {
        "event_id": correction_id,
        "at": _iso(now),
        "type": "CODE_HAVEN_CORRECTION",
        "invalid_event_id": invalid_event_id,
        "invalid_event_type": invalid.get("type"),
        "reason": str(request["reason"]),
        "reducer_effect": "EXCLUDED",
    }
    if previous:
        if {k: previous.get(k) for k in correction if k != "at"} != {k: correction.get(k) for k in correction if k != "at"}:
            raise TransferError("REPLAY_CONFLICT", "correction event payload changed")
    else:
        habitat["event_ids"].append(correction_id)
        del habitat["event_ids"][:-HISTORY_CAPACITY]
        _record(habitat, correction)
    invalidated = habitat.setdefault("invalidated_event_ids", [])
    if invalid_event_id not in invalidated:
        invalidated.append(invalid_event_id)
        del invalidated[:-HISTORY_CAPACITY]
    refresh_snapshot(morph)
    return {"schema": HABITAT_SCHEMA, "morph_id": morph["morph_id"], "place": habitat["place"],
            "authority": morph["authority"], "correction": correction,
            "invalidated_event_ids": deepcopy(invalidated)}

