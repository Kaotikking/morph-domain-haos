"""Canonical portable Morph Core and append-only Living Code Chronicle."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any

MORPH_CORE_SCHEMA = "serein.morph-core.v1"
MORPH_NINE_CORE_SCHEMA = "serein.morph-nine-core.v1"
ELEMENTAL_VOICE_SCHEMA = "serein.elemental-voice.v1"
CHRONICLE_SCHEMA = "serein.living-code-chronicle.v1"
MAX_CHRONICLE_EVENTS = 512
PRIMITIVE_ELEMENTS = {"FIRE", "WATER", "EARTH", "AIR"}
PLACES = {"NURSERY", "HORIZON", "SEREIN_GARDENS", "CODE_HAVEN", "VOID"}
AUTHORITY_STATES = {"REMOTE_ACTIVE", "HAOS_ACTIVE", "FROZEN", "STASIS"}
CORE_FIELDS = {"schema", "identity", "life", "state", "embodiment", "chronicle"}
NINE_CORE_FIELDS = {"schema", "platform", "root", "memory", "knowledge", "ui",
                    "audio", "personality", "modular", "cloud"}
IDENTITY_FIELDS = {"morph_id", "founder_lineage", "device_birth_lineage", "born_at",
                   "generation", "parent_ids", "primitive_element", "genome_version"}
LIFE_FIELDS = {"growth_q16", "care_counts", "relationship_counts", "journey_count",
               "elemental_mastery_q16"}
STATE_FIELDS = {"place", "authority", "active_frame", "needs_q8", "mood", "expression"}
EMBODIMENT_FIELDS = {"body_id", "body_class", "capabilities"}
CHRONICLE_FIELDS = {"schema", "events"}
EVENT_FIELDS = {"event_id", "kind", "observed_at", "source", "place", "frame", "evidence_digest"}
ROOT_FIELDS = {"identity", "historic_role", "core_origin", "emergence_event"}
PLATFORM_FIELDS = {"runtime", "embodiment"}
MEMORY_FIELDS = {"life", "chronicle"}
KNOWLEDGE_FIELDS = {"schema", "learned"}
UI_FIELDS = {"expression", "visual_seed", "expression_stage"}
AUDIO_FIELDS = {"schema", "voice_seed", "element_voice", "trait_modifier",
                "expression_level", "render_model", "signature_digest"}
PERSONALITY_FIELDS = {"mood", "active_trait", "trait_origin", "trait_stage"}
MODULAR_FIELDS = {"capabilities"}
CLOUD_FIELDS = {"place", "authority", "active_frame", "needs_q8", "reconciliation"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class MorphCoreError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _exact(value: dict[str, Any], fields: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise MorphCoreError("INVALID_MORPH_CORE", f"{name} fields are not exact")


def _id(value: Any, name: str) -> None:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise MorphCoreError("INVALID_MORPH_CORE", f"{name} is invalid")


def _timestamp(value: Any) -> None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as err:
        raise MorphCoreError("INVALID_MORPH_CORE", "timestamp is invalid") from err
    if parsed.tzinfo is None:
        raise MorphCoreError("INVALID_MORPH_CORE", "timestamp requires timezone")
    parsed.astimezone(UTC)


def _bounded_map(value: Any, maximum: int, name: str) -> None:
    if not isinstance(value, dict) or len(value) > 32:
        raise MorphCoreError("INVALID_MORPH_CORE", f"{name} is invalid")
    for key, amount in value.items():
        _id(key, name)
        if type(amount) is not int or not 0 <= amount <= maximum:
            raise MorphCoreError("INVALID_MORPH_CORE", f"{name} value is invalid")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def derive_elemental_voice(identity: dict[str, Any], genome_sha256: str,
                           element_voice: str, trait_modifier: str,
                           expression_level: int = 1) -> dict[str, Any]:
    """Derive a portable voice recipe; never author per-Morph recordings."""
    if not DIGEST_RE.fullmatch(str(genome_sha256)):
        raise MorphCoreError("INVALID_MORPH_CORE", "genome digest is invalid")
    for value, name in ((element_voice, "element_voice"), (trait_modifier, "trait_modifier")):
        _id(value, name)
    if type(expression_level) is not int or not 1 <= expression_level <= 5:
        raise MorphCoreError("INVALID_MORPH_CORE", "audio expression level is invalid")
    seed_material = {
        "morph_id": identity["morph_id"],
        "device_birth_lineage": identity["device_birth_lineage"],
        "genome_sha256": genome_sha256,
        "element_voice": element_voice,
        "trait_modifier": trait_modifier,
    }
    signature = hashlib.sha256(_canonical(seed_material).encode()).hexdigest()
    return {
        "schema": ELEMENTAL_VOICE_SCHEMA,
        "voice_seed": signature[:16],
        "element_voice": element_voice,
        "trait_modifier": trait_modifier,
        "expression_level": expression_level,
        "render_model": ELEMENTAL_VOICE_SCHEMA,
        "signature_digest": signature,
    }


def validate_nine_core(core: dict[str, Any]) -> dict[str, Any]:
    _exact(core, NINE_CORE_FIELDS, "nine core Morph")
    if core["schema"] != MORPH_NINE_CORE_SCHEMA:
        raise MorphCoreError("INCOMPATIBLE_MORPH_CORE", "nine core schema is not admitted")
    platform, root, memory = core["platform"], core["root"], core["memory"]
    knowledge, ui, audio = core["knowledge"], core["ui"], core["audio"]
    personality, modular, cloud = core["personality"], core["modular"], core["cloud"]
    _exact(platform, PLATFORM_FIELDS, "platform core")
    _id(platform["runtime"], "runtime")
    _exact(root, ROOT_FIELDS, "root core")
    identity = root["identity"]
    _exact(identity, IDENTITY_FIELDS, "identity")
    for field in ("morph_id", "founder_lineage", "device_birth_lineage", "genome_version"):
        _id(identity[field], field)
    _timestamp(identity["born_at"])
    if type(identity["generation"]) is not int or identity["generation"] < 0:
        raise MorphCoreError("INVALID_MORPH_CORE", "generation is invalid")
    if not isinstance(identity["parent_ids"], list) or len(identity["parent_ids"]) > 2:
        raise MorphCoreError("INVALID_MORPH_CORE", "parent_ids is invalid")
    for parent in identity["parent_ids"]: _id(parent, "parent_id")
    if identity["primitive_element"] not in PRIMITIVE_ELEMENTS:
        raise MorphCoreError("INVALID_MORPH_CORE", "primitive element is invalid")
    for field in ("historic_role", "core_origin", "emergence_event"): _id(root[field], field)
    _exact(memory, MEMORY_FIELDS, "memory core")
    legacy = {"schema": MORPH_CORE_SCHEMA, "identity": identity, "life": memory["life"],
              "state": {"place": cloud["place"], "authority": cloud["authority"],
                        "active_frame": cloud["active_frame"], "needs_q8": cloud["needs_q8"],
                        "mood": personality["mood"], "expression": ui["expression"]},
              "embodiment": platform["embodiment"], "chronicle": memory["chronicle"]}
    validate_morph_core(legacy)
    _exact(knowledge, KNOWLEDGE_FIELDS, "knowledge core")
    _id(knowledge["schema"], "knowledge schema")
    if not isinstance(knowledge["learned"], dict) or len(knowledge["learned"]) > 32:
        raise MorphCoreError("INVALID_MORPH_CORE", "knowledge is invalid")
    _exact(ui, UI_FIELDS, "ui core")
    _id(ui["expression"], "expression")
    if not DIGEST_RE.fullmatch(str(ui["visual_seed"])):
        raise MorphCoreError("INVALID_MORPH_CORE", "visual seed is invalid")
    if type(ui["expression_stage"]) is not int or not 1 <= ui["expression_stage"] <= 5:
        raise MorphCoreError("INVALID_MORPH_CORE", "expression stage is invalid")
    _exact(audio, AUDIO_FIELDS, "audio core")
    if audio["schema"] != ELEMENTAL_VOICE_SCHEMA or audio["render_model"] != ELEMENTAL_VOICE_SCHEMA:
        raise MorphCoreError("INVALID_MORPH_CORE", "audio model is invalid")
    if not re.fullmatch(r"[0-9a-f]{16}", str(audio["voice_seed"])):
        raise MorphCoreError("INVALID_MORPH_CORE", "voice seed is invalid")
    for field in ("element_voice", "trait_modifier"): _id(audio[field], field)
    if type(audio["expression_level"]) is not int or not 1 <= audio["expression_level"] <= 5:
        raise MorphCoreError("INVALID_MORPH_CORE", "audio expression level is invalid")
    if not DIGEST_RE.fullmatch(str(audio["signature_digest"])):
        raise MorphCoreError("INVALID_MORPH_CORE", "audio signature is invalid")
    _exact(personality, PERSONALITY_FIELDS, "personality core")
    for field in ("mood", "active_trait", "trait_origin"): _id(personality[field], field)
    if type(personality["trait_stage"]) is not int or not 0 <= personality["trait_stage"] <= 5:
        raise MorphCoreError("INVALID_MORPH_CORE", "trait stage is invalid")
    _exact(modular, MODULAR_FIELDS, "modular core")
    if not isinstance(modular["capabilities"], list) or len(modular["capabilities"]) > 32:
        raise MorphCoreError("INVALID_MORPH_CORE", "capabilities are invalid")
    for capability in modular["capabilities"]: _id(capability, "capability")
    _exact(cloud, CLOUD_FIELDS, "cloud core")
    _id(cloud["reconciliation"], "reconciliation")
    return deepcopy(core)


def awaken_inward_bloom(previous: dict[str, Any], genome_sha256: str,
                        event_id: str, observed_at: str, actor: str,
                        evidence_digest: str) -> dict[str, Any]:
    """Record Dustdevil's one-time Void emergence without advancing life time."""
    old = validate_morph_core(previous)
    if old["schema"] != MORPH_CORE_SCHEMA:
        raise MorphCoreError("INWARD_BLOOM_ALREADY_RECORDED", "Inward Bloom is one-time")
    identity = old["identity"]
    if (identity["generation"] != 1 or len(identity["parent_ids"]) != 2
            or old["state"]["place"] != "VOID" or old["state"]["authority"] != "HAOS_ACTIVE"):
        raise MorphCoreError("INWARD_BLOOM_PRESTATE_MISMATCH", "live-born Void stasis is required")
    for value, name in ((event_id, "event_id"), (actor, "actor")): _id(value, name)
    _timestamp(observed_at)
    if not DIGEST_RE.fullmatch(str(evidence_digest)):
        raise MorphCoreError("INVALID_MORPH_CORE", "evidence digest is invalid")
    chronicle = deepcopy(old["chronicle"])
    chronicle["events"].append({
        "event_id": event_id,
        "kind": "inward-bloom",
        "observed_at": observed_at,
        "source": actor,
        "place": "VOID",
        "frame": "haos-void",
        "evidence_digest": evidence_digest,
    })
    visual_seed = hashlib.sha256((identity["morph_id"] + "|inward-bloom").encode()).hexdigest()
    result = {
        "schema": MORPH_NINE_CORE_SCHEMA,
        "platform": {"runtime": "frame-kernel-v1", "embodiment": deepcopy(old["embodiment"])},
        "root": {"identity": deepcopy(identity), "historic_role": "first-whole",
                 "core_origin": "naturally-developed", "emergence_event": "inward-bloom"},
        "memory": {"life": deepcopy(old["life"]), "chronicle": chronicle},
        "knowledge": {"schema": "serein.morph-knowledge.v1", "learned": {}},
        "ui": {"expression": old["state"]["expression"], "visual_seed": visual_seed,
               "expression_stage": 1},
        "audio": derive_elemental_voice(identity, genome_sha256, "dust", "inward-bloom", 1),
        "personality": {"mood": old["state"]["mood"], "active_trait": "inward-bloom",
                        "trait_origin": "void-emergent", "trait_stage": 0},
        "modular": {"capabilities": deepcopy(old["embodiment"]["capabilities"])},
        "cloud": {"place": "VOID", "authority": "HAOS_ACTIVE", "active_frame": "haos-void",
                  "needs_q8": deepcopy(old["state"]["needs_q8"]), "reconciliation": "local-first"},
    }
    return validate_nine_core(result)


