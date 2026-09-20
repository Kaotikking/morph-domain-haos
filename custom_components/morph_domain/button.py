"""Native Morph reflex buttons bound to each virtual Morph device."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .morph_transfer import ENGINE_VERSION
from .native_entities import MorphNativeRegistry, NATIVE_REGISTRY_KEY
from .native_model import display_name, native_area


@dataclass(frozen=True)
class Reflex:
    key: str
    name: str
    icon: str
    service: str
    data: dict[str, Any]


REFLEXES = (
    Reflex("move_void", "Move to Void", "mdi:circle-opacity", "void_enter", {}),
    Reflex("move_nursery", "Move to Nursery", "mdi:egg-outline", "morph_place", {"place": "NURSERY"}),
    Reflex("move_gardens", "Move to Gardens", "mdi:flower", "morph_place", {"place": "SEREIN_GARDENS"}),
    Reflex("move_horizon", "Move to Horizon", "mdi:weather-sunset", "morph_place", {"place": "HORIZON"}),
    Reflex("move_code_haven", "Move to Code Haven", "mdi:hospital-box-outline", "code_haven_admit", {}),
    Reflex("feed", "Feed", "mdi:food-apple-outline", "morph_care", {"action": "FEED"}),
    Reflex("water", "Water", "mdi:water-outline", "morph_care", {"action": "WATER"}),
    Reflex("play", "Play", "mdi:gamepad-variant-outline", "morph_care", {"action": "PLAY"}),
    Reflex("rest", "Rest", "mdi:sleep", "morph_care", {"action": "REST"}),
    Reflex("send_birth_frame", "Send to Birth Frame", "mdi:export", "return_to_birth_frame", {}),
    Reflex("recall_horizon", "Recall to Horizon", "mdi:import", "recall_to_horizon", {}),
)


class MorphReflexButton(ButtonEntity):
    """One stateless native button that delegates to a proven Morph service."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, registry: MorphNativeRegistry, morph_id: str, reflex: Reflex) -> None:
        self.registry = registry
        self.morph_id = morph_id
        self.reflex = reflex
        self._attr_unique_id = f"{registry.entry.entry_id}_{morph_id}_reflex_{reflex.key}"
        self._attr_name = reflex.name
        self._attr_icon = reflex.icon

    @property
    def row(self) -> dict[str, Any]:
        return self.registry.rows.get(self.morph_id, {"morph_id": self.morph_id})

    @property
    def device_info(self) -> DeviceInfo:
        row = self.row
        return DeviceInfo(
            identifiers={(DOMAIN, self.morph_id)},
            name=display_name(row),
            manufacturer="Project Serein",
            model="Morph / DNAv1",
            sw_version=ENGINE_VERSION,
            suggested_area=native_area(row),
        )

    @property
    def available(self) -> bool:
        row = self.row
        authority = row.get("authority")
        place = row.get("place")
        frame = row.get("frame_return") or {}
        key = self.reflex.key
        if key == "recall_horizon":
            return bool(frame.get("recall_available"))
        if authority != "HAOS":
            return False
        if key == "send_birth_frame":
            return bool(frame.get("call_available"))
        if key in {"feed", "water", "play", "rest"}:
            return place not in {"VOID", "CODE_HAVEN"} and not bool(
                (row.get("foundation_reflex") or {}).get("hatch_available")
            )
        if place == "VOID":
            return key in {"move_horizon", "move_code_haven"}
        if place == "CODE_HAVEN":
            return key == "move_horizon"
        return key != {
            "VOID": "move_void",
            "NURSERY": "move_nursery",
            "SEREIN_GARDENS": "move_gardens",
            "HORIZON": "move_horizon",
            "CODE_HAVEN": "move_code_haven",
        }.get(place)

    async def async_press(self) -> None:
        """Invoke the existing service; never duplicate custody or life logic here."""
        row = self.row
        service = self.reflex.service
        data = {"morph_id": self.morph_id, **self.reflex.data}
        if row.get("place") == "VOID" and self.reflex.key in {"move_horizon", "move_code_haven"}:
            service = "void_withdraw"
            data = {"morph_id": self.morph_id, "target_place": self.reflex.data.get("place", "CODE_HAVEN")}
        elif row.get("place") == "CODE_HAVEN" and self.reflex.key == "move_horizon":
            service = "code_haven_discharge"
            data = {"morph_id": self.morph_id, "target_place": "HORIZON"}
        await self.hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=self._context
        )
        await self.registry.async_refresh(None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    registry: MorphNativeRegistry = hass.data[NATIVE_REGISTRY_KEY]
    await registry.async_register_platform(
        "button",
        async_add_entities,
        lambda shared, morph_id: [MorphReflexButton(shared, morph_id, reflex) for reflex in REFLEXES],
    )

