"""Config flow: the scale's address. It has to be awake once, so a wrong address is caught here."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import async_fetch_status, async_probe
from .const import DOMAIN, NAME

DEFAULT_HOST = "hds.local"


class HdsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        host = DEFAULT_HOST
        if user_input is not None:
            host = user_input[CONF_HOST].strip().removeprefix("http://").rstrip("/").lower()
            session = async_get_clientsession(self.hass)
            probe = await async_probe(session, host)
            if probe is not None and await async_fetch_status(session, host):
                # The scale's own id where the firmware gives one, so a new address is the same scale.
                await self.async_set_unique_id(probe.device_id or host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(title=NAME, data={CONF_HOST: host})
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}), errors=errors
        )
