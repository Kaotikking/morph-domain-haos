"""Home Assistant transport and durable-storage adapter for MorphDomain."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
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


class MorphTransferManager:
    def __init__(self, hass: HomeAssistant, ledger: MorphTransferLedger) -> None:
        self.hass = hass
        self.store = Store[dict[str, Any]](hass, STORE_VERSION, STORE_KEY, private=True, atomic_writes=True)
        self.ledger = ledger
        self.lock = asyncio.Lock()
        self.metrics = MorphRuntimeMetrics()

    async def handle(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        from .migration import legacy_engine_enabled
        if action not in {"status", "evidence"} and legacy_engine_enabled(self.hass):
            raise TransferError("ENGINE_CONFLICT", "legacy Morph engine is active")
        async with self.lock:
            now = datetime.now(UTC)
            candidate = MorphTransferLedger(deepcopy(self.ledger.data))
            maintenance_changed = candidate.reconcile_expired(now)
            self.metrics.record_expiry_reconciliation(changed=maintenance_changed)
            if action == "prepare": result = candidate.prepare_inbound(body, now)
            elif action == "migrate": result = candidate.migrate_to_morph_core(body, now)
            elif action == "inward-bloom": result = candidate.record_inward_bloom(body, now)
            elif action == "repair-element": result = candidate.repair_primitive_element(body, now)
            elif action == "commit":
                _exact(body, {"transfer_id", "snapshot_digest"}, "commit request")
                result = candidate.commit_inbound(str(body["transfer_id"]), str(body["snapshot_digest"]), now)
            elif action == "status":
                if set(body) not in ({"transfer_id"}, {"return_id"}, {"transfer_id", "include_snapshot"}, {"return_id", "include_snapshot"}):
                    raise TransferError("INVALID_SCHEMA", "status request fields are not exact")
                result = candidate.status(str(body.get("transfer_id") or body.get("return_id")), include_snapshot=bool(body.get("include_snapshot")))
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
        if action not in {"list", "status", "history"} and legacy_engine_enabled(self.hass):
            raise TransferError("ENGINE_CONFLICT", "legacy Morph engine is active")
        from .morph_habitat import (
            advance_morph,
            care_for_morph,
            habitat_history,
            habitat_list,
            habitat_status,
            call_morph,
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
            changed = candidate.reconcile_expired(now)
            self.metrics.record_expiry_reconciliation(changed=changed)
            # The periodic scheduler is the only owner of elapsed-life advancement.
            # Reading the dashboard/API must never advance life or sample HAOS.
            if not action_is_read("habitat", action):
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
            elif action == "status":
                _exact(body, {"morph_id"}, "habitat status request")
                result = habitat_status(candidate, str(body["morph_id"]), now)
            elif action == "place":
                result = place_morph(candidate, body, now)
                changed = True
            elif action == "care":
                result = care_for_morph(candidate, body, now)
                changed = True
            elif action == "call":
                result = call_morph(candidate, body, now)
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
            else:
                raise TransferError("NOT_FOUND", "unknown habitat action")
            if changed:
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            self.metrics.record_storage_decision(performed=changed)
            self.metrics.record_api(started, read=action_is_read("habitat", action))
            return result

    async def tick_habitats(self) -> None:
        """Persist one bounded interval for every HAOS-owned active Morph."""
        from .migration import legacy_engine_enabled
        if legacy_engine_enabled(self.hass):
            return
        from .morph_habitat import advance_morph, read_environment, run_automatic_reflexes

        started = perf_counter()
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
            if changed:
                await self.store.async_save(candidate.data)
                self.ledger = candidate
            self.metrics.record_storage_decision(performed=changed)
            self.metrics.record_tick(started, evaluated=evaluated, advanced=advanced)
            for notice in notices:
                if notice["kind"] == "GRADUATED":
                    title, message = "Morph graduated", f"{notice['morph_id']} moved from Nursery to Horizon."
                else:
                    title, message = "Morph needs Code Haven review", f"{notice['morph_id']} is isolated in Code Haven for Operator review."
                await self.hass.services.async_call(
                    "persistent_notification", "create",
                    {"notification_id": notice["id"], "title": title, "message": message},
                    blocking=False,
                )


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



