"""MorphDomain: a removable HAOS habitat for Serein Morphs."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .morph_habitat import HABITAT_DATA_KEY, async_setup_morph_habitat
from .morph_transfer import DATA_KEY, async_setup_morph_transfer
from .migration import legacy_engine_enabled

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load MorphDomain without claiming authority over any Morph."""
    if legacy_engine_enabled(hass):
        # Two active life engines may never share or fork Morph authority.
        return False
    await async_setup_morph_transfer(hass)
    await async_setup_morph_habitat(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities and periodic work; durable Morph state remains stored."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    cancel = hass.data.pop(HABITAT_DATA_KEY, None)
    if cancel is not None:
        cancel()
    hass.services.async_remove(DOMAIN, "morph_place")
    hass.services.async_remove(DOMAIN, "morph_care")
    hass.data.pop(DATA_KEY, None)
    return True

