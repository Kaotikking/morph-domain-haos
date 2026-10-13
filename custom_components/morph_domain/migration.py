"""Local candidate: preserve exclusion of every legacy Morph engine."""
import sys

from homeassistant.core import HomeAssistant

LEGACY_RUNTIME_KEYS = (
    "serein_gateway_morph_transfer",
    "serein_gateway_morph_habitat_registered",
    "serein_gateway_morph_reflex",
)


def legacy_engine_enabled(hass: HomeAssistant) -> bool:
    """Deny resident engines and unknown enabled Gateway implementations.

This reads process-local source/runtime facts only. It never reads, migrates,
clears, or claims private Morph storage. A disabled entry does not prove an
already-running legacy engine stopped.
"""
    if any(key in hass.data for key in LEGACY_RUNTIME_KEYS):
        return True
    if not any(entry.disabled_by is None
               for entry in hass.config_entries.async_entries("serein_gateway")):
        return False
    gateway = sys.modules.get("custom_components.serein_gateway")
    # Old, absent, partially imported, or malformed implementations fail closed.
    return getattr(gateway, "LEGACY_MORPH_ENGINE", None) is not False
