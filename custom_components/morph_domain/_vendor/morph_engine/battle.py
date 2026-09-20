"""Deterministic, non-destructive MorphDomain battle beta."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from typing import Any

from ..morph_sdk.word_pools_v1 import pool
from ..morph_sdk.morph_core import MORPH_NINE_CORE_SCHEMA
from ..morph_sdk.transfer import TransferError

BATTLE_SCHEMA = "serein.morph-battle.v1"
MODES = {"UNRANKED_SPARRING"}
ELEMENT_EDGE = {"FIRE": "AIR", "AIR": "EARTH", "EARTH": "WATER", "WATER": "FIRE"}
MOVE_TIERS = ("STATUS", "SPEED", "POWER", "SUPER")


def _core(morph: dict[str, Any]) -> dict[str, Any]:
    return morph.get("snapshot", {}).get("payload", {}).get("morph_core", {})


def _profile(morph: dict[str, Any]) -> dict[str, Any]:
    core = _core(morph)
    if core.get("schema") != MORPH_NINE_CORE_SCHEMA:
        raise TransferError("NINE_CORE_REQUIRED", "Code Haven alignment is required before battle")
    habitat = morph.get("habitat", {})
    if morph.get("authority") != "HAOS":
        raise TransferError("HAOS_CUSTODY_REQUIRED", "battle requires HAOS custody")
    if habitat.get("place") not in {"HORIZON", "SEREIN_GARDENS"}:
        raise TransferError("BATTLE_PLACE_REQUIRED", "battle is available only in Horizon or Gardens")
    if core.get("platform", {}).get("embodiment", {}).get("body_class") == "morph-egg":
        raise TransferError("HATCH_REQUIRED", "an egg cannot battle")
    identity = core.get("root", {}).get("identity", {})
    element = str(identity.get("primitive_element", "UNKNOWN")).upper()
    if element not in ELEMENT_EDGE:
        raise TransferError("KNOWN_ELEMENT_REQUIRED", "battle requires a canonical elemental lineage")
    life = morph.get("snapshot", {}).get("payload", {})
    care = [255 - int(life.get("fatigue_q8", 255)), int(life.get("food_q8", 0)),
            int(life.get("water_q8", 0)), int(life.get("play_q8", 0)), int(life.get("rest_q8", 0))]
    care_level = max(1, min(5, 1 + sum(max(0, min(255, n)) for n in care) // 256))
    expression = max(1, min(5, int(core.get("ui", {}).get("expression_stage", 1))))
    trait = str(core.get("personality", {}).get("active_trait", "unexpressed"))
    trait_stage = max(0, min(5, int(core.get("personality", {}).get("trait_stage", 0))))
    return {"morph_id": morph["morph_id"], "element": element, "care": care_level,
            "expression": expression, "trait": trait, "trait_stage": trait_stage,
            "snapshot_digest": morph["snapshot_digest"]}


def _move(profile: dict[str, Any], tier: str, seed: str) -> dict[str, Any]:
    words_b, words_c = pool(profile["element"], "B"), pool(profile["element"], "C")
    digest = sha256(f"{seed}|{profile['morph_id']}|{tier}".encode()).digest()
    name = f"{words_b[digest[0] % len(words_b)]} {words_c[digest[1] % len(words_c)]}"
    return {"tier": tier, "name": name, "element": profile["element"]}


def preview(ledger: Any, first_id: str, second_id: str, battle_id: str) -> dict[str, Any]:
    if first_id == second_id:
        raise TransferError("DISTINCT_MORPHS_REQUIRED", "a Morph cannot battle itself")
    morphs = ledger.data.get("morphs", {})
    if first_id not in morphs or second_id not in morphs:
        raise TransferError("NOT_FOUND", "both Morphs must be admitted")
    profiles = [_profile(morphs[first_id]), _profile(morphs[second_id])]
    return {"schema": BATTLE_SCHEMA, "battle_id": battle_id, "mode": "UNRANKED_SPARRING",
            "state": "READY", "participants": [{**p, "moves": [_move(p, t, battle_id) for t in MOVE_TIERS]}
                                                for p in profiles],
            "effects": {"custody": False, "dna": False, "injury": False, "rank": False}}


def resolve(ledger: Any, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    required = {"schema", "battle_id", "first_morph_id", "second_morph_id", "mode"}
    if set(request) != required or request.get("schema") != BATTLE_SCHEMA or request.get("mode") not in MODES:
        raise TransferError("INVALID_BATTLE_REQUEST", "battle request is not admitted")
    battle_id = str(request["battle_id"])
    existing = ledger.data.setdefault("operations", {}).get(battle_id)
    if existing is not None:
        if existing.get("operation_kind") != "BATTLE_BETA" or existing.get("request") != request:
            raise TransferError("REPLAY_MISMATCH", "battle ID is already bound to different facts")
        return deepcopy(existing["result"])
    ready = preview(ledger, str(request["first_morph_id"]), str(request["second_morph_id"]), battle_id)
    profiles = ready["participants"]
    scores = []
    for attacker, defender in (profiles, profiles[::-1]):
        elemental = 2 if ELEMENT_EDGE[attacker["element"]] == defender["element"] else -1 if ELEMENT_EDGE[defender["element"]] == attacker["element"] else 0
        entropy = int.from_bytes(sha256(f"{battle_id}|{attacker['morph_id']}".encode()).digest()[:2], "big") % 5
        scores.append(attacker["care"] * 3 + attacker["expression"] * 2 + attacker["trait_stage"] + elemental + entropy)
    winner = None if scores[0] == scores[1] else profiles[0 if scores[0] > scores[1] else 1]["morph_id"]
    result = {**ready, "state": "COMPLETE", "resolved_at": now.isoformat(),
              "scores": {profiles[0]["morph_id"]: scores[0], profiles[1]["morph_id"]: scores[1]},
              "winner_morph_id": winner, "outcome": "DRAW" if winner is None else "WIN",
              "receipt_digest": sha256(f"{battle_id}|{scores}|{winner}".encode()).hexdigest()}
    ledger.data["operations"][battle_id] = {"operation_kind": "BATTLE_BETA", "state": "COMPLETE",
        "request": deepcopy(request), "result": deepcopy(result), "created_at": now.isoformat()}
    return result


def history(ledger: Any) -> dict[str, Any]:
    rows = [deepcopy(op["result"]) for op in ledger.data.get("operations", {}).values()
            if op.get("operation_kind") == "BATTLE_BETA" and isinstance(op.get("result"), dict)]
    return {"schema": BATTLE_SCHEMA, "mode": "UNRANKED_SPARRING", "battles": rows[-25:]}