def core_identity(core: dict[str, Any]) -> dict[str, Any]:
    return core["root"]["identity"] if core.get("schema") == MORPH_NINE_CORE_SCHEMA else core["identity"]


def core_life(core: dict[str, Any]) -> dict[str, Any]:
    return core["memory"]["life"] if core.get("schema") == MORPH_NINE_CORE_SCHEMA else core["life"]


def core_state(core: dict[str, Any]) -> dict[str, Any]:
    if core.get("schema") == MORPH_NINE_CORE_SCHEMA:
        return {
            "place": core["cloud"]["place"], "authority": core["cloud"]["authority"],
            "active_frame": core["cloud"]["active_frame"], "needs_q8": core["cloud"]["needs_q8"],
            "mood": core["personality"]["mood"], "expression": core["ui"]["expression"],
        }
    return core["state"]


def set_core_authority(core: dict[str, Any], authority: str) -> None:
    if core.get("schema") == MORPH_NINE_CORE_SCHEMA:
        core["cloud"]["authority"] = authority
    else:
        core["state"]["authority"] = authority


def validate_morph_core(core: dict[str, Any]) -> dict[str, Any]:
    if isinstance(core, dict) and core.get("schema") == MORPH_NINE_CORE_SCHEMA:
        return validate_nine_core(core)
    _exact(core, CORE_FIELDS, "morph core")
    if core["schema"] != MORPH_CORE_SCHEMA:
        raise MorphCoreError("INCOMPATIBLE_MORPH_CORE", "morph core schema is not admitted")
    identity, life, state = core["identity"], core["life"], core["state"]
    embodiment, chronicle = core["embodiment"], core["chronicle"]
    _exact(identity, IDENTITY_FIELDS, "identity")
    for field in ("morph_id", "founder_lineage", "device_birth_lineage", "genome_version"):
        _id(identity[field], field)
    _timestamp(identity["born_at"])
    if type(identity["generation"]) is not int or identity["generation"] < 0:
        raise MorphCoreError("INVALID_MORPH_CORE", "generation is invalid")
    if not isinstance(identity["parent_ids"], list) or len(identity["parent_ids"]) > 2:
        raise MorphCoreError("INVALID_MORPH_CORE", "parent_ids is invalid")
    for parent in identity["parent_ids"]: _id(parent, "parent_id")
    if identity["primitive_element"] not in PRIMITIVE_ELEMENTS:
        raise MorphCoreError("INVALID_MORPH_CORE", "primitive element is invalid")
    _exact(life, LIFE_FIELDS, "life")
    for field in ("growth_q16", "journey_count"):
        if type(life[field]) is not int or not 0 <= life[field] <= 65535:
            raise MorphCoreError("INVALID_MORPH_CORE", f"{field} is invalid")
    _bounded_map(life["care_counts"], 4294967295, "care_counts")
    _bounded_map(life["relationship_counts"], 4294967295, "relationship_counts")
    _bounded_map(life["elemental_mastery_q16"], 65535, "elemental_mastery_q16")
    _exact(state, STATE_FIELDS, "state")
    if state["place"] not in PLACES or state["authority"] not in AUTHORITY_STATES:
        raise MorphCoreError("INVALID_MORPH_CORE", "place or authority is invalid")
    _id(state["active_frame"], "active_frame")
    _bounded_map(state["needs_q8"], 255, "needs_q8")
    for field in ("mood", "expression"): _id(state[field], field)
    _exact(embodiment, EMBODIMENT_FIELDS, "embodiment")
    for field in ("body_id", "body_class"): _id(embodiment[field], field)
    if not isinstance(embodiment["capabilities"], list) or len(embodiment["capabilities"]) > 32:
        raise MorphCoreError("INVALID_MORPH_CORE", "capabilities are invalid")
    for capability in embodiment["capabilities"]: _id(capability, "capability")
    _exact(chronicle, CHRONICLE_FIELDS, "chronicle")
    if (chronicle["schema"] != CHRONICLE_SCHEMA
            or not isinstance(chronicle["events"], list)
            or len(chronicle["events"]) > MAX_CHRONICLE_EVENTS):
        raise MorphCoreError("INVALID_CHRONICLE", "chronicle is invalid")
    seen = set()
    for event in chronicle["events"]:
        _exact(event, EVENT_FIELDS, "chronicle event")
        for field in ("event_id", "kind", "source", "frame"): _id(event[field], field)
        _timestamp(event["observed_at"])
        if event["place"] not in PLACES or not DIGEST_RE.fullmatch(str(event["evidence_digest"])):
            raise MorphCoreError("INVALID_CHRONICLE", "chronicle event evidence is invalid")
        if event["event_id"] in seen:
            raise MorphCoreError("CHRONICLE_REPLAY", "chronicle event id was repeated")
        seen.add(event["event_id"])
    return deepcopy(core)


def verify_successor(previous: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Fail closed on identity rewrite, history loss, or counter regression."""
    old, new = validate_morph_core(previous), validate_morph_core(candidate)
    def parts(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        if value["schema"] == MORPH_NINE_CORE_SCHEMA:
            return value["root"]["identity"], value["memory"]["life"], value["memory"]["chronicle"]["events"]
        return value["identity"], value["life"], value["chronicle"]["events"]
    old_identity, old_life, old_events = parts(old)
    new_identity, new_life, new_events = parts(new)
    if old_identity != new_identity:
        raise MorphCoreError("IDENTITY_CONFLICT", "immutable Morph identity changed")
    for field in ("growth_q16", "journey_count"):
        if new_life[field] < old_life[field]:
            raise MorphCoreError("LIFE_REGRESSION", f"{field} regressed")
    for field in ("care_counts", "relationship_counts", "elemental_mastery_q16"):
        for key, value in old_life[field].items():
            if new_life[field].get(key, -1) < value:
                raise MorphCoreError("LIFE_REGRESSION", f"{field}.{key} regressed")
    if new_events[:len(old_events)] != old_events:
        raise MorphCoreError("CHRONICLE_REWRITE", "Living Code Chronicle is append-only")

