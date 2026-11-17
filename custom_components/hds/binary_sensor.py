"""Charging state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HdsConfigEntry, HdsCoordinator
from .entity import HdsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HdsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([HdsCharging(entry.runtime_data)])


class HdsCharging(HdsEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HdsCoordinator) -> None:
        super().__init__(coordinator, "charging")

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.status
        return status.charging if status else None
