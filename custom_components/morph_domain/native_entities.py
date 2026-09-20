"""HAOS-native virtual Morph devices and their nine core entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .morph_habitat import habitat_list
from .morph_transfer import DATA_KEY, ENGINE_VERSION
from .native_model import CORE_ORDER, PLACE_AREAS, core_projection, custody_state, display_name, native_area


NATIVE_REGISTRY_KEY = f"{DOMAIN}_native_registry"
REFRESH_INTERVAL = timedelta(seconds=30)


class MorphNativeRegistry:
    """Share one authoritative roster read across all native entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
        self.hass = hass
        self.entry = entry
        self.add = add
        self.rows: dict[str, dict[str, Any]] = {}
        self.entities: dict[str, list[MorphNativeEntity]] = {}
        self.cancel = None

    async def async_start(self) -> None:
        await self.async_refresh(None)
        self.cancel = async_track_time_interval(self.hass, self.async_refresh, REFRESH_INTERVAL)

    async def async_refresh(self, _: Any) -> None:
        manager = self.hass.data[DATA_KEY]
        async with manager.lock:
            result = habitat_list(manager.ledger, datetime.now(UTC))
        self.rows = {row["morph_id"]: row for row in result["morphs"]}

        new_entities: list[MorphNativeEntity] = []
        device_registry = dr.async_get(self.hass)
        for morph_id in sorted(self.rows):
            if morph_id in self.entities:
                continue
            row = self.rows[morph_id]
            # Register first so the entity callback and the first area sync cannot race.
            # The lookup identity is scoped to this config entry, as required by the
            # current Home Assistant device-registry contract.
            device_registry.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, morph_id)},
                name=display_name(row),
                manufacturer="Project Serein",
                model="Morph / DNAv1",
                sw_version=ENGINE_VERSION,
                suggested_area=native_area(row),
            )
            group: list[MorphNativeEntity] = [MorphStatusEntity(self, morph_id)]
            group.extend(MorphCoreEntity(self, morph_id, core) for core in CORE_ORDER)
            self.entities[morph_id] = group
            new_entities.extend(group)
        if new_entities:
            self.add(new_entities, True)

        for group in self.entities.values():
            for entity in group:
                if entity.hass is not None:
                    entity.async_write_ha_state()
        await self.async_sync_areas()

    async def async_sync_areas(self) -> None:
        """Mirror HAOS custody into native area assignment without changing Morph truth."""
        area_registry = ar.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        areas = {
            name: area_registry.async_get_or_create(name)
            for name in PLACE_AREAS.values()
        }

        for morph_id, row in self.rows.items():
            device = device_registry.async_get_device_by_identifier(
                (DOMAIN, morph_id), self.entry.entry_id
            )
            if device is None:
                continue
            area_name = native_area(row)
            area_id = areas[area_name].id if area_name else None
            if device.area_id != area_id:
                device_registry.async_update_device(device.id, area_id=area_id)


class MorphNativeEntity(SensorEntity):
    """Base entity sharing one stable virtual Morph device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, registry: MorphNativeRegistry, morph_id: str, suffix: str) -> None:
        self.registry = registry
        self.morph_id = morph_id
        self._attr_unique_id = f"{registry.entry.entry_id}_{morph_id}_{suffix}"

    @property
    def row(self) -> dict[str, Any]:
        return self.registry.rows.get(self.morph_id, {"morph_id": self.morph_id})

    @property
    def available(self) -> bool:
        return self.morph_id in self.registry.rows

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


class MorphStatusEntity(MorphNativeEntity):
    """Primary device entity: custody-aware location and public life summary."""

    _attr_name = "State"
    _attr_icon = "mdi:creation"

    def __init__(self, registry: MorphNativeRegistry, morph_id: str) -> None:
        super().__init__(registry, morph_id, "state")

    @property
    def native_value(self) -> str:
        return custody_state(self.row)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self.row
        return {
            "schema": "serein.morph-native-device.v1",
            "morph_id": self.morph_id,
            "display_name": display_name(row),
            "authority": row.get("authority", "UNKNOWN"),
            "place": row.get("place", "UNKNOWN"),
            "habitat_engine_state": row.get("habitat_engine_state", "UNKNOWN"),
            "generation": row.get("generation"),
            "custody_revision": row.get("custody_revision"),
            "lineage_generation": row.get("lineage_generation"),
            "care_levels": row.get("care_levels") or {},
        }


class MorphCoreEntity(MorphNativeEntity):
    """One bounded entity for one canonical portable Morph core."""

    def __init__(self, registry: MorphNativeRegistry, morph_id: str, core_name: str) -> None:
        super().__init__(registry, morph_id, f"core_{core_name}")
        self.core_name = core_name
        self._attr_name = core_name.title()
        self._attr_icon = {
            "platform": "mdi:chip",
            "root": "mdi:fingerprint",
            "memory": "mdi:memory",
            "knowledge": "mdi:book-open-variant",
            "ui": "mdi:palette",
            "audio": "mdi:waveform",
            "personality": "mdi:emoticon-outline",
            "modular": "mdi:puzzle",
            "cloud": "mdi:map-marker-radius",
        }[core_name]

    @property
    def native_value(self) -> Any:
        return core_projection(self.row, self.core_name)[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = core_projection(self.row, self.core_name)[1]
        return {"schema": "serein.morph-native-core.v1", "core": self.core_name, **attributes}


async def async_setup_native_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    registry = MorphNativeRegistry(hass, entry, async_add_entities)
    hass.data[NATIVE_REGISTRY_KEY] = registry
    await registry.async_start()

