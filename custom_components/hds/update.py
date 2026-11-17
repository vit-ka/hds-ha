"""Firmware update check. Reports only: the scale installs updates from its own WiFi Update menu."""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HdsConfigEntry, HdsCoordinator
from .entity import HdsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HdsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([HdsFirmwareUpdate(entry.runtime_data)])


class HdsFirmwareUpdate(HdsEntity, UpdateEntity):
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_title = "Half Decent Scale firmware"

    def __init__(self, coordinator: HdsCoordinator) -> None:
        super().__init__(coordinator, "firmware")

    @property
    def entity_picture(self) -> None:
        """No picture: the default is this integration's brand icon, and it has none to serve."""
        return None

    @property
    def installed_version(self) -> str | None:
        status = self.coordinator.data.status
        return status.firmware if status else None

    @property
    def latest_version(self) -> str | None:
        """The catalog's version; until it has been read, the installed one, so no update is claimed."""
        release = self.coordinator.data.release
        return release.version if release else self.installed_version

    @property
    def release_url(self) -> str | None:
        release = self.coordinator.data.release
        return release.url if release else None
