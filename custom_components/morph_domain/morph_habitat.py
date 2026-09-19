"""Home Assistant API, service, scheduler, and SERN adapter for MorphDomain."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .morph_transfer import DATA_KEY, MorphTransferManager, TransferError
from .http_policy import admin_authorized
from .sern import SernEnvelopeError, validate_envelope
from ._vendor.morph_engine.habitat import *


_LOGGER = logging.getLogger(__name__)


class MorphSernView(HomeAssistantView):
    """Validate and acknowledge SERN control envelopes without moving custody."""

    url = "/api/morph-domain/v1/sern/validate"
    name = "api:morph-domain:v1:sern:validate"
    requires_auth = True

    async def post(self, request: Any) -> Any:
        try:
            envelope = validate_envelope(await request.json())
            return self.json({
                "ok": True,
                "schema": envelope.as_dict()["schema"],
                "message_id": envelope.message_id,
                "digest": envelope.digest,
                "custody_changed": False,
            })
        except SernEnvelopeError as err:
            return self.json(
                {"ok": False, "error": {"code": err.code, "message": str(err)}},
                status_code=400,
            )
        except (TypeError, ValueError):
            return self.json(
                {"ok": False, "error": {"code": "INVALID_REQUEST", "message": "request is invalid"}},
                status_code=400,
            )


class MorphHabitatView(HomeAssistantView):
    url = "/api/morph-domain/v1/habitat/{action}"
    name = "api:morph-domain:v1:habitat"
    requires_auth = True

    async def post(self, request: Any, action: str) -> Any:
        if not admin_authorized("habitat", action, request.get("hass_user")):
            return self.json({"ok": False, "error": {"code": "ADMIN_REQUIRED", "message": "administrator authority is required"}}, status_code=403)
        manager: MorphTransferManager = request.app["hass"].data[DATA_KEY]
        try:
            body = await request.json()
            if action in {"game-start", "game-move"}:
                # The operator identity comes from HAOS authentication, never
                # from a client-supplied game packet.
                if "operator_id" in body:
                    raise ValueError("operator identity is server-bound")
                body["operator_id"] = request["hass_user"].id
            if action == "return-frame":
                result = await manager.return_to_frame(body)
            elif action == "recall-frame":
                result = await manager.recall_from_frame(body)
            else:
                result = await manager.handle_habitat(action, body)
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)
        except (TypeError, ValueError):
            return self.json({"ok": False, "error": {"code": "INVALID_REQUEST", "message": "request is invalid"}}, status_code=400)


class MorphHabitatStatusView(HomeAssistantView):
    """Authenticated, side-effect-free status of one known Morph."""

    url = "/api/morph-domain/v1/habitat/status/{morph_id}"
    name = "api:morph-domain:v1:habitat:status:get"
    requires_auth = True

    async def get(self, request: Any, morph_id: str) -> Any:
        manager: MorphTransferManager = request.app["hass"].data[DATA_KEY]
        try:
            result = await manager.handle_habitat("status", {"morph_id": morph_id})
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)


class MorphHabitatListView(HomeAssistantView):
    """Authenticated, side-effect-free roster for resolving canonical Morph IDs."""

    url = "/api/morph-domain/v1/habitat/list"
    name = "api:morph-domain:v1:habitat:list:get"
    requires_auth = True

    async def get(self, request: Any) -> Any:
        manager: MorphTransferManager = request.app["hass"].data[DATA_KEY]
        try:
            result = await manager.handle_habitat("list", {})
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)


class MorphHabitatHistoryView(HomeAssistantView):
    """Authenticated, side-effect-free bounded habitat history."""

    url = "/api/morph-domain/v1/habitat/history/{morph_id}"
    name = "api:morph-domain:v1:habitat:history:get"
    requires_auth = True

    async def get(self, request: Any, morph_id: str) -> Any:
        manager: MorphTransferManager = request.app["hass"].data[DATA_KEY]
        try:
            result = await manager.handle_habitat("history", {"morph_id": morph_id})
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)


class MorphHabitatRuntimeView(HomeAssistantView):
    """Authenticated scheduler witness; reading it never advances Morph life."""

    url = "/api/morph-domain/v1/habitat/runtime"
    name = "api:morph-domain:v1:habitat:runtime:get"
    requires_auth = True

    async def get(self, request: Any) -> Any:
        state = request.app["hass"].data.get(HABITAT_DATA_KEY, {})
        return self.json({"ok": True, "result": {
            "registered": bool(state),
            "last_started_at": state.get("last_started_at") if isinstance(state, dict) else None,
            "last_succeeded_at": state.get("last_succeeded_at") if isinstance(state, dict) else None,
            "last_error": state.get("last_error") if isinstance(state, dict) else None,
        }})


async def async_setup_morph_habitat(hass: HomeAssistant) -> None:
    if HABITAT_DATA_KEY in hass.data:
        return
    hass.http.register_view(MorphHabitatView)
    hass.http.register_view(MorphHabitatStatusView)
    hass.http.register_view(MorphHabitatListView)
    hass.http.register_view(MorphHabitatHistoryView)
    hass.http.register_view(MorphHabitatRuntimeView)
    hass.http.register_view(MorphSernView)
    async def handle_place(call: Any) -> None:
        await hass.data[DATA_KEY].handle_habitat("place", {
            "schema": HABITAT_SCHEMA,
            "event_id": call.context.id or str(uuid.uuid4()),
            "morph_id": call.data["morph_id"],
            "place": call.data["place"],
        })

    async def handle_care(call: Any) -> None:
        await hass.data[DATA_KEY].handle_habitat("care", {
            "schema": HABITAT_SCHEMA,
            "event_id": call.context.id or str(uuid.uuid4()),
            "morph_id": call.data["morph_id"],
            "action": call.data["action"],
        })

    async def handle_return_to_birth_frame(call: Any) -> None:
        manager = hass.data[DATA_KEY]
        morph_id = str(call.data["morph_id"])
        morph = manager.ledger.data.get("morphs", {}).get(morph_id)
        if morph is None:
            raise TransferError("NOT_FOUND", "Morph is not admitted")
        await manager.return_to_frame({
            "schema": HABITAT_SCHEMA,
            "morph_id": morph_id,
            "target_frame": morph.get("source_frame"),
        })

    async def handle_recall_to_horizon(call: Any) -> None:
        manager = hass.data[DATA_KEY]
        morph_id = str(call.data["morph_id"])
        morph = manager.ledger.data.get("morphs", {}).get(morph_id)
        if morph is None:
            raise TransferError("NOT_FOUND", "Morph is not admitted")
        await manager.recall_from_frame({"schema": HABITAT_SCHEMA, "morph_id": morph_id,
                                         "source_frame": morph.get("source_frame")})

    hass.services.async_register(
        "morph_domain", "morph_place", handle_place,
        schema=vol.Schema({vol.Required("morph_id"): str,
                           vol.Required("place"): vol.In(sorted(PLACES))}),
    )
    hass.services.async_register(
        "morph_domain", "morph_care", handle_care,
        schema=vol.Schema({vol.Required("morph_id"): str,
                           vol.Required("action"): vol.In(sorted(CARE_ACTIONS))}),
    )
    hass.services.async_register(
        "morph_domain", "return_to_birth_frame", handle_return_to_birth_frame,
        schema=vol.Schema({vol.Required("morph_id"): str}),
    )
    hass.services.async_register(
        "morph_domain", "recall_to_horizon", handle_recall_to_horizon,
        schema=vol.Schema({vol.Required("morph_id"): str}),
    )
    runtime = {
        "cancel": None,
        "last_started_at": None,
        "last_succeeded_at": None,
        "last_error": None,
    }
    hass.data[HABITAT_DATA_KEY] = runtime

    async def async_tick_habitats(_: Any) -> None:
        """Run one fault-contained engine tick and retain an API witness."""
        runtime["last_started_at"] = datetime.now(UTC).isoformat()
        try:
            await hass.data[DATA_KEY].tick_habitats()
        except Exception as err:  # Home Assistant must schedule the next tick.
            runtime["last_error"] = f"{type(err).__name__}: {err}"
            _LOGGER.exception("MorphDomain habitat tick failed; the next interval remains scheduled")
            return
        runtime["last_succeeded_at"] = datetime.now(UTC).isoformat()
        runtime["last_error"] = None

    # Catch up immediately after a reload/restart, then continue every 30 s.
    # This prevents a reload boundary from leaving every Morph frozen until an
    # unrelated mutation happens to advance the ledger.
    await async_tick_habitats(None)
    runtime["cancel"] = async_track_time_interval(
        hass,
        async_tick_habitats,
        TICK_INTERVAL,
    )

