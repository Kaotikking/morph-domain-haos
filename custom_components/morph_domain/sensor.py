"""HAOS-native Horizon overview for hosted Morphs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .morph_habitat import habitat_list
from .morph_transfer import DATA_KEY


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose one stable, non-authoritative Horizon overview entity."""
    async_add_entities([MorphDomainHorizonEntity(hass, entry)], True)


class MorphDomainHorizonEntity(SensorEntity):
    """Mirror current Morph habitat truth without owning it."""

    _attr_has_entity_name = True
    _attr_name = "Morphs hosted"
    _attr_icon = "mdi:creation"
    _attr_native_unit_of_measurement = "Morphs"
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._attr_unique_id = f"{entry.entry_id}_morph_horizon"
        self._attr_native_value = 0
        self._attr_extra_state_attributes: dict[str, Any] = {
            "schema": "serein.morph-habitat.v1", "places": [], "morphs": []
        }

    async def async_update(self) -> None:
        """Read the locked in-memory ledger; the periodic engine owns writes."""
        manager = self.hass.data[DATA_KEY]
        async with manager.lock:
            result = habitat_list(manager.ledger, datetime.now(UTC))
        rows = []
        for morph in result["morphs"]:
            life = morph["life"]
            authority = morph["authority"]
            if authority == "HAOS":
                transfer_phase = "HAOS_HORIZON"
            elif authority == "FROZEN_FOR_RETURN":
                transfer_phase = "RETURNING"
            elif authority.startswith(("esp32-frame:", "android-frame:")):
                transfer_phase = "FRAME"
            else:
                transfer_phase = "FROZEN_OR_UNKNOWN"
            rows.append({
                "morph_id": morph["morph_id"],
                "founder_id": morph["founder_id"],
                "device_birth_lineage": morph["device_birth_lineage"],
                "authority": authority,
                "transfer_phase": transfer_phase,
                "place": morph["place"],
                "habitat_engine_state": morph["habitat_engine_state"],
                "behavior": life["behavior"],
                "food_q8": life["food_q8"],
                "water_q8": life["water_q8"],
                "play_q8": life["play_q8"],
                "rest_q8": life["rest_q8"],
                "attention_q8": life["attention_q8"],
                "elemental_expression_q8": morph["environment"]["expression_q8"],
                "dominant_environment": morph["environment"]["dominant"],
                "environment_sample": morph["environment"]["last_sample"],
            })
        self._attr_native_value = sum(1 for row in rows if row["authority"] == "HAOS")
        self._attr_extra_state_attributes = {
            "schema": result["schema"],
            "places": ["VOID", "NURSERY", "SEREIN_GARDENS", "HORIZON", "CODE_HAVEN"],
            "morphs": rows,
        }
