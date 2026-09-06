"""Canonical portable Morph Core and append-only Living Code Chronicle."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
from typing import Any

MORPH_CORE_SCHEMA = "serein.morph-core.v1"
CHRONICLE_SCHEMA = "serein.living-code-chronicle.v1"
MAX_CHRONICLE_EVENTS = 512
PRIMITIVE_ELEMENTS = {"FIRE", "WATER", "EARTH", "AIR"}
PLACES = {"NURSERY", "HORIZON", "SEREIN_GARDENS", "CODE_HAVEN", "VOID"}
AUTHORITY_STATES = {"REMOTE_ACTIVE", "HAOS_ACTIVE", "FROZEN", "STASIS"}
CORE_FIELDS = {"schema", "identity", "life", "state", "embodiment", "chronicle"}
IDENTITY_FIELDS = {"morph_id", "founder_lineage", "device_birth_lineage", "born_at",
                   "generation", "parent_ids", "primitive_element", "genome_version"}
LIFE_FIELDS = {"growth_q16", "care_counts", "relationship_counts", "journey_count",
               "elemental_mastery_q16"}
STATE_FIELDS = {"place", "authority", "active_frame", "needs_q8", "mood", "expression"}
EMBODIMENT_FIELDS = {"body_id", "body_class", "capabilities"}
CHRONICLE_FIELDS = {"schema", "events"}
EVENT_FIELDS = {"event_id", "kind", "observed_at", "source", "place", "frame", "evidence_digest"}
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


def validate_morph_core(core: dict[str, Any]) -> dict[str, Any]:
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
    if old["identity"] != new["identity"]:
        raise MorphCoreError("IDENTITY_CONFLICT", "immutable Morph identity changed")
    for field in ("growth_q16", "journey_count"):
        if new["life"][field] < old["life"][field]:
            raise MorphCoreError("LIFE_REGRESSION", f"{field} regressed")
    for field in ("care_counts", "relationship_counts", "elemental_mastery_q16"):
        for key, value in old["life"][field].items():
            if new["life"][field].get(key, -1) < value:
                raise MorphCoreError("LIFE_REGRESSION", f"{field}.{key} regressed")
    old_events, new_events = old["chronicle"]["events"], new["chronicle"]["events"]
    if new_events[:len(old_events)] != old_events:
        raise MorphCoreError("CHRONICLE_REWRITE", "Living Code Chronicle is append-only")



