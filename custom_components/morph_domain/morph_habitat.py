"""Home Assistant API, service, scheduler, and SERN adapter for MorphDomain."""

from __future__ import annotations

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
            result = await manager.handle_habitat(action, await request.json())
            return self.json({"ok": True, "result": result})
        except TransferError as err:
            return self.json({"ok": False, "error": {"code": err.code, "message": str(err)}}, status_code=409)
        except (TypeError, ValueError):
            return self.json({"ok": False, "error": {"code": "INVALID_REQUEST", "message": "request is invalid"}}, status_code=400)


async def async_setup_morph_habitat(hass: HomeAssistant) -> None:
    if HABITAT_DATA_KEY in hass.data:
        return
    hass.http.register_view(MorphHabitatView)
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

    hass.services.async_register(
        "morph_domain", "morph_place", handle_place,
        schema={"morph_id": str, "place": vol.In(sorted(PLACES))},
    )
    hass.services.async_register(
        "morph_domain", "morph_care", handle_care,
        schema={"morph_id": str, "action": vol.In(sorted(CARE_ACTIONS))},
    )
    hass.data[HABITAT_DATA_KEY] = async_track_time_interval(
        hass,
        lambda _: hass.async_create_task(hass.data[DATA_KEY].tick_habitats()),
        TICK_INTERVAL,
    )

