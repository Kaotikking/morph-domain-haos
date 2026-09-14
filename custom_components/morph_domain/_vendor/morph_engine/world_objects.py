"""Local Pet World object-interaction model; no Morph-state or authority writes.

Affinities are explicit inputs from an admitted personality/knowledge source, never
inferred from a Morph ID. A caller must persist accepted events through the
appropriate nine-Core boundary before treating this as a runtime feature.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

OBJECTS = {
    "HORIZON": ("rest-nook", "gathering-stone", "discovery-prism", "walking-path"),
    "SEREIN_GARDENS": ("play-orb", "shared-chimes", "quiet-pool", "pattern-tiles"),
}
PREFERENCE_THRESHOLD = 3
OBJECT_ELEMENTS = {
    "rest-nook": "EARTH", "gathering-stone": "EARTH",
    "discovery-prism": "AIR", "walking-path": "AIR",
    "play-orb": "FIRE", "shared-chimes": "AIR",
    "quiet-pool": "WATER", "pattern-tiles": "EARTH",
}
ELEMENTAL_REST = {
    "AIR": "AIR_CURRENTS",
    "WATER": "SWIM",
    "FIRE": "EMBER_WARMTH",
    "EARTH": "GROUNDING",
}


class WorldObjectError(ValueError):
    pass


def elemental_rest_scene(core: dict[str, Any]) -> str:
    """Presentation code from immutable primary element; never a DNA change."""
    try:
        identity = core["root"]["identity"] if core["schema"] == "serein.morph-nine-core.v1" else core["identity"]
        return ELEMENTAL_REST[identity["primitive_element"]]
    except (KeyError, TypeError) as err:
        raise WorldObjectError("canonical primary element required") from err


def new_history(morph_id: str) -> dict[str, Any]:
    if not isinstance(morph_id, str) or not morph_id:
        raise WorldObjectError("Morph identity required")
    return {"morph_id": morph_id, "events": {}, "counts": {}, "preferences": []}


def affinity_from_nine_core(core: dict[str, Any], place: str) -> dict[str, int]:
    """Derive bounded starting attraction only from admitted identity and life state."""
    if not isinstance(core, dict) or core.get("schema") != "serein.morph-nine-core.v1" or place not in OBJECTS:
        raise WorldObjectError("admitted nine-core Morph and place required")
    try:
        element = core["root"]["identity"]["primitive_element"]
        needs = core["cloud"]["needs_q8"]
        learned = core["knowledge"]["learned"]
        history = learned.get("world_objects", new_history(core["root"]["identity"]["morph_id"]))
    except (KeyError, TypeError) as err:
        raise WorldObjectError("incomplete nine-core state") from err
    if element not in {"FIRE", "WATER", "AIR", "EARTH"} or not isinstance(needs, dict):
        raise WorldObjectError("invalid elemental or life source")
    if history.get("morph_id") != core["root"]["identity"]["morph_id"]:
        raise WorldObjectError("world history belongs to another Morph")
    result = {}
    for object_id in OBJECTS[place]:
        score = 1 + (2 if OBJECT_ELEMENTS[object_id] == element else 0)
        if object_id in {"rest-nook", "quiet-pool"} and needs.get("rest", 255) < 128:
            score += 2
        if object_id in {"play-orb", "shared-chimes", "pattern-tiles"} and needs.get("play", 255) < 128:
            score += 2
        if object_id in history.get("preferences", []):
            score += 1
        result[object_id] = min(5, score)
    return result


def choose_object(place: str, affinities: dict[str, int], history: dict[str, Any]) -> str:
    """Stable choice from explicitly supplied 0–5 affinity and observed history."""
    if place not in OBJECTS or not isinstance(affinities, dict):
        raise WorldObjectError("unknown place or affinity source")
    if not isinstance(history, dict) or not isinstance(history.get("counts"), dict):
        raise WorldObjectError("invalid history")
    allowed = OBJECTS[place]
    if set(affinities) != set(allowed) or any(type(v) is not int or not 0 <= v <= 5 for v in affinities.values()):
        raise WorldObjectError("complete bounded affinity set required")
    if not any(affinities.values()):
        raise WorldObjectError("no willing object choice")
    # Repeated visits can distinguish a preference, but do not manufacture one.
    return max(allowed, key=lambda name: (affinities[name], history["counts"].get(name, 0), -allowed.index(name)))


def interact(histories: dict[str, dict[str, Any]], *, event_id: str, place: str,
             object_id: str, participants: tuple[str, ...], willing: dict[str, bool]) -> dict[str, Any]:
    """Accept one solo Horizon or reciprocal joint event, atomically for all sides."""
    if place not in OBJECTS or object_id not in OBJECTS[place]:
        raise WorldObjectError("object does not belong to place")
    if not isinstance(event_id, str) or not event_id or len(set(participants)) != len(participants):
        raise WorldObjectError("invalid event identity")
    if place == "HORIZON" and len(participants) not in (1, 2):
        raise WorldObjectError("Horizon requires one or two participants")
    if place == "SEREIN_GARDENS" and len(participants) != 2:
        raise WorldObjectError("Gardens requires exactly two participants")
    if any(identity not in histories or histories[identity].get("morph_id") != identity
           for identity in participants if identity != "OPERATOR"):
        raise WorldObjectError("unknown Morph participant")
    if "OPERATOR" in participants and (place != "SEREIN_GARDENS" or len(participants) != 2):
        raise WorldObjectError("operator play is Gardens-only")
    if set(willing) != set(participants):
        raise WorldObjectError("each participant must give a decision")
    if not all(type(value) is bool for value in willing.values()):
        raise WorldObjectError("willingness must be explicit")
    if not all(willing.values()):
        return {"event_id": event_id, "result": "DECLINED", "credited": []}
    morph_ids = [identity for identity in participants if identity != "OPERATOR"]
    seen = [event_id in histories[identity]["events"] for identity in morph_ids]
    if any(seen):
        if not all(seen):
            raise WorldObjectError("partial prior event")
        prior = [histories[identity]["events"][event_id] for identity in morph_ids]
        if any(row != prior[0] for row in prior) or prior[0]["place"] != place or prior[0]["object_id"] != object_id or tuple(prior[0]["participants"]) != participants:
            raise WorldObjectError("replay payload changed")
        return {"event_id": event_id, "result": "REPLAY", "credited": []}
    event = {"event_id": event_id, "place": place, "object_id": object_id,
             "participants": list(participants)}
    for identity in morph_ids:
        history = histories[identity]
        history["events"][event_id] = deepcopy(event)
        history["counts"][object_id] = history["counts"].get(object_id, 0) + 1
        if history["counts"][object_id] >= PREFERENCE_THRESHOLD and object_id not in history["preferences"]:
            history["preferences"].append(object_id)
    return {"event_id": event_id, "result": "ACCEPTED", "credited": morph_ids}
