"""Half Decent Scale: battery state and a firmware update check, read over the scale's WiFi WebSocket."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import HdsConfigEntry, HdsCoordinator

PLATFORMS = (Platform.BINARY_SENSOR, Platform.SENSOR, Platform.UPDATE)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: HdsConfigEntry) -> bool:
    coordinator = HdsCoordinator(hass, entry)
    await coordinator.async_load()
    # The scale is usually asleep, so a refresh without an answer is not a reason to retry setup.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HdsConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
