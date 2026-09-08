"""Authenticated, fail-closed Morph transfer ledger for HAOS.

The ledger owns authority transitions; the dashboard is only a mirror.  Android
retains its recovery copy until an authoritative status readback proves the
corresponding commit.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
from typing import Any

try:
    from .morph_core import (MorphCoreError, awaken_inward_bloom, core_identity,
                             core_state, set_core_authority, validate_morph_core,
                             verify_successor)
except ImportError:  # Direct module loading in the focused contract tests.
    import importlib.util
    from pathlib import Path
    _core_spec = importlib.util.spec_from_file_location("morph_core", Path(__file__).with_name("morph_core.py"))
    _core_module = importlib.util.module_from_spec(_core_spec)
    _core_spec.loader.exec_module(_core_module)
    MorphCoreError = _core_module.MorphCoreError
    awaken_inward_bloom = _core_module.awaken_inward_bloom
    core_identity = _core_module.core_identity
    core_state = _core_module.core_state
    set_core_authority = _core_module.set_core_authority
    validate_morph_core = _core_module.validate_morph_core
    verify_successor = _core_module.verify_successor

API_SCHEMA = "serein.morph-transfer.v1"
LIFE_SCHEMA = "serein.android.morph-life-state.v1"
PORTABLE_LIFE_SCHEMA = "serein.morph-life-state.v2"
MORPH_CORE_LIFE_SCHEMA = "serein.morph-life-state.v3"
MORPH_CORE_MIGRATION_SCHEMA = "serein.morph-core-migration.v1"
MORPH_CORE_REPAIR_SCHEMA = "serein.morph-core-repair.v1"
INWARD_BLOOM_SCHEMA = "serein.inward-bloom.v1"
FIRST_WHOLE_MORPH_ID = "morph-child:37ca6f7dfd4fbba83f43ab4e88f8bf90"
MORPH_EVIDENCE_SCHEMA = "serein.morph-evidence-bundle.v1"
CANONICAL_FOUNDER_PRIMITIVES = {"PULSE": "WATER", "SPARK": "AIR"}
ENGINE_VERSION = "android-morph-life-engine.v1"
ESPHOME_ENGINE_VERSION = "esphome-morph-life-engine.v1"
ADMITTED_ENGINES = {ENGINE_VERSION, ESPHOME_ENGINE_VERSION}
ANDROID_EXTENSION_SCHEMA = "serein.android.morph-life-extension.v1"
STORE_KEY = "morph_domain.transfer"
LEGACY_STORE_KEY = "serein_gateway.morph_transfer"
STORE_VERSION = 1
DATA_KEY = "morph_domain_transfer"
MAX_SNAPSHOT_BYTES = 131072
LIFE_FIELDS = {"saved_epoch_seconds", "behavior", "arousal_q8", "security_q8",
               "curiosity_q8", "social_q8", "fatigue_q8", "food_q8", "water_q8",
               "play_q8", "rest_q8", "attention_q8", "memories"}
Q8_FIELDS = LIFE_FIELDS - {"saved_epoch_seconds", "behavior", "memories"}
BEHAVIORS = {"SETTLE", "INVESTIGATE", "PLAY", "DOZE", "FOOD", "WATER", "ATTEND"}
MEMORY_CODES = {"PLAY", "REST", "SOCIAL", "NOVEL"}
MEMORY_CAPACITY = 8
MEMORY_HORIZON_MS = 120000


class TransferError(ValueError):
    """A closed-contract transfer rejection."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _exact(value: dict[str, Any], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise TransferError("INVALID_SCHEMA", f"{name} fields are not exact")


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as err:
        raise TransferError("INVALID_TIME", "timestamp is invalid") from err
    if parsed.tzinfo is None:
        raise TransferError("INVALID_TIME", "timestamp requires timezone")
    return parsed.astimezone(UTC)


