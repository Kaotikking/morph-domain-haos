"""One-engine migration guards for MorphDomain."""

from homeassistant.core import HomeAssistant


def legacy_engine_enabled(hass: HomeAssistant) -> bool:
    """Return true while an enabled legacy Serein Gateway entry exists."""
    return any(
        entry.disabled_by is None
        for entry in hass.config_entries.async_entries("serein_gateway")
    )

