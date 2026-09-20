"""Home Assistant transport and durable-storage adapter for MorphDomain."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
import uuid
from time import perf_counter
from typing import Any

import voluptuous as vol
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ._vendor.morph_sdk.transfer import *
from ._vendor.morph_sdk.transfer import _exact
from .http_policy import action_is_read, admin_authorized, durable_write_required
from .runtime_metrics import MorphRuntimeMetrics

# Kept explicit for migration auditing and package-contract readback.
STORE_KEY = "morph_domain.transfer"
LEGACY_STORE_KEY = "serein_gateway.morph_transfer"

FRAME_CONTRACTS = {
    "esp32-frame:v1:pet-frame-sentinel": {
        "window_service": "pet_frame_v12_morph_window_update",
        "request_service": "pet_frame_v12_morph_transfer_request_return",
        "import_service": "pet_frame_v12_morph_transfer_import_return",
        "resume_service": "pet_frame_v12_morph_transfer_resume",
        "freeze_service": "pet_frame_v12_morph_transfer_freeze",
        "state_entity": "sensor.pet_frame_v12_6_0_earth_form_sentinel_sentinel_morph_transfer_state",
        "request_entity": "sensor.pet_frame_v12_6_1_wifi_recovery_sentinel_sentinel_morph_return_request",
        "portable_core_entity": "sensor.pet_frame_v12_6_0_earth_form_sentinel_sentinel_morph_portable_core",
        "engine_extension_entity": "sensor.pet_frame_v12_6_0_earth_form_sentinel_sentinel_morph_engine_extension",
        "core_contract_entity": "sensor.pet_frame_v12_6_0_earth_form_sentinel_sentinel_morph_core_contract",
    },
}


def _compact_state(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.startswith("v1|"):
        raise TransferError("FRAME_STATE_INVALID", "frame compact state is not admitted v1")
    result: dict[str, Any] = {}
    for part in text.split("|")[1:]:
        if "=" not in part:
            raise TransferError("FRAME_STATE_INVALID", "frame compact state is malformed")
        key, value = part.split("=", 1)
        result[key] = int(value) if value.isdigit() else value
    return result


def build_frame_recall_offer(morph: dict[str, Any], transfer_id: str,
                             portable_text: str, extension_text: str,
                             contract_text: str, now: datetime) -> dict[str, Any]:
    """Build the exact next-generation offer from a frozen admitted frame."""
    portable = _compact_state(portable_text)
    extension = _compact_state(extension_text)
    contract = _compact_state(contract_text)
    required_portable = {"saved", "behavior", "arousal", "security", "curiosity", "social",
                         "fatigue", "food", "water", "play", "rest", "attention"}
    required_extension = {"birth", "feed_count", "water_count", "play_count", "rest_count",
                          "development", "earth", "growth", "stage", "world", "seen", "encounters"}
    if not required_portable <= portable.keys() or not required_extension <= extension.keys():
        raise TransferError("FRAME_STATE_INCOMPLETE", "frame did not publish the complete portable life state")
    snapshot = deepcopy(morph["snapshot"])
    payload = snapshot["payload"]
    for target, source in {
        "saved_epoch_seconds": "saved", "behavior": "behavior", "arousal_q8": "arousal",
        "security_q8": "security", "curiosity_q8": "curiosity", "social_q8": "social",
        "fatigue_q8": "fatigue", "food_q8": "food", "water_q8": "water",
        "play_q8": "play", "rest_q8": "rest", "attention_q8": "attention",
    }.items():
        payload[target] = portable[source]
    ext_payload = payload["engine_extension"]["payload"]
    ext_payload["birth_epoch"] = extension["birth"]
    ext_payload["care_counts"] = {"feed": extension["feed_count"], "water": extension["water_count"],
                                  "play": extension["play_count"], "rest": extension["rest_count"]}
    ext_payload["development_q8"] = max(int(ext_payload.get("development_q8", 0)), extension["development"])
    mastery = ext_payload.setdefault("elemental_mastery_q16", {})
    mastery["EARTH"] = max(int(mastery.get("EARTH", 0)), extension["earth"])
    ext_payload["growth_q16"] = max(int(ext_payload.get("growth_q16", 0)), extension["growth"])
    ext_payload["expression_stage"] = max(int(ext_payload.get("expression_stage", 0)), extension["stage"])
    ext_payload["world_location"] = extension["world"]
    ext_payload["founder_seen_mask"] = extension["seen"]
    ext_payload["founder_encounters"] = max(int(ext_payload.get("founder_encounters", 0)), extension["encounters"])
    payload["engine_extension"]["sha256"] = sha256_json(ext_payload)
    core = payload.get("morph_core")
    if not isinstance(core, dict):
        raise TransferError("MORPH_CORE_REQUIRED", "frame recall requires the retained nine-core Morph snapshot")
    needs = {"attention": portable["attention"], "energy": 255-portable["fatigue"],
             "food": portable["food"], "play": portable["play"],
             "rest": portable["rest"], "water": portable["water"]}
    if core.get("schema") == "serein.morph-nine-core.v1":
        core["cloud"].update({"active_frame": "haos-horizon", "authority": "HAOS_ACTIVE",
                              "place": "HORIZON", "needs_q8": needs})
        core["personality"]["mood"] = str(portable["behavior"]).lower()
        life = core["memory"]["life"]
    else:
        core["state"].update({"active_frame": "haos-horizon", "authority": "HAOS_ACTIVE",
                              "place": "HORIZON", "mood": str(portable["behavior"]).lower(),
                              "needs_q8": needs})
        life = core["life"]
    life["care_counts"] = deepcopy(ext_payload["care_counts"])
    life["growth_q16"] = max(int(life.get("growth_q16", 0)), extension["growth"])
    life.setdefault("elemental_mastery_q16", {})["earth"] = mastery["EARTH"]
    life.setdefault("relationship_counts", {})["founder_encounters"] = ext_payload["founder_encounters"]
    life["journey_count"] = max(int(life.get("journey_count", 0)), int(contract.get("journeys", 0)))
    snapshot["sha256"] = sha256_json(payload)
    created = now.astimezone(UTC)
    return {"schema": API_SCHEMA, "transfer_id": transfer_id, "morph_id": morph["morph_id"],
            "founder_id": morph["founder_id"], "device_birth_lineage": morph["device_birth_lineage"],
            "source_frame": morph["source_frame"], "target_frame": "HAOS",
            "generation": int(morph["generation"])+1, "predecessor_generation": int(morph["generation"]),
            "created_at": created.isoformat(), "expires_at": (created+timedelta(minutes=5)).isoformat(),
            "engine_version": morph["engine_version"], "genome": morph["genome"],
            "genome_sha256": morph["genome_sha256"], "snapshot": snapshot}

def reflex_notice_content(notice: dict[str, str]) -> tuple[str, str]:
    """Fail closed on unknown reflex kinds instead of sending a false diagnosis."""
    kind = notice["kind"]
    morph_id = notice["morph_id"]
    if kind == "HATCHED":
        return "Morph hatched", f"{morph_id} hatched and received a name in Nursery."
    if kind == "GRADUATED":
        return "Morph graduated", f"{morph_id} moved from Nursery to Horizon."
    if kind == "INTERVENTION":
        return "Morph needs Code Haven review", f"{morph_id} is isolated in Code Haven for Operator review."
    raise ValueError(f"unknown Morph reflex notice kind: {kind}")


class MorphTransferView(HomeAssistantView):
    url = "/api/morph-domain/v1/transfer/{action}"
    name = "api:morph-domain:v1:transfer"
    requires_auth = True

    async def post(self, request: Any, action: str) -> Any:
        if not admin_authorized("transfer", action, request.get("hass_user")):
            return self.json({"ok": False, "error": {"code": "ADMIN_REQUIRED", "message": "administrator authority is required"}}, status_code=403)
        manager: MorphTransferManager = request.app["hass"].data[DATA_KEY]
        try:
            body = await request.json()
            result = await manager.handle(action, body)
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)
        except (json.JSONDecodeError, vol.Invalid, TypeError, ValueError):
            return self.json({"ok": False, "error": {"code": "INVALID_REQUEST", "message": "request is invalid"}}, status_code=400)


class MorphTransferStatusView(HomeAssistantView):
    """Authenticated status read without transfer maintenance or storage writes."""

    url = "/api/morph-domain/v1/transfer/status/{transfer_id}"
    name = "api:morph-domain:v1:transfer:status:get"
    requires_auth = True

    async def get(self, request: Any, transfer_id: str) -> Any:
        manager: MorphTransferManager = request.app["hass"].data[DATA_KEY]
        try:
            result = await manager.handle("status", {"transfer_id": transfer_id})
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)


class MorphTransferManager:
    def __init__(self, hass: HomeAssistant, ledger: MorphTransferLedger) -> None:
        from ._vendor.morph_engine.haos_runtime import build_haos_runtime
        self.hass = hass
        self.store = Store[dict[str, Any]](hass, STORE_VERSION, STORE_KEY, private=True, atomic_writes=True)
        self.ledger = ledger
        self.lock = asyncio.Lock()
        self.metrics = MorphRuntimeMetrics()
        self.domain_runtime = build_haos_runtime(store_loaded=True, ledger_data=ledger.data)

    async def handle(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        from .migration import legacy_engine_enabled
        if action not in {"status", "evidence"} and legacy_engine_enabled(self.hass):
            raise TransferError("ENGINE_CONFLICT", "legacy Morph engine is active")
        async with self.lock:
            now = datetime.now(UTC)
            candidate = MorphTransferLedger(deepcopy(self.ledger.data))
            # Reads observe the last durable state; only the scheduler or a
            # mutation may reconcile expirations and persist a successor.
            maintenance_changed = False if action_is_read("transfer", action) else candidate.reconcile_expired(now)
            self.metrics.record_expiry_reconciliation(changed=maintenance_changed)
            if action == "prepare": result = candidate.prepare_inbound(body, now)
            elif action == "migrate": result = candidate.migrate_to_morph_core(body, now)
            elif action == "align-nine-core": result = candidate.align_existing_nine_core(body, now)
            elif action == "inward-bloom": result = candidate.record_inward_bloom(body, now)
            elif action == "repair-element": result = candidate.repair_primitive_element(body, now)
            elif action == "commit":
                _exact(body, {"transfer_id", "snapshot_digest"}, "commit request")
                result = candidate.commit_inbound(str(body["transfer_id"]), str(body["snapshot_digest"]), now)
            elif action == "status":
                if set(body) not in ({"transfer_id"}, {"return_id"}, {"transfer_id", "include_snapshot"}, {"return_id", "include_snapshot"}):
                    raise TransferError("INVALID_SCHEMA", "status request fields are not exact")
                result = candidate.status(str(body.get("transfer_id") or body.get("return_id")), include_snapshot=bool(body.get("include_snapshot")))
            elif action == "current-snapshot":
                _exact(body, {"morph_id"}, "current snapshot request")
                result = candidate.current_snapshot(str(body["morph_id"]))
            elif action == "evidence":
                _exact(body, {"operation_id"}, "evidence request")
                result = candidate.evidence_bundle(str(body["operation_id"]))
            elif action == "prepare-return": result = candidate.prepare_return(body, now)
            elif action == "commit-return":
                _exact(body, {"return_id", "snapshot_digest"}, "return commit request")
                result = candidate.commit_return(str(body["return_id"]), str(body["snapshot_digest"]), now)
            else: raise TransferError("NOT_FOUND", "unknown transfer action")
            write_required = durable_write_required("transfer", action, maintenance_changed)
            if write_required:
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            self.metrics.record_storage_decision(performed=write_required)
            self.metrics.record_api(started, read=action_is_read("transfer", action))
            return result

    async def handle_habitat(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        """Mutate/read habitat state under the same durable authority lock."""
        from .migration import legacy_engine_enabled
        if action not in {"list", "status", "history", "starter-status", "chronicle-page", "battle-preview", "battle-history"} and legacy_engine_enabled(self.hass):
            raise TransferError("ENGINE_CONFLICT", "legacy Morph engine is active")
        from .morph_habitat import (
            advance_morph,
            care_for_morph,
            habitat_history,
            habitat_list,
            habitat_status,
            place_morph,
            read_environment,
            update_presentation,
            register_founder_axis,
            advance_founder_axis,
        )
        from ._vendor.morph_sdk.gen1_origin import create_starter, hatch_starter, starter_status

        async with self.lock:
            now = datetime.now(UTC)
            candidate = MorphTransferLedger(deepcopy(self.ledger.data))
            # A habitat read must not advance time, expire an operation, or
            # save any Morph state. The scheduler owns elapsed-life work.
            changed = False if action_is_read("habitat", action) or action == "recover-transfers" else candidate.reconcile_expired(now)
            self.metrics.record_expiry_reconciliation(changed=changed)
            # The periodic scheduler is the only owner of elapsed-life advancement.
            # Reading the dashboard/API must never advance life or sample HAOS.
            if not action_is_read("habitat", action):
                if action not in {"game-start", "game-move", "reduce-event"}:
                    environment = read_environment(self.hass, now)
                    for morph in candidate.data["morphs"].values():
                        changed = advance_morph(morph, now, environment) or changed
            if action == "list":
                _exact(body, set(), "list request")
                result = habitat_list(candidate, now)
            elif action == "starter-status":
                _exact(body, set(), "starter status request")
                result = starter_status(candidate)
            elif action == "starter-create":
                result = create_starter(candidate, body, now)
                changed = True
            elif action == "starter-hatch":
                result = hatch_starter(candidate, body, now)
                changed = True
            elif action == "egg-hatch":
                from .morph_habitat import hatch_egg
                result = hatch_egg(candidate, body, now)
                changed = True
            elif action == "status":
                _exact(body, {"morph_id"}, "habitat status request")
                result = habitat_status(candidate, str(body["morph_id"]), now)
            elif action == "window":
                from ._vendor.morph_engine.morph_window import build_morph_window
                _exact(body, {"morph_id"}, "Morph Window request")
                status = habitat_status(candidate, str(body["morph_id"]), now)
                result = build_morph_window(status, candidate.data["operations"], now)
            elif action == "place":
                result = place_morph(candidate, body, now)
                changed = True
            elif action == "care":
                result = care_for_morph(candidate, body, now)
                changed = True
            elif action == "environment-interaction":
                from .morph_habitat import apply_environment_interaction
                _exact(body, {"schema", "event_id", "morph_id", "activity"}, "environment interaction request")
                if body["schema"] != "serein.morph-foundation-reflex.v1":
                    raise TransferError("INVALID_SCHEMA", "environment reflex schema is not admitted")
                result = apply_environment_interaction(candidate, morph_id=str(body["morph_id"]),
                    event_id=str(body["event_id"]), activity=str(body["activity"]), now=now)
                changed = True
            elif action == "code-haven-admit":
                from .morph_habitat import admit_code_haven
                result = admit_code_haven(candidate, body, now)
                changed = True
            elif action == "code-haven-discharge":
                from .morph_habitat import discharge_code_haven
                result = discharge_code_haven(candidate, body, now)
                changed = True
            elif action == "nursery-pair-admit":
                from .morph_habitat import admit_nursery_pair
                result = admit_nursery_pair(candidate, body, now)
                changed = True
            elif action == "void-enter":
                from .morph_habitat import enter_void_stasis
                result = enter_void_stasis(candidate, body, now)
                changed = True
            elif action == "void-withdraw":
                from .morph_habitat import withdraw_void_stasis
                result = withdraw_void_stasis(candidate, body, now)
                changed = True
            elif action == "recover-transfers":
                _exact(body, {"schema", "event_id"}, "transfer recovery request")
                if body["schema"] != "serein.morph-foundation-reflex.v1":
                    raise TransferError("INVALID_SCHEMA", "recovery schema is not admitted")
                before = {key: value.get("state") for key, value in candidate.data["operations"].items()}
                recovered = candidate.reconcile_expired(now)
                after = {key: value.get("state") for key, value in candidate.data["operations"].items()}
                changed_ids = sorted(key for key in after if before.get(key) != after.get(key))
                result = {"schema": "serein.morph-foundation-reflex.v1", "reflex": "TRANSFER_RECOVERY",
                    "event_id": body["event_id"], "changed": recovered, "operation_ids": changed_ids,
                    "state": "RECONCILED" if recovered else "NO_PENDING_RECOVERY"}
                changed = recovered or changed
            elif action == "game-start":
                from .morph_habitat import start_garden_game
                result = start_garden_game(candidate, body, now)
                changed = True
            elif action == "game-move":
                from .morph_habitat import play_garden_game
                result = play_garden_game(candidate, body, now)
                changed = True
            elif action == "reduce-event":
                from ._vendor.morph_engine.event_reducer import reduce_local_event
                from ._vendor.morph_engine.haos_runtime import build_haos_runtime
                _exact(body, {"event", "sern_packet"}, "reducer request")
                domain_runtime = getattr(self, "domain_runtime", None)
                if domain_runtime is None:
                    domain_runtime = build_haos_runtime(store_loaded=True, ledger_data=self.ledger.data)
                result = reduce_local_event(candidate, body["event"], body["sern_packet"], now,
                                            domain_runtime=domain_runtime)
                # The one existing private Store must durably retain committed
                # and rejected tickets before either is acknowledged.
                changed = candidate.data != self.ledger.data
            elif action == "return-frame":
                # The complete frame return is an async, multi-boundary reflex;
                # it owns its lock and durable checkpoints below.
                raise TransferError("INTERNAL_ROUTE", "return-frame must use the transaction reflex")
            elif action == "call":
                # Retained only so old clients fail truthfully. A call receipt is
                # not a custody transfer and must never be exposed as one again.
                raise TransferError("CALL_ONLY_DISABLED", "use the complete return-frame reflex")
            elif action == "correct-event":
                from .morph_habitat import correct_habitat_event
                result = correct_habitat_event(candidate, body, now)
                changed = True
            elif action == "presentation":
                result = update_presentation(candidate, body, now)
                changed = True
            elif action == "register-axis":
                result = register_founder_axis(candidate, body, now)
                changed = True
            elif action == "advance-axis":
                result = advance_founder_axis(candidate, body, now)
                changed = True
            elif action == "history":
                _exact(body, {"morph_id"}, "history request")
                result = habitat_history(candidate, str(body["morph_id"]), now)
            elif action == "chronicle-page":
                from .morph_habitat import chronicle_page
                _exact(body, {"morph_id", "after_sequence", "limit"}, "chronicle page request")
                result = chronicle_page(candidate, str(body["morph_id"]), body["after_sequence"], body["limit"], now)
            elif action == "battle-preview":
                from ._vendor.morph_engine.battle import preview
                _exact(body, {"battle_id", "first_morph_id", "second_morph_id"}, "battle preview request")
                result = preview(candidate, str(body["first_morph_id"]), str(body["second_morph_id"]), str(body["battle_id"]))
            elif action == "battle-history":
                from ._vendor.morph_engine.battle import history
                _exact(body, set(), "battle history request")
                result = history(candidate)
            elif action == "battle-spar":
                from ._vendor.morph_engine.battle import resolve
                result = resolve(candidate, body, now)
                changed = True
            else:
                raise TransferError("NOT_FOUND", "unknown habitat action")
            if changed:
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            self.metrics.record_storage_decision(performed=changed)
            self.metrics.record_api(started, read=action_is_read("habitat", action))
            return result

    async def return_to_frame(self, body: dict[str, Any]) -> dict[str, Any]:
        """Run the destination-owned ESPHome return protocol as one resumable reflex."""
        _exact(body, {"schema", "morph_id", "target_frame"}, "frame return request")
        if body["schema"] != "serein.morph-habitat.v1":
            raise TransferError("INVALID_SCHEMA", "frame return schema is not admitted")
        morph_id = str(body["morph_id"])
        target_frame = str(body["target_frame"])
        contract = FRAME_CONTRACTS.get(target_frame)
        if contract is None:
            raise TransferError("FRAME_REFLEX_UNPROVEN", "this frame has no admitted full-return contract")

        async with self.lock:
            now = datetime.now(UTC)
            candidate = MorphTransferLedger(deepcopy(self.ledger.data))
            candidate.reconcile_expired(now)
            morph = candidate.data["morphs"].get(morph_id)
            if morph is None:
                raise TransferError("NOT_FOUND", "Morph is not admitted")
            if morph.get("source_frame") != target_frame:
                raise TransferError("WRONG_LINEAGE", "return target is not the retained birth frame")
            habitat = morph.get("habitat") or {}
            if morph.get("authority") == "HAOS" and habitat.get("place") != "HORIZON":
                raise TransferError("RETURN_REQUIRES_HORIZON", "only a HAOS-owned Morph in Horizon may return")

            state = self.hass.states.get(contract["state_entity"])
            if state is None or state.state in {"unknown", "unavailable"}:
                raise TransferError("FRAME_UNAVAILABLE", "the destination frame state is unavailable")
            frame_state = str(state.state)
            if frame_state.startswith("FROZEN_FOR_HAOS"):
                if morph.get("authority") != "HAOS":
                    raise TransferError("AUTHORITY_CONFLICT", "frame and HAOS authority states disagree")
                # The destination creates and durably saves the return ID before
                # HAOS freezes its own authority. No HAOS-generated substitute exists.
                await self.hass.services.async_call(
                    "esphome", contract["request_service"], {}, blocking=True,
                )
                frame_state = await self._wait_frame_state(
                    contract["state_entity"], "RETURN_REQUESTED", timeout=12,
                )
            if not frame_state.startswith(("RETURN_REQUESTED", "IMPORTED_INACTIVE", "FRAME_ACTIVE")):
                raise TransferError("FRAME_NOT_READY", "destination frame has no resumable return state")
            return_id = await self._wait_frame_value(
                contract["state_entity"], frame_state.split("|", 1)[0],
                contract["request_entity"], timeout=12,
            )
            if not return_id:
                raise TransferError("DESTINATION_ID_NOT_DURABLE", "frame did not publish its saved return id")

            operation = candidate.data.get("operations", {}).get(return_id)
            if operation is None:
                if morph.get("authority") != "HAOS":
                    raise TransferError("RETURN_JOURNAL_MISSING", "destination request has no HAOS recovery journal")
                expires_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
                prepared = candidate.prepare_return({
                    "schema": API_SCHEMA,
                    "return_id": return_id,
                    "morph_id": morph_id,
                    "target_frame": target_frame,
                    "expires_at": expires_at,
                }, datetime.now(UTC))
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            else:
                prepared = candidate.status(return_id, include_snapshot=True)
                if prepared.get("morph_id") != morph_id or operation.get("target_frame") != target_frame:
                    raise TransferError("RETURN_JOURNAL_CONFLICT", "saved return journal targets another Morph or frame")

            # Portable-life fields remain at the payload root even when the
            # nine-core Morph snapshot is embedded alongside them.
            life = prepared["snapshot"]["payload"]
            service_data = {
                "return_id": return_id,
                "snapshot_digest": prepared["snapshot_digest"],
                "generation": prepared["generation"],
                **{key: life[key] for key in (
                    "saved_epoch_seconds", "behavior", "arousal_q8", "security_q8",
                    "curiosity_q8", "social_q8", "fatigue_q8", "food_q8", "water_q8",
                    "play_q8", "rest_q8", "attention_q8",
                )},
            }
            if frame_state.startswith("RETURN_REQUESTED"):
                await self.hass.services.async_call(
                    "esphome", contract["import_service"], service_data, blocking=True,
                )
                frame_state = await self._wait_frame_state(
                    contract["state_entity"], "IMPORTED_INACTIVE", timeout=12,
                )

            if operation is None or operation.get("state") == "RETURN_PREPARED":
                committed = candidate.commit_return(return_id, prepared["snapshot_digest"], datetime.now(UTC))
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            else:
                committed = candidate.status(return_id)
            if not frame_state.startswith("FRAME_ACTIVE"):
                await self.hass.services.async_call(
                    "esphome", contract["resume_service"],
                    {"return_id": return_id, "snapshot_digest": prepared["snapshot_digest"]},
                    blocking=True,
                )
                frame_state = await self._wait_frame_state(
                    contract["state_entity"], "FRAME_ACTIVE", timeout=12,
                )
            return {
                "schema": "serein.morph-frame-return-result.v1",
                "return_id": return_id,
                "morph_id": morph_id,
                "target_frame": target_frame,
                "snapshot_digest": prepared["snapshot_digest"],
                "generation": prepared["generation"],
                "custody_committed": committed["authority"] == target_frame,
                "destination_state_durable": True,
                "destination_render_verified": False,
                "frame_state": frame_state,
                "operation_state": committed["operation_state"],
            }

    async def recall_from_frame(self, body: dict[str, Any]) -> dict[str, Any]:
        """Freeze an admitted birth frame and atomically reclaim its Morph into Horizon."""
        _exact(body, {"schema", "morph_id", "source_frame"}, "frame recall request")
        if body["schema"] != "serein.morph-habitat.v1":
            raise TransferError("INVALID_SCHEMA", "frame recall schema is not admitted")
        morph_id, source_frame = str(body["morph_id"]), str(body["source_frame"])
        contract = FRAME_CONTRACTS.get(source_frame)
        if contract is None:
            raise TransferError("FRAME_REFLEX_UNPROVEN", "this frame has no admitted full-recall contract")
        async with self.lock:
            now = datetime.now(UTC)
            candidate = MorphTransferLedger(deepcopy(self.ledger.data))
            candidate.reconcile_expired(now)
            morph = candidate.data["morphs"].get(morph_id)
            if morph is None:
                raise TransferError("NOT_FOUND", "Morph is not admitted")
            if morph.get("source_frame") != source_frame:
                raise TransferError("WRONG_LINEAGE", "recall source is not the retained birth frame")
            if morph.get("authority") != source_frame:
                raise TransferError("AUTHORITY_CONFLICT", "birth frame does not own the current generation")
            state = self.hass.states.get(contract["state_entity"])
            state_text = "" if state is None else str(state.state)
            expected = f"FRAME_ACTIVE|generation={morph['generation']}|frozen=no"
            if state_text != expected:
                raise TransferError("FRAME_NOT_READY", "frame generation or authority does not match HAOS")
            transfer_id = f"sentinel-{int(morph['generation']) + 1}-{uuid.uuid4().hex}"
            await self.hass.services.async_call("esphome", contract["freeze_service"],
                                                {"transfer_id": transfer_id}, blocking=True)
            frozen = await self._wait_frame_state(contract["state_entity"], "FROZEN_FOR_HAOS", timeout=12)
            if f"generation={morph['generation']}" not in frozen:
                raise TransferError("GENERATION_CONFLICT", "frame froze a different generation")
            values: dict[str, str] = {}
            for key in ("portable_core_entity", "engine_extension_entity", "core_contract_entity"):
                entity = self.hass.states.get(contract[key])
                value = "" if entity is None else str(entity.state)
                if value in {"", "unknown", "unavailable"}:
                    raise TransferError("FRAME_STATE_INCOMPLETE", "frozen frame state is unavailable")
                values[key] = value
            offer = build_frame_recall_offer(morph, transfer_id, values["portable_core_entity"],
                                             values["engine_extension_entity"],
                                             values["core_contract_entity"], datetime.now(UTC))
            prepared = candidate.prepare_inbound(offer, datetime.now(UTC))
            await self.store.async_save(candidate.data)
            self.ledger = candidate
            active = candidate.commit_inbound(transfer_id, prepared["snapshot_digest"], datetime.now(UTC))
            from ._vendor.morph_engine.habitat import place_morph
            placed = place_morph(candidate, {"schema": "serein.morph-habitat.v1",
                                             "event_id": f"horizon-{transfer_id}",
                                             "morph_id": morph_id, "place": "HORIZON"}, datetime.now(UTC))
            await self.store.async_save(candidate.data)
            self.ledger = candidate
            return {"schema": "serein.morph-frame-recall-result.v1", "transfer_id": transfer_id,
                    "morph_id": morph_id, "source_frame": source_frame,
                    "snapshot_digest": active["snapshot_digest"], "generation": active["generation"],
                    "custody_committed": active["authority"] == "HAOS",
                    "source_state_durable": frozen.startswith("FROZEN_FOR_HAOS"),
                    "destination_state_durable": True, "destination_render_verified": False,
                    "place": placed["place"], "operation_state": active["operation_state"]}

    async def _wait_frame_state(self, entity_id: str, prefix: str, timeout: int) -> str:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            state = self.hass.states.get(entity_id)
            value = "" if state is None else str(state.state)
            if value.startswith(prefix):
                return value
            await asyncio.sleep(0.25)
        raise TransferError("FRAME_ACK_TIMEOUT", f"frame did not acknowledge {prefix}")

    async def _wait_frame_value(self, state_entity: str, state_prefix: str,
                                value_entity: str, timeout: int) -> str:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            state = self.hass.states.get(state_entity)
            value = self.hass.states.get(value_entity)
            state_text = "" if state is None else str(state.state)
            value_text = "" if value is None else str(value.state)
            if state_text.startswith(state_prefix) and value_text not in {"", "unknown", "unavailable"}:
                return value_text
            await asyncio.sleep(0.25)
        raise TransferError("FRAME_ACK_TIMEOUT", "frame did not publish its return request")

    async def tick_habitats(self) -> None:
        """Persist one bounded interval for every HAOS-owned active Morph."""
        from .migration import legacy_engine_enabled
        if legacy_engine_enabled(self.hass):
            return
        from .morph_habitat import (
            advance_morph,
            habitat_status,
            read_environment,
            run_automatic_reflexes,
            run_social_reflexes,
        )
        from ._vendor.morph_engine.morph_window import build_morph_window

        started = perf_counter()
        frame_windows: list[tuple[str, dict[str, Any]]] = []
        async with self.lock:
            now = datetime.now(UTC)
            candidate = MorphTransferLedger(deepcopy(self.ledger.data))
            changed = candidate.reconcile_expired(now)
            self.metrics.record_expiry_reconciliation(changed=changed)
            environment = read_environment(self.hass, now)
            evaluated = 0
            advanced = 0
            for morph in candidate.data["morphs"].values():
                evaluated += 1
                morph_advanced = advance_morph(morph, now, environment)
                advanced += int(morph_advanced)
                changed = morph_advanced or changed
            reflex_changed, notices = run_automatic_reflexes(candidate, now)
            changed = reflex_changed or changed
            social_changed = run_social_reflexes(candidate, now)
            changed = social_changed or changed
            if changed:
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            # Build only reduced, read-only Window packets while the exact
            # ledger generation is locked.  Delivery happens after release so
            # a sleeping/offline Frame can never stall Morph life.
            for morph_id, morph in candidate.data["morphs"].items():
                contract = FRAME_CONTRACTS.get(str(morph.get("source_frame")))
                if not contract or not contract.get("window_service"):
                    continue
                status = habitat_status(candidate, morph_id, now)
                window = build_morph_window(status, candidate.data["operations"], now)
                frame_windows.append((str(contract["window_service"]), {
                    "schema": window["schema"],
                    "morph_id": window["morph_id"],
                    "display_name": window["display_name"],
                    "window_state": window["state"],
                    "authority": window["authority"],
                    "place": window["place"],
                    "custody_revision": int(window["custody_revision"]),
                    "lineage_generation": int(window.get("lineage_generation") or 0),
                    "snapshot_digest": window["snapshot_digest"],
                    "scene_kind": window["scene"]["kind"],
                    "scene_expression": window["scene"]["expression"],
                    "palette_primary": window["avatar"]["palette"][1],
                    "palette_accent": window["avatar"]["palette"][2],
                    "avatar_rows": "/".join(window["avatar"]["rows"]),
                    "avatar_digest": window["avatar"]["avatar_digest"],
                    "window_digest": window["window_digest"],
                }))
            self.metrics.record_storage_decision(performed=changed)
            self.metrics.record_tick(started, evaluated=evaluated, advanced=advanced)
            for notice in notices:
                title, message = reflex_notice_content(notice)
                await self.hass.services.async_call(
                    "persistent_notification", "create",
                    {"notification_id": notice["id"], "title": title, "message": message},
                    blocking=False,
                )
        for service, payload in frame_windows:
            if not self.hass.services.has_service("esphome", service):
                continue
            try:
                await self.hass.services.async_call(
                    "esphome", service, payload, blocking=False,
                )
            except Exception:
                # Presentation delivery is deliberately below custody/life.
                # The next scheduler interval retries without changing truth.
                continue


async def async_setup_morph_transfer(hass: HomeAssistant) -> None:
    if DATA_KEY in hass.data:
        return
    store = Store[dict[str, Any]](hass, STORE_VERSION, STORE_KEY, private=True, atomic_writes=True)
    data = await store.async_load()
    if data is None:
        legacy_store = Store[dict[str, Any]](
            hass, STORE_VERSION, LEGACY_STORE_KEY, private=True, atomic_writes=True
        )
        legacy_data = await legacy_store.async_load()
        if legacy_data is not None:
            # Copy, never move: the old integration remains a rollback source.
            data = deepcopy(legacy_data)
            await store.async_save(data)
    ledger = MorphTransferLedger(data or MorphTransferLedger.empty().data)
    identity_created = False
    if not ledger.data.get("installation_id"):
        ledger.data["installation_id"] = uuid.uuid4().hex
        identity_created = True
    if ledger.reconcile_expired(datetime.now(UTC)):
        await store.async_save(ledger.data)
    elif identity_created:
        await store.async_save(ledger.data)
    manager = MorphTransferManager(hass, ledger)
    manager.store = store
    hass.data[DATA_KEY] = manager
    hass.http.register_view(MorphTransferView)
    hass.http.register_view(MorphTransferStatusView)

