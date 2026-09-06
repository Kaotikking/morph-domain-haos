"""HAOS-hosted Morph habitat layered on the transfer authority ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import uuid
from typing import Any


from ..morph_sdk.transfer import (
    MorphTransferLedger,
    TransferError,
    _exact,
    refresh_snapshot,
)
from ..morph_sdk.presentation import (
    PresentationError, bind_presentation, change_presentation, neutral_presentation,
)

HABITAT_SCHEMA = "serein.morph-habitat.v1"
HABITAT_ENGINE = "haos-morph-habitat.v1"
HABITAT_DATA_KEY = "morph_domain_habitat_registered"
PLACES = {"VOID", "NURSERY", "SEREIN_GARDENS", "HORIZON", "CODE_HAVEN"}
ACTIVE_PLACES = {"NURSERY", "SEREIN_GARDENS", "HORIZON"}
CARE_ACTIONS = {"FEED", "WATER", "PLAY", "REST"}
VOID_LOCK = timedelta(hours=24)
HISTORY_CAPACITY = 128
TICK_INTERVAL = timedelta(seconds=30)
CARE_FIELDS = ("food_q8", "water_q8", "play_q8", "rest_q8", "attention_q8")
FRAME_ALIASES = {
    "android-morph-habitat:x4": "android-frame:v1:182b7920-d0e7-4e78-a321-1ac6722471da",
}
ELEMENTS = ("FIRE", "WATER", "AIR", "EARTH")
ENVIRONMENT_SCHEMA = "serein.morph-environment.v1"
WEATHER_WATER_STATES = {"rainy", "pouring", "lightning-rainy", "snowy-rainy"}
ENVIRONMENT_ENTITIES = {
    "weather": "weather.kigm",
    "sun": "sun.sun",
    "temperature": "sensor.kigm_temperature",
    "humidity": "sensor.kigm_relative_humidity",
    "wind": "sensor.kigm_wind_speed",
}


def _iso(now: datetime) -> str:
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sync_morph_core_state(morph: dict[str, Any], *, sync_place: bool = False) -> None:
    """Keep v3's shared outer state and Morph Core view identical."""
    snapshot = morph["snapshot"]
    if snapshot["schema"] != "serein.morph-life-state.v3":
        return
    payload = snapshot["payload"]
    state = payload["morph_core"]["state"]
    state["needs_q8"] = {
        "attention": payload["attention_q8"],
        "energy": 255 - payload["fatigue_q8"],
        "food": payload["food_q8"],
        "play": payload["play_q8"],
        "rest": payload["rest_q8"],
        "water": payload["water_q8"],
    }
    state["mood"] = payload["behavior"].lower()
    state["authority"] = "HAOS_ACTIVE"
    if sync_place:
        place = morph["habitat"]["place"]
        state["place"] = place
        state["active_frame"] = f"haos-{place.lower().replace('_', '-')}"


def _habitat(morph: dict[str, Any], now: datetime) -> dict[str, Any]:
    habitat = morph.get("habitat")
    if not isinstance(habitat, dict):
        habitat = {
            "schema": HABITAT_SCHEMA,
            "engine_version": HABITAT_ENGINE,
            "place": "HORIZON",
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
    return habitat


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
        "weather": rows["weather"].state if rows["weather"] else None,
        "sun": rows["sun"].state if rows["sun"] else None,
        "temperature_f": _number(rows["temperature"].state if rows["temperature"] else None),
        "humidity_percent": _number(rows["humidity"].state if rows["humidity"] else None),
        "wind_mph": _number(rows["wind"].state if rows["wind"] else None),
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


def habitat_status(ledger: MorphTransferLedger, morph_id: str, now: datetime) -> dict[str, Any]:
    morph = ledger.data["morphs"].get(str(morph_id))
    if not morph:
        raise TransferError("NOT_FOUND", "Morph is not known to HAOS")
    habitat = _habitat(morph, now)
    alias = next((name for name, frame in FRAME_ALIASES.items() if frame == morph["source_frame"]), None)
    result = {
        "schema": HABITAT_SCHEMA,
        "morph_id": morph["morph_id"],
        "founder_id": morph["founder_id"],
        "device_birth_lineage": morph["device_birth_lineage"],
        "source_frame": morph["source_frame"],
        "authority": morph["authority"],
        "generation": morph["generation"],
        "snapshot_digest": morph["snapshot_digest"],
        "engine_state": morph["engine_state"],
        "habitat_engine_state": "ACTIVE" if morph["authority"] == "HAOS" and habitat["place"] in ACTIVE_PLACES else "STASIS" if habitat["place"] == "VOID" else "DIAGNOSTIC_HOLD" if habitat["place"] == "CODE_HAVEN" else "REMOTE",
        "place": habitat["place"],
        "entered_at": habitat["entered_at"],
        "last_tick_at": habitat["last_tick_at"],
        "void_locked_until": habitat["void_locked_until"],
        "nursery_elapsed_seconds": habitat["nursery_elapsed_seconds"],
        "environment": deepcopy(habitat["environment"]),
        "presentation": deepcopy(habitat["presentation"]),
        "life": deepcopy(morph["snapshot"]["payload"]),
    }
    if alias is not None:
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
    refresh_snapshot(morph)
    return habitat_status(ledger, morph["morph_id"], now)


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
    if action == "FEED":
        payload["food_q8"] = min(255, int(payload["food_q8"]) + 48)
        payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 8)
        payload["behavior"] = "FOOD"
        memory = {"code": "SOCIAL", "age_ms": 0, "weight": 80}
    elif action == "WATER":
        payload["water_q8"] = min(255, int(payload["water_q8"]) + 48)
        payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 6)
        payload["behavior"] = "WATER"
        memory = {"code": "SOCIAL", "age_ms": 0, "weight": 72}
    elif action == "PLAY":
        payload["play_q8"] = min(255, int(payload["play_q8"]) + 40)
        payload["attention_q8"] = min(255, int(payload["attention_q8"]) + 18)
        payload["arousal_q8"] = min(255, int(payload["arousal_q8"]) + 20)
        payload["behavior"] = "PLAY"
        memory = {"code": "PLAY", "age_ms": 0, "weight": 220}
    else:
        payload["rest_q8"] = min(255, int(payload["rest_q8"]) + 48)
        payload["fatigue_q8"] = max(0, int(payload["fatigue_q8"]) - 40)
        payload["arousal_q8"] = max(0, int(payload["arousal_q8"]) - 24)
        payload["behavior"] = "DOZE"
        memory = {"code": "REST", "age_ms": 0, "weight": 220}
    payload["saved_epoch_seconds"] = int(now.timestamp())
    payload["memories"] = (payload["memories"] + [memory])[-8:]
    habitat["last_tick_at"] = _iso(now)
    habitat["event_ids"].append(event_id)
    del habitat["event_ids"][:-HISTORY_CAPACITY]
    _record(habitat, {"event_id": event_id, "at": _iso(now), "type": "CARE", "action": action})
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
    if FRAME_ALIASES.get(target_frame) != morph["source_frame"]:
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

