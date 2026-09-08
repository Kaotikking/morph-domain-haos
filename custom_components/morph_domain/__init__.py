"""MorphDomain: a removable HAOS habitat for Serein Morphs."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from pathlib import Path

from .const import DOMAIN
from .morph_habitat import HABITAT_DATA_KEY, async_setup_morph_habitat
from .morph_transfer import DATA_KEY, async_setup_morph_transfer
from .migration import legacy_engine_enabled

PLATFORMS = (Platform.SENSOR,)
PANEL_PATH = "morph-domain"
STATIC_URL = "/morph-domain-static"
STATIC_DATA_KEY = "morph_domain_panel_static"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load MorphDomain without claiming authority over any Morph."""
    if legacy_engine_enabled(hass):
        # Two active life engines may never share or fork Morph authority.
        return False
    await async_setup_morph_transfer(hass)
    await async_setup_morph_habitat(hass)
    if not frontend.async_panel_exists(hass, PANEL_PATH):
        if STATIC_DATA_KEY not in hass.data:
            await hass.http.async_register_static_paths([
                StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)
            ])
            hass.data[STATIC_DATA_KEY] = True
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name="morph-domain-panel",
            frontend_url_path=PANEL_PATH,
            module_url=f"{STATIC_URL}/morph-domain-panel.js",
            sidebar_title="MorphDomain",
            sidebar_icon="mdi:creation-outline",
            require_admin=True,
            config={},
        )
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
    frontend.async_remove_panel(hass, PANEL_PATH)
    hass.data.pop(DATA_KEY, None)
    return True

