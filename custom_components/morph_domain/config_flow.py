"""Configuration flow for MorphDomain."""

from homeassistant import config_entries

from .const import DOMAIN


class MorphDomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single local MorphDomain instance."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Install locally with no external credentials."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if self.hass.config_entries.async_entries("serein_gateway"):
            return self.async_abort(reason="legacy_engine_active")
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="MorphDomain", data={})
