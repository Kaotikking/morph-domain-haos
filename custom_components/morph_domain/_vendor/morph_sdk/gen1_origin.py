"""Gen-1 consumer origin transactions.

The module is intentionally pure. Home Assistant supplies durable locking and
storage; this code owns the fail-closed state transitions.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import uuid
from typing import Any

from .morph_core import (
    CHRONICLE_SCHEMA,
    MORPH_NINE_CORE_SCHEMA,
    derive_elemental_voice,
    validate_nine_core,
)
from .transfer import (
    ANDROID_EXTENSION_SCHEMA,
    ENGINE_VERSION,
    MORPH_CORE_LIFE_SCHEMA,
    MorphTransferLedger,
    TransferError,
    _exact,
    canonical_json,
    refresh_snapshot,
    sha256_json,
)

ORIGIN_SCHEMA = "serein.morph-origin.v1"
STARTERS = {"01": "FIRE", "02": "AIR", "03": "EARTH", "04": "WATER"}
PRIVATE_SEREIN_FOUNDERS = {"EMBER", "SPARK", "BREEZE", "SENTINEL", "PULSE"}


def _iso(now: datetime) -> str:
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _starter_operations(ledger: MorphTransferLedger) -> list[dict[str, Any]]:
    return [op for op in ledger.data["operations"].values()
            if op.get("operation_kind") == "GEN1_STARTER_BIRTH"]


def starter_status(ledger: MorphTransferLedger) -> dict[str, Any]:
    claims = _starter_operations(ledger)
    if len(claims) > 1:
        raise TransferError("STARTER_STATE_CONFLICT", "multiple starter claims exist")
    claim = claims[0] if claims else None
    return {
        "schema": ORIGIN_SCHEMA,
        "state": "CLAIMED" if claim else "AVAILABLE",
        "starter_id": claim.get("starter_id") if claim else None,
        "morph_id": claim.get("morph_id") if claim else None,
        "place": claim.get("place") if claim else None,
        "options": [
            {"starter_id": f"L1-{element_id}", "element": element,
             "horizon_state": "SELECTABLE" if claim is None else
                 ("CHOSEN" if claim.get("starter_id") == f"L1-{element_id}" else "UNDISCOVERED")}
            for element_id, element in STARTERS.items()
        ],
        "private_founders_changed": False,
    }


def _birth_core(*, morph_id: str, starter_id: str, element: str,
                birth_lineage: str, born_at: str, genome_sha256: str,
                event_id: str) -> dict[str, Any]:
    identity = {
        "morph_id": morph_id,
        "founder_lineage": starter_id.lower(),
        "device_birth_lineage": birth_lineage,
        "born_at": born_at,
        "generation": 0,
        "parent_ids": [],
        "primitive_element": element,
        "genome_version": "dnav1",
    }
    needs = {"attention": 220, "energy": 220, "food": 220,
             "play": 220, "rest": 220, "water": 220}
    event_digest = hashlib.sha256(
        canonical_json({"morph_id": morph_id, "starter_id": starter_id,
                        "birth_lineage": birth_lineage, "born_at": born_at}).encode()
    ).hexdigest()
    voice = derive_elemental_voice(identity, genome_sha256, element.lower(), "starter-latent", 1)
    core = {
        "schema": MORPH_NINE_CORE_SCHEMA,
        "platform": {"runtime": "haos-morphdomain-v1",
                     "embodiment": {"body_id": "nursery-egg", "body_class": "morph-egg",
                                      "capabilities": ["hatch"]}},
        "root": {"identity": identity, "historic_role": "platform-legendary",
                 "core_origin": "starter-egg", "emergence_event": "starter-claim"},
        "memory": {"life": {"growth_q16": 0, "care_counts": {},
                              "relationship_counts": {}, "journey_count": 0,
                              "elemental_mastery_q16": {}},
                   "chronicle": {"schema": CHRONICLE_SCHEMA, "events": [{
                       "event_id": event_id, "kind": "starter-birth",
                       "observed_at": born_at, "source": "haos-morphdomain",
                       "place": "NURSERY", "frame": "haos-nursery",
                       "evidence_digest": event_digest,
                   }]}},
        "knowledge": {"schema": "serein.morph-knowledge.v1", "learned": {
            f"E-{key}": "CHOSEN" if key == starter_id[-2:] else "HORIZON_UNDISCOVERED"
            for key in STARTERS
        }},
        "ui": {"expression": "egg", "visual_seed": hashlib.sha256((morph_id + "|egg").encode()).hexdigest(),
               "expression_stage": 1},
        "audio": voice,
        "personality": {"mood": "settle", "active_trait": "unexpressed",
                        "trait_origin": "lineage-latent", "trait_stage": 0},
        "modular": {"capabilities": ["hatch"]},
        "cloud": {"place": "NURSERY", "authority": "HAOS_ACTIVE",
                  "active_frame": "haos-nursery", "needs_q8": needs,
                  "reconciliation": "local-first"},
    }
    return validate_nine_core(core)


def create_starter(ledger: MorphTransferLedger, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    _exact(request, {"schema", "event_id", "starter_id"}, "starter request")
    if request["schema"] != ORIGIN_SCHEMA:
        raise TransferError("INVALID_SCHEMA", "starter request schema is not admitted")
    installation_id = str(ledger.data.get("installation_id", ""))
    event_id, starter_id = map(str, (request["event_id"], request["starter_id"]))
    if not event_id or not installation_id or starter_id not in {f"L1-{x}" for x in STARTERS}:
        raise TransferError("INVALID_STARTER", "starter selection is invalid")
    existing_event = ledger.data["operations"].get(event_id)
    if existing_event:
        if (existing_event.get("operation_kind") != "GEN1_STARTER_BIRTH"
                or existing_event.get("starter_id") != starter_id
                or existing_event.get("installation_id") != installation_id):
            raise TransferError("REPLAY_CONFLICT", "starter event id payload changed")
        return deepcopy(existing_event["result"])
    claims = _starter_operations(ledger)
    if claims:
        raise TransferError("STARTER_ALREADY_CLAIMED", "this installation already has a Legendary starter")
    public_or_imported = [morph for morph in ledger.data["morphs"].values()
                          if str(morph.get("founder_id", "")).upper() not in PRIVATE_SEREIN_FOUNDERS]
    if public_or_imported:
        raise TransferError("IMPORT_SUPPRESSES_STARTER", "an imported or existing Morph suppresses starter creation")

    element_id, element = starter_id[-2:], STARTERS[starter_id[-2:]]
    born_at = _iso(now)
    morph_id = f"morph-l1:{element_id.lower()}:{uuid.uuid5(uuid.NAMESPACE_URL, installation_id + '|' + event_id).hex}"
    birth_lineage = f"haos-starter:{installation_id.lower()}:{starter_id.lower()}"
    genome = canonical_json({"schema": "serein.morph-genome.v1", "origin_class": "L1",
                             "starter_id": starter_id, "primitive_element": element,
                             "parents": [], "installation_id": installation_id})
    genome_sha256 = hashlib.sha256(genome.encode()).hexdigest()
    core = _birth_core(morph_id=morph_id, starter_id=starter_id, element=element,
                       birth_lineage=birth_lineage, born_at=born_at,
                       genome_sha256=genome_sha256, event_id=event_id)
    payload = {
        "saved_epoch_seconds": int(now.timestamp()), "behavior": "SETTLE",
        "arousal_q8": 96, "security_q8": 160, "curiosity_q8": 160, "social_q8": 96,
        "fatigue_q8": 35, "food_q8": 220, "water_q8": 220, "play_q8": 220,
        "rest_q8": 220, "attention_q8": 220, "memories": [],
        "engine_extension": {"schema": ANDROID_EXTENSION_SCHEMA, "payload": {},
                             "sha256": sha256_json({})},
        "morph_core": core,
    }
    snapshot = {"schema": MORPH_CORE_LIFE_SCHEMA, "payload": payload,
                "sha256": sha256_json(payload)}
    morph = {
        "morph_id": morph_id, "founder_id": starter_id,
        "device_birth_lineage": birth_lineage, "generation": 1,
        "authority": "HAOS", "engine_state": "ACTIVE_DEFERRED_TICK",
        "engine_version": ENGINE_VERSION, "snapshot": snapshot,
        "genome": genome, "genome_sha256": genome_sha256,
        "snapshot_digest": "", "source_frame": f"haos-installation:{installation_id}",
        "committed_at": born_at,
    }
    refresh_snapshot(morph)
    ledger.data["morphs"][morph_id] = morph
    result = {"schema": ORIGIN_SCHEMA, "state": "STARTER_EGG_CREATED",
              "starter_id": starter_id, "morph_id": morph_id, "place": "NURSERY",
              "snapshot_digest": morph["snapshot_digest"], "authority": "HAOS",
              "parents": [], "private_founders_changed": False}
    ledger.data["operations"][event_id] = {
        "operation_kind": "GEN1_STARTER_BIRTH", "state": "COMMITTED",
        "event_id": event_id, "starter_id": starter_id,
        "installation_id": installation_id, "morph_id": morph_id,
        "place": "NURSERY", "created_at": born_at, "result": deepcopy(result),
    }
    return result