def validate_snapshot(snapshot: dict[str, Any]) -> str:
    _exact(snapshot, {"schema", "payload", "sha256"}, "life snapshot")
    if snapshot["schema"] not in {LIFE_SCHEMA, PORTABLE_LIFE_SCHEMA, MORPH_CORE_LIFE_SCHEMA}:
        raise TransferError("INCOMPATIBLE_LIFE_SCHEMA", "life schema is not admitted")
    encoded = canonical_json(snapshot)
    if len(encoded.encode()) > MAX_SNAPSHOT_BYTES:
        raise TransferError("SNAPSHOT_TOO_LARGE", "life snapshot exceeds limit")
    payload = snapshot["payload"]
    if not isinstance(payload, dict):
        raise TransferError("INVALID_LIFE_STATE", "life payload must be an object")
    expected_fields = LIFE_FIELDS if snapshot["schema"] == LIFE_SCHEMA else LIFE_FIELDS | {"engine_extension"}
    if snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA:
        expected_fields |= {"morph_core"}
    _exact(payload, expected_fields, "life payload")
    if snapshot["schema"] in {PORTABLE_LIFE_SCHEMA, MORPH_CORE_LIFE_SCHEMA}:
        extension = payload["engine_extension"]
        if not isinstance(extension, dict):
            raise TransferError("INVALID_ENGINE_EXTENSION", "engine extension must be an object")
        _exact(extension, {"schema", "payload", "sha256"}, "engine extension")
        if not isinstance(extension["schema"], str) or not extension["schema"]:
            raise TransferError("INVALID_ENGINE_EXTENSION", "engine extension schema is required")
        if not isinstance(extension["payload"], dict):
            raise TransferError("INVALID_ENGINE_EXTENSION", "engine extension payload must be an object")
        extension_digest = sha256_json(extension["payload"])
        if not hmac.compare_digest(str(extension["sha256"]), extension_digest):
            raise TransferError("ENGINE_EXTENSION_DIGEST_MISMATCH", "engine extension digest mismatch")
    if snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA:
        try:
            core = validate_morph_core(payload["morph_core"])
        except MorphCoreError as err:
            raise TransferError(err.code, str(err)) from err
    if type(payload["saved_epoch_seconds"]) is not int or payload["saved_epoch_seconds"] <= 0:
        raise TransferError("INVALID_LIFE_STATE", "saved epoch must be positive")
    if payload["behavior"] not in BEHAVIORS:
        raise TransferError("INVALID_LIFE_STATE", "behavior is not admitted")
    for field in Q8_FIELDS:
        if type(payload[field]) is not int or not 0 <= payload[field] <= 255:
            raise TransferError("INVALID_LIFE_STATE", f"{field} must be an integer from 0 to 255")
    if snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA:
        expected_needs = {
            "attention": payload["attention_q8"],
            "energy": 255 - payload["fatigue_q8"],
            "food": payload["food_q8"],
            "play": payload["play_q8"],
            "rest": payload["rest_q8"],
            "water": payload["water_q8"],
        }
        state = core_state(core)
        if state["needs_q8"] != expected_needs or state["mood"] != payload["behavior"].lower():
            raise TransferError("MORPH_CORE_STATE_CONFLICT", "Morph Core state differs from portable life state")
    memories = payload["memories"]
    if not isinstance(memories, list) or len(memories) > MEMORY_CAPACITY:
        raise TransferError("INVALID_LIFE_STATE", "memory collection exceeds admitted capacity")
    for memory in memories:
        if not isinstance(memory, dict):
            raise TransferError("INVALID_LIFE_STATE", "memory must be an object")
        _exact(memory, {"code", "age_ms", "weight"}, "memory")
        if memory["code"] not in MEMORY_CODES:
            raise TransferError("INVALID_LIFE_STATE", "memory code is not admitted")
        if type(memory["age_ms"]) is not int or not 0 <= memory["age_ms"] <= MEMORY_HORIZON_MS:
            raise TransferError("INVALID_LIFE_STATE", "memory age exceeds admitted horizon")
        if type(memory["weight"]) is not int or not 0 <= memory["weight"] <= 255:
            raise TransferError("INVALID_LIFE_STATE", "memory weight must be an integer from 0 to 255")
    expected = sha256_json(payload)
    if not hmac.compare_digest(str(snapshot["sha256"]), expected):
        raise TransferError("DIGEST_MISMATCH", "life snapshot digest mismatch")
    return hashlib.sha256(encoded.encode()).hexdigest()


def refresh_snapshot(morph: dict[str, Any]) -> None:
    """Rebind a locally mutated snapshot and require it to remain admissible."""
    snapshot = morph["snapshot"]
    snapshot["sha256"] = sha256_json(snapshot["payload"])
    morph["snapshot_digest"] = validate_snapshot(snapshot)


@dataclass
class MorphTransferLedger:
    data: dict[str, Any]

    @classmethod
    def empty(cls) -> "MorphTransferLedger":
        return cls({"schema": API_SCHEMA, "morphs": {}, "operations": {}})

    def prepare_inbound(self, request: dict[str, Any], now: datetime) -> dict[str, Any]:
        fields = {"schema", "transfer_id", "morph_id", "founder_id", "device_birth_lineage",
                  "source_frame", "target_frame", "generation", "predecessor_generation",
                  "created_at", "expires_at", "engine_version", "genome", "genome_sha256", "snapshot"}
        _exact(request, fields, "prepare request")
        if request["schema"] != API_SCHEMA or request["target_frame"] != "HAOS":
            raise TransferError("INVALID_TARGET", "request is not HAOS transfer v1")
        if request["engine_version"] not in ADMITTED_ENGINES:
            raise TransferError("INCOMPATIBLE_ENGINE", "life engine is not admitted")
        if request["engine_version"] == ESPHOME_ENGINE_VERSION and request["snapshot"]["schema"] not in {PORTABLE_LIFE_SCHEMA, MORPH_CORE_LIFE_SCHEMA}:
            raise TransferError("INCOMPATIBLE_LIFE_SCHEMA", "ESPHome requires the portable life schema")
        generation, predecessor = request["generation"], request["predecessor_generation"]
        if type(generation) is not int or type(predecessor) is not int or generation <= 0 or predecessor < 0:
            raise TransferError("GENERATION_CONFLICT", "generation values must be positive integers")
        if generation != predecessor + 1:
            raise TransferError("GENERATION_CONFLICT", "generation must immediately succeed predecessor")
        created, expires = _parse_time(request["created_at"]), _parse_time(request["expires_at"])
        if expires <= now.astimezone(UTC) or expires <= created:
            raise TransferError("EXPIRED", "transfer offer expired")
        digest = validate_snapshot(request["snapshot"])
        if request["snapshot"]["schema"] == MORPH_CORE_LIFE_SCHEMA:
            extension = request["snapshot"]["payload"]["engine_extension"]
            if request["engine_version"] == ENGINE_VERSION:
                if extension["schema"] != ANDROID_EXTENSION_SCHEMA or extension["payload"] != {}:
                    raise TransferError("INVALID_ENGINE_EXTENSION", "Android Morph Core extension must use the exact empty v1 envelope")
        if request["snapshot"]["schema"] == MORPH_CORE_LIFE_SCHEMA:
            identity = core_identity(request["snapshot"]["payload"]["morph_core"])
            if (identity["morph_id"] != request["morph_id"]
                    or identity["device_birth_lineage"] != request["device_birth_lineage"]):
                raise TransferError("IDENTITY_CONFLICT", "Morph Core identity differs from transfer envelope")
        if not isinstance(request["genome"], str) or not request["genome"]:
            raise TransferError("INVALID_GENOME", "canonical genome is required")
        genome_digest = hashlib.sha256(request["genome"].encode()).hexdigest()
        if not hmac.compare_digest(str(request["genome_sha256"]), genome_digest):
            raise TransferError("GENOME_DIGEST_MISMATCH", "genome digest mismatch")
        transfer_id, morph_id = str(request["transfer_id"]), str(request["morph_id"])
        existing = self.data["operations"].get(transfer_id)
        fingerprint = sha256_json(request)
        if existing:
            if existing["request_fingerprint"] != fingerprint:
                raise TransferError("REPLAY_CONFLICT", "transfer id payload changed")
            return self.status(transfer_id)
        current = self.data["morphs"].get(morph_id)
        if current is None and predecessor != 0:
            raise TransferError("GENERATION_CONFLICT", "first admitted generation must succeed zero")
        if current and current["authority"] != request["source_frame"]:
            raise TransferError("AUTHORITY_CONFLICT", "source does not own current generation")
        if current and current["generation"] != request["predecessor_generation"]:
            raise TransferError("GENERATION_CONFLICT", "predecessor does not match")
        if current:
            self._verify_identity(current, request)
            old_snapshot, new_snapshot = current["snapshot"], request["snapshot"]
            if old_snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA and new_snapshot["schema"] != MORPH_CORE_LIFE_SCHEMA:
                raise TransferError("LIFE_SCHEMA_DOWNGRADE", "Morph Core v3 cannot downgrade")
            if old_snapshot["schema"] != MORPH_CORE_LIFE_SCHEMA and new_snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA:
                raise TransferError("MORPH_CORE_MIGRATION_REQUIRED", "legacy life requires an attributable migration record")
            if old_snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA and new_snapshot["schema"] == MORPH_CORE_LIFE_SCHEMA:
                try:
                    verify_successor(old_snapshot["payload"]["morph_core"], new_snapshot["payload"]["morph_core"])
                except MorphCoreError as err:
                    raise TransferError(err.code, str(err)) from err
        op = deepcopy(request)
        op.update({"state": "PREPARED", "snapshot_digest": digest,
                   "request_fingerprint": fingerprint, "authority": request["source_frame"],
                   "prepared_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")})
        self.data["operations"][transfer_id] = op
        return self.status(transfer_id)

    def commit_inbound(self, transfer_id: str, snapshot_digest: str, now: datetime) -> dict[str, Any]:
        op = self._op(transfer_id)
        if op["snapshot_digest"] != snapshot_digest:
            raise TransferError("DIGEST_MISMATCH", "commit digest differs")
        if op["state"] == "ACTIVE_HAOS":
            return self.status(transfer_id)
        if op["state"] != "PREPARED":
            raise TransferError("INVALID_STATE", "operation cannot commit inbound")
        if _parse_time(op["expires_at"]) <= now.astimezone(UTC):
            op["state"] = "EXPIRED"
            raise TransferError("EXPIRED", "transfer offer expired")
        current = self.data["morphs"].get(op["morph_id"])
        if current:
            if current["authority"] != op["source_frame"]:
                raise TransferError("AUTHORITY_CONFLICT", "active authority changed")
            if current["generation"] != op["predecessor_generation"]:
                raise TransferError("GENERATION_CONFLICT", "predecessor changed before commit")
            self._verify_identity(current, op)
        elif op["predecessor_generation"] != 0:
            raise TransferError("GENERATION_CONFLICT", "first admitted generation must succeed zero")
        self.data["morphs"][op["morph_id"]] = {
            "morph_id": op["morph_id"], "founder_id": op["founder_id"],
            "device_birth_lineage": op["device_birth_lineage"], "generation": op["generation"],
            "authority": "HAOS", "engine_state": "ACTIVE_DEFERRED_TICK",
            "engine_version": op["engine_version"], "snapshot": deepcopy(op["snapshot"]),
            "genome": op["genome"], "genome_sha256": op["genome_sha256"],
            "snapshot_digest": op["snapshot_digest"], "source_frame": op["source_frame"],
            "committed_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")}
        op["state"], op["authority"] = "ACTIVE_HAOS", "HAOS"
        return self.status(transfer_id)

    def migrate_to_morph_core(self, request: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Atomically replace one legacy snapshot with its attributable v3 form.

        Migration is deliberately not an authority transition or a transfer
        generation.  The current owner remains active while the exact current
        legacy checkpoint is upgraded in place.
        """
        fields = {"schema", "migration_id", "morph_id", "founder_id",
                  "device_birth_lineage", "genome_sha256", "source_frame", "current_authority", "generation",
                  "predecessor_snapshot_digest", "created_at", "actor", "reason",
                  "evidence_digest", "snapshot"}
        _exact(request, fields, "migration request")
        if request["schema"] != MORPH_CORE_MIGRATION_SCHEMA:
            raise TransferError("INVALID_SCHEMA", "migration schema is not admitted")
        migration_id = str(request["migration_id"])
        if not migration_id or not isinstance(request["actor"], str) or not request["actor"]:
            raise TransferError("INVALID_ATTRIBUTION", "migration id and actor are required")
        if not isinstance(request["reason"], str) or not request["reason"]:
            raise TransferError("INVALID_ATTRIBUTION", "migration reason is required")
        if not isinstance(request["evidence_digest"], str) or not hmac.compare_digest(
                request["evidence_digest"], request["evidence_digest"].lower()
        ) or len(request["evidence_digest"]) != 64:
            raise TransferError("INVALID_ATTRIBUTION", "migration evidence digest is invalid")
        try:
            int(request["evidence_digest"], 16)
        except ValueError as err:
            raise TransferError("INVALID_ATTRIBUTION", "migration evidence digest is invalid") from err
        created = _parse_time(request["created_at"])
        if created > now.astimezone(UTC):
            raise TransferError("INVALID_TIME", "migration attribution is in the future")
        fingerprint = sha256_json(request)
        existing = self.data["operations"].get(migration_id)
        if existing:
            if existing.get("operation_kind") != "MORPH_CORE_MIGRATION" or existing["request_fingerprint"] != fingerprint:
                raise TransferError("REPLAY_CONFLICT", "migration id payload changed")
            return deepcopy(existing.get("completion_receipt") or self.status(migration_id))
        morph = self.data["morphs"].get(str(request["morph_id"]))
        if not morph:
            raise TransferError("NOT_FOUND", "Morph is not admitted")
        for field in ("morph_id", "founder_id", "device_birth_lineage", "genome_sha256", "source_frame"):
            if morph[field] != request[field]:
                raise TransferError("IDENTITY_CONFLICT", f"migration rewrites immutable {field}")
        if morph["authority"] != request["current_authority"]:
            raise TransferError("AUTHORITY_CONFLICT", "migration authority differs from current authority")
        if type(request["generation"]) is not int or morph["generation"] != request["generation"]:
            raise TransferError("GENERATION_CONFLICT", "migration generation differs from current generation")
        if not hmac.compare_digest(str(request["predecessor_snapshot_digest"]), morph["snapshot_digest"]):
            raise TransferError("PREDECESSOR_DIGEST_MISMATCH", "migration predecessor digest differs from current checkpoint")
        if morph["snapshot"]["schema"] == MORPH_CORE_LIFE_SCHEMA:
            raise TransferError("LIFE_SCHEMA_DOWNGRADE", "current Morph already carries v3")
        predecessor_schema = morph["snapshot"]["schema"]
        if predecessor_schema not in {LIFE_SCHEMA, PORTABLE_LIFE_SCHEMA}:
            raise TransferError("INCOMPATIBLE_LIFE_SCHEMA", "only legacy v1/v2 life can migrate to Morph Core v3")
        if request["snapshot"].get("schema") != MORPH_CORE_LIFE_SCHEMA:
            raise TransferError("LIFE_SCHEMA_DOWNGRADE", "migration target must be Morph Core v3")
        requested_core_state = request["snapshot"].get("payload", {}).get("morph_core", {}).get("state", {})
        if (requested_core_state.get("place") != "CODE_HAVEN"
                or requested_core_state.get("active_frame") != "haos-code-haven"):
            raise TransferError(
                "CODE_HAVEN_REQUIRED",
                "Morph Core writes are admitted only inside Code Haven",
            )
        digest = validate_snapshot(request["snapshot"])
        core_identity = request["snapshot"]["payload"]["morph_core"]["identity"]
        if (core_identity["morph_id"] != morph["morph_id"]
                or core_identity["device_birth_lineage"] != morph["device_birth_lineage"]):
            raise TransferError("IDENTITY_CONFLICT", "migration rewrites immutable Morph identity")
        migrated_payload = request["snapshot"]["payload"]
        legacy_payload = morph["snapshot"]["payload"]
        for field, value in legacy_payload.items():
            if migrated_payload.get(field) != value:
                raise TransferError("LEGACY_LIFE_REWRITE", f"migration rewrites legacy {field}")
        if predecessor_schema == LIFE_SCHEMA:
            extension = migrated_payload["engine_extension"]
            if (morph["engine_version"] != ENGINE_VERSION
                    or extension["schema"] != ANDROID_EXTENSION_SCHEMA
                    or extension["payload"] != {}):
                raise TransferError("INVALID_ENGINE_EXTENSION", "v1 migration requires the exact empty Android extension")
            core = migrated_payload["morph_core"]
            if core["life"] != {"growth_q16": 0, "care_counts": {}, "relationship_counts": {},
                               "journey_count": 0, "elemental_mastery_q16": {}}:
                raise TransferError("INVENTED_HISTORY", "v1 migration cannot invent missing accumulated life")
            events = core["chronicle"]["events"]
            expected_event = {
                "event_id": migration_id,
                "kind": "migration",
                "observed_at": request["created_at"],
                "source": request["actor"],
                "place": core["state"]["place"],
                "frame": core["state"]["active_frame"],
                "evidence_digest": request["evidence_digest"],
            }
            if events != [expected_event]:
                raise TransferError("INVENTED_HISTORY", "v1 migration admits only its attributable migration event")
        predecessor_snapshot = deepcopy(morph["snapshot"])
        op = deepcopy(request)
        op.update({"operation_kind": "MORPH_CORE_MIGRATION", "state": "MIGRATED",
                   "authority": morph["authority"], "snapshot_digest": digest,
                   "request_fingerprint": fingerprint,
                   "predecessor_schema": morph["snapshot"]["schema"],
                   "predecessor_snapshot": predecessor_snapshot,
                   "completed_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")})
        morph["snapshot"] = deepcopy(request["snapshot"])
        morph["snapshot_digest"] = digest
        morph["migrated_at"] = op["completed_at"]
        morph["migration_id"] = migration_id
        self.data["operations"][migration_id] = op
        op["completion_receipt"] = self.status(migration_id, include_snapshot=True)
        return deepcopy(op["completion_receipt"])

    def record_inward_bloom(self, request: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Record Dustdevil's unique Void-origin transition to nine portable Cores."""
        fields = {"schema", "bloom_id", "morph_id", "current_authority", "generation",
                  "predecessor_snapshot_digest", "created_at", "actor", "evidence_digest"}
        _exact(request, fields, "Inward Bloom request")
        if request["schema"] != INWARD_BLOOM_SCHEMA:
            raise TransferError("INVALID_SCHEMA", "Inward Bloom schema is not admitted")
        bloom_id = str(request["bloom_id"])
        fingerprint = sha256_json(request)
        existing = self.data["operations"].get(bloom_id)
        if existing:
            if existing.get("operation_kind") != "INWARD_BLOOM" or existing["request_fingerprint"] != fingerprint:
                raise TransferError("REPLAY_CONFLICT", "Inward Bloom id payload changed")
            return deepcopy(existing["completion_receipt"])
        morph = self.data["morphs"].get(str(request["morph_id"]))
        if not morph or morph["morph_id"] != FIRST_WHOLE_MORPH_ID or morph["founder_id"] != "DESCENDANT":
            raise TransferError("INWARD_BLOOM_NOT_ELIGIBLE", "only Dustdevil owns the first Inward Bloom")
        if morph["authority"] != request["current_authority"] or morph["authority"] != "HAOS":
            raise TransferError("AUTHORITY_CONFLICT", "HAOS authority is required")
        if morph["generation"] != request["generation"]:
            raise TransferError("GENERATION_CONFLICT", "generation differs from current state")
        if not hmac.compare_digest(str(request["predecessor_snapshot_digest"]), morph["snapshot_digest"]):
            raise TransferError("PREDECESSOR_DIGEST_MISMATCH", "predecessor differs from frozen checkpoint")
        if morph.get("habitat", {}).get("place") != "VOID" or morph.get("habitat", {}).get("engine_state") != "STASIS":
            raise TransferError("INWARD_BLOOM_PRESTATE_MISMATCH", "Dustdevil must be in Void stasis")
        for field in ("bloom_id", "actor"):
            if not isinstance(request[field], str) or not request[field]:
                raise TransferError("INVALID_ATTRIBUTION", f"{field} is required")
        created = _parse_time(request["created_at"])
        if created > now.astimezone(UTC):
            raise TransferError("INVALID_TIME", "Inward Bloom attribution is in the future")
        if not isinstance(request["evidence_digest"], str) or len(request["evidence_digest"]) != 64:
            raise TransferError("INVALID_ATTRIBUTION", "evidence digest is invalid")
        try: int(request["evidence_digest"], 16)
        except ValueError as err: raise TransferError("INVALID_ATTRIBUTION", "evidence digest is invalid") from err
        if morph["snapshot"]["schema"] != MORPH_CORE_LIFE_SCHEMA:
            raise TransferError("INCOMPATIBLE_LIFE_SCHEMA", "Inward Bloom requires portable Morph Core life")
        predecessor = deepcopy(morph["snapshot"])
        try:
            candidate = awaken_inward_bloom(
                predecessor["payload"]["morph_core"], morph["genome_sha256"], bloom_id,
                request["created_at"], request["actor"], request["evidence_digest"],
            )
        except MorphCoreError as err:
            raise TransferError(err.code, str(err)) from err
        morph["snapshot"]["payload"]["morph_core"] = candidate
        refresh_snapshot(morph)
        op = deepcopy(request)
        op.update({"operation_kind": "INWARD_BLOOM", "state": "RECORDED",
                   "authority": "HAOS", "snapshot_digest": morph["snapshot_digest"],
                   "snapshot": deepcopy(morph["snapshot"]),
                   "predecessor_snapshot": predecessor, "request_fingerprint": fingerprint,
                   "completed_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")})
        self.data["operations"][bloom_id] = op
        op["completion_receipt"] = self.status(bloom_id, include_snapshot=True)
        return deepcopy(op["completion_receipt"])

    def repair_primitive_element(self, request: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Correct one proven founder-element error, only inside Code Haven."""
        fields = {"schema", "repair_id", "morph_id", "current_authority", "generation",
                  "predecessor_snapshot_digest", "expected_current_element", "corrected_element",
                  "created_at", "actor", "reason", "evidence_digest"}
        _exact(request, fields, "Morph Core repair request")
        if request["schema"] != MORPH_CORE_REPAIR_SCHEMA:
            raise TransferError("INVALID_SCHEMA", "repair schema is not admitted")
        repair_id = str(request["repair_id"])
        if not repair_id or not request["actor"] or not request["reason"]:
            raise TransferError("INVALID_ATTRIBUTION", "repair id, actor, and reason are required")
        if (not isinstance(request["evidence_digest"], str)
                or len(request["evidence_digest"]) != 64):
            raise TransferError("INVALID_ATTRIBUTION", "repair evidence digest is invalid")
        try:
            int(request["evidence_digest"], 16)
        except ValueError as err:
            raise TransferError("INVALID_ATTRIBUTION", "repair evidence digest is invalid") from err
        created = _parse_time(request["created_at"])
        if created > now.astimezone(UTC):
            raise TransferError("INVALID_TIME", "repair attribution is in the future")
        fingerprint = sha256_json(request)
        existing = self.data["operations"].get(repair_id)
        if existing:
            if existing.get("operation_kind") != "MORPH_CORE_REPAIR" or existing["request_fingerprint"] != fingerprint:
                raise TransferError("REPLAY_CONFLICT", "repair id payload changed")
            return deepcopy(existing.get("completion_receipt") or self.status(repair_id, include_snapshot=True))
        morph = self.data["morphs"].get(str(request["morph_id"]))
        if not morph:
            raise TransferError("NOT_FOUND", "Morph is not admitted")
        if morph["authority"] != "HAOS" or request["current_authority"] != "HAOS":
            raise TransferError("AUTHORITY_CONFLICT", "Code Haven repair requires HAOS authority")
        if morph["generation"] != request["generation"]:
            raise TransferError("GENERATION_CONFLICT", "repair generation differs from current generation")
        if not hmac.compare_digest(str(request["predecessor_snapshot_digest"]), morph["snapshot_digest"]):
            raise TransferError("PREDECESSOR_DIGEST_MISMATCH", "repair predecessor differs from current checkpoint")
        if morph["snapshot"]["schema"] != MORPH_CORE_LIFE_SCHEMA:
            raise TransferError("INCOMPATIBLE_LIFE_SCHEMA", "repair requires Morph Core v3")
        core = morph["snapshot"]["payload"]["morph_core"]
        if core["state"]["place"] != "CODE_HAVEN" or core["state"]["active_frame"] != "haos-code-haven":
            raise TransferError("CODE_HAVEN_REQUIRED", "Morph Core repair is admitted only inside Code Haven")
        identity = core["identity"]
        if identity["primitive_element"] != request["expected_current_element"]:
            raise TransferError("REPAIR_PRESTATE_MISMATCH", "current primitive element differs from repair prestate")
        canonical = CANONICAL_FOUNDER_PRIMITIVES.get(morph["founder_id"])
        if canonical is None or request["corrected_element"] != canonical:
            raise TransferError("NONCANONICAL_REPAIR", "requested primitive is not canonical for this founder")
        predecessor_snapshot = deepcopy(morph["snapshot"])
        identity["primitive_element"] = canonical
        core["chronicle"]["events"].append({
            "event_id": repair_id, "kind": "lineage-correction",
            "observed_at": request["created_at"], "source": request["actor"],
            "place": "CODE_HAVEN", "frame": "haos-code-haven",
            "evidence_digest": request["evidence_digest"],
        })
        refresh_snapshot(morph)
        op = deepcopy(request)
        op.update({"operation_kind": "MORPH_CORE_REPAIR", "state": "REPAIRED",
                   "authority": "HAOS", "snapshot_digest": morph["snapshot_digest"],
                   "snapshot": deepcopy(morph["snapshot"]), "founder_id": morph["founder_id"],
                   "device_birth_lineage": morph["device_birth_lineage"],
                   "genome_sha256": morph["genome_sha256"], "request_fingerprint": fingerprint,
                   "predecessor_snapshot": predecessor_snapshot,
                   "completed_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")})
        self.data["operations"][repair_id] = op
        op["completion_receipt"] = self.status(repair_id, include_snapshot=True)
        return deepcopy(op["completion_receipt"])

    def prepare_return(self, request: dict[str, Any], now: datetime) -> dict[str, Any]:
        _exact(request, {"schema", "return_id", "morph_id", "target_frame", "expires_at"}, "return request")
        if request["schema"] != API_SCHEMA:
            raise TransferError("INVALID_SCHEMA", "return schema is not admitted")
        return_id = str(request["return_id"])
        existing = self.data["operations"].get(return_id)
        fingerprint = sha256_json(request)
        if existing:
            if existing["request_fingerprint"] != fingerprint:
                raise TransferError("REPLAY_CONFLICT", "return id payload changed")
            return self.status(return_id, include_snapshot=True)
        morph = self.data["morphs"].get(str(request["morph_id"]))
        if not morph or morph["authority"] != "HAOS":
            raise TransferError("AUTHORITY_CONFLICT", "HAOS is not active authority")
        if request["target_frame"] != morph["source_frame"]:
            raise TransferError("WRONG_LINEAGE", "return target is not original Android frame")
        if _parse_time(request["expires_at"]) <= now.astimezone(UTC):
            raise TransferError("EXPIRED", "return offer expired")
        # Freeze the portable v3 authority state before serializing the exact
        # Android offer.  HAOS retains this recovery checkpoint until commit.
        if morph["snapshot"]["schema"] == MORPH_CORE_LIFE_SCHEMA:
            validate_snapshot(morph["snapshot"])
            set_core_authority(morph["snapshot"]["payload"]["morph_core"], "FROZEN")
            refresh_snapshot(morph)
        morph["authority"], morph["engine_state"] = "FROZEN_FOR_RETURN", "FROZEN"
        op = {**deepcopy(request), "state": "RETURN_PREPARED", "authority": "HAOS_FROZEN",
              "request_fingerprint": fingerprint, "snapshot": deepcopy(morph["snapshot"]),
              "snapshot_digest": morph["snapshot_digest"], "founder_id": morph["founder_id"],
              "device_birth_lineage": morph["device_birth_lineage"], "generation": morph["generation"],
              "genome": morph["genome"], "genome_sha256": morph["genome_sha256"],
              "engine_version": morph["engine_version"],
              "prepared_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")}
        self.data["operations"][return_id] = op
        return self.status(return_id, include_snapshot=True)

    def commit_return(self, return_id: str, snapshot_digest: str, now: datetime) -> dict[str, Any]:
        op = self._op(return_id)
        if op["snapshot_digest"] != snapshot_digest:
            raise TransferError("DIGEST_MISMATCH", "return commit digest differs")
        if op["state"] == "RETURNED_ANDROID":
            return self.status(return_id)
        if op["state"] != "RETURN_PREPARED":
            raise TransferError("INVALID_RETURN_COMMIT", "return commit does not match prepared snapshot")
        if _parse_time(op["expires_at"]) <= now.astimezone(UTC):
            raise TransferError("EXPIRED", "return offer expired")
        morph = self.data["morphs"][op["morph_id"]]
        if morph["authority"] != "FROZEN_FOR_RETURN":
            raise TransferError("AUTHORITY_CONFLICT", "HAOS return freeze was lost")
        if morph["generation"] != op["generation"] or morph["snapshot_digest"] != op["snapshot_digest"]:
            raise TransferError("RETURN_CHECKPOINT_CONFLICT", "HAOS return checkpoint changed")
        morph["authority"], morph["engine_state"] = op["target_frame"], "REMOTE_ACTIVE"
        op["state"], op["authority"] = "RETURNED_ANDROID", op["target_frame"]
        op["committed_at"] = now.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return self.status(return_id)

    def status(self, transfer_id: str, include_snapshot: bool = False) -> dict[str, Any]:
        op = self._op(transfer_id)
        result = {key: op[key] for key in ("schema", "transfer_id", "morph_id", "snapshot_digest", "generation") if key in op}
        if "return_id" in op:
            result["return_id"] = op["return_id"]
        if "migration_id" in op:
            result["migration_id"] = op["migration_id"]
        if "bloom_id" in op:
            result["bloom_id"] = op["bloom_id"]
        morph = self.data["morphs"].get(op["morph_id"])
        if morph:
            result["current_generation"] = morph["generation"]
            result["current_snapshot_digest"] = morph["snapshot_digest"]
        else:
            result["current_generation"] = None
            result["current_snapshot_digest"] = None
        result["operation_state"] = op["state"]
        result["authority"] = morph["authority"] if morph else op["authority"]
        result["morph_state"] = morph["engine_state"] if morph else "NOT_ACTIVE"
        if include_snapshot and "snapshot" in op:
            result["snapshot"] = deepcopy(op["snapshot"])
            # Migration receipts carry identity and the migrated snapshot, but
            # intentionally omit transfer-only envelope fields.  Return every
            # attributable field that the operation actually owns instead of
            # turning a valid migration readback into an internal error.
            for field in ("founder_id", "device_birth_lineage", "engine_version",
                          "genome", "genome_sha256"):
                if field in op:
                    result[field] = op[field]
        result["receipt_digest"] = sha256_json(result)
        return result

    def evidence_bundle(self, operation_id: str) -> dict[str, Any]:
        """Return authenticated migration/repair lineage without changing state."""
        op = self._op(operation_id)
        kind = op.get("operation_kind")
        if kind not in {"MORPH_CORE_MIGRATION", "MORPH_CORE_REPAIR"}:
            raise TransferError("EVIDENCE_NOT_AVAILABLE", "operation has no admitted evidence bundle")
        if "predecessor_snapshot" not in op or "completion_receipt" not in op:
            raise TransferError(
                "HISTORICAL_EVIDENCE_UNAVAILABLE",
                "operation predates immutable evidence capture and must not be reconstructed",
            )
        request_fields = ({"schema", "migration_id", "morph_id", "founder_id",
            "device_birth_lineage", "genome_sha256", "source_frame", "current_authority",
            "generation", "predecessor_snapshot_digest", "created_at", "actor", "reason",
            "evidence_digest", "snapshot"} if kind == "MORPH_CORE_MIGRATION" else
            {"schema", "repair_id", "morph_id", "current_authority", "generation",
             "predecessor_snapshot_digest", "expected_current_element", "corrected_element",
             "created_at", "actor", "reason", "evidence_digest"})
        request = {key: deepcopy(op[key]) for key in request_fields}
        result = deepcopy(op["completion_receipt"])
        bundle = {"schema": MORPH_EVIDENCE_SCHEMA, "operation_id": operation_id,
                  "operation_kind": kind, "morph_id": op["morph_id"],
                  "predecessor_snapshot": deepcopy(op["predecessor_snapshot"]),
                  "request": request, "result": result}
        bundle["bundle_digest"] = sha256_json(bundle)
        return bundle

    def reconcile_expired(self, now: datetime) -> bool:
        """Recover expired interrupted handoffs without creating two owners."""
        changed = False
        for op in self.data["operations"].values():
            if op["state"] == "PREPARED" and _parse_time(op["expires_at"]) <= now:
                op["state"] = "EXPIRED"
                changed = True
            elif op["state"] == "RETURN_PREPARED" and _parse_time(op["expires_at"]) <= now:
                morph = self.data["morphs"].get(op["morph_id"])
                if (morph and morph["authority"] == "FROZEN_FOR_RETURN"
                        and morph["generation"] == op["generation"]
                        and morph["snapshot_digest"] == op["snapshot_digest"]):
                    morph["authority"], morph["engine_state"] = "HAOS", "ACTIVE_DEFERRED_TICK"
                    if morph["snapshot"]["schema"] == MORPH_CORE_LIFE_SCHEMA:
                        set_core_authority(morph["snapshot"]["payload"]["morph_core"], "HAOS_ACTIVE")
                        refresh_snapshot(morph)
                op["state"], op["authority"] = "RETURN_EXPIRED", "HAOS"
                changed = True
        return changed

    @staticmethod
    def _verify_identity(current: dict[str, Any], candidate: dict[str, Any]) -> None:
        for field in ("morph_id", "founder_id", "device_birth_lineage", "genome_sha256", "source_frame"):
            if current[field] != candidate[field]:
                raise TransferError("IDENTITY_CONFLICT", f"immutable {field} changed")

    def _op(self, transfer_id: str) -> dict[str, Any]:
        try:
            return self.data["operations"][str(transfer_id)]
        except KeyError as err:
            raise TransferError("NOT_FOUND", "transfer operation not found") from err

